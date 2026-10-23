# CloudSentry: Autonomous AWS Incident Triaging & Remediation Agent

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
