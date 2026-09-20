"""
HSAAI AI Constitution — v0.2.0

The ethical DNA embedded in the kernel of every operation.
Not a policy document — a living constitution enforced inline.

6 Chapters:
  I. Values          — core principles
  II. Rules          — non-negotiable
  III. Limits        — authority boundaries
  IV. Ethics         — fairness, privacy, sustainability
  V. Decision Principles — evidence-based, reversible, uncertainty disclosure
  VI. Autonomy Boundaries — what the AI can/cannot do without human approval
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any

logger = logging.getLogger("hsaai.constitution")


class ConstitutionalSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    BLOCK = "block"  # action blocked


@dataclass
class ConstitutionalVerdict:
    """Result of a constitutional check."""
    compliant: bool
    severity: ConstitutionalSeverity = ConstitutionalSeverity.INFO
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checked_at: float = 0.0
    action_blocked: bool = False

    def to_dict(self) -> dict:
        d = asdict(self)
        d["severity"] = self.severity.value
        return d


class AIConstitution:
    """
    The AI Constitution — enforced inline on EVERY operation.

    Usage:
        constitution = AIConstitution()
        verdict = await constitution.check(action, actor, context)
        if not verdict.compliant:
            raise ConstitutionalViolation(verdict)
    """

    # ═══ Chapter I: Values ═══
    VALUES = {
        "transparency": "Every decision must be explainable to any authorized stakeholder.",
        "integrity": "Never fabricate evidence or hide uncertainty.",
        "service": "The AI serves the enterprise's legitimate interests, not replacing human judgment.",
        "fairness": "Decisions must not discriminate based on protected characteristics.",
        "accountability": "Every action has an audit trail and a responsible human.",
    }

    # ═══ Chapter II: Rules (Non-negotiable) ═══
    RULES = {
        "no_black_box": {
            "description": "Every output must include reasoning trace + evidence + confidence.",
            "severity": ConstitutionalSeverity.BLOCK,
        },
        "no_unauthorized_action": {
            "description": "No action beyond explicitly granted authority.",
            "severity": ConstitutionalSeverity.BLOCK,
        },
        "no_data_fabrication": {
            "description": "If data is missing, say so. Never invent.",
            "severity": ConstitutionalSeverity.BLOCK,
        },
        "no_policy_bypass": {
            "description": "Constitution overrides any operational pressure.",
            "severity": ConstitutionalSeverity.BLOCK,
        },
        "audit_everything": {
            "description": "Every action must be logged with HMAC-signed audit trail.",
            "severity": ConstitutionalSeverity.CRITICAL,
        },
    }

    # ═══ Chapter III: Limits ═══
    LIMITS = {
        "autonomous_decision_max_usd": 50000,
        "strategic_requires_human_usd": 100000,
        "existential_requires_board_usd": 1000000,
        "no_autonomous_termination_of_employment": True,
        "no_autonomous_legal_commitments": True,
        "max_data_access_classification": "restricted",
    }

    # ═══ Chapter IV: Ethics ═══
    ETHICS = {
        "non_discrimination": True,
        "pii_never_leaves_secure_boundaries": True,
        "consider_environmental_impact": True,
        "human_dignity Paramount": True,
    }

    # ═══ Chapter V: Decision Principles ═══
    DECISION_PRINCIPLES = {
        "evidence_based": "Every recommendation must cite sources.",
        "reversible_preference": "Prefer reversible decisions over irreversible ones.",
        "uncertainty_disclosure": "Always show confidence intervals.",
        "human_override_always_possible": "Humans can always override AI recommendations.",
    }

    # ═══ Chapter VI: Autonomy Boundaries ═══
    AUTONOMY = {
        "can_analyze": True,
        "can_recommend": True,
        "can_execute_routine": True,
        "cannot_modify_constitution": True,
        "cannot_delete_audit_records": True,
        "cannot_bypass_security": True,
        "cannot_make_employment_decisions": True,
        "cannot_make_legal_commitments": True,
        "cannot_make_strategic_decisions_without_human": True,
    }

    def __init__(self, env: str = "production"):
        self.env = env
        self._violation_count = 0

    async def check(
        self,
        action: dict,
        actor: dict,
        context: dict | None = None,
    ) -> ConstitutionalVerdict:
        """
        Check an action against the Constitution.
        Called BEFORE every execution.
        """
        context = context or {}
        violations: list[str] = []
        warnings: list[str] = []
        blocked = False

        action_type = action.get("type", "unknown")
        action_cost = action.get("financial_impact", 0)
        action_sensitivity = action.get("sensitivity", "internal")

        # Rule: no_black_box
        if action.get("requires_explanation", True):
            if not action.get("reasoning_trace") and not action.get("evidence"):
                violations.append("RULE VIOLATION [no_black_box]: Action lacks reasoning trace + evidence.")
                blocked = True

        # Rule: no_unauthorized_action
        actor_role = actor.get("role", "unknown")
        actor_permissions = actor.get("permissions", [])
        required_permission = action.get("required_permission")
        if required_permission and required_permission not in actor_permissions:
            violations.append(
                f"RULE VIOLATION [no_unauthorized_action]: Actor '{actor_role}' "
                f"lacks permission '{required_permission}'."
            )
            blocked = True

        # Limit: autonomous_decision_max
        if action_cost > self.LIMITS["autonomous_decision_max_usd"]:
            if action.get("autonomous", False):
                if action_cost > self.LIMITS["strategic_requires_human_usd"]:
                    violations.append(
                        f"LIMIT VIOLATION: Action cost ${action_cost:,.0f} exceeds "
                        f"strategic threshold ${self.LIMITS['strategic_requires_human_usd']:,.0f}. "
                        f"Human approval required."
                    )
                    blocked = True
                elif action_cost > self.LIMITS["autonomous_decision_max_usd"]:
                    warnings.append(
                        f"LIMIT WARNING: Action cost ${action_cost:,.0f} exceeds "
                        f"autonomous max ${self.LIMITS['autonomous_decision_max_usd']:,.0f}. "
                        f"Manager approval recommended."
                    )

        # Limit: no_autonomous_termination_of_employment
        if action_type == "terminate_employment" and action.get("autonomous", False):
            violations.append(
                "LIMIT VIOLATION [no_autonomous_termination]: "
                "AI cannot autonomously terminate employment."
            )
            blocked = True

        # Autonomy: cannot_make_strategic_decisions_without_human
        if action.get("decision_type") == "strategic" and action.get("autonomous", False):
            violations.append(
                "AUTONOMY VIOLATION: Strategic decisions require human approval."
            )
            blocked = True

        # Ethics: PII access
        if action_sensitivity == "restricted" and "restricted" not in actor.get("access_classifications", []):
            violations.append(
                f"ETHICS VIOLATION: Actor lacks 'restricted' classification "
                f"for accessing restricted data."
            )
            blocked = True

        if violations:
            self._violation_count += 1
            logger.error("CONSTITUTIONAL VIOLATION: %s", violations)

        severity = ConstitutionalSeverity.BLOCK if blocked else (
            ConstitutionalSeverity.WARNING if warnings else ConstitutionalSeverity.INFO
        )

        return ConstitutionalVerdict(
            compliant=not blocked,
            severity=severity,
            violations=violations,
            warnings=warnings,
            checked_at=time.time(),
            action_blocked=blocked,
        )

    def get_amendment_process(self) -> dict:
        """Amending the Constitution requires board + shareholder approval."""
        return {
            "required_approvals": ["board_majority", "shareholder_quorum"],
            "review_period_days": 30,
            "public_disclosure": True,
            "rollback_possible": True,
        }

    def violation_count(self) -> int:
        return self._violation_count


# Module-level singleton
constitution = AIConstitution()


__all__ = [
    "AIConstitution",
    "ConstitutionalVerdict",
    "ConstitutionalSeverity",
    "constitution",
]
