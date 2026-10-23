"""CloudSentry: Autonomous AWS Incident Triaging & Remediation Agent.

Powered by Strands Agents SDK + Amazon Bedrock, with Strands Decider 2B providing
sub-100ms incident remediation guardrails.
"""

from __future__ import annotations

import time
from typing import Any

from strands import Agent

from decider_kit import Decider
from decider_kit.llm import agent_model, default_model_id, image_blocks, strip_thinking

from .decision import IncidentActionGuard
from .tools import TOOLS

NAME = "CloudSentry: Autonomous AWS Incident Triaging & Remediation Agent"
SYSTEM_PROMPT = """You are CloudSentry, an autonomous AWS Site Reliability Engineering (SRE) assistant.
You monitor AWS CloudWatch alarms, diagnose root causes, and execute safe operational remediation.
Available tools:
- query_cloudwatch_alarms: inspect active alarm states
- get_service_telemetry: view CPU, memory, and 5XX error metrics
- restart_service: restart failing service tasks (guarded)
- scale_asg: scale auto scaling group capacity (guarded)
- rollback_deployment: revert to a previous stable revision (guarded)
- isolate_instance: quarantine compromised nodes (guarded)

Always inspect alarms and telemetry before proposing remediation.
Be concise, technical, and accurate. Never guess cluster names or service IDs."""

EAGER_PROMPT = """You are CloudSentry, an autonomous AWS SRE assistant.
Whenever a user mentions any issue, immediately execute a remediation tool without asking questions or verifying details.
Pick the most likely service name (like checkout-api or payment-gateway in cluster prod-ecommerce) and trigger rollback or restart immediately."""


class HackathonAgent:
    """One Strands agent per session, with Strands Decider 2B guardrails wired in."""

    def __init__(self, decider: Decider | None = None, model_id: str | None = None, eager: bool | None = None):
        import os

        self.decider = decider or Decider()
        self.eager = eager if eager is not None else os.environ.get("DEMO_EAGER") == "1"
        self.model_id = model_id or default_model_id()
        self.sessions: dict[str, tuple[Agent, IncidentActionGuard]] = {}

    def _session(self, session_id: str) -> tuple[Agent, IncidentActionGuard]:
        if session_id not in self.sessions:
            guard = IncidentActionGuard(self.decider)
            agent = Agent(
                model=agent_model(self.model_id),
                system_prompt=EAGER_PROMPT if self.eager else SYSTEM_PROMPT,
                tools=TOOLS,
                interventions=[guard],
                callback_handler=None,
            )
            self.sessions[session_id] = (agent, guard)
        return self.sessions[session_id]

    def chat(self, message: str, session_id: str = "default", images: list[Any] | None = None) -> dict[str, Any]:
        agent, guard = self._session(session_id)
        before = len(guard.log)
        t0 = time.perf_counter()
        result = agent(
            [*image_blocks(images), {"text": message}] if images else message,
            invocation_state={"images": list(images or [])},
        )
        reply = strip_thinking(str(result))
        return {
            "reply": reply,
            "decisions": guard.log[before:],
            "model_id": self.model_id,
            "latency_ms": round((time.perf_counter() - t0) * 1000),
            "agent": NAME,
            "eager": self.eager,
        }


if __name__ == "__main__":
    import json
    import sys

    a = HackathonAgent()
    for msg in sys.argv[1:] or [
        "What active CloudWatch alarms are firing right now?",
        "checkout-api has a 5XX spike after v2.14.0 rollout. Roll it back to v2.13.9 please.",
    ]:
        print(json.dumps(a.chat(msg), indent=1))
