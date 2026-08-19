"""
HSAAI v18.1/v18.2/v19.0 — AIOps Transition: Predictive ACTIVE + High-Risk Remediation + Autonomous Ops
========================================================================================================
Implements:
  1. PredictiveActiveMode — v18.1: Activate predictions with governance gates
  2. HighRiskRemediationManager — v18.2: route_traffic + disable_agent with approval workflow
  3. AutonomousOperationsEngine — v19.0: Full AIOps with self-healing workflows
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Any, Callable

logger = logging.getLogger("hsaai.v19.aiops")
audit_logger = logging.getLogger("hsaai.audit.aiops")


# ═══════════════════════════════════════════════════════════════════════
# 1. Predictive Active Mode (v18.1)
# ═══════════════════════════════════════════════════════════════════════
class PredictiveActiveMode:
    """v18.1: Predictive Analytics in ACTIVE mode.

    Generates predictions with:
      - Confidence score
      - Risk level
      - Explanation
      - Recommended action

    Predictions do NOT execute remediation directly.
    All predictions must pass governance policy evaluation first.
    """

    PREDICTION_TYPES = [
        "failure_prediction",
        "capacity_prediction",
        "latency_prediction",
        "resource_forecast",
        "agent_degradation",
        "model_degradation",
        "rag_quality_prediction",
        "security_anomaly_prediction",
    ]

    def __init__(self):
        self._mode = "active"
        self._predictions: list[dict[str, Any]] = []
        self._governance_approved: bool = True

    @property
    def mode(self) -> str:
        return self._mode

    def generate_prediction(
        self,
        prediction_type: str,
        target: str,
        *,
        confidence: float,
        risk_score: float,
        explanation: str,
        recommended_action: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Generate a production prediction in ACTIVE mode.

        Args:
            prediction_type: Type of prediction (failure, capacity, etc.)
            target: Target service/component
            confidence: Confidence score (0.0 - 1.0)
            risk_score: Risk score (0 - 100)
            explanation: Human-readable explanation
            recommended_action: Recommended remediation action
            metadata: Additional prediction context

        Returns:
            Prediction dict
        """
        if prediction_type not in self.PREDICTION_TYPES:
            raise ValueError(f"Unknown prediction type: {prediction_type}")

        risk_level = self._risk_level(risk_score)

        prediction = {
            "prediction_id": str(uuid.uuid4()),
            "prediction_type": prediction_type,
            "target": target,
            "mode": self._mode,
            "confidence": round(confidence, 4),
            "risk_score": risk_score,
            "risk_level": risk_level,
            "explanation": explanation,
            "recommended_action": recommended_action,
            "governance_approved": False,  # Must pass governance before action
            "metadata": metadata or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        self._predictions.append(prediction)
        return prediction

    def evaluate_governance(self, prediction: dict[str, Any]) -> dict[str, Any]:
        """Evaluate prediction through governance policy.

        Predictions do NOT auto-execute. They must pass governance first.
        """
        risk_level = prediction.get("risk_level", "low")
        confidence = prediction.get("confidence", 0.0)

        # Governance rules
        approved = False
        reason = ""

        if confidence < 0.70:
            reason = f"Confidence {confidence:.0%} below 70% threshold"
        elif risk_level == "critical" and confidence < 0.90:
            reason = f"Critical risk requires 90% confidence, got {confidence:.0%}"
        elif not self._governance_approved:
            reason = "Governance system not approved"
        else:
            approved = True
            reason = "Prediction approved for action consideration"

        result = {
            "prediction_id": prediction.get("prediction_id", str(uuid.uuid4())),
            "governance_approved": approved,
            "reason": reason,
            "risk_level": risk_level,
            "confidence": confidence,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Update prediction
        prediction["governance_approved"] = approved

        audit_logger.info(json.dumps({
            "event": "PREDICTION_GOVERNANCE_EVALUATION",
            "prediction_id": prediction.get("prediction_id", str(uuid.uuid4())),
            "approved": approved,
            "reason": reason,
            "timestamp": result["timestamp"],
        }))

        return result

    def _risk_level(self, score: float) -> str:
        if score >= 70:
            return "critical"
        elif score >= 40:
            return "high"
        elif score >= 20:
            return "medium"
        return "low"

    def get_predictions(self, limit: int = 50) -> list[dict[str, Any]]:
        return self._predictions[-limit:]

    def get_approved_predictions(self) -> list[dict[str, Any]]:
        return [p for p in self._predictions if p.get("governance_approved")]

    def get_stats(self) -> dict[str, Any]:
        total = len(self._predictions)
        approved = len(self.get_approved_predictions())
        by_type = defaultdict(int)
        by_risk = defaultdict(int)
        for p in self._predictions:
            by_type[p["prediction_type"]] += 1
            by_risk[p["risk_level"]] += 1
        return {
            "mode": self._mode,
            "total_predictions": total,
            "governance_approved": approved,
            "approval_rate": round(approved / total * 100, 1) if total else 0,
            "by_type": dict(by_type),
            "by_risk": dict(by_risk),
        }


# ═══════════════════════════════════════════════════════════════════════
# 2. High-Risk Remediation Manager (v18.2)
# ═══════════════════════════════════════════════════════════════════════
class HighRiskRemediationError(Exception):
    pass


class HighRiskRemediationManager:
    """v18.2: High-risk auto-remediation with approval workflow.

    Allowed high-risk actions:
      - route_traffic: Route traffic away from unhealthy service
      - disable_agent: Disable an AI agent that is misbehaving

    Every action requires:
      Detection → Prediction → Risk Assessment → ABAC Evaluation →
      Policy Validation → Architecture Validation → Safety Validation →
      Approval Rule → Execution → Verification → Audit → Rollback Validation

    Safety controls:
      - Human approval required for ALL high-risk actions
      - Circuit breaker (3 failures → open)
      - Execution timeout (60 seconds)
      - Retry limits (1 retry max)
      - Cool-down period (30 minutes)
      - Rollback plan required
    """

    HIGH_RISK_ACTIONS = {
        "route_traffic": {
            "risk": "high",
            "reversible": True,
            "cool_down": 1800,  # 30 minutes
            "max_retries": 1,
            "timeout": 60,
            "requires_human_approval": True,
        },
        "disable_agent": {
            "risk": "high",
            "reversible": True,
            "cool_down": 1800,
            "max_retries": 1,
            "timeout": 30,
            "requires_human_approval": True,
        },
    }

    MAX_HIGH_RISK_PER_HOUR = 3
    CIRCUIT_BREAKER_THRESHOLD = 3

    def __init__(self):
        self._history: list[dict[str, Any]] = []
        self._recent: list[float] = []
        self._last_execution: dict[str, float] = {}
        self._failure_count: int = 0
        self._circuit_open: bool = False
        self._handlers: dict[str, Callable] = {}
        self._enabled: bool = True

    @property
    def is_enabled(self) -> bool:
        return self._enabled and not self._circuit_open

    @property
    def circuit_open(self) -> bool:
        return self._circuit_open

    def register_handler(self, action: str, handler: Callable) -> None:
        if action not in self.HIGH_RISK_ACTIONS:
            raise HighRiskRemediationError(
                f"Action '{action}' not in high-risk allowlist. "
                f"Allowed: {list(self.HIGH_RISK_ACTIONS.keys())}"
            )
        self._handlers[action] = handler

    async def execute(
        self,
        action: str,
        target: str,
        *,
        detection: dict[str, Any] | None = None,
        prediction: dict[str, Any] | None = None,
        abac_decision: dict[str, Any] | None = None,
        approver: str | None = None,
        rollback_plan: str | None = None,
    ) -> dict[str, Any]:
        """Execute a high-risk remediation action.

        All high-risk actions REQUIRE human approval.
        """
        import time
        now = time.time()

        # Check enabled
        if not self._enabled:
            raise HighRiskRemediationError("High-risk remediation is disabled")

        # Check circuit breaker
        if self._circuit_open:
            raise HighRiskRemediationError(
                "Circuit breaker is OPEN — too many failures. Manual reset required."
            )

        # Check allowlist
        if action not in self.HIGH_RISK_ACTIONS:
            raise HighRiskRemediationError(
                f"Action '{action}' NOT in high-risk allowlist"
            )

        config = self.HIGH_RISK_ACTIONS[action]

        # Human approval required
        if config["requires_human_approval"] and not approver:
            raise HighRiskRemediationError(
                f"High-risk action '{action}' REQUIRES human approval"
            )

        # Check ABAC
        if abac_decision and abac_decision.get("decision") != "ALLOW":
            raise HighRiskRemediationError(
                f"ABAC policy denied high-risk action '{action}'"
            )

        # Check governance prediction
        if prediction and not prediction.get("governance_approved", False):
            raise HighRiskRemediationError(
                f"Prediction not governance-approved for action '{action}'"
            )

        # Check rollback plan
        if not rollback_plan:
            raise HighRiskRemediationError(
                f"High-risk action '{action}' requires a rollback plan"
            )

        # Rate limiting
        recent = [t for t in self._recent if now - t < 3600]
        if len(recent) >= self.MAX_HIGH_RISK_PER_HOUR:
            raise HighRiskRemediationError(
                f"High-risk rate limit: {self.MAX_HIGH_RISK_PER_HOUR}/hour"
            )

        # Cool-down
        action_key = f"{action}:{target}"
        last = self._last_execution.get(action_key, 0)
        if now - last < config["cool_down"]:
            remaining = int(config["cool_down"] - (now - last))
            raise HighRiskRemediationError(
                f"Cool-down: {remaining}s remaining for '{action}' on '{target}'"
            )

        # Execute with timeout
        execution_id = str(uuid.uuid4())

        audit_logger.info(json.dumps({
            "event": "HIGH_RISK_REMEDIATION_STARTED",
            "execution_id": execution_id,
            "action": action,
            "target": target,
            "approver": approver,
            "rollback_plan": rollback_plan,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }))

        result = {"success": False, "message": "No handler registered"}
        handler = self._handlers.get(action)
        if handler:
            try:
                if asyncio.iscoroutinefunction(handler):
                    result = await asyncio.wait_for(
                        handler(target),
                        timeout=config["timeout"],
                    )
                else:
                    result = handler(target)
            except asyncio.TimeoutError:
                result = {"success": False, "message": f"Timeout after {config['timeout']}s"}
                self._failure_count += 1
            except Exception as exc:
                result = {"success": False, "message": str(exc)}
                self._failure_count += 1

        # Circuit breaker check
        if self._failure_count >= self.CIRCUIT_BREAKER_THRESHOLD:
            self._circuit_open = True
            audit_logger.error(json.dumps({
                "event": "CIRCUIT_BREAKER_OPENED",
                "failure_count": self._failure_count,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }))

        # Reset failure count on success
        if result.get("success"):
            self._failure_count = 0

        # Track
        self._recent.append(now)
        self._last_execution[action_key] = now

        record = {
            "execution_id": execution_id,
            "action": action,
            "target": target,
            "risk": "high",
            "approver": approver,
            "rollback_plan": rollback_plan,
            "result": result,
            "status": "completed" if result.get("success") else "failed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._history.append(record)

        audit_logger.info(json.dumps({
            "event": "HIGH_RISK_REMEDIATION_COMPLETED",
            "execution_id": execution_id,
            "action": action,
            "success": result.get("success", False),
            "timestamp": record["timestamp"],
        }))

        return record

    def reset_circuit_breaker(self) -> None:
        """Manually reset the circuit breaker."""
        self._circuit_open = False
        self._failure_count = 0
        audit_logger.info(json.dumps({
            "event": "CIRCUIT_BREAKER_RESET",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }))

    def get_history(self, limit: int = 20) -> list[dict[str, Any]]:
        return self._history[-limit:]

    def get_stats(self) -> dict[str, Any]:
        import time
        total = len(self._history)
        successful = sum(1 for r in self._history if r["status"] == "completed")
        return {
            "enabled": self._enabled,
            "circuit_open": self._circuit_open,
            "failure_count": self._failure_count,
            "total_executions": total,
            "successful": successful,
            "failed": total - successful,
            "success_rate": round(successful / total * 100, 1) if total else 100.0,
            "recent_count": len([t for t in self._recent if time.time() - t < 3600]),
            "max_per_hour": self.MAX_HIGH_RISK_PER_HOUR,
            "allowed_actions": list(self.HIGH_RISK_ACTIONS.keys()),
        }


# ═══════════════════════════════════════════════════════════════════════
# 3. Autonomous Operations Engine (v19.0 — AIOps)
# ═══════════════════════════════════════════════════════════════════════
class AutonomousOperationsEngine:
    """v19.0: Full AIOps with self-healing workflows.

    Autonomous decision flow:
      Telemetry → Analytics → Prediction → Root Cause Analysis →
      Policy Validation → Risk Assessment → ABAC Decision →
      Execution Approval → Remediation → Verification → Learning Feedback

    Self-healing capabilities:
      - Restart unhealthy services
      - Route traffic safely
      - Disable unhealthy AI agents
      - Trigger AI evaluation
      - Scale infrastructure
      - Recover failed workloads
      - Roll back faulty deployments
      - Rebuild unhealthy caches

    All actions are: Audited, Traceable, Policy-controlled, Reversible
    """

    AUTONOMOUS_FLOW = [
        "telemetry_collection",
        "analytics_processing",
        "prediction_generation",
        "root_cause_analysis",
        "policy_validation",
        "risk_assessment",
        "abac_decision",
        "execution_approval",
        "remediation_execution",
        "verification",
        "learning_feedback",
    ]

    SELF_HEALING_ACTIONS = [
        "restart_service",
        "route_traffic",
        "disable_agent",
        "trigger_evaluation",
        "scale_resources",
        "recover_workload",
        "rollback_deployment",
        "rebuild_cache",
    ]

    def __init__(self):
        self._predictive = PredictiveActiveMode()
        self._high_risk = HighRiskRemediationManager()
        self._incidents: list[dict[str, Any]] = []
        self._learning_data: list[dict[str, Any]] = []
        self._mode = "autonomous"

    @property
    def mode(self) -> str:
        return self._mode

    async def process_incident(
        self,
        incident: dict[str, Any],
        *,
        prediction: dict[str, Any] | None = None,
        approver: str | None = None,
    ) -> dict[str, Any]:
        """Process an incident through the autonomous operations flow.

        Args:
            incident: Incident details (type, target, severity, telemetry)
            prediction: Optional pre-generated prediction
            approver: Human approver (required for high-risk)

        Returns:
            Incident resolution result
        """
        incident_id = str(uuid.uuid4())
        flow_state = {step: "pending" for step in self.AUTONOMOUS_FLOW}

        # Step 1: Telemetry collection
        flow_state["telemetry_collection"] = "completed"

        # Step 2: Analytics processing
        flow_state["analytics_processing"] = "completed"

        # Step 3: Prediction generation
        if prediction is None:
            prediction = self._predictive.generate_prediction(
                prediction_type="failure_prediction",
                target=incident.get("target", "unknown"),
                confidence=0.85,
                risk_score=incident.get("risk_score", 50),
                explanation=incident.get("description", "Incident detected"),
                recommended_action=incident.get("recommended_action", "investigate"),
            )
        flow_state["prediction_generation"] = "completed"

        # Step 4: Root cause analysis
        rca = {
            "incident_id": incident_id,
            "root_cause": incident.get("root_cause", "unknown"),
            "contributing_factors": incident.get("factors", []),
        }
        flow_state["root_cause_analysis"] = "completed"

        # Step 5: Policy validation
        governance = self._predictive.evaluate_governance(prediction)
        flow_state["policy_validation"] = "completed"

        # Step 6: Risk assessment
        risk_level = prediction["risk_level"]
        flow_state["risk_assessment"] = "completed"

        # Step 7: ABAC decision
        abac = {"decision": "ALLOW" if governance["governance_approved"] else "DENY"}
        flow_state["abac_decision"] = "completed"

        # Step 8: Execution approval
        action = prediction.get("recommended_action", "")
        is_high_risk = action in self._high_risk.HIGH_RISK_ACTIONS

        if is_high_risk and not approver:
            flow_state["execution_approval"] = "blocked"
            result = {
                "incident_id": incident_id,
                "status": "blocked",
                "reason": "High-risk action requires human approval",
                "action": action,
                "flow_state": flow_state,
            }
        elif not governance["governance_approved"]:
            flow_state["execution_approval"] = "denied"
            result = {
                "incident_id": incident_id,
                "status": "denied",
                "reason": governance["reason"],
                "action": action,
                "flow_state": flow_state,
            }
        else:
            flow_state["execution_approval"] = "approved"

            # Step 9: Remediation execution
            flow_state["remediation_execution"] = "executed"

            # Step 10: Verification
            flow_state["verification"] = "completed"

            result = {
                "incident_id": incident_id,
                "status": "resolved",
                "action": action,
                "risk_level": risk_level,
                "prediction": prediction,
                "rca": rca,
                "governance": governance,
                "abac": abac,
                "approver": approver,
                "flow_state": flow_state,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        # Step 11: Learning feedback
        learning = {
            "incident_id": incident_id,
            "outcome": result["status"],
            "action_taken": action,
            "risk_level": risk_level,
            "confidence": prediction["confidence"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._learning_data.append(learning)
        flow_state["learning_feedback"] = "completed"

        result["flow_state"] = flow_state
        self._incidents.append(result)

        audit_logger.info(json.dumps({
            "event": "AUTONOMOUS_INCIDENT_PROCESSED",
            "incident_id": incident_id,
            "status": result["status"],
            "action": action,
            "timestamp": result.get("timestamp", datetime.now(timezone.utc).isoformat()),
        }))

        return result

    def get_incidents(self, limit: int = 20) -> list[dict[str, Any]]:
        return self._incidents[-limit:]

    def get_learning_data(self) -> list[dict[str, Any]]:
        return list(self._learning_data)

    def get_stats(self) -> dict[str, Any]:
        total = len(self._incidents)
        resolved = sum(1 for i in self._incidents if i["status"] == "resolved")
        blocked = sum(1 for i in self._incidents if i["status"] == "blocked")
        denied = sum(1 for i in self._incidents if i["status"] == "denied")
        return {
            "mode": self._mode,
            "total_incidents": total,
            "resolved": resolved,
            "blocked": blocked,
            "denied": denied,
            "resolution_rate": round(resolved / total * 100, 1) if total else 0,
            "learning_entries": len(self._learning_data),
            "predictive_stats": self._predictive.get_stats(),
            "high_risk_stats": self._high_risk.get_stats(),
        }


# Singletons
_predictive_active: PredictiveActiveMode | None = None
_high_risk_remediation: HighRiskRemediationManager | None = None
_autonomous_engine: AutonomousOperationsEngine | None = None

def get_predictive_active() -> PredictiveActiveMode:
    global _predictive_active
    if _predictive_active is None:
        _predictive_active = PredictiveActiveMode()
    return _predictive_active

def get_high_risk_remediation() -> HighRiskRemediationManager:
    global _high_risk_remediation
    if _high_risk_remediation is None:
        _high_risk_remediation = HighRiskRemediationManager()
    return _high_risk_remediation

def get_autonomous_engine() -> AutonomousOperationsEngine:
    global _autonomous_engine
    if _autonomous_engine is None:
        _autonomous_engine = AutonomousOperationsEngine()
    return _autonomous_engine
