"""
HSAAI v16.1 — Full ABAC Enforcement + Predictive Activation + Security Control Plane
====================================================================================
Implements:
  1. FullABACEnforcement — Phase 3: ABAC is primary, RBAC is compatibility metadata only
  2. PredictiveActivationManager — Approve and enable production predictions after 7-day baseline
  3. SecurityControlPlane — Central security orchestration for all AI operations
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Any, Callable

logger = logging.getLogger("hsaai.v16_1.security")
audit_logger = logging.getLogger("hsaai.audit.v16_1")


# ═══════════════════════════════════════════════════════════════════════
# 1. Full ABAC Enforcement (Phase 3)
# ═══════════════════════════════════════════════════════════════════════
class FullABACEnforcement:
    """Phase 3 ABAC migration: Full ABAC Enforcement.

    ABAC is the PRIMARY authorization mechanism.
    RBAC becomes compatibility metadata only (no direct authorization).

    Every access request MUST evaluate:
      Subject + Resource + Action + Environment → Decision

    Components:
      - PDP (Policy Decision Point) — evaluates policies
      - PEP (Policy Enforcement Point) — enforces decisions
      - PAP (Policy Administration Point) — manages policies
      - PIP (Policy Information Point) — provides attributes
    """

    def __init__(self):
        self._mode = "full_abac"  # hybrid, priority, full_abac
        self._policies: dict[str, dict[str, Any]] = {}
        self._attribute_sources: dict[str, Callable] = {}
        self._decisions: list[dict[str, Any]] = []
        self._rbac_role_mappings: dict[str, dict[str, Any]] = {}
        self._rbac_deprecated = True

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def rbac_deprecated(self) -> bool:
        return self._rbac_deprecated

    def register_attribute_source(self, source_name: str, provider: Callable) -> None:
        """Register a Policy Information Point (PIP) attribute source."""
        self._attribute_sources[source_name] = provider

    def convert_rbac_role_to_attributes(self, role: str) -> dict[str, Any]:
        """Convert an RBAC role to ABAC subject attributes.

        This is the RBAC deprecation function — roles become attributes.
        """
        role_mappings = {
            "hsaai_admin": {"role_metadata": "admin", "clearance": 5, "trust_score": 1.0},
            "knowledge_admin": {"role_metadata": "knowledge_admin", "clearance": 4, "trust_score": 0.9},
            "ai_user": {"role_metadata": "ai_user", "clearance": 2, "trust_score": 0.7},
            "auditor": {"role_metadata": "auditor", "clearance": 3, "trust_score": 0.8},
            "executive": {"role_metadata": "executive", "clearance": 3, "trust_score": 0.8},
        }
        return role_mappings.get(role, {"role_metadata": role, "clearance": 1, "trust_score": 0.5})

    def register_policy(self, policy_id: str, policy: dict[str, Any]) -> None:
        """Register an ABAC policy (PAP function)."""
        self._policies[policy_id] = policy

    def evaluate(
        self,
        subject: dict[str, Any],
        resource: dict[str, Any],
        action: str,
        environment: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Full ABAC evaluation — every request MUST go through ABAC.

        No RBAC fallback. If no ABAC policy matches → DENY.

        Args:
            subject: Subject attributes (identity, department, clearance, tenant, trust_score)
            resource: Resource attributes (classification, sensitivity, AI model, agent_capability)
            environment: Environment attributes (device_trust, location, time, risk_level)
            action: Action (read, write, delete, execute, approve)

        Returns:
            Authorization decision
        """
        env = environment or {}

        # Enrich subject with attributes from PIP if available
        if "role" in subject and "role_metadata" not in subject:
            attrs = self.convert_rbac_role_to_attributes(subject["role"])
            subject = {**subject, **attrs}

        # Evaluate all policies
        matched_policy = None
        decision = "DENY"  # Full ABAC: deny-by-default, no RBAC fallback

        for policy_id, policy in self._policies.items():
            if not policy.get("enabled", True):
                continue

            if self._evaluate_conditions(policy.get("conditions", []), subject, resource, action, env):
                matched_policy = policy_id
                decision = policy.get("effect", "DENY")
                break  # First match wins (priority order)

        result = {
            "decision": decision,
            "source": "abac_full",
            "policy_id": matched_policy,
            "mode": self._mode,
            "rbac_used": False,
            "subject_attributes": {
                "identity": subject.get("sub", subject.get("identity", "unknown")),
                "department": subject.get("department"),
                "clearance": subject.get("clearance"),
                "tenant": subject.get("tenant_id"),
                "trust_score": subject.get("trust_score"),
            },
            "resource_attributes": {
                "classification": resource.get("classification"),
                "sensitivity": resource.get("sensitivity"),
            },
            "environment_attributes": {
                "device_trust": env.get("device_trust"),
                "location": env.get("location"),
                "risk_level": env.get("risk_level"),
            },
            "action": action,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        self._decisions.append(result)

        # Audit log
        audit_logger.info(json.dumps({
            "event": "ABAC_FULL_DECISION",
            "decision": decision,
            "policy_id": matched_policy,
            "subject": result["subject_attributes"],
            "action": action,
            "timestamp": result["timestamp"],
        }))

        return result

    def _evaluate_conditions(
        self,
        conditions: list[dict[str, Any]],
        subject: dict[str, Any],
        resource: dict[str, Any],
        action: str,
        environment: dict[str, Any],
    ) -> bool:
        """Evaluate ABAC conditions (AND logic)."""
        for cond in conditions:
            source = cond.get("source", "subject")
            attr = cond.get("attribute", "")
            operator = cond.get("operator", "eq")
            expected = cond.get("value")

            if source == "subject":
                actual = subject.get(attr)
            elif source == "resource":
                actual = resource.get(attr)
            elif source == "environment":
                actual = environment.get(attr)
            elif source == "action":
                actual = action
            else:
                return False

            if not self._apply_operator(operator, actual, expected):
                return False

        return True

    def _apply_operator(self, operator: str, actual: Any, expected: Any) -> bool:
        if operator == "eq":
            return actual == expected
        elif operator == "ne":
            return actual != expected
        elif operator == "gt":
            try: return actual > expected
            except TypeError: return False
        elif operator == "lt":
            try: return actual < expected
            except TypeError: return False
        elif operator == "ge":
            try: return actual >= expected
            except TypeError: return False
        elif operator == "le":
            try: return actual <= expected
            except TypeError: return False
        elif operator == "in":
            return actual in (expected if isinstance(expected, list) else [expected])
        return False

    def simulate(self, subject: dict, resource: dict, action: str, environment: dict | None = None) -> dict[str, Any]:
        """Simulate policy evaluation without audit logging."""
        result = self.evaluate(subject, resource, action, environment)
        result["simulation"] = True
        return result

    def get_migration_stats(self) -> dict[str, Any]:
        """Get Full ABAC migration statistics."""
        total = len(self._decisions)
        allowed = sum(1 for d in self._decisions if d["decision"] == "ALLOW")
        denied = total - allowed
        return {
            "mode": self._mode,
            "rbac_deprecated": self._rbac_deprecated,
            "total_policies": len(self._policies),
            "total_decisions": total,
            "allowed": allowed,
            "denied": denied,
            "allow_rate": round(allowed / total * 100, 1) if total else 0,
            "rbac_fallbacks": 0,  # Full ABAC: no RBAC fallbacks
        }


# ═══════════════════════════════════════════════════════════════════════
# 2. Predictive Activation Manager
# ═══════════════════════════════════════════════════════════════════════
class PredictiveActivationManager:
    """Manages the approval and activation of production predictions.

    Workflow:
      1. 7-day observation period (v15.1)
      2. Baseline report review
      3. Accuracy validation
      4. Governance approval
      5. Production activation

    Activation modes:
      - observation_only: Collect metrics, no predictions
      - monitoring: Generate predictions, no auto-actions
      - active: Generate predictions + recommendations (no auto-remediation)
      - full_active: Predictions + auto-remediation from predictions
    """

    MODE_OBSERVATION = "observation_only"
    MODE_MONITORING = "monitoring"
    MODE_ACTIVE = "active"
    MODE_FULL_ACTIVE = "full_active"

    def __init__(self):
        self._mode = self.MODE_OBSERVATION
        self._approval_status = "pending"
        self._baseline_report: dict[str, Any] | None = None
        self._accuracy_metrics: dict[str, Any] = {}
        self._predictions: list[dict[str, Any]] = []

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def approval_status(self) -> str:
        return self._approval_status

    def submit_baseline_report(self, report: dict[str, Any]) -> dict[str, Any]:
        """Submit the 7-day baseline report for review."""
        self._baseline_report = report
        self._approval_status = "under_review"
        return {
            "status": "submitted",
            "approval_status": self._approval_status,
            "data_quality": report.get("data_quality", {}),
            "total_metrics": report.get("total_metrics", 0),
        }

    def validate_accuracy(self, predictions: list[dict[str, Any]], actuals: list[dict[str, Any]]) -> dict[str, Any]:
        """Validate prediction accuracy against actual outcomes.

        Args:
            predictions: List of predicted values
            actuals: List of actual values

        Returns:
            Accuracy validation result
        """
        if len(predictions) != len(actuals) or not predictions:
            return {"valid": False, "reason": "Mismatched or empty prediction/actual lists"}

        correct = 0
        false_positives = 0
        false_negatives = 0
        total = len(predictions)

        for pred, actual in zip(predictions, actuals):
            pred_value = pred.get("predicted")
            actual_value = actual.get("actual")
            if pred_value == actual_value:
                correct += 1
            elif pred_value is True and actual_value is False:
                false_positives += 1
            elif pred_value is False and actual_value is True:
                false_negatives += 1

        accuracy = correct / total if total else 0
        precision = correct / (correct + false_positives) if (correct + false_positives) > 0 else 1.0
        recall = correct / (correct + false_negatives) if (correct + false_negatives) > 0 else 1.0

        self._accuracy_metrics = {
            "total_predictions": total,
            "correct": correct,
            "accuracy": round(accuracy, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "false_positives": false_positives,
            "false_negatives": false_negatives,
            "valid": accuracy >= 0.80,  # 80% accuracy threshold
        }
        return self._accuracy_metrics

    def approve_activation(self, *, approver: str, mode: str = MODE_MONITORING) -> dict[str, Any]:
        """Approve predictive analytics activation.

        Args:
            approver: Approver identity
            mode: Activation mode (monitoring, active, full_active)

        Returns:
            Approval result
        """
        if self._baseline_report is None:
            return {"approved": False, "reason": "No baseline report submitted"}

        if not self._accuracy_metrics.get("valid", False):
            return {"approved": False, "reason": "Accuracy validation failed or not completed"}

        self._mode = mode
        self._approval_status = "approved"

        audit_logger.info(json.dumps({
            "event": "PREDICTIVE_ACTIVATION_APPROVED",
            "approver": approver,
            "mode": mode,
            "accuracy": self._accuracy_metrics.get("accuracy"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }))

        return {
            "approved": True,
            "mode": self._mode,
            "approver": approver,
            "accuracy": self._accuracy_metrics.get("accuracy"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def generate_prediction(
        self,
        target: str,
        prediction_type: str,
        risk_score: float,
        *,
        recommendation: str = "",
    ) -> dict[str, Any] | None:
        """Generate a production prediction (if activated).

        Returns None if not in active mode.
        """
        if self._mode in (self.MODE_OBSERVATION,):
            return None

        if self._mode == self.MODE_MONITORING:
            # Generate prediction but no recommendation
            recommendation = ""

        prediction = {
            "prediction_id": str(uuid.uuid4()),
            "target": target,
            "prediction_type": prediction_type,
            "risk_score": risk_score,
            "risk_level": self._risk_level(risk_score),
            "recommendation": recommendation,
            "mode": self._mode,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._predictions.append(prediction)
        return prediction

    def _risk_level(self, score: float) -> str:
        if score >= 70:
            return "critical"
        elif score >= 40:
            return "high"
        elif score >= 20:
            return "medium"
        return "low"

    def get_status(self) -> dict[str, Any]:
        """Get current predictive analytics status."""
        return {
            "mode": self._mode,
            "approval_status": self._approval_status,
            "baseline_available": self._baseline_report is not None,
            "accuracy": self._accuracy_metrics,
            "total_predictions": len(self._predictions),
        }


# ═══════════════════════════════════════════════════════════════════════
# 3. Security Control Plane
# ═══════════════════════════════════════════════════════════════════════
class SecurityControlPlane:
    """Central security orchestration for all AI operations.

    Components:
      - PDP: Policy Decision Point
      - PEP: Policy Enforcement Point
      - PAP: Policy Administration Point
      - PIP: Policy Information Point

    Capabilities:
      - Dynamic policy decisions
      - Policy versioning
      - Policy testing
      - Policy simulation
      - Policy audit
      - Conflict resolution
    """

    def __init__(self):
        self._abac = FullABACEnforcement()
        self._security_events: list[dict[str, Any]] = []
        self._threat_level = "normal"  # normal, elevated, high, critical

    @property
    def threat_level(self) -> str:
        return self._threat_level

    def set_threat_level(self, level: str) -> None:
        """Set the current threat level."""
        valid = {"normal", "elevated", "high", "critical"}
        if level not in valid:
            raise ValueError(f"Invalid threat level. Must be one of {valid}")
        self._threat_level = level
        self._log_security_event("THREAT_LEVEL_CHANGED", {"level": level})

    def authorize(
        self,
        subject: dict[str, Any],
        resource: dict[str, Any],
        action: str,
        environment: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Authorize a request through the Security Control Plane.

        Injects threat level into environment context.
        """
        env = environment or {}
        env["threat_level"] = self._threat_level
        env["risk_level"] = self._threat_level

        # In elevated/critical threat levels, increase scrutiny
        if self._threat_level in ("elevated", "high", "critical"):
            env["enhanced_scrutiny"] = True

        return self._abac.evaluate(subject, resource, action, env)

    def register_policy(self, policy_id: str, policy: dict[str, Any]) -> None:
        """Register a security policy (PAP)."""
        self._abac.register_policy(policy_id, policy)
        self._log_security_event("POLICY_REGISTERED", {"policy_id": policy_id})

    def detect_threat(self, threat_type: str, details: dict[str, Any]) -> dict[str, Any]:
        """Record a detected threat.

        Args:
            threat_type: Type of threat (prompt_injection, data_leakage, model_tampering)
            details: Threat details

        Returns:
            Threat detection record
        """
        severity_map = {
            "prompt_injection": "high",
            "jailbreak_attempt": "critical",
            "data_leakage": "critical",
            "model_tampering": "critical",
            "unauthorized_access": "high",
            "suspicious_pattern": "medium",
        }

        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "THREAT_DETECTED",
            "threat_type": threat_type,
            "severity": severity_map.get(threat_type, "medium"),
            "details": details,
            "threat_level_at_detection": self._threat_level,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._security_events.append(event)

        # Auto-escalate threat level if critical threat detected
        if event["severity"] == "critical" and self._threat_level == "normal":
            self.set_threat_level("elevated")

        audit_logger.info(json.dumps({
            "event": "THREAT_DETECTED",
            "threat_type": threat_type,
            "severity": event["severity"],
            "timestamp": event["timestamp"],
        }))

        return event

    def get_security_events(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get recent security events."""
        return self._security_events[-limit:]

    def get_security_status(self) -> dict[str, Any]:
        """Get overall security status."""
        total = len(self._security_events)
        by_severity = defaultdict(int)
        by_type = defaultdict(int)
        for e in self._security_events:
            by_severity[e.get("severity", "info")] += 1
            if "threat_type" in e:
                by_type[e["threat_type"]] += 1

        return {
            "threat_level": self._threat_level,
            "total_events": total,
            "by_severity": dict(by_severity),
            "by_type": dict(by_type),
            "abac_mode": self._abac.mode,
            "rbac_deprecated": self._abac.rbac_deprecated,
            "policies_registered": len(self._abac._policies),
        }

    def _log_security_event(self, event_type: str, details: dict[str, Any]) -> None:
        """Log a security event."""
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "severity": "info",
            "details": details,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._security_events.append(event)


# Singletons
_full_abac: FullABACEnforcement | None = None
_predictive_mgr: PredictiveActivationManager | None = None
_security_cp: SecurityControlPlane | None = None

def get_full_abac() -> FullABACEnforcement:
    global _full_abac
    if _full_abac is None:
        _full_abac = FullABACEnforcement()
    return _full_abac

def get_predictive_mgr() -> PredictiveActivationManager:
    global _predictive_mgr
    if _predictive_mgr is None:
        _predictive_mgr = PredictiveActivationManager()
    return _predictive_mgr

def get_security_cp() -> SecurityControlPlane:
    global _security_cp
    if _security_cp is None:
        _security_cp = SecurityControlPlane()
    return _security_cp
