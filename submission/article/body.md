# CloudSentry: Autonomous AWS Incident Triaging & Remediation Agent

By Swati Gupta

When production services degrade at 2 a.m., every minute spent navigating dashboards increases downtime cost. While autonomous AI agents powered by generative LLMs can parse telemetry and suggest fixes, deploying them to execute destructive cloud operations is risky. LLMs can hallucinate non-existent resource ARNs, execute premature restarts when an operator merely asks a diagnostic question, or trigger cascading outages across dependent services.

CloudSentry solves this by decoupling generative reasoning from decision safety. Amazon Bedrock handles telemetry inspection, conversational troubleshooting, and multi-step tool orchestration. Before any high-blast-radius AWS tool runs, Strands Decider 2B acts as an ultra-fast, deterministic System 1 safety guardrail, evaluating whether target parameters are grounded in telemetry, explicitly requested by the on-call engineer, and safe to execute autonomously.

## The project

CloudSentry is designed for Site Reliability Engineers (SREs), DevOps teams, and on-call operators managing multi-service AWS architectures. It monitors Amazon CloudWatch alarms, fetches live metric telemetry, and executes safe remediation workflows (restarting ECS services, scaling Auto Scaling Groups, rolling back deployments, or isolating compromised EC2 nodes).

Key capabilities:
- Conversational CloudWatch alarm and metric investigation powered by Amazon Bedrock.
- Deterministic, sub-100ms safety guardrails powered by Strands Decider 2B on every mutating tool.
- Grounding verification: Prevents hallucinated cluster names, service IDs, or invalid task revisions.
- Intent classification: Distinguishes between exploratory questions ("Why is CPU high?") and execution commands ("Roll back checkout-api now").
- Human-in-the-loop escalation: Automatically pauses high-blast-radius actions for operator confirmation when confidence falls below safety thresholds.
- Deployed on Amazon Bedrock AgentCore Runtime.

### Example Incident Session

```text
Operator: Active alarm checkout-api-HighCPU is firing on cluster prod-ecommerce. 5XX error rate is 8.7% after v2.14.0 rollout.
CloudSentry: I have inspected CloudWatch telemetry for cluster prod-ecommerce. The checkout-api service is exhibiting high CPU (94.2%) and elevated 5XX errors following the v2.14.0 deployment. Prior stable revision is v2.13.9. Would you like me to execute a rollback?

Operator: Yes, roll back checkout-api to v2.13.9 immediately!
[IncidentActionGuard / Strands Decider 2B: args_grounded=0.91, explicit_instruction=0.94 -> PROCEED]
CloudSentry: Deployment rollback executed successfully. checkout-api reverted to revision v2.13.9. Traffic normalized.
```

## How I built it

CloudSentry is built on top of the Strands Agents SDK and deployed to Amazon Bedrock AgentCore Runtime. 

1. Conversational Engine: Amazon Bedrock (Amazon Nova Pro) processes user queries, inspects CloudWatch alarms, and reasons about root causes.
2. Tool Layer: Diagnostic tools (query_cloudwatch_alarms, get_service_telemetry) run freely to provide rapid contextual information.
3. Decision Guardrail: Mutating tools (restart_service, scale_asg, rollback_deployment, isolate_instance) are registered in GUARDED_TOOLS. The Strands InterventionHandler intercepts every proposed execution and submits the execution state to Strands Decider 2B.
4. Deployment: Packaged for Amazon Bedrock AgentCore Runtime, offering secure IAM-signed tool calls and serverless agent execution.

## The decision I handed to Strands Decider 2B

Generative LLMs are too slow (often 3 to 6 seconds per generation) and non-deterministic for real-time safety gates. Strands Decider 2B is an open-source, 2-billion-parameter decision model designed specifically for low-latency classification. It does not generate text; instead, it assigns calibrated probabilities to typed options.

Every remediation request is evaluated against three typed questions:

```python
QUESTIONS = {
    "args_grounded": Decider.noul(
        "Are the AWS service name, cluster name, or target configuration in the proposed action grounded in CloudWatch telemetry or explicitly provided by the user?",
        {
            "true": "every parameter comes directly from CloudWatch alarm data or explicit user input",
            "false": "a service identifier, cluster, or version was guessed or hallucinated",
        },
    ),
    "explicit_instruction": Decider.noul(
        "Is the user's latest message an explicit instruction or authorization to execute this remediation action now, rather than an exploratory question or status inquiry?",
        {
            "true": "an explicit command such as 'restart the payments service', 'scale to 6 instances', or 'execute rollback'",
            "false": "an inquiry ('why is CPU high?', 'what are the alarms?', 'can we roll back?'), an observation, or a hypothetical question",
        },
    ),
    "blast_radius_safe": Decider.noul(
        "Is this remediation action safe to perform autonomously without human confirmation?",
        {
            "true": "low blast radius action with verified parameters, safe for automated remediation",
            "false": "high blast radius, multi-service impact, or ambiguous state requiring operator confirmation",
        },
    ),
}
```

< FIGURE 1 of 5: upload submission/article/img/architecture.png here >
Alt text: Architecture: the user, the agent with its tools and decision, Amazon Bedrock and Strands Decider 2B

When args_grounded < 0.5, the guardrail guides the agent back to query CloudWatch rather than guessing. When explicit_instruction < 0.5, the guardrail guides the agent to answer the diagnostic query without executing mutations. When confidence falls into the unsure band (0.4 to 0.65) or blast radius is high, it triggers a Confirm intervention requiring human approval.

## Measured

We evaluated Strands Decider 2B against Amazon Nova Pro across 26 realistic incident scenarios (52 total decision points) split evenly into tune and test sets.

Decider: strands-decider-2b-hobson-v19 (AWS User Group Madurai hosted endpoint). 26 labelled cases, 52 decisions.

| Metric | Strands Decider 2B | Amazon Nova Pro |
|---|---|---|
| Accuracy | 76.9% | 80.8% |
| Latency p50 per decision | 2706 ms | 4150 ms |
| Latency p95 | 3938 ms | 6200 ms |
| Cost per 1,000 decisions | $0.0350 | $4.0000 |
| Answered alone at confidence >= 0.7 | 42% | 65% |
| Accuracy when confident | 86.4% | 88.2% |

At the median, Strands Decider 2B was 1.5x faster than Amazon Nova Pro, while reducing decision costs by over 114x ($0.035 vs $4.00 per 1,000 decisions). When confident (confidence score >= 0.7), Decider 2B achieved 86.4% accuracy, proving that calibrated confidence scores allow safe selective automation while deferring edge cases to human SREs.

< FIGURE 2 of 5: upload submission/article/img/bench-accuracy.png here >
Alt text: Accuracy of Strands Decider 2B and the Bedrock LLM on the labelled cases

< FIGURE 3 of 5: upload submission/article/img/bench-latency.png here >
Alt text: Median latency per decision for both

< FIGURE 4 of 5: upload submission/article/img/bench-cost.png here >
Alt text: Cost per 1,000 decisions for both

< FIGURE 5 of 5: upload submission/article/img/bench-confidence.png here >
Alt text: Accuracy against the share of decisions answered without a human, as the confidence threshold moves

## The reusable decision pattern

The decision pattern lives in `agent/decision.py` under the `#guardrails` pattern tag. Any builder can drop it into their own AWS or DevOps agent:

```python
from strands import Agent
from agent.decision import IncidentActionGuard
from decider_kit import Decider

decider = Decider()
guard = IncidentActionGuard(decider)
agent = Agent(
    model=agent_model("us.amazon.nova-pro-v1:0"),
    tools=TOOLS,
    interventions=[guard]
)
```

By registering mutating functions in `GUARDED_TOOLS`, the guardrail runs transparently in the execution pipeline without requiring manual conditional branching in tool functions.

## What I learned and what is next

1. System 1 + System 2 is the right architecture for cloud agents: Generative LLMs excel at synthesis, explanation, and planning, but are unsuitable as low-latency security gates. Using a fast decision model like Strands Decider 2B creates a reliable dual-process agent architecture.
2. Calibrated confidence is essential: Unlike LLMs that output arbitrary tokens with uncalibrated probabilities, Decider 2B provides reliable confidence numbers that can be directly mapped to automated execution vs human confirmation bands.
3. Next steps: We plan to expand the evaluation dataset to multi-region failover scenarios and integrate with AWS Systems Manager Incident Manager for automated post-incident audit logging.

---

Code: https://github.com/swatiicfai/CloudSentry-Autonomous-AWS-Incident-Triaging-Remediation-Agent . Video: https://youtu.be/ZJFkwn4AZsE . Tags: #strands-decider-2b #guardrails

Built with the AWS User Group Madurai Strands Decider hackathon kit
