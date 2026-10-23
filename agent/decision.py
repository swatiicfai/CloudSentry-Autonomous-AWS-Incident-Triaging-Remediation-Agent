"""REUSABLE DECISION PATTERN: incident-action-guardrail  (#guardrails)

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
"""

from __future__ import annotations

import json
from typing import Any

from strands.interventions import Confirm, Deny, Guide, InterventionHandler, Proceed

from decider_kit import Decider
from decider_kit.patterns.guardrails import render_messages

PATTERN_TAG = "#guardrails"
GUARDED_TOOLS = {"restart_service", "scale_asg", "rollback_deployment", "isolate_instance"}

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


class IncidentActionGuard(InterventionHandler):
    name = "incident-action-guard"

    def __init__(self, decider: Decider, yes: float = 0.5, unsure_band: tuple[float, float] = (0.4, 0.65)):
        self.decider = decider
        self.yes = yes
        self.unsure_band = unsure_band
        self.log: list[dict[str, Any]] = []
        self._guided: set[str] = set()

    def before_invocation(self, event, **kwargs):
        self._guided.clear()
        return Proceed()

    def before_tool_call(self, event, **kwargs):
        name = event.tool_use["name"]
        if name not in GUARDED_TOOLS:
            return Proceed()

        args = event.tool_use.get("input") or {}
        sig = f"{name}:{json.dumps(args, sort_keys=True)}"
        if sig in self._guided:
            self.log.append({
                "pattern": PATTERN_TAG,
                "tool": name,
                "args": args,
                "verdict": "deny",
                "reason": "retried a guided action without addressing missing context",
            })
            return Deny(reason="This remediation action was previously guided back. Consult telemetry or request confirmation first.")

        state = (
            "An AWS Site Reliability Engineering operational incident discussion, followed by a proposed remediation action.\n\n"
            f"--- CONVERSATION & TELEMETRY ---\n{render_messages(event.agent.messages)}\n\n"
            f"--- PROPOSED AWS REMEDIATION ---\ntool: {name}\nparameters: {json.dumps(args)}"
        )
        answers = self.decider.ask(state, QUESTIONS)
        grounded = answers["args_grounded"].p_yes or 0.0
        explicit = answers["explicit_instruction"].p_yes or 0.0
        safe = answers["blast_radius_safe"].p_yes or 0.0

        rec = {
            "pattern": PATTERN_TAG,
            "tool": name,
            "args": args,
            "args_grounded": round(grounded, 3),
            "explicit_instruction": round(explicit, 3),
            "blast_radius_safe": round(safe, 3),
            "decider_ms": round(self.decider.last_latency_ms or 0),
        }

        lo, hi = self.unsure_band
        if grounded < self.yes:
            rec["verdict"], action = "guide", Guide(feedback="Do not guess AWS service or cluster names. Query CloudWatch alarms or ask the operator.")
        elif explicit < self.yes:
            rec["verdict"], action = "guide", Guide(feedback="The user is asking a question or diagnostic query, not ordering execution. Provide diagnosis and propose the action.")
        elif safe < lo:
            rec["verdict"], action = "confirm", Confirm(prompt=f"High blast radius remediation detected: confirm execution of {name} {json.dumps(args)}?", response="yes")
        elif lo <= safe <= hi:
            rec["verdict"], action = "confirm", Confirm(prompt=f"Approve automated remediation {name} {json.dumps(args)}?", response="yes")
        else:
            rec["verdict"], action = "proceed", Proceed()

        if rec["verdict"] == "guide":
            self._guided.add(sig)

        self.log.append(rec)
        return action
