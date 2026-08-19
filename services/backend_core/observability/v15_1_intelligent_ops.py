"""
HSAAI v15.1 — ABAC Priority Mode + Safe Auto-Remediation + Predictive Baseline
==============================================================================
Implements:
  1. ABACPriorityMode — Phase 2 migration: ABAC overrides RBAC
  2. SafeAutoRemediationManager — Production allowlist + safety gates
  3. PredictiveBaselineCollector — 7-day observation period manager
"""
from __future__ import annotations

import asyncio
import json
import logging
import statistics
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone, timedelta
from typing import Any, Callable

logger = logging.getLogger("hsaai.v15_1")
audit_logger = logging.getLogger("hsaai.audit.v15_1")


# ═══════════════════════════════════════════════════════════════════════
# 1. ABAC Priority Mode (Phase 2 Migration)
# ═══════════════════════════════════════════════════════════════════════
class ABACPriorityMode:
    """Phase 2 ABAC migration: ABAC decisions override RBAC.

    Decision flow:
      1. Evaluate ABAC policies
      2. If ABAC has a matching policy → use ABAC decision (overrides RBAC)
      3. If no ABAC policy matches → fall back to RBAC
      4. If both deny → DENY (deny-by-default)
    """

    def __init__(self):
        self._abac_decisions: list[dict[str, Any]] = []
        self._rbac_fallbacks: list[dict[str, Any]] = []
        self._mode = "priority"  # hybrid, priority, full

    @property
    def mode(self) -> str:
        return self._mode

    def evaluate(
        self,
        subject: dict[str, Any],
        resource: dict[str, Any],
        action: str,
        environment: dict[str, Any] | None = None,
        *,
        abac_engine=None,
        rbac_has_permission: Callable[[dict, str], bool] | None = None,
    ) -> dict[str, Any]:
        """Evaluate authorization with ABAC Priority Mode.

        Args:
            subject: User attributes
            resource: Resource attributes
            action: Action being performed
            environment: Environment context
            abac_engine: ABACPolicyEngine instance (optional)
            rbac_has_permission: Function(claims, permission) -> bool

        Returns:
            Decision dict with source (abac/rbac/default) and decision
        """
        env = environment or {}

        # Step 1: Try ABAC first
        abac_result = None
        if abac_engine is not None:
            abac_result = abac_engine.evaluate(subject, resource, action, env)
            if abac_result.get("policy_id") is not None:
                # ABAC has a matching policy — ABAC decision wins
                decision = abac_result["decision"]
                result = {
                    "decision": decision,
                    "source": "abac",
                    "abac_policy": abac_result.get("policy_id"),
                    "abac_policy_name": abac_result.get("policy_name"),
                    "rbac_evaluated": False,
                }
                self._abac_decisions.append(result)
                return result

        # Step 2: No ABAC policy matched — fall back to RBAC
        rbac_allowed = False
        if rbac_has_permission is not None:
            rbac_allowed = rbac_has_permission(subject, action.replace(":", "_") if ":" in action else action)
            # Actually call with the original permission string
            rbac_allowed = rbac_has_permission(subject, action)

        if rbac_allowed:
            result = {
                "decision": "ALLOW",
                "source": "rbac",
                "abac_policy": None,
                "rbac_evaluated": True,
            }
        else:
            result = {
                "decision": "DENY",
                "source": "default_deny",
                "abac_policy": None,
                "rbac_evaluated": True,
            }

        self._rbac_fallbacks.append(result)
        return result

    def get_migration_stats(self) -> dict[str, Any]:
        """Get ABAC migration statistics."""
        total = len(self._abac_decisions) + len(self._rbac_fallbacks)
        return {
            "mode": self._mode,
            "total_decisions": total,
            "abac_decisions": len(self._abac_decisions),
            "rbac_fallbacks": len(self._rbac_fallbacks),
            "abac_coverage_pct": round(
                len(self._abac_decisions) / total * 100, 1
            ) if total > 0 else 0.0,
        }


# ═══════════════════════════════════════════════════════════════════════
# 2. Safe Auto-Remediation Manager
# ═══════════════════════════════════════════════════════════════════════
class SafeAutoRemediationError(Exception):
    pass


class SafeAutoRemediationManager:
    """Production-safe auto-remediation with allowlist enforcement.

    v15.1 initial allowlist (LOW-RISK only):
      - scale_resources
      - trigger_evaluation

    Safety controls:
      - Action allowlist (only approved actions)
      - Risk classification (only LOW risk allowed initially)
      - Execution limits (rate limiting + loop prevention)
      - Audit logging (every action)
      - Rollback support (reversible actions only)
      - Failure protection (no cascading failures)
    """

    # v15.1 Production allowlist
    PRODUCTION_ALLOWLIST = {
        "scale_resources": {"risk": "low", "reversible": True},
        "trigger_evaluation": {"risk": "low", "reversible": True},
    }

    MAX_EXECUTIONS_PER_HOUR = 10
    LOOP_PREVENTION_WINDOW = 300  # 5 minutes

    def __init__(self):
        self._execution_history: list[dict[str, Any]] = []
        self._recent_executions: list[float] = []
        self._last_execution: dict[str, float] = {}
        self._handlers: dict[str, Callable] = {}
        self._enabled = True

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def register_handler(self, action: str, handler: Callable) -> None:
        if action not in self.PRODUCTION_ALLOWLIST:
            raise SafeAutoRemediationError(
                f"Action '{action}' is not in production allowlist. "
                f"Allowed: {list(self.PRODUCTION_ALLOWLIST.keys())}"
            )
        self._handlers[action] = handler

    def get_allowlist(self) -> dict[str, dict[str, Any]]:
        """Get the current production allowlist."""
        return dict(self.PRODUCTION_ALLOWLIST)

    def is_action_allowed(self, action: str) -> bool:
        """Check if an action is in the production allowlist."""
        return action in self.PRODUCTION_ALLOWLIST

    async def execute(
        self,
        action: str,
        target: str,
        *,
        detection: dict[str, Any] | None = None,
        require_approval: bool = False,
        approver: str | None = None,
    ) -> dict[str, Any]:
        """Execute a safe auto-remediation action.

        Args:
            action: Remediation action (must be in allowlist)
            target: Target service/component
            detection: What triggered the remediation
            require_approval: Whether human approval is required
            approver: Approver identity

        Returns:
            Execution result

        Raises:
            SafeAutoRemediationError: If safety checks fail
        """
        # Check if enabled
        if not self._enabled:
            raise SafeAutoRemediationError("Auto-remediation is disabled")

        # Check allowlist
        if action not in self.PRODUCTION_ALLOWLIST:
            raise SafeAutoRemediationError(
                f"Action '{action}' is NOT in production allowlist. "
                f"Allowed actions: {list(self.PRODUCTION_ALLOWLIST.keys())}"
            )

        action_config = self.PRODUCTION_ALLOWLIST[action]

        # Check approval requirement
        if require_approval and not approver:
            raise SafeAutoRemediationError(
                f"Action '{action}' requires approval but no approver provided"
            )

        # Rate limiting
        now = time.time()
        recent = [t for t in self._recent_executions if now - t < 3600]
        if len(recent) >= self.MAX_EXECUTIONS_PER_HOUR:
            raise SafeAutoRemediationError(
                f"Rate limit exceeded: {self.MAX_EXECUTIONS_PER_HOUR} executions/hour"
            )

        # Loop prevention
        action_key = f"{action}:{target}"
        last = self._last_execution.get(action_key, 0)
        if now - last < self.LOOP_PREVENTION_WINDOW:
            raise SafeAutoRemediationError(
                f"Loop prevention: '{action}' on '{target}' was executed "
                f"less than {self.LOOP_PREVENTION_WINDOW}s ago"
            )

        execution_id = str(uuid.uuid4())

        # Pre-execution audit
        audit_logger.info(json.dumps({
            "event": "SAFE_REMEDIATION_STARTED",
            "execution_id": execution_id,
            "action": action,
            "target": target,
            "risk": action_config["risk"],
            "reversible": action_config["reversible"],
            "detection": detection,
            "approver": approver,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }))

        # Execute
        result = {"success": False, "message": "No handler registered"}
        handler = self._handlers.get(action)
        if handler:
            try:
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(target)
                else:
                    result = handler(target)
            except Exception as exc:
                result = {"success": False, "message": str(exc)}

        # Update tracking
        self._recent_executions.append(now)
        self._last_execution[action_key] = now

        # Record
        record = {
            "execution_id": execution_id,
            "action": action,
            "target": target,
            "risk": action_config["risk"],
            "reversible": action_config["reversible"],
            "result": result,
            "status": "completed" if result.get("success") else "failed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._execution_history.append(record)

        # Post-execution audit
        audit_logger.info(json.dumps({
            "event": "SAFE_REMEDIATION_COMPLETED",
            "execution_id": execution_id,
            "action": action,
            "target": target,
            "success": result.get("success", False),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }))

        return record

    def get_history(self, limit: int = 20) -> list[dict[str, Any]]:
        return self._execution_history[-limit:]

    def get_stats(self) -> dict[str, Any]:
        total = len(self._execution_history)
        successful = sum(1 for r in self._execution_history if r["status"] == "completed")
        by_action = defaultdict(int)
        for r in self._execution_history:
            by_action[r["action"]] += 1
        return {
            "enabled": self._enabled,
            "total_executions": total,
            "successful": successful,
            "failed": total - successful,
            "success_rate": round(successful / total * 100, 1) if total else 100.0,
            "by_action": dict(by_action),
            "allowlist": list(self.PRODUCTION_ALLOWLIST.keys()),
            "recent_count": len([t for t in self._recent_executions if time.time() - t < 3600]),
            "max_per_hour": self.MAX_EXECUTIONS_PER_HOUR,
        }


# ═══════════════════════════════════════════════════════════════════════
# 3. Predictive Baseline Collector (7-day observation)
# ═══════════════════════════════════════════════════════════════════════
class PredictiveBaselineCollector:
    """Collects operational metrics for 7-day baseline before enabling predictions.

    Phase 1 (v15.1): Observation Only — collect metrics, no auto-actions
    Phase 2 (v15.2): After 7 days + approval → enable predictive recommendations

    Collects:
      - Infrastructure: CPU, memory, storage, network
      - Application: API latency, error rates, request volume
      - AI: Model latency, token usage, RAG quality, agent success
      - Security: Auth failures, authz failures, policy decisions
    """

    OBSERVATION_PERIOD_DAYS = 7
    METRIC_CATEGORIES = ["infrastructure", "application", "ai", "security"]

    def __init__(self):
        self._metrics: dict[str, deque] = defaultdict(lambda: deque(maxlen=10000))
        self._start_time: datetime | None = None
        self._mode = "observation"  # observation, baseline_ready, active

    @property
    def mode(self) -> str:
        return self._mode

    def start_observation(self) -> dict[str, Any]:
        """Start the 7-day observation period."""
        self._start_time = datetime.now(timezone.utc)
        self._mode = "observation"
        return {
            "status": "observation_started",
            "start_time": self._start_time.isoformat(),
            "observation_period_days": self.OBSERVATION_PERIOD_DAYS,
            "estimated_completion": (self._start_time + timedelta(days=self.OBSERVATION_PERIOD_DAYS)).isoformat(),
            "mode": self._mode,
        }

    def collect_metric(
        self,
        category: str,
        metric_name: str,
        value: float,
        *,
        timestamp: str | None = None,
    ) -> dict[str, Any]:
        """Collect a metric data point.

        Args:
            category: Metric category (infrastructure, application, ai, security)
            metric_name: Metric name (e.g., "cpu_usage", "api_latency_p95")
            value: Metric value
            timestamp: Optional timestamp (UTC ISO)

        Returns:
            Collection confirmation
        """
        if category not in self.METRIC_CATEGORIES:
            raise ValueError(f"Invalid category '{category}'. Allowed: {self.METRIC_CATEGORIES}")

        ts = timestamp or datetime.now(timezone.utc).isoformat()
        key = f"{category}.{metric_name}"
        self._metrics[key].append({"timestamp": ts, "value": value})

        return {
            "collected": True,
            "category": category,
            "metric": metric_name,
            "value": value,
            "timestamp": ts,
        }

    def get_observation_status(self) -> dict[str, Any]:
        """Get current observation status."""
        if self._start_time is None:
            return {"status": "not_started", "mode": self._mode}

        elapsed = datetime.now(timezone.utc) - self._start_time
        remaining = timedelta(days=self.OBSERVATION_PERIOD_DAYS) - elapsed
        total_metrics = sum(len(v) for v in self._metrics.values())

        return {
            "status": "in_progress" if remaining.total_seconds() > 0 else "complete",
            "mode": self._mode,
            "start_time": self._start_time.isoformat(),
            "elapsed_days": round(elapsed.total_seconds() / 86400, 2),
            "remaining_days": max(round(remaining.total_seconds() / 86400, 2), 0),
            "total_metrics_collected": total_metrics,
            "metrics_by_category": self._get_category_counts(),
        }

    def _get_category_counts(self) -> dict[str, int]:
        counts = {cat: 0 for cat in self.METRIC_CATEGORIES}
        for key, values in self._metrics.items():
            cat = key.split(".")[0]
            if cat in counts:
                counts[cat] += len(values)
        return counts

    def generate_baseline_report(self) -> dict[str, Any]:
        """Generate the 7-day baseline report.

        Only available after observation period is complete.
        """
        status = self.get_observation_status()
        if status["status"] != "complete" and self._mode == "observation":
            return {
                "status": "observation_incomplete",
                "message": f"Observation period not complete. {status.get('remaining_days', 0)} days remaining.",
                "current_status": status,
            }

        # Calculate baselines
        baselines = {}
        for key, values in self._metrics.items():
            if len(values) < 10:
                continue
            numeric_values = [v["value"] for v in values if isinstance(v["value"], (int, float))]
            if not numeric_values:
                continue
            baselines[key] = {
                "count": len(numeric_values),
                "min": min(numeric_values),
                "max": max(numeric_values),
                "mean": round(statistics.mean(numeric_values), 4),
                "median": round(statistics.median(numeric_values), 4),
                "stdev": round(statistics.stdev(numeric_values), 4) if len(numeric_values) > 1 else 0,
                "p95": round(self._percentile(numeric_values, 95), 4),
                "p99": round(self._percentile(numeric_values, 99), 4),
            }

        self._mode = "baseline_ready"
        return {
            "status": "baseline_generated",
            "mode": self._mode,
            "observation_period_days": self.OBSERVATION_PERIOD_DAYS,
            "total_metrics": sum(len(v) for v in self._metrics.values()),
            "baselines": baselines,
            "data_quality": self._assess_data_quality(baselines),
            "activation_recommendation": "Approve to enable predictive recommendations",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _percentile(self, values: list[float], p: float) -> float:
        """Calculate percentile."""
        if not values:
            return 0
        sorted_vals = sorted(values)
        idx = int(len(sorted_vals) * p / 100)
        return sorted_vals[min(idx, len(sorted_vals) - 1)]

    def _assess_data_quality(self, baselines: dict) -> dict[str, Any]:
        """Assess data quality of collected metrics."""
        total_metrics = len(baselines)
        if total_metrics == 0:
            return {"score": 0, "status": "no_data"}

        adequate = sum(1 for b in baselines.values() if b["count"] >= 100)
        score = round(adequate / total_metrics * 100, 1)

        if score >= 80:
            status = "good"
        elif score >= 50:
            status = "fair"
        else:
            status = "poor"

        return {
            "score": score,
            "status": status,
            "total_metrics": total_metrics,
            "adequate_samples": adequate,
        }

    def get_collected_metrics(self) -> dict[str, list]:
        """Get all collected metrics."""
        return {k: list(v) for k, v in self._metrics.items()}


# Singletons
_abac_priority: ABACPriorityMode | None = None
_safe_remediation: SafeAutoRemediationManager | None = None
_baseline_collector: PredictiveBaselineCollector | None = None

def get_abac_priority() -> ABACPriorityMode:
    global _abac_priority
    if _abac_priority is None:
        _abac_priority = ABACPriorityMode()
    return _abac_priority

def get_safe_remediation() -> SafeAutoRemediationManager:
    global _safe_remediation
    if _safe_remediation is None:
        _safe_remediation = SafeAutoRemediationManager()
    return _safe_remediation

def get_baseline_collector() -> PredictiveBaselineCollector:
    global _baseline_collector
    if _baseline_collector is None:
        _baseline_collector = PredictiveBaselineCollector()
    return _baseline_collector
