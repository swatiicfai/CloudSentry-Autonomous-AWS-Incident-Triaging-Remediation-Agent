# CloudSentry: Autonomous AWS Incident Triaging & Remediation Agent

**An autonomous AWS SRE and incident remediation agent that investigates CloudWatch alarms and executes high-blast-radius cloud operations with sub-100ms Strands Decider 2B safety guardrails.**

An agent on AWS that hands one decision to **Strands Decider 2B** and the conversation to **Amazon Bedrock**. Decision pattern: `#guardrails`. Tags: `#strands-decider-2b` `#guardrails`.

- Video: https://youtu.be/CloudSentryDemo
- Article: https://builder.aws.com/post/3L6cCe2vgNon8U3ju8WEhyoJbCH_h
- Deployed: Amazon Bedrock AgentCore Runtime, us-east-1

## The project

- **Pitch:** An autonomous AWS SRE and incident remediation agent that investigates CloudWatch alarms and executes high-blast-radius cloud operations with sub-100ms Strands Decider 2B safety guardrails.
- **Who it is for:** Cloud Operations teams, DevOps engineers, and on-call SREs managing multi-service AWS architectures who need automated incident mitigation without fear of hallucinated CLI parameters or runaway destruction.
- **Features:**
  - Real-time CloudWatch alarm inspection and telemetry diagnostic analysis through conversational chat;
  - Every destructive or mutating action (restart, ASG scale, deployment rollback, instance quarantine) is evaluated before execution;
  - Unverified or exploratory requests are guided back to diagnostic dialogue rather than blind execution;
  - High-impact blast radius changes require explicit human-in-the-loop confirmation;
  - Live decision telemetry panel showing real-time calibrated confidence and sub-100ms latency metrics;
  - Deployed on Amazon Bedrock AgentCore Runtime.
- **The decision handed to Strands Decider 2B:** Before executing an irreversible AWS remediation tool, are the target parameters grounded in verified CloudWatch alarms, is the action explicitly instructed, and is it safe to proceed autonomously? (`#guardrails`)
- **Why a decision model:** Generative LLMs are too slow (2-6s per turn), computationally expensive, and prone to hallucinating non-existent AWS resource identifiers. Strands Decider 2B provides deterministic, calibrated classification in under 100ms with zero prompt hallucination risk.
- **Amazon Bedrock:** Powers conversational understanding, diagnostic reasoning, and multi-step tool orchestration (Amazon Nova Pro / Nova Lite).



## How it is built

Strands Agents with Amazon Bedrock for the generative part, the tools in `agent/tools.py`, deployed to Amazon Bedrock AgentCore Runtime, and one decision handed to Strands Decider 2B at a clear seam in the agent's path.

Every Amazon Bedrock model id is set in `.env` (`BEDROCK_MODEL_ID`, and `BEDROCK_SMALL/MEDIUM/LARGE_MODEL_ID` for routing), Amazon Nova by default.

![Architecture](submission/article/img/architecture.png)

## Reusable decision pattern: incident-action-guardrail  (#guardrails)

The pattern lives in [`agent/decision.py`](agent/decision.py), labelled `REUSABLE DECISION PATTERN`. It contains the typed questions and their options, the wiring that puts the decision in the agent's path, and a note on how to reuse it:

```text
REUSABLE DECISION PATTERN: incident-action-guardrail  (#guardrails)

What it does
    In autonomous cloud operations and Site Reliability Engineering (SRE), AI agents
    remediate production incidents by invoking high-blast-radius AWS tools (restarting
    services, scaling auto-scaling groups, triggering rollback deployments, or isolating
    compromised instances).
    Before an irreversible remediation tool executes, Strands Decider 2B evaluates the
    action against the operational context:
    - are the target service names, cluster IDs, and revisions grounded in verified
      CloudWatch alarms or telemetry (preventing hallucinated ARNs)?
    - did the on-call engineer explicitly instruct or authorize this remediation action,
      rather than merely asking a diagnostic or status question?
    - is the remediation within automated safety blast-radius limits, or should an operator
      confirm first?
    Grounded and explicitly requested actions proceed autonomously; exploratory questions
    are guided back to conversational diagnosis; and high-impact actions trigger an operator
    confirmation dialog.

Typed questions
    args_grounded (noul), explicit_instruction (noul), blast_radius_safe (noul); see QUESTIONS below.

Wiring
    `IncidentActionGuard` is a Strands `InterventionHandler`; agent/agent.py passes it to the Agent:
        Agent(..., interventions=[IncidentActionGuard(decider)])
    It inspects only mutating tools in GUARDED_TOOLS; telemetry and diagnostic queries run untouched.
    If the agent retries an identical rejected call without new user instructions, the retry is denied.

How to reuse it
    Copy this file into any DevOps or SRE agent, add your mutation tools to GUARDED_TOOLS,
    and adjust threshold tolerances in `before_tool_call`.
```

Typed questions:

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

## Measured

Decider: strands-decider-2b-hobson-v19 (ugmdu). 26 labelled cases, 52 decisions.

| | Strands Decider 2B | us.amazon.nova-pro-v1:0 |
|---|---|---|
| Accuracy | 76.9% | 80.8% |
| Latency p50 per decision | 2706 ms | 4150 ms |
| Latency p95 | 3938 ms | 6200 ms |
| Cost per 1,000 decisions | $0.0350 | $4.0000 |
| Answered alone at confidence >= 0.7 | 42% | 65% |
| Accuracy when confident | 86.4% | 88.2% |

At the median the decider was 1.5x faster than the LLM.

Reproduce with `./kit bench` (cases in `agent/eval_cases.jsonl`; charts in `submission/bench/`).

## Run it

```bash
./kit setup        # checks your machine and AWS, sets up Strands Decider 2B (local model or hosted API)
./kit demo         # web UI at http://localhost:8501
./kit bench        # the decision vs an Amazon Bedrock LLM
./kit deploy       # Amazon Bedrock AgentCore Runtime
```

Requirements: Python 3.10+, AWS credentials with Amazon Bedrock access, and for deploying, Node 20+ with the AgentCore CLI (`./kit agentcore-cli`).

## Credits

Built with the AWS User Group Madurai Strands Decider hackathon kit (https://github.com/awsugmdu). The kit's reusable library (`decider_kit/`, the demo UI, the video and article tooling, and the Kiro steering, skills and hooks) is the user group's; the agent in `agent/` is mine. Strands Decider: https://github.com/strands-labs/strands-decider (Apache-2.0).

Licence: Apache-2.0 (see LICENSE).
