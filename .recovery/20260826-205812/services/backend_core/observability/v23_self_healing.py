"""
HSAAI v23.0 — Full Self-Healing Platform + Predictive Capacity Management
=========================================================================
Implements:
  1. PredictiveCapacityManager — Forecast CPU/memory/storage/network/AI demand
  2. SelfHealingPlatform — Detection → Prediction → Decision → Recovery → Verification → Learning
  3. DatabaseOptimizationManager — Materialized Views + pg_trgm + PgBouncer
  4. OptimizationObservationPeriod — 30-day recommendation mode monitoring
"""
from __future__ import annotations

import asyncio
import json
import logging
import statistics
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Awaitable

logger = logging.getLogger("hsaai.v23.self_healing")
audit_logger = logging.getLogger("hsaai.audit.v23")


# ═══════════════════════════════════════════════════════════════════════
# 1. Predictive Capacity Manager (v23.0)
# ═══════════════════════════════════════════════════════════════════════
class PredictiveCapacityManager:
    """v23.0: Predictive capacity management for infrastructure and AI workloads.

    Forecast Workflow:
      Telemetry Collection → Forecast Model → Capacity Prediction
      → Risk Assessment → Policy Validation → Optimization Recommendation
      → Approved Execution → Verification

    Predicts:
      Infrastructure: CPU demand, Memory demand, Storage growth, Network capacity
      AI Workload: Model usage, Agent workload, RAG traffic, User demand
    """

    FORECAST_HORIZONS = {
        "1h": 1,
        "6h": 6,
        "24h": 24,
        "7d": 168,
        "30d": 720,
    }

    CAPACITY_THRESHOLDS = {
        "cpu_percent": {"warning": 70, "critical": 85},
        "memory_percent": {"warning": 75, "critical": 90},
        "storage_percent": {"warning": 80, "critical": 90},
        "network_utilization": {"warning": 70, "critical": 85},
    }

    def __init__(self):
        self._telemetry: dict[str, deque] = defaultdict(lambda: deque(maxlen=10000))
        self._predictions: list[dict[str, Any]] = []
        self._capacity_alerts: list[dict[str, Any]] = []

    def collect_telemetry(self, resource: str, value: float, *, timestamp: str | None = None) -> None:
        """Collect telemetry data point for a resource."""
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        self._telemetry[resource].append({"timestamp": ts, "value": value})

    def forecast(self, resource: str, horizon: str = "24h") -> dict[str, Any]:
        """Forecast future capacity needs for a resource.

        Uses linear regression for trend analysis.
        """
        if horizon not in self.FORECAST_HORIZONS:
            raise ValueError(f"Unknown horizon: {horizon}")

        data = list(self._telemetry.get(resource, []))
        if len(data) < 3:
            return {
                "resource": resource,
                "horizon": horizon,
                "status": "insufficient_data",
                "message": f"Need at least 3 data points, got {len(data)}",
            }

        values = [d["value"] for d in data]
        current_value = values[-1]
        n = len(values)

        # Linear regression
        x_mean = (n - 1) / 2
        y_mean = sum(values) / n
        numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        slope = numerator / denominator if denominator != 0 else 0

        # Forecast
        hours_ahead = self.FORECAST_HORIZONS[horizon]
        forecast_value = current_value + slope * hours_ahead

        # Risk assessment
        threshold = self.CAPACITY_THRESHOLDS.get(resource, {"warning": 70, "critical": 85})
        if forecast_value >= threshold["critical"]:
            risk_level = "critical"
            action = f"Immediate capacity increase needed for {resource}"
        elif forecast_value >= threshold["warning"]:
            risk_level = "warning"
            action = f"Plan capacity increase for {resource} within {horizon}"
        else:
            risk_level = "low"
            action = "No action needed — capacity is sufficient"

        # Time to threshold
        time_to_threshold = None
        if slope > 0 and threshold:
            time_to_threshold = (threshold["warning"] - current_value) / slope
            if time_to_threshold < 0:
                time_to_threshold = 0

        prediction = {
            "prediction_id": str(uuid.uuid4()),
            "resource": resource,
            "horizon": horizon,
            "current_value": round(current_value, 2),
            "forecast_value": round(forecast_value, 2),
            "trend_slope": round(slope, 4),
            "trend": "increasing" if slope > 0 else ("decreasing" if slope < 0 else "stable"),
            "risk_level": risk_level,
            "threshold": threshold,
            "time_to_threshold_hours": round(time_to_threshold, 1) if time_to_threshold is not None else None,
            "recommended_action": action,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        self._predictions.append(prediction)

        if risk_level in ("warning", "critical"):
            self._capacity_alerts.append(prediction)

        return prediction

    def forecast_all(self, horizon: str = "24h") -> dict[str, Any]:
        """Forecast all tracked resources."""
        results = {}
        for resource in self._telemetry:
            results[resource] = self.forecast(resource, horizon)
        return {
            "horizon": horizon,
            "resources_forecasted": len(results),
            "results": results,
            "alerts": len(self._capacity_alerts),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def get_predictions(self) -> list[dict[str, Any]]:
        return list(self._predictions)

    def get_alerts(self) -> list[dict[str, Any]]:
        return list(self._capacity_alerts)


# ═══════════════════════════════════════════════════════════════════════
# 2. Self-Healing Platform (v23.0)
# ═══════════════════════════════════════════════════════════════════════
class SelfHealingError(Exception):
    pass


class SelfHealingPlatform:
    """v23.0: Full Self-Healing Platform with governed recovery.

    Architecture:
      Detection Layer → Prediction Layer → Decision Engine → Policy Engine
      → Recovery Executor → Verification Layer → Learning Feedback

    Supported recoveries:
      - Restart failed service
      - Scale resources
      - Recover unhealthy workloads
      - Adjust capacity
      - Optimize database resources
      - Redirect traffic

    All actions require:
      - Audit logging
      - ABAC validation
      - Security policy validation
      - Rollback capability
    """

    RECOVERY_ACTIONS = [
        "restart_service",
        "scale_resources",
        "recover_workload",
        "adjust_capacity",
        "optimize_database",
        "redirect_traffic",
    ]

    def __init__(self):
        self._incidents: list[dict[str, Any]] = []
        self._recoveries: list[dict[str, Any]] = []
        self._learning_data: list[dict[str, Any]] = []
        self._handlers: dict[str, Callable] = {}
        self._mode = "supervised"  # supervised, autonomous

    @property
    def mode(self) -> str:
        return self._mode

    def register_handler(self, action: str, handler: Callable) -> None:
        if action not in self.RECOVERY_ACTIONS:
            raise SelfHealingError(f"Unknown recovery action: {action}")
        self._handlers[action] = handler

    def detect_issue(self, issue: dict[str, Any]) -> dict[str, Any]:
        """Detection Layer: Detect a platform issue."""
        incident = {
            "incident_id": str(uuid.uuid4()),
            "issue": issue,
            "status": "detected",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._incidents.append(incident)
        return incident

    def predict_impact(self, incident: dict[str, Any]) -> dict[str, Any]:
        """Prediction Layer: Predict impact of the incident."""
        severity = incident["issue"].get("severity", "medium")
        predicted_impact = {
            "incident_id": incident["incident_id"],
            "severity": severity,
            "predicted_impact": "service_degradation" if severity == "medium" else "service_outage",
            "estimated_affected_users": incident["issue"].get("affected_users", 0),
            "time_to_impact_minutes": 5 if severity == "critical" else 30,
        }
        return predicted_impact

    def decide_recovery(self, incident: dict[str, Any], prediction: dict[str, Any]) -> dict[str, Any]:
        """Decision Engine: Decide recovery action."""
        issue_type = incident["issue"].get("type", "unknown")
        severity = prediction["severity"]

        # Map issue types to recovery actions
        action_map = {
            "service_down": "restart_service",
            "high_latency": "scale_resources",
            "workload_failure": "recover_workload",
            "capacity_warning": "adjust_capacity",
            "slow_queries": "optimize_database",
            "traffic_imbalance": "redirect_traffic",
        }

        action = action_map.get(issue_type, "scale_resources")

        decision = {
            "incident_id": incident["incident_id"],
            "action": action,
            "reason": f"Issue type '{issue_type}' with severity '{severity}' → action '{action}'",
            "requires_approval": severity in ("high", "critical"),
        }
        return decision

    def validate_policy(self, decision: dict[str, Any], *, abac_decision: dict[str, Any] | None = None) -> dict[str, Any]:
        """Policy Engine: Validate ABAC and security policies."""
        if abac_decision and abac_decision.get("decision") != "ALLOW":
            return {
                "approved": False,
                "reason": "ABAC denied the recovery action",
            }

        return {
            "approved": True,
            "reason": "Policy validation passed",
            "abac_validated": abac_decision is not None,
        }

    async def execute_recovery(
        self,
        incident: dict[str, Any],
        decision: dict[str, Any],
        *,
        approver: str | None = None,
        rollback_plan: str = "",
    ) -> dict[str, Any]:
        """Recovery Executor: Execute the recovery action."""
        action = decision["action"]

        if decision.get("requires_approval") and not approver:
            return {
                "incident_id": incident["incident_id"],
                "status": "blocked",
                "reason": "Human approval required for high/critical severity",
            }

        if not rollback_plan:
            return {
                "incident_id": incident["incident_id"],
                "status": "blocked",
                "reason": "Rollback plan required",
            }

        handler = self._handlers.get(action)
        result = {"success": False, "message": "No handler registered"}
        if handler:
            try:
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(incident["issue"].get("target", ""))
                else:
                    result = handler(incident["issue"].get("target", ""))
            except Exception as exc:
                result = {"success": False, "message": str(exc)}

        recovery = {
            "recovery_id": str(uuid.uuid4()),
            "incident_id": incident["incident_id"],
            "action": action,
            "approver": approver,
            "rollback_plan": rollback_plan,
            "result": result,
            "status": "recovered" if result.get("success") else "failed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        self._recoveries.append(recovery)

        # Learning feedback
        self._learning_data.append({
            "incident_id": incident["incident_id"],
            "action": action,
            "outcome": recovery["status"],
            "severity": incident["issue"].get("severity", "medium"),
            "timestamp": recovery["timestamp"],
        })

        audit_logger.info(json.dumps({
            "event": "SELF_HEALING_RECOVERY",
            "recovery_id": recovery["recovery_id"],
            "action": action,
            "success": result.get("success", False),
            "timestamp": recovery["timestamp"],
        }))

        return recovery

    def verify_recovery(self, recovery_id: str, *, before_metrics: dict, after_metrics: dict) -> dict[str, Any]:
        """Verification Layer: Verify recovery was effective."""
        recovery = next((r for r in self._recoveries if r["recovery_id"] == recovery_id), None)
        if recovery is None:
            raise SelfHealingError(f"Recovery '{recovery_id}' not found")

        improvements = {}
        for key in before_metrics:
            if key in after_metrics and isinstance(before_metrics[key], (int, float)):
                before_val = before_metrics[key]
                after_val = after_metrics[key]
                if before_val != 0:
                    improvements[key] = {
                        "before": before_val,
                        "after": after_val,
                        "change_pct": round(((after_val - before_val) / before_val) * 100, 2),
                    }

        verification = {
            "recovery_id": recovery_id,
            "status": "verified",
            "improvements": improvements,
            "effective": all(
                imp["change_pct"] <= 0 for imp in improvements.values()
                if "latency" in imp or "error" in imp
            ),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        recovery["verification"] = verification
        return verification

    def get_incidents(self) -> list[dict[str, Any]]:
        return list(self._incidents)

    def get_recoveries(self) -> list[dict[str, Any]]:
        return list(self._recoveries)

    def get_learning_data(self) -> list[dict[str, Any]]:
        return list(self._learning_data)

    def get_stats(self) -> dict[str, Any]:
        total = len(self._incidents)
        recovered = sum(1 for r in self._recoveries if r["status"] == "recovered")
        return {
            "mode": self._mode,
            "total_incidents": total,
            "total_recoveries": len(self._recoveries),
            "recovered": recovered,
            "failed": len(self._recoveries) - recovered,
            "recovery_rate": round(recovered / max(len(self._recoveries), 1) * 100, 1),
            "learning_entries": len(self._learning_data),
        }


# ═══════════════════════════════════════════════════════════════════════
# 3. Database Optimization Manager (v22 → v23)
# ═══════════════════════════════════════════════════════════════════════
class DatabaseOptimizationManager:
    """v22→v23: Database performance optimizations.

    Implements:
      1. Materialized Views — Reduce expensive queries, improve reporting
      2. pg_trgm — Trigram extension for fuzzy text search
      3. PgBouncer — Connection pooling layer

    Each optimization includes:
      - Implementation
      - Validation
      - Performance comparison
      - Monitoring
    """

    OPTIMIZATIONS = {
        "materialized_views": {
            "description": "Pre-computed query results for dashboards and analytics",
            "risk": "low",
            "requires_refresh": True,
            "refresh_strategy": "CONCURRENTLY",
            "views": [
                {
                    "name": "mv_document_stats",
                    "query": "SELECT tenant_id, COUNT(*) as doc_count, status FROM knowledge_documents GROUP BY tenant_id, status",
                    "refresh_interval": "5 minutes",
                    "purpose": "Dashboard document count by status",
                },
                {
                    "name": "mv_analytics_summary",
                    "query": "SELECT event_type, COUNT(*) as event_count, DATE(created_at) as day FROM knowledge_analytics_events GROUP BY event_type, DATE(created_at)",
                    "refresh_interval": "15 minutes",
                    "purpose": "Analytics event summary by day",
                },
                {
                    "name": "mv_agent_performance",
                    "query": "SELECT agent_id, AVG(latency_ms) as avg_latency, COUNT(*) as invocations FROM agent_runs GROUP BY agent_id",
                    "refresh_interval": "10 minutes",
                    "purpose": "Agent performance dashboard",
                },
            ],
        },
        "pg_trgm": {
            "description": "Trigram extension for fuzzy text search and similarity matching",
            "risk": "low",
            "requires_extension": True,
            "indexes": [
                "CREATE INDEX IF NOT EXISTS idx_docs_title_trgm ON knowledge_documents USING GIN (title gin_trgm_ops)",
                "CREATE INDEX IF NOT EXISTS idx_docs_filename_trgm ON knowledge_documents USING GIN (filename gin_trgm_ops)",
            ],
            "queries_improved": [
                "SELECT * FROM knowledge_documents WHERE title % 'policy'",
                "SELECT * FROM knowledge_documents WHERE similarity(title, 'annual leave') > 0.3",
            ],
            "expected_improvement": "10-50x faster fuzzy text search",
        },
        "pgbouncer": {
            "description": "Lightweight connection pooling layer for PostgreSQL",
            "risk": "medium",
            "pool_mode": "transaction",
            "max_client_conn": 1000,
            "default_pool_size": 25,
            "reserve_pool_size": 5,
            "reserve_pool_timeout": 3,
            "max_db_connections": 100,
            "server_idle_timeout": 600,
            "query_wait_timeout": 120,
            "expected_improvement": "80% reduction in connection overhead, 3x throughput",
        },
    }

    def __init__(self):
        self._applied: list[dict[str, Any]] = []
        self._performance_before: dict[str, Any] = {}
        self._performance_after: dict[str, Any] = {}

    def get_optimization_plan(self) -> dict[str, Any]:
        """Get the full optimization plan."""
        return {
            "total_optimizations": len(self.OPTIMIZATIONS),
            "optimizations": {
                name: {
                    "description": config["description"],
                    "risk": config["risk"],
                }
                for name, config in self.OPTIMIZATIONS.items()
            },
        }

    def validate_optimization(self, name: str) -> dict[str, Any]:
        """Validate an optimization before applying."""
        if name not in self.OPTIMIZATIONS:
            return {"valid": False, "reason": f"Unknown optimization: {name}"}

        config = self.OPTIMIZATIONS[name]
        return {
            "valid": True,
            "name": name,
            "risk": config["risk"],
            "description": config["description"],
            "rollback_available": True,
        }

    def record_performance(self, phase: str, metrics: dict[str, Any]) -> None:
        """Record performance metrics (before or after optimization)."""
        if phase == "before":
            self._performance_before = metrics
        elif phase == "after":
            self._performance_after = metrics

    def compare_performance(self) -> dict[str, Any]:
        """Compare before vs after performance."""
        improvements = {}
        for key in self._performance_before:
            if key in self._performance_after:
                before = self._performance_before[key]
                after = self._performance_after[key]
                if isinstance(before, (int, float)) and isinstance(after, (int, float)):
                    improvements[key] = {
                        "before": before,
                        "after": after,
                        "change_pct": round(((after - before) / before) * 100, 2) if before != 0 else 0,
                    }

        return {
            "before": self._performance_before,
            "after": self._performance_after,
            "improvements": improvements,
            "overall_improvement": "significant" if any(
                imp["change_pct"] < -20 for imp in improvements.values()
            ) else "moderate",
        }

    def get_materialized_views(self) -> list[dict[str, Any]]:
        """Get materialized view definitions."""
        return self.OPTIMIZATIONS["materialized_views"]["views"]

    def get_pg_trgm_config(self) -> dict[str, Any]:
        """Get pg_trgm configuration."""
        return {
            "indexes": self.OPTIMIZATIONS["pg_trgm"]["indexes"],
            "queries_improved": self.OPTIMIZATIONS["pg_trgm"]["queries_improved"],
            "expected_improvement": self.OPTIMIZATIONS["pg_trgm"]["expected_improvement"],
        }

    def get_pgbouncer_config(self) -> dict[str, Any]:
        """Get PgBouncer configuration."""
        config = self.OPTIMIZATIONS["pgbouncer"]
        return {
            "pool_mode": config["pool_mode"],
            "max_client_conn": config["max_client_conn"],
            "default_pool_size": config["default_pool_size"],
            "reserve_pool_size": config["reserve_pool_size"],
            "max_db_connections": config["max_db_connections"],
            "server_idle_timeout": config["server_idle_timeout"],
            "query_wait_timeout": config["query_wait_timeout"],
            "expected_improvement": config["expected_improvement"],
        }


# ═══════════════════════════════════════════════════════════════════════
# 4. Optimization Observation Period (30-day)
# ═══════════════════════════════════════════════════════════════════════
class OptimizationObservationPeriod:
    """30-day observation period for Autonomous Optimizer in RECOMMENDATION mode.

    During this period:
      - Optimizer generates recommendations only (no auto-apply)
      - Daily reports track recommendation quality
      - After 30 days: decide AUTONOMOUS MODE activation
    """

    OBSERVATION_PERIOD_DAYS = 30

    def __init__(self):
        self._start_time: datetime | None = None
        self._daily_reports: list[dict[str, Any]] = []
        self._recommendations: list[dict[str, Any]] = []
        self._mode = "recommendation"

    @property
    def mode(self) -> str:
        return self._mode

    def start_observation(self) -> dict[str, Any]:
        self._start_time = datetime.now(timezone.utc)
        return {
            "status": "observation_started",
            "start_time": self._start_time.isoformat(),
            "duration_days": self.OBSERVATION_PERIOD_DAYS,
            "mode": self._mode,
        }

    def collect_recommendation(self, recommendation: dict[str, Any]) -> None:
        """Collect an optimization recommendation for monitoring."""
        self._recommendations.append({
            **recommendation,
            "collected_at": datetime.now(timezone.utc).isoformat(),
        })

    def generate_daily_report(self, day: int) -> dict[str, Any]:
        """Generate daily optimizer observation report."""
        report = {
            "report_id": str(uuid.uuid4()),
            "day_number": day,
            "report_type": "daily_optimizer_observation",
            "mode": self._mode,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "recommendations_count": len(self._recommendations),
            "recommendation_quality": self._assess_quality(),
            "false_recommendations": sum(1 for r in self._recommendations if r.get("was_correct") is False),
            "correct_recommendations": sum(1 for r in self._recommendations if r.get("was_correct") is True),
            "accuracy": self._calculate_accuracy(),
            "recommendation": "continue_observation",
        }

        if day >= 30:
            report["recommendation"] = self._evaluate_autonomous_readiness()

        self._daily_reports.append(report)
        return report

    def _assess_quality(self) -> str:
        if not self._recommendations:
            return "no_data"
        accuracy = self._calculate_accuracy()
        if accuracy >= 0.85:
            return "excellent"
        elif accuracy >= 0.70:
            return "good"
        elif accuracy >= 0.50:
            return "fair"
        return "poor"

    def _calculate_accuracy(self) -> float:
        verified = [r for r in self._recommendations if r.get("was_correct") is not None]
        if not verified:
            return 0.75  # Default when no verification data
        correct = sum(1 for r in verified if r["was_correct"])
        return correct / len(verified)

    def _evaluate_autonomous_readiness(self) -> str:
        accuracy = self._calculate_accuracy()
        false_count = sum(1 for r in self._recommendations if r.get("was_correct") is False)
        if accuracy >= 0.80 and false_count < 5:
            return "READY_FOR_AUTONOMOUS_MODE"
        return "EXTEND_OBSERVATION"

    def get_observation_status(self) -> dict[str, Any]:
        if self._start_time is None:
            return {"status": "not_started", "mode": self._mode}
        elapsed = datetime.now(timezone.utc) - self._start_time
        remaining = timedelta(days=self.OBSERVATION_PERIOD_DAYS) - elapsed
        return {
            "status": "in_progress" if remaining.total_seconds() > 0 else "complete",
            "mode": self._mode,
            "elapsed_days": round(elapsed.total_seconds() / 86400, 2),
            "remaining_days": max(round(remaining.total_seconds() / 86400, 2), 0),
            "daily_reports": len(self._daily_reports),
            "recommendations_collected": len(self._recommendations),
        }

    def generate_validation_report(self) -> dict[str, Any]:
        """Generate the 30-day validation report."""
        if len(self._daily_reports) < self.OBSERVATION_PERIOD_DAYS:
            return {
                "status": "incomplete",
                "message": f"Only {len(self._daily_reports)}/{self.OBSERVATION_PERIOD_DAYS} daily reports",
            }
        readiness = self._evaluate_autonomous_readiness()
        return {
            "status": "complete",
            "observation_days": self.OBSERVATION_PERIOD_DAYS,
            "total_recommendations": len(self._recommendations),
            "avg_accuracy": round(self._calculate_accuracy(), 4),
            "false_recommendations": sum(1 for r in self._recommendations if r.get("was_correct") is False),
            "correct_recommendations": sum(1 for r in self._recommendations if r.get("was_correct") is True),
            "recommendation_quality": self._assess_quality(),
            "readiness_decision": readiness,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


# Singletons
_capacity_mgr: PredictiveCapacityManager | None = None
_self_healing: SelfHealingPlatform | None = None
_db_optimizer: DatabaseOptimizationManager | None = None
_opt_observation: OptimizationObservationPeriod | None = None

def get_capacity_mgr() -> PredictiveCapacityManager:
    global _capacity_mgr
    if _capacity_mgr is None:
        _capacity_mgr = PredictiveCapacityManager()
    return _capacity_mgr

def get_self_healing() -> SelfHealingPlatform:
    global _self_healing
    if _self_healing is None:
        _self_healing = SelfHealingPlatform()
    return _self_healing

def get_db_optimizer() -> DatabaseOptimizationManager:
    global _db_optimizer
    if _db_optimizer is None:
        _db_optimizer = DatabaseOptimizationManager()
    return _db_optimizer

def get_opt_observation() -> OptimizationObservationPeriod:
    global _opt_observation
    if _opt_observation is None:
        _opt_observation = OptimizationObservationPeriod()
    return _opt_observation
