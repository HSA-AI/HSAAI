"""
HSAAI v13 — ABAC Policy Engine & Continuous Bias Monitoring
============================================================
Implements:
  1. ABACPolicyEngine — Attribute-Based Access Control with dynamic policies
  2. BiasDetectionScheduler — Daily automated bias evaluation
  3. ContinuousResponsibleAIMonitor — Production Responsible AI monitoring
  4. PolicyConflictDetector — Detect conflicting ABAC policies
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Any, Callable

logger = logging.getLogger("hsaai.v13.abac")
audit_logger = logging.getLogger("hsaai.audit.abac")


# ═══════════════════════════════════════════════════════════════════════
# 1. ABAC Policy Engine
# ═══════════════════════════════════════════════════════════════════════
class ABACPolicyError(Exception):
    """Base exception for ABAC policy errors."""
    pass


class ABACDecision:
    """ABAC authorization decision."""
    ALLOW = "ALLOW"
    DENY = "DENY"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ABACPolicy:
    """A single ABAC policy rule.

    A policy evaluates:
      Subject (user) attributes + Resource attributes + Action + Environment

    Decision: ALLOW or DENY

    Example policy:
      IF subject.department == resource.department
      AND subject.clearance >= resource.classification
      AND environment.trusted == True
      THEN: ALLOW
    """

    def __init__(
        self,
        policy_id: str,
        name: str,
        description: str,
        effect: str = ABACDecision.ALLOW,
        conditions: list[dict[str, Any]] | None = None,
        priority: int = 100,
        enabled: bool = True,
    ):
        self.policy_id = policy_id
        self.name = name
        self.description = description
        self.effect = effect
        self.conditions = conditions or []
        self.priority = priority
        self.enabled = enabled
        self.version = 1
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.updated_at = self.created_at

    def evaluate(
        self,
        subject: dict[str, Any],
        resource: dict[str, Any],
        action: str,
        environment: dict[str, Any],
    ) -> str:
        """Evaluate this policy against the request.

        Returns:
            ABACDecision.ALLOW, DENY, or NOT_APPLICABLE
        """
        if not self.enabled:
            return ABACDecision.NOT_APPLICABLE

        # All conditions must match (AND logic)
        for condition in self.conditions:
            if not self._evaluate_condition(condition, subject, resource, action, environment):
                return ABACDecision.NOT_APPLICABLE

        # All conditions matched — return the effect
        return self.effect

    def _evaluate_condition(
        self,
        condition: dict[str, Any],
        subject: dict[str, Any],
        resource: dict[str, Any],
        action: str,
        environment: dict[str, Any],
    ) -> bool:
        """Evaluate a single condition.

        Condition format:
          {"attribute_source": "subject|resource|environment|action",
           "attribute": "department",
           "operator": "eq|ne|gt|lt|ge|le|in|contains",
           "value": <value>}
        """
        source = condition.get("attribute_source", "subject")
        attr = condition.get("attribute", "")
        operator = condition.get("operator", "eq")
        expected = condition.get("value")

        # Get the actual value from the appropriate source
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

        # Apply operator
        if operator == "eq":
            return actual == expected
        elif operator == "ne":
            return actual != expected
        elif operator == "gt":
            try:
                return actual > expected
            except TypeError:
                return False
        elif operator == "lt":
            try:
                return actual < expected
            except TypeError:
                return False
        elif operator == "ge":
            try:
                return actual >= expected
            except TypeError:
                return False
        elif operator == "le":
            try:
                return actual <= expected
            except TypeError:
                return False
        elif operator == "in":
            return actual in (expected if isinstance(expected, list) else [expected])
        elif operator == "contains":
            try:
                return expected in actual
            except TypeError:
                return False
        else:
            return False


class ABACPolicyEngine:
    """Enterprise ABAC Policy Engine with dynamic authorization.

    Features:
      - Policy management (create, update, delete, version)
      - Dynamic policy evaluation
      - Priority-based conflict resolution
      - Deny-by-default
      - Policy conflict detection
      - Audit logging for all decisions
      - Policy simulation (what-if)

    Policy Evaluation Order:
      1. Sort policies by priority (lower number = higher priority)
      2. Evaluate each policy
      3. First matching DENY policy → DENY
      4. First matching ALLOW policy → ALLOW
      5. If no match → DENY (deny-by-default)
    """

    def __init__(self):
        self._policies: dict[str, ABACPolicy] = {}
        self._policy_versions: dict[str, list[ABACPolicy]] = defaultdict(list)
        self._decision_cache: dict[str, tuple[str, float]] = {}
        self._cache_ttl = 5.0  # seconds

    def create_policy(self, policy: ABACPolicy) -> dict[str, Any]:
        """Create a new ABAC policy."""
        if policy.policy_id in self._policies:
            raise ABACPolicyError(f"Policy '{policy.policy_id}' already exists")
        self._policies[policy.policy_id] = policy
        self._policy_versions[policy.policy_id].append(policy)

        audit_logger.info(json.dumps({
            "event": "POLICY_CREATED",
            "policy_id": policy.policy_id,
            "policy_name": policy.name,
            "effect": policy.effect,
            "priority": policy.priority,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }))

        return {
            "policy_id": policy.policy_id,
            "name": policy.name,
            "status": "created",
            "version": policy.version,
        }

    def update_policy(
        self,
        policy_id: str,
        *,
        conditions: list[dict] | None = None,
        effect: str | None = None,
        priority: int | None = None,
        enabled: bool | None = None,
    ) -> dict[str, Any]:
        """Update an existing policy (creates a new version)."""
        if policy_id not in self._policies:
            raise ABACPolicyError(f"Policy '{policy_id}' not found")

        old = self._policies[policy_id]
        new = ABACPolicy(
            policy_id=old.policy_id,
            name=old.name,
            description=old.description,
            effect=effect or old.effect,
            conditions=conditions or old.conditions,
            priority=priority if priority is not None else old.priority,
            enabled=enabled if enabled is not None else old.enabled,
        )
        new.version = old.version + 1
        new.created_at = old.created_at

        self._policies[policy_id] = new
        self._policy_versions[policy_id].append(new)

        audit_logger.info(json.dumps({
            "event": "POLICY_UPDATED",
            "policy_id": policy_id,
            "new_version": new.version,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }))

        return {
            "policy_id": policy_id,
            "version": new.version,
            "status": "updated",
        }

    def delete_policy(self, policy_id: str) -> dict[str, Any]:
        """Delete a policy."""
        if policy_id not in self._policies:
            raise ABACPolicyError(f"Policy '{policy_id}' not found")
        del self._policies[policy_id]

        audit_logger.info(json.dumps({
            "event": "POLICY_DELETED",
            "policy_id": policy_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }))

        return {"policy_id": policy_id, "status": "deleted"}

    def evaluate(
        self,
        subject: dict[str, Any],
        resource: dict[str, Any],
        action: str,
        environment: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Evaluate ABAC policies for a request.

        Args:
            subject: User attributes (role, department, clearance, etc.)
            resource: Resource attributes (classification, tenant, type, etc.)
            action: Action being performed (read, write, delete, etc.)
            environment: Environment attributes (time, location, device_trust)

        Returns:
            Decision dict with ALLOW/DENY and matched policy info
        """
        env = environment or {}

        # Check cache
        cache_key = json.dumps({
            "subject": subject, "resource": resource,
            "action": action, "environment": env
        }, sort_keys=True)
        now = datetime.now(timezone.utc).timestamp()
        if cache_key in self._decision_cache:
            decision, expires = self._decision_cache[cache_key]
            if now < expires:
                return {"decision": decision, "cached": True}

        # Sort policies by priority (lower = higher priority)
        sorted_policies = sorted(
            self._policies.values(),
            key=lambda p: p.priority
        )

        matched_policy = None
        decision = ABACDecision.DENY  # deny-by-default

        for policy in sorted_policies:
            result = policy.evaluate(subject, resource, action, env)
            if result == ABACDecision.DENY:
                # Explicit DENY wins immediately
                matched_policy = policy
                decision = ABACDecision.DENY
                break
            elif result == ABACDecision.ALLOW:
                matched_policy = policy
                decision = ABACDecision.ALLOW
                break  # First ALLOW wins (priority order)

        # Cache the decision
        self._decision_cache[cache_key] = (decision, now + self._cache_ttl)

        # Audit log
        audit_logger.info(json.dumps({
            "event": "POLICY_DECISION",
            "decision": decision,
            "policy_id": matched_policy.policy_id if matched_policy else None,
            "policy_name": matched_policy.name if matched_policy else "default-deny",
            "subject": subject,
            "resource": resource,
            "action": action,
            "environment": env,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }))

        return {
            "decision": decision,
            "policy_id": matched_policy.policy_id if matched_policy else None,
            "policy_name": matched_policy.name if matched_policy else "default-deny",
            "cached": False,
        }

    def simulate(
        self,
        subject: dict[str, Any],
        resource: dict[str, Any],
        action: str,
        environment: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Simulate policy evaluation without caching or audit logging."""
        env = environment or {}
        sorted_policies = sorted(self._policies.values(), key=lambda p: p.priority)

        matched = None
        decision = ABACDecision.DENY
        evaluations = []

        for policy in sorted_policies:
            result = policy.evaluate(subject, resource, action, env)
            evaluations.append({
                "policy_id": policy.policy_id,
                "policy_name": policy.name,
                "result": result,
            })
            if result == ABACDecision.DENY:
                matched = policy
                decision = ABACDecision.DENY
                break
            elif result == ABACDecision.ALLOW:
                matched = policy
                decision = ABACDecision.ALLOW
                break

        return {
            "decision": decision,
            "matched_policy": matched.policy_id if matched else None,
            "all_evaluations": evaluations,
            "simulation": True,
        }

    def detect_conflicts(self) -> list[dict[str, Any]]:
        """Detect policies that may conflict (same conditions, different effects)."""
        conflicts = []
        policies = list(self._policies.values())

        for i, p1 in enumerate(policies):
            for p2 in policies[i + 1:]:
                if p1.effect != p2.effect and self._conditions_overlap(p1.conditions, p2.conditions):
                    conflicts.append({
                        "policy_1": p1.policy_id,
                        "policy_2": p2.policy_id,
                        "conflict": "overlapping_conditions_different_effect",
                        "resolution": "priority-based (lower priority number wins)",
                    })
        return conflicts

    def _conditions_overlap(self, c1: list, c2: list) -> bool:
        """Check if two condition sets overlap (simplified)."""
        if not c1 or not c2:
            return True
        # Simple check: if same attribute + operator + value
        for cond1 in c1:
            for cond2 in c2:
                if (cond1.get("attribute") == cond2.get("attribute")
                    and cond1.get("operator") == cond2.get("operator")
                    and cond1.get("value") == cond2.get("value")):
                    return True
        return False

    def list_policies(self) -> list[dict[str, Any]]:
        """List all policies."""
        return [
            {
                "policy_id": p.policy_id,
                "name": p.name,
                "effect": p.effect,
                "priority": p.priority,
                "enabled": p.enabled,
                "version": p.version,
            }
            for p in self._policies.values()
        ]

    def get_policy_versions(self, policy_id: str) -> list[dict[str, Any]]:
        """Get all versions of a policy."""
        if policy_id not in self._policy_versions:
            return []
        return [
            {
                "version": v.version,
                "effect": v.effect,
                "priority": v.priority,
                "enabled": v.enabled,
                "created_at": v.created_at,
            }
            for v in self._policy_versions[policy_id]
        ]


# Module-level singleton
_abac_engine: ABACPolicyEngine | None = None


def get_abac_engine() -> ABACPolicyEngine:
    """Get the singleton ABACPolicyEngine instance."""
    global _abac_engine
    if _abac_engine is None:
        _abac_engine = ABACPolicyEngine()
    return _abac_engine


# ═══════════════════════════════════════════════════════════════════════
# 2. Bias Detection Scheduler
# ═══════════════════════════════════════════════════════════════════════
class BiasDetectionScheduler:
    """Daily automated bias evaluation scheduler.

    Workflow:
      1. Trigger (daily cron)
      2. Collect AI outputs from production
      3. Collect evaluation dataset
      4. Run bias analysis
      5. Calculate fairness metrics
      6. Generate risk report
      7. Store results
      8. Notify governance team
    """

    def __init__(self):
        self._jobs: dict[str, dict[str, Any]] = {}
        self._results: list[dict[str, Any]] = []

    def schedule_daily_evaluation(
        self,
        target_model: str,
        protected_attributes: list[str],
        *,
        time: str = "02:00",
        notify_team: str = "governance@hsaai.group",
    ) -> dict[str, Any]:
        """Schedule a daily bias evaluation job.

        Args:
            target_model: Model to evaluate
            protected_attributes: Attributes to check (gender, ethnicity, etc.)
            time: Daily execution time (HH:MM format)
            notify_team: Team to notify with results

        Returns:
            Job configuration
        """
        job_id = f"bias_eval_{target_model}_{uuid.uuid4().hex[:8]}"
        job = {
            "job_id": job_id,
            "target_model": target_model,
            "protected_attributes": protected_attributes,
            "schedule": "daily",
            "time": time,
            "notify_team": notify_team,
            "status": "scheduled",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_run": None,
            "next_run": self._next_run_time(time),
            "run_count": 0,
        }
        self._jobs[job_id] = job
        return job

    def _next_run_time(self, time_str: str) -> str:
        """Calculate next run time."""
        hour, minute = map(int, time_str.split(":"))
        now = datetime.now(timezone.utc)
        next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(days=1)
        return next_run.isoformat()

    async def execute_evaluation(
        self,
        job_id: str,
        predictions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Execute a bias evaluation job.

        Args:
            job_id: Job ID to execute
            predictions: AI predictions to evaluate

        Returns:
            Evaluation result
        """
        if job_id not in self._jobs:
            raise ValueError(f"Job '{job_id}' not found")

        job = self._jobs[job_id]
        job["status"] = "running"
        job["last_run"] = datetime.now(timezone.utc).isoformat()

        # Run bias detection for each protected attribute
        from backend_core.ai_operations.ai_evaluation_v12 import (
            BiasDetectionEngine,
            FairnessMetrics,
        )

        bias_engine = BiasDetectionEngine()
        results = {}

        for attr in job["protected_attributes"]:
            dataset_bias = bias_engine.analyze_dataset_bias(predictions, attr)
            output_bias = bias_engine.analyze_output_bias(predictions, attr)
            fairness = FairnessMetrics.calculate_all(predictions, attr)
            results[attr] = {
                "dataset_bias": dataset_bias,
                "output_bias": output_bias,
                "fairness": fairness,
            }

        # Generate risk report
        risk_level = self._calculate_risk_level(results)
        report = {
            "report_id": str(uuid.uuid4()),
            "job_id": job_id,
            "target_model": job["target_model"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "protected_attributes": job["protected_attributes"],
            "results": results,
            "risk_level": risk_level,
            "recommendations": self._generate_recommendations(results, risk_level),
            "notify_team": job["notify_team"],
        }

        self._results.append(report)
        job["status"] = "completed"
        job["run_count"] += 1

        return report

    def _calculate_risk_level(self, results: dict[str, Any]) -> str:
        """Calculate overall risk level from bias results."""
        max_severity = "low"
        severity_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}

        for attr, data in results.items():
            ds_severity = data.get("dataset_bias", {}).get("severity", "low")
            ob_severity = data.get("output_bias", {}).get("severity", "low")
            for sev in [ds_severity, ob_severity]:
                if severity_order.get(sev, 0) > severity_order.get(max_severity, 0):
                    max_severity = sev

        return max_severity

    def _generate_recommendations(self, results: dict, risk_level: str) -> list[str]:
        """Generate recommendations based on bias results."""
        recs = []
        if risk_level in ("high", "critical"):
            recs.append("Immediate action required: Review model training data for representation")
            recs.append("Consider retraining with balanced dataset")
            recs.append("Notify AI Governance Committee")
        elif risk_level == "medium":
            recs.append("Monitor bias trends — schedule follow-up evaluation")
            recs.append("Review model for potential fairness improvements")
        else:
            recs.append("Bias levels within acceptable range — continue monitoring")

        for attr, data in results.items():
            if data.get("output_bias", {}).get("status") == "fail":
                recs.append(f"Output bias detected for '{attr}' — review prediction distribution")

        return recs

    def get_job_status(self, job_id: str) -> dict[str, Any] | None:
        """Get status of a scheduled job."""
        return self._jobs.get(job_id)

    def list_jobs(self) -> list[dict[str, Any]]:
        """List all scheduled jobs."""
        return list(self._jobs.values())

    def get_reports(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent bias reports."""
        return self._results[-limit:]

    def get_report_template(self) -> dict[str, Any]:
        """Get daily bias monitoring report template."""
        return {
            "report_metadata": {
                "report_id": "<uuid>",
                "report_type": "daily_bias_monitoring",
                "timestamp": "<UTC ISO>",
                "generated_by": "BiasDetectionScheduler",
            },
            "evaluation_context": {
                "target_model": "<model_name>",
                "model_version": "<version>",
                "dataset_version": "<dataset_hash>",
                "protected_attributes": ["gender", "ethnicity", "age_group"],
            },
            "bias_results": {
                "dataset_bias": {
                    "analysis_type": "representation",
                    "per_attribute": "<results>",
                },
                "output_bias": {
                    "analysis_type": "prediction_distribution",
                    "per_attribute": "<results>",
                },
            },
            "fairness_metrics": {
                "demographic_parity": "<result>",
                "equal_opportunity": "<result>",
                "equalized_odds": "<result>",
                "disparate_impact": "<result>",
            },
            "risk_assessment": {
                "risk_level": "low|medium|high|critical",
                "severity_score": "<0-100>",
                "affected_groups": ["<groups>"],
            },
            "recommendations": [
                "<actionable recommendation 1>",
                "<actionable recommendation 2>",
            ],
            "required_actions": [
                {"action": "<action>", "owner": "<team>", "deadline": "<date>"},
            ],
            "audit_history": {
                "previous_reports": "<count>",
                "trend": "improving|stable|degrading",
                "last_7_days": "<summary>",
            },
        }


# Module-level singleton
_bias_scheduler: BiasDetectionScheduler | None = None


def get_bias_scheduler() -> BiasDetectionScheduler:
    """Get the singleton BiasDetectionScheduler instance."""
    global _bias_scheduler
    if _bias_scheduler is None:
        _bias_scheduler = BiasDetectionScheduler()
    return _bias_scheduler


# ═══════════════════════════════════════════════════════════════════════
# 3. Continuous Responsible AI Monitor
# ═══════════════════════════════════════════════════════════════════════
class ContinuousResponsibleAIMonitor:
    """Continuous Responsible AI monitoring for production.

    Monitors:
      - Hallucination rate (continuous)
      - Bias trends (daily)
      - Fairness scores (daily)
      - Safety violations (real-time)
      - User satisfaction (weekly)
      - Cost tracking (continuous)
    """

    def __init__(self):
        self._metrics_history: list[dict[str, Any]] = []
        self._alerts: list[dict[str, Any]] = []
        self._thresholds = {
            "hallucination_rate": 0.05,
            "bias_severity": "medium",
            "fairness_fail_rate": 0.1,
            "safety_violation_count": 0,
            "csat_min": 4.5,
            "cost_per_query_max": 0.05,
        }

    def record_metric(self, metric_name: str, value: Any, *, target: str = "global") -> dict[str, Any]:
        """Record a Responsible AI metric."""
        entry = {
            "metric_id": str(uuid.uuid4()),
            "metric_name": metric_name,
            "value": value,
            "target": target,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._metrics_history.append(entry)

        # Check threshold
        if metric_name in self._thresholds:
            threshold = self._thresholds[metric_name]
            violated = False
            if isinstance(threshold, (int, float)) and isinstance(value, (int, float)):
                violated = value > threshold
            elif isinstance(threshold, str):
                severity_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
                violated = severity_order.get(value, 0) > severity_order.get(threshold, 0)

            if violated:
                alert = {
                    "alert_id": str(uuid.uuid4()),
                    "metric_name": metric_name,
                    "value": value,
                    "threshold": threshold,
                    "target": target,
                    "severity": "warning",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "message": f"Metric '{metric_name}' exceeded threshold: {value} > {threshold}",
                }
                self._alerts.append(alert)

        return entry

    def get_metrics_summary(self) -> dict[str, Any]:
        """Get summary of all recorded metrics."""
        by_name = defaultdict(list)
        for m in self._metrics_history:
            by_name[m["metric_name"]].append(m["value"])

        summary = {}
        for name, values in by_name.items():
            if all(isinstance(v, (int, float)) for v in values):
                summary[name] = {
                    "count": len(values),
                    "latest": values[-1],
                    "average": sum(values) / len(values),
                    "min": min(values),
                    "max": max(values),
                }
            else:
                summary[name] = {
                    "count": len(values),
                    "latest": values[-1],
                }

        return {
            "total_metrics": len(self._metrics_history),
            "total_alerts": len(self._alerts),
            "by_metric": summary,
            "thresholds": self._thresholds,
        }

    def get_alerts(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent alerts."""
        return self._alerts[-limit:]

    def get_thresholds(self) -> dict[str, Any]:
        """Get current thresholds."""
        return dict(self._thresholds)

    def update_threshold(self, metric_name: str, value: Any) -> None:
        """Update a monitoring threshold."""
        self._thresholds[metric_name] = value


# Module-level singleton
_responsible_ai_monitor: ContinuousResponsibleAIMonitor | None = None


def get_responsible_ai_monitor() -> ContinuousResponsibleAIMonitor:
    """Get the singleton ContinuousResponsibleAIMonitor instance."""
    global _responsible_ai_monitor
    if _responsible_ai_monitor is None:
        _responsible_ai_monitor = ContinuousResponsibleAIMonitor()
    return _responsible_ai_monitor
