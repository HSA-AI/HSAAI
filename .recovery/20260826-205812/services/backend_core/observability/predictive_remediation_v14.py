"""
HSAAI v14 — Predictive Analytics & Auto-Remediation Engine
============================================================
Implements:
  1. PredictiveAnalyticsEngine — Capacity prediction, failure prediction, AI performance prediction
  2. AnomalyDetector — Real-time anomaly detection with scoring
  3. AutoRemediationEngine — Automated remediation with safety controls
  4. IntelligentAlertManager — AI-powered alert routing and escalation
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

logger = logging.getLogger("hsaai.v14.observability")
audit_logger = logging.getLogger("hsaai.audit.remediation")


# ═══════════════════════════════════════════════════════════════════════
# 1. Predictive Analytics Engine
# ═══════════════════════════════════════════════════════════════════════
class PredictiveAnalyticsEngine:
    """Predictive analytics for capacity, failure, and AI performance."""

    def __init__(self):
        self._metrics_history: dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self._predictions: list[dict[str, Any]] = []

    def record_metric(self, metric_name: str, value: float, *, timestamp: str | None = None) -> None:
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        self._metrics_history[metric_name].append({"timestamp": ts, "value": value})

    def predict_capacity(self, metric_name: str, *, threshold: float, forecast_hours: int = 24) -> dict[str, Any]:
        history = list(self._metrics_history.get(metric_name, []))
        if len(history) < 3:
            return {"metric_name": metric_name, "prediction_type": "capacity", "status": "insufficient_data", "message": f"Need at least 3 data points, got {len(history)}"}
        values = [h["value"] for h in history]
        current_value = values[-1]
        n = len(values)
        x_mean = (n - 1) / 2
        y_mean = sum(values) / n
        numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        slope = numerator / denominator if denominator != 0 else 0
        if slope <= 0:
            return {"metric_name": metric_name, "prediction_type": "capacity", "current_value": current_value, "threshold": threshold, "trend": "decreasing", "status": "safe", "estimated_time_to_threshold": None, "message": "Metric is decreasing or stable"}
        remaining = threshold - current_value
        if remaining <= 0:
            return {"metric_name": metric_name, "prediction_type": "capacity", "current_value": current_value, "threshold": threshold, "trend": "exceeded", "status": "critical", "estimated_time_to_threshold": "already_exceeded", "message": "Threshold already exceeded!"}
        hours_to_threshold = remaining / slope if slope > 0 else float('inf')
        if hours_to_threshold <= forecast_hours:
            status = "warning"
        elif hours_to_threshold <= forecast_hours * 2:
            status = "caution"
        else:
            status = "safe"
        prediction = {"metric_name": metric_name, "prediction_type": "capacity", "current_value": round(current_value, 2), "threshold": threshold, "trend_slope": round(slope, 4), "trend": "increasing", "estimated_time_to_threshold_hours": round(hours_to_threshold, 1), "forecast_hours": forecast_hours, "status": status, "prediction_id": str(uuid.uuid4()), "timestamp": datetime.now(timezone.utc).isoformat()}
        self._predictions.append(prediction)
        return prediction

    def predict_failure(self, service_name: str, error_rate: float, latency_p95: float, *, error_threshold: float = 0.05, latency_threshold: float = 2000.0) -> dict[str, Any]:
        risk_score = 0
        risk_factors = []
        if error_rate > error_threshold:
            risk_score += 40
            risk_factors.append(f"Error rate {error_rate:.2%} exceeds threshold {error_threshold:.2%}")
        if latency_p95 > latency_threshold:
            risk_score += 30
            risk_factors.append(f"Latency P95 {latency_p95}ms exceeds threshold {latency_threshold}ms")
        if error_rate > error_threshold * 2:
            risk_score += 20
            risk_factors.append("Error rate is 2x above threshold")
        if latency_p95 > latency_threshold * 2:
            risk_score += 10
            risk_factors.append("Latency is 2x above threshold")
        if risk_score >= 70:
            risk_level = "critical"
        elif risk_score >= 40:
            risk_level = "high"
        elif risk_score >= 20:
            risk_level = "medium"
        else:
            risk_level = "low"
        recs = {"critical": "Immediate intervention required", "high": "Review service health", "medium": "Monitor closely", "low": "Service is healthy"}
        prediction = {"prediction_id": str(uuid.uuid4()), "service_name": service_name, "prediction_type": "failure", "error_rate": error_rate, "latency_p95": latency_p95, "risk_score": risk_score, "risk_level": risk_level, "risk_factors": risk_factors, "recommendation": recs.get(risk_level, "Monitor"), "timestamp": datetime.now(timezone.utc).isoformat()}
        self._predictions.append(prediction)
        return prediction

    def predict_ai_performance(self, model_name: str, latency_history: list[float], error_history: list[float]) -> dict[str, Any]:
        if len(latency_history) < 3:
            return {"model_name": model_name, "status": "insufficient_data"}
        latency_trend = self._calc_trend(latency_history)
        error_trend = self._calc_trend(error_history) if error_history else 0
        degradation_score = 0
        if latency_trend > 0.1:
            degradation_score += 30
        if error_trend > 0.05:
            degradation_score += 40
        if latency_history[-1] > statistics.mean(latency_history) * 1.5:
            degradation_score += 20
        if degradation_score >= 50:
            status = "degrading"
        elif degradation_score >= 25:
            status = "warning"
        else:
            status = "stable"
        prediction = {"prediction_id": str(uuid.uuid4()), "model_name": model_name, "prediction_type": "ai_performance", "latency_trend": round(latency_trend, 4), "error_trend": round(error_trend, 4), "degradation_score": degradation_score, "status": status, "current_latency": latency_history[-1], "avg_latency": round(statistics.mean(latency_history), 2), "timestamp": datetime.now(timezone.utc).isoformat()}
        self._predictions.append(prediction)
        return prediction

    def _calc_trend(self, values: list[float]) -> float:
        n = len(values)
        if n < 2:
            return 0
        x_mean = (n - 1) / 2
        y_mean = sum(values) / n
        numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        return numerator / denominator if denominator != 0 else 0

    def get_all_predictions(self) -> list[dict[str, Any]]:
        return list(self._predictions)


# ═══════════════════════════════════════════════════════════════════════
# 2. Anomaly Detector
# ═══════════════════════════════════════════════════════════════════════
class AnomalyDetector:
    """Real-time anomaly detection using z-score."""

    def __init__(self, window_size: int = 100, z_threshold: float = 3.0):
        self._windows: dict[str, deque] = defaultdict(lambda: deque(maxlen=window_size))
        self.window_size = window_size
        self.z_threshold = z_threshold
        self._anomalies: list[dict[str, Any]] = []

    def observe(self, metric_name: str, value: float) -> dict[str, Any] | None:
        window = self._windows[metric_name]
        window.append(value)
        if len(window) < 10:
            return None
        mean = statistics.mean(window)
        stdev = statistics.stdev(window) if len(window) > 1 else 0
        if stdev == 0:
            return None
        z_score = (value - mean) / stdev
        if abs(z_score) > self.z_threshold:
            anomaly = {"anomaly_id": str(uuid.uuid4()), "metric_name": metric_name, "value": value, "expected_mean": round(mean, 4), "std_dev": round(stdev, 4), "z_score": round(z_score, 2), "direction": "above" if z_score > 0 else "below", "severity": "critical" if abs(z_score) > 5 else "high" if abs(z_score) > 4 else "medium", "timestamp": datetime.now(timezone.utc).isoformat(), "recommended_action": self._rec_action(metric_name, z_score)}
            self._anomalies.append(anomaly)
            return anomaly
        return None

    def _rec_action(self, metric_name: str, z_score: float) -> str:
        if "error" in metric_name.lower():
            return "Investigate error source"
        elif "latency" in metric_name.lower():
            return "Check resource utilization"
        elif "security" in metric_name.lower():
            return "Security anomaly — investigate immediately"
        return f"Anomaly detected (z={z_score:.2f}) — investigate"

    def get_anomalies(self, limit: int = 20) -> list[dict[str, Any]]:
        return self._anomalies[-limit:]

    def get_anomaly_score(self, metric_name: str) -> float:
        window = self._windows.get(metric_name, deque())
        if len(window) < 10:
            return 0.0
        values = list(window)
        mean = statistics.mean(values)
        stdev = statistics.stdev(values) if len(values) > 1 else 0
        if stdev == 0:
            return 0.0
        z = abs((values[-1] - mean) / stdev)
        return min(z / 5.0, 1.0)


# ═══════════════════════════════════════════════════════════════════════
# 3. Auto-Remediation Engine
# ═══════════════════════════════════════════════════════════════════════
class AutoRemediationError(Exception):
    pass


class AutoRemediationEngine:
    """Automated remediation with safety controls."""

    RISK_LOW = "low"
    RISK_MEDIUM = "medium"
    RISK_HIGH = "high"
    RISK_CRITICAL = "critical"

    ACTION_RISK = {
        "restart_service": RISK_MEDIUM,
        "scale_resources": RISK_LOW,
        "clear_workloads": RISK_MEDIUM,
        "restart_component": RISK_MEDIUM,
        "disable_workflow": RISK_MEDIUM,
        "route_traffic": RISK_HIGH,
        "disable_agent": RISK_HIGH,
        "trigger_evaluation": RISK_LOW,
        "rollback_config": RISK_CRITICAL,
    }

    MAX_REMEDIATIONS_PER_HOUR = 5
    LOOP_PREVENTION_WINDOW = 300

    def __init__(self):
        self._remediation_history: list[dict[str, Any]] = []
        self._recent_remediations: list[float] = []
        self._executed_actions: dict[str, float] = {}
        self._action_handlers: dict[str, Callable] = {}

    def register_handler(self, action: str, handler: Callable) -> None:
        self._action_handlers[action] = handler

    async def execute_remediation(self, detection: dict[str, Any], action: str, *, target: str, require_approval: bool = False, approver: str | None = None) -> dict[str, Any]:
        if action not in self.ACTION_RISK:
            raise AutoRemediationError(f"Unknown action: {action}")
        risk_level = self.ACTION_RISK[action]
        if risk_level == self.RISK_CRITICAL and not approver:
            raise AutoRemediationError(f"Critical action '{action}' requires human approval")
        if require_approval and not approver:
            raise AutoRemediationError(f"Action '{action}' requires approval")
        now = time.time()
        recent = [t for t in self._recent_remediations if now - t < 3600]
        if len(recent) >= self.MAX_REMEDIATIONS_PER_HOUR:
            raise AutoRemediationError(f"Rate limit exceeded: {self.MAX_REMEDIATIONS_PER_HOUR}/hour")
        action_key = f"{action}:{target}"
        last = self._executed_actions.get(action_key, 0)
        if now - last < self.LOOP_PREVENTION_WINDOW:
            raise AutoRemediationError(f"Loop prevention: action recently executed")
        remediation_id = str(uuid.uuid4())
        audit_logger.info(json.dumps({"event": "AUTO_REMEDIATION_STARTED", "remediation_id": remediation_id, "action": action, "target": target, "risk_level": risk_level}))
        result = {"success": False, "message": "No handler registered"}
        handler = self._action_handlers.get(action)
        if handler:
            try:
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(target)
                else:
                    result = handler(target)
            except Exception as exc:
                result = {"success": False, "message": str(exc)}
        self._recent_remediations.append(now)
        self._executed_actions[action_key] = now
        entry = {"remediation_id": remediation_id, "action": action, "target": target, "risk_level": risk_level, "result": result, "status": "completed" if result.get("success") else "failed", "timestamp": datetime.now(timezone.utc).isoformat()}
        self._remediation_history.append(entry)
        audit_logger.info(json.dumps({"event": "AUTO_REMEDIATION_COMPLETED", "remediation_id": remediation_id, "success": result.get("success", False)}))
        return entry

    def get_history(self, limit: int = 20) -> list[dict[str, Any]]:
        return self._remediation_history[-limit:]

    def get_stats(self) -> dict[str, Any]:
        total = len(self._remediation_history)
        successful = sum(1 for r in self._remediation_history if r.get("status") == "completed")
        return {"total_remediations": total, "successful": successful, "failed": total - successful, "success_rate": round(successful / total * 100, 1) if total else 100.0, "recent_count": len([t for t in self._recent_remediations if time.time() - t < 3600]), "max_per_hour": self.MAX_REMEDIATIONS_PER_HOUR}


# ═══════════════════════════════════════════════════════════════════════
# 4. Intelligent Alert Manager
# ═══════════════════════════════════════════════════════════════════════
class IntelligentAlertManager:
    """AI-powered alert management."""

    SEVERITY_LOW = "low"
    SEVERITY_MEDIUM = "medium"
    SEVERITY_HIGH = "high"
    SEVERITY_CRITICAL = "critical"

    ESCALATION_TIMERS = {SEVERITY_CRITICAL: 300, SEVERITY_HIGH: 900, SEVERITY_MEDIUM: 3600, SEVERITY_LOW: 14400}
    NOTIFICATION_CHANNELS = {SEVERITY_CRITICAL: ["pagerduty", "slack", "email"], SEVERITY_HIGH: ["pagerduty", "slack"], SEVERITY_MEDIUM: ["slack", "email"], SEVERITY_LOW: ["email"]}

    def __init__(self):
        self._alerts: list[dict[str, Any]] = []
        self._dedup_window: dict[str, float] = {}
        self._dedup_ttl = 300

    def create_alert(self, title: str, severity: str, *, source: str = "unknown", description: str = "", labels: dict[str, str] | None = None) -> dict[str, Any] | None:
        fingerprint = f"{title}:{source}:{severity}"
        now = time.time()
        if fingerprint in self._dedup_window:
            if now - self._dedup_window[fingerprint] < self._dedup_ttl:
                return None
        self._dedup_window[fingerprint] = now
        alert = {"alert_id": str(uuid.uuid4()), "title": title, "severity": severity, "source": source, "description": description, "labels": labels or {}, "notification_channels": self.NOTIFICATION_CHANNELS.get(severity, ["email"]), "escalation_timer_seconds": self.ESCALATION_TIMERS.get(severity, 3600), "status": "firing", "created_at": datetime.now(timezone.utc).isoformat(), "fingerprint": fingerprint}
        self._alerts.append(alert)
        return alert

    def acknowledge_alert(self, alert_id: str, *, acknowledged_by: str) -> dict[str, Any] | None:
        for alert in self._alerts:
            if alert["alert_id"] == alert_id:
                alert["status"] = "acknowledged"
                alert["acknowledged_by"] = acknowledged_by
                alert["acknowledged_at"] = datetime.now(timezone.utc).isoformat()
                return alert
        return None

    def resolve_alert(self, alert_id: str) -> dict[str, Any] | None:
        for alert in self._alerts:
            if alert["alert_id"] == alert_id:
                alert["status"] = "resolved"
                alert["resolved_at"] = datetime.now(timezone.utc).isoformat()
                return alert
        return None

    def get_active_alerts(self) -> list[dict[str, Any]]:
        return [a for a in self._alerts if a["status"] == "firing"]

    def get_alerts_by_severity(self, severity: str) -> list[dict[str, Any]]:
        return [a for a in self._alerts if a["severity"] == severity]

    def get_all_alerts(self, limit: int = 50) -> list[dict[str, Any]]:
        return self._alerts[-limit:]

    def get_stats(self) -> dict[str, Any]:
        by_severity = defaultdict(int)
        by_status = defaultdict(int)
        for a in self._alerts:
            by_severity[a["severity"]] += 1
            by_status[a["status"]] += 1
        return {"total_alerts": len(self._alerts), "active": len(self.get_active_alerts()), "by_severity": dict(by_severity), "by_status": dict(by_status)}


# Singletons
_predictive_engine: PredictiveAnalyticsEngine | None = None
_anomaly_detector: AnomalyDetector | None = None
_remediation_engine: AutoRemediationEngine | None = None
_alert_manager: IntelligentAlertManager | None = None

def get_predictive_engine() -> PredictiveAnalyticsEngine:
    global _predictive_engine
    if _predictive_engine is None:
        _predictive_engine = PredictiveAnalyticsEngine()
    return _predictive_engine

def get_anomaly_detector() -> AnomalyDetector:
    global _anomaly_detector
    if _anomaly_detector is None:
        _anomaly_detector = AnomalyDetector()
    return _anomaly_detector

def get_remediation_engine() -> AutoRemediationEngine:
    global _remediation_engine
    if _remediation_engine is None:
        _remediation_engine = AutoRemediationEngine()
    return _remediation_engine

def get_alert_manager() -> IntelligentAlertManager:
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = IntelligentAlertManager()
    return _alert_manager
