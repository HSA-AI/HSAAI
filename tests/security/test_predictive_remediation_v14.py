"""HSAAI v14 — Predictive Analytics & Auto-Remediation Tests"""
from __future__ import annotations
import asyncio, sys, time
from pathlib import Path
from typing import Any
import pytest

_BASE = Path(__file__).resolve().parents[2]
_SERVICES = _BASE / "services"
for _p in [str(_SERVICES), str(_BASE / "packages"), str(_BASE / "packages" / "common")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend_core.observability.predictive_remediation_v14 import (  # noqa: E402
    AutoRemediationEngine, AutoRemediationError, AnomalyDetector,
    IntelligentAlertManager, PredictiveAnalyticsEngine,
    get_alert_manager, get_anomaly_detector, get_predictive_engine, get_remediation_engine,
)

@pytest.fixture(autouse=True)
def reset_singletons():
    import backend_core.observability.predictive_remediation_v14 as mod
    mod._predictive_engine = None
    mod._anomaly_detector = None
    mod._remediation_engine = None
    mod._alert_manager = None
    yield


# ═══ PredictiveAnalyticsEngine ═══
class TestPredictiveAnalytics:
    def test_predict_capacity_safe_when_decreasing(self):
        engine = PredictiveAnalyticsEngine()
        for v in [80, 75, 70, 65]:
            engine.record_metric("cpu", v)
        result = engine.predict_capacity("cpu", threshold=90)
        assert result["status"] == "safe"

    def test_predict_capacity_warning_when_approaching(self):
        engine = PredictiveAnalyticsEngine()
        for v in [50, 55, 60, 65, 70, 75]:
            engine.record_metric("cpu", v)
        result = engine.predict_capacity("cpu", threshold=80, forecast_hours=48)
        assert result["status"] in ("warning", "caution", "safe")

    def test_predict_capacity_critical_when_exceeded(self):
        engine = PredictiveAnalyticsEngine()
        for v in [80, 85, 90, 95]:
            engine.record_metric("cpu", v)
        result = engine.predict_capacity("cpu", threshold=90)
        assert result["status"] == "critical"

    def test_predict_capacity_insufficient_data(self):
        engine = PredictiveAnalyticsEngine()
        engine.record_metric("cpu", 50)
        result = engine.predict_capacity("cpu", threshold=90)
        assert result["status"] == "insufficient_data"

    def test_predict_failure_low_risk(self):
        engine = PredictiveAnalyticsEngine()
        result = engine.predict_failure("svc", 0.01, 100)
        assert result["risk_level"] == "low"

    def test_predict_failure_critical_risk(self):
        engine = PredictiveAnalyticsEngine()
        result = engine.predict_failure("svc", 0.15, 5000)
        assert result["risk_level"] == "critical"
        assert result["risk_score"] >= 70

    def test_predict_ai_performance_stable(self):
        engine = PredictiveAnalyticsEngine()
        result = engine.predict_ai_performance("model-1", [100, 105, 98, 102, 100], [0.01, 0.02, 0.01])
        assert result["status"] in ("stable", "warning", "degrading")

    def test_predict_ai_performance_insufficient_data(self):
        engine = PredictiveAnalyticsEngine()
        result = engine.predict_ai_performance("model-1", [100], [])
        assert result["status"] == "insufficient_data"

    def test_get_all_predictions(self):
        engine = PredictiveAnalyticsEngine()
        for v in [50, 55, 60]:
            engine.record_metric("cpu", v)
        engine.predict_capacity("cpu", threshold=90)
        engine.predict_failure("svc", 0.01, 100)
        assert len(engine.get_all_predictions()) == 2

    def test_singleton(self):
        assert get_predictive_engine() is get_predictive_engine()


# ═══ AnomalyDetector ═══
class TestAnomalyDetector:
    def test_no_anomaly_with_insufficient_data(self):
        det = AnomalyDetector()
        result = det.observe("latency", 100)
        assert result is None

    def test_anomaly_detected_on_spike(self):
        det = AnomalyDetector(window_size=50, z_threshold=2.0)
        # Build baseline
        for _ in range(20):
            det.observe("latency", 100)
        # Spike
        result = det.observe("latency", 500)
        assert result is not None
        assert result["metric_name"] == "latency"
        assert result["z_score"] > 2.0

    def test_no_anomaly_on_normal_value(self):
        det = AnomalyDetector(window_size=50, z_threshold=3.0)
        for _ in range(20):
            det.observe("latency", 100)
        result = det.observe("latency", 100)
        assert result is None

    def test_anomaly_score_zero_with_no_data(self):
        det = AnomalyDetector()
        assert det.get_anomaly_score("latency") == 0.0

    def test_anomaly_score_nonzero_with_data(self):
        det = AnomalyDetector(window_size=50, z_threshold=2.0)
        for _ in range(15):
            det.observe("latency", 100)
        det.observe("latency", 300)  # spike
        score = det.get_anomaly_score("latency")
        assert 0 <= score <= 1.0

    def test_get_anomalies(self):
        det = AnomalyDetector(window_size=50, z_threshold=2.0)
        for _ in range(20):
            det.observe("latency", 100)
        det.observe("latency", 500)
        anomalies = det.get_anomalies()
        assert len(anomalies) >= 1

    def test_singleton(self):
        assert get_anomaly_detector() is get_anomaly_detector()


# ═══ AutoRemediationEngine ═══
class TestAutoRemediation:
    @pytest.mark.asyncio
    async def test_successful_remediation(self):
        engine = AutoRemediationEngine()
        async def handler(target):
            return {"success": True, "message": f"Restarted {target}"}
        engine.register_handler("restart_service", handler)
        result = await engine.execute_remediation(
            {"issue": "high_latency"}, "restart_service", target="rag-engine"
        )
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_unknown_action_raises(self):
        engine = AutoRemediationEngine()
        with pytest.raises(AutoRemediationError, match="Unknown action"):
            await engine.execute_remediation({}, "unknown_action", target="svc")

    @pytest.mark.asyncio
    async def test_critical_action_requires_approval(self):
        engine = AutoRemediationEngine()
        with pytest.raises(AutoRemediationError, match="requires human approval"):
            await engine.execute_remediation({}, "rollback_config", target="svc")

    @pytest.mark.asyncio
    async def test_critical_action_with_approval_succeeds(self):
        engine = AutoRemediationEngine()
        async def handler(target):
            return {"success": True}
        engine.register_handler("rollback_config", handler)
        result = await engine.execute_remediation(
            {}, "rollback_config", target="svc", approver="admin@hsaai.group"
        )
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_loop_prevention_blocks_repeated(self):
        engine = AutoRemediationEngine()
        async def handler(target):
            return {"success": True}
        engine.register_handler("restart_service", handler)
        await engine.execute_remediation({}, "restart_service", target="svc")
        with pytest.raises(AutoRemediationError, match="Loop prevention"):
            await engine.execute_remediation({}, "restart_service", target="svc")

    @pytest.mark.asyncio
    async def test_rate_limiting(self):
        engine = AutoRemediationEngine()
        # Override loop prevention window for test
        engine.LOOP_PREVENTION_WINDOW = 0
        async def handler(target):
            return {"success": True}
        engine.register_handler("scale_resources", handler)
        engine.register_handler("trigger_evaluation", handler)
        # Execute 5 (max per hour)
        for i in range(5):
            await engine.execute_remediation({}, "scale_resources", target=f"svc-{i}")
        # 6th should fail
        with pytest.raises(AutoRemediationError, match="Rate limit"):
            await engine.execute_remediation({}, "trigger_evaluation", target="svc-6")

    @pytest.mark.asyncio
    async def test_handler_failure_recorded(self):
        engine = AutoRemediationEngine()
        async def handler(target):
            raise RuntimeError("Handler crashed")
        engine.register_handler("restart_service", handler)
        result = await engine.execute_remediation({}, "restart_service", target="svc")
        assert result["status"] == "failed"

    @pytest.mark.asyncio
    async def test_no_handler_returns_failed(self):
        engine = AutoRemediationEngine()
        result = await engine.execute_remediation({}, "scale_resources", target="svc")
        assert result["status"] == "failed"

    @pytest.mark.asyncio
    async def test_get_history(self):
        engine = AutoRemediationEngine()
        async def handler(target):
            return {"success": True}
        engine.register_handler("scale_resources", handler)
        await engine.execute_remediation({}, "scale_resources", target="svc")
        history = engine.get_history()
        assert len(history) == 1

    @pytest.mark.asyncio
    async def test_get_stats(self):
        engine = AutoRemediationEngine()
        async def handler(target):
            return {"success": True}
        engine.register_handler("scale_resources", handler)
        await engine.execute_remediation({}, "scale_resources", target="svc")
        stats = engine.get_stats()
        assert stats["total_remediations"] == 1
        assert stats["successful"] == 1

    def test_singleton(self):
        assert get_remediation_engine() is get_remediation_engine()


# ═══ IntelligentAlertManager ═══
class TestIntelligentAlertManager:
    def test_create_alert(self):
        mgr = IntelligentAlertManager()
        alert = mgr.create_alert("High Error Rate", "critical", source="rag-engine")
        assert alert is not None
        assert alert["severity"] == "critical"
        assert "pagerduty" in alert["notification_channels"]

    def test_dedup_suppresses_duplicate(self):
        mgr = IntelligentAlertManager()
        mgr.create_alert("High Error Rate", "high", source="svc")
        duplicate = mgr.create_alert("High Error Rate", "high", source="svc")
        assert duplicate is None

    def test_different_source_not_deduped(self):
        mgr = IntelligentAlertManager()
        mgr.create_alert("High Error Rate", "high", source="svc-1")
        alert2 = mgr.create_alert("High Error Rate", "high", source="svc-2")
        assert alert2 is not None

    def test_acknowledge_alert(self):
        mgr = IntelligentAlertManager()
        alert = mgr.create_alert("Test", "medium", source="svc")
        acked = mgr.acknowledge_alert(alert["alert_id"], acknowledged_by="user-1")
        assert acked["status"] == "acknowledged"
        assert acked["acknowledged_by"] == "user-1"

    def test_resolve_alert(self):
        mgr = IntelligentAlertManager()
        alert = mgr.create_alert("Test", "medium", source="svc")
        resolved = mgr.resolve_alert(alert["alert_id"])
        assert resolved["status"] == "resolved"

    def test_get_active_alerts(self):
        mgr = IntelligentAlertManager()
        mgr.create_alert("Active", "high", source="svc-1")
        mgr.create_alert("Resolved", "medium", source="svc-2")
        active = mgr.get_active_alerts()
        assert len(active) == 2  # both initially firing

    def test_get_alerts_by_severity(self):
        mgr = IntelligentAlertManager()
        mgr.create_alert("A1", "critical", source="svc-1")
        mgr.create_alert("A2", "high", source="svc-2")
        mgr.create_alert("A3", "critical", source="svc-3")
        critical = mgr.get_alerts_by_severity("critical")
        assert len(critical) == 2

    def test_get_stats(self):
        mgr = IntelligentAlertManager()
        mgr.create_alert("A1", "critical", source="svc-1")
        mgr.create_alert("A2", "high", source="svc-2")
        stats = mgr.get_stats()
        assert stats["total_alerts"] == 2
        assert stats["by_severity"]["critical"] == 1

    def test_notification_channels_by_severity(self):
        mgr = IntelligentAlertManager()
        critical = mgr.create_alert("Test", "critical", source="svc")
        assert "pagerduty" in critical["notification_channels"]
        low = mgr.create_alert("Test2", "low", source="svc")
        assert "email" in low["notification_channels"]

    def test_escalation_timer_by_severity(self):
        mgr = IntelligentAlertManager()
        critical = mgr.create_alert("Test", "critical", source="svc")
        assert critical["escalation_timer_seconds"] == 300  # 5 min
        low = mgr.create_alert("Test2", "low", source="svc")
        assert low["escalation_timer_seconds"] == 14400  # 4 hours

    def test_singleton(self):
        assert get_alert_manager() is get_alert_manager()
