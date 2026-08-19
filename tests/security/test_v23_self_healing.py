"""HSAAI v23 — Self-Healing Platform + Predictive Capacity + DB Optimization + Optimizer Observation Tests"""
from __future__ import annotations
import asyncio, sys
from pathlib import Path
from typing import Any
import pytest

_BASE = Path(__file__).resolve().parents[2]
_SERVICES = _BASE / "services"
for _p in [str(_SERVICES), str(_BASE / "packages"), str(_BASE / "packages" / "common")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend_core.observability.v23_self_healing import (  # noqa: E402
    DatabaseOptimizationManager, OptimizationObservationPeriod,
    PredictiveCapacityManager, SelfHealingError, SelfHealingPlatform,
    get_capacity_mgr, get_db_optimizer, get_opt_observation, get_self_healing,
)

@pytest.fixture(autouse=True)
def reset_singletons():
    import backend_core.observability.v23_self_healing as mod
    mod._capacity_mgr = None
    mod._self_healing = None
    mod._db_optimizer = None
    mod._opt_observation = None
    yield


# ═══ PredictiveCapacityManager ═══
class TestPredictiveCapacityManager:
    def test_collect_telemetry(self):
        mgr = PredictiveCapacityManager()
        mgr.collect_telemetry("cpu_percent", 65.5)
        assert len(mgr._telemetry["cpu_percent"]) == 1

    def test_forecast_insufficient_data(self):
        mgr = PredictiveCapacityManager()
        mgr.collect_telemetry("cpu_percent", 50)
        result = mgr.forecast("cpu_percent", "24h")
        assert result["status"] == "insufficient_data"

    def test_forecast_increasing_trend(self):
        mgr = PredictiveCapacityManager()
        for v in [50, 55, 60, 65, 70, 75]:
            mgr.collect_telemetry("cpu_percent", v)
        result = mgr.forecast("cpu_percent", "24h")
        assert "forecast_value" in result
        assert result["trend"] == "increasing"
        assert result["forecast_value"] > 70

    def test_forecast_decreasing_trend(self):
        mgr = PredictiveCapacityManager()
        for v in [80, 75, 70, 65, 60]:
            mgr.collect_telemetry("cpu_percent", v)
        result = mgr.forecast("cpu_percent", "24h")
        assert result["trend"] == "decreasing"

    def test_forecast_critical_risk(self):
        mgr = PredictiveCapacityManager()
        for v in [80, 82, 84, 86, 88, 90]:
            mgr.collect_telemetry("cpu_percent", v)
        result = mgr.forecast("cpu_percent", "24h")
        assert result["risk_level"] == "critical"

    def test_forecast_low_risk(self):
        mgr = PredictiveCapacityManager()
        for v in [20, 21, 22, 23, 24, 25]:
            mgr.collect_telemetry("cpu_percent", v)
        result = mgr.forecast("cpu_percent", "24h")
        assert result["risk_level"] == "low"

    def test_unknown_horizon_raises(self):
        mgr = PredictiveCapacityManager()
        with pytest.raises(ValueError, match="Unknown horizon"):
            mgr.forecast("cpu_percent", "100y")

    def test_forecast_all(self):
        mgr = PredictiveCapacityManager()
        for v in [50, 55, 60]:
            mgr.collect_telemetry("cpu_percent", v)
            mgr.collect_telemetry("memory_percent", v)
        result = mgr.forecast_all("24h")
        assert result["resources_forecasted"] == 2

    def test_get_alerts(self):
        mgr = PredictiveCapacityManager()
        for v in [80, 82, 84, 86, 88]:
            mgr.collect_telemetry("cpu_percent", v)
        mgr.forecast("cpu_percent", "24h")
        alerts = mgr.get_alerts()
        assert len(alerts) >= 1

    def test_singleton(self):
        assert get_capacity_mgr() is get_capacity_mgr()


# ═══ SelfHealingPlatform ═══
class TestSelfHealingPlatform:
    @pytest.mark.asyncio
    async def test_full_recovery_flow(self):
        platform = SelfHealingPlatform()
        async def handler(target): return {"success": True, "message": f"Restarted {target}"}
        platform.register_handler("restart_service", handler)

        # Detection
        incident = platform.detect_issue({
            "type": "service_down", "severity": "medium", "target": "rag-engine",
        })
        assert incident["status"] == "detected"

        # Prediction
        prediction = platform.predict_impact(incident)
        assert prediction["severity"] == "medium"

        # Decision
        decision = platform.decide_recovery(incident, prediction)
        assert decision["action"] == "restart_service"

        # Policy validation
        policy = platform.validate_policy(decision)
        assert policy["approved"] is True

        # Execution
        recovery = await platform.execute_recovery(
            incident, decision, rollback_plan="restart manually"
        )
        assert recovery["status"] == "recovered"

    @pytest.mark.asyncio
    async def test_high_severity_requires_approval(self):
        platform = SelfHealingPlatform()
        async def handler(target): return {"success": True}
        platform.register_handler("restart_service", handler)

        incident = platform.detect_issue({
            "type": "service_down", "severity": "critical", "target": "ai-core",
        })
        prediction = platform.predict_impact(incident)
        decision = platform.decide_recovery(incident, prediction)
        # No approver → blocked
        result = await platform.execute_recovery(incident, decision, rollback_plan="plan")
        assert result["status"] == "blocked"

    @pytest.mark.asyncio
    async def test_high_severity_with_approver_succeeds(self):
        platform = SelfHealingPlatform()
        async def handler(target): return {"success": True}
        platform.register_handler("restart_service", handler)

        incident = platform.detect_issue({
            "type": "service_down", "severity": "critical", "target": "ai-core",
        })
        prediction = platform.predict_impact(incident)
        decision = platform.decide_recovery(incident, prediction)
        result = await platform.execute_recovery(
            incident, decision, approver="admin", rollback_plan="plan"
        )
        assert result["status"] == "recovered"

    @pytest.mark.asyncio
    async def test_no_rollback_plan_blocks(self):
        platform = SelfHealingPlatform()
        incident = platform.detect_issue({"type": "high_latency", "severity": "medium", "target": "svc"})
        prediction = platform.predict_impact(incident)
        decision = platform.decide_recovery(incident, prediction)
        result = await platform.execute_recovery(incident, decision)
        assert result["status"] == "blocked"
        assert "Rollback" in result["reason"]

    @pytest.mark.asyncio
    async def test_abac_denial_blocks(self):
        platform = SelfHealingPlatform()
        incident = platform.detect_issue({"type": "high_latency", "severity": "medium", "target": "svc"})
        prediction = platform.predict_impact(incident)
        decision = platform.decide_recovery(incident, prediction)
        policy = platform.validate_policy(decision, abac_decision={"decision": "DENY"})
        assert policy["approved"] is False

    @pytest.mark.asyncio
    async def test_handler_failure_recorded(self):
        platform = SelfHealingPlatform()
        async def handler(target): raise RuntimeError("Handler crashed")
        platform.register_handler("restart_service", handler)
        incident = platform.detect_issue({"type": "service_down", "severity": "medium", "target": "svc"})
        prediction = platform.predict_impact(incident)
        decision = platform.decide_recovery(incident, prediction)
        result = await platform.execute_recovery(incident, decision, rollback_plan="plan")
        assert result["status"] == "failed"

    def test_verify_recovery(self):
        platform = SelfHealingPlatform()
        # Manually add a recovery for verification
        platform._recoveries.append({
            "recovery_id": "test-123",
            "action": "scale_resources",
            "status": "recovered",
        })
        verification = platform.verify_recovery(
            "test-123",
            before_metrics={"latency_ms": 200},
            after_metrics={"latency_ms": 150},
        )
        assert verification["status"] == "verified"
        assert "latency_ms" in verification["improvements"]

    def test_verify_unknown_recovery_raises(self):
        platform = SelfHealingPlatform()
        with pytest.raises(SelfHealingError, match="not found"):
            platform.verify_recovery("unknown", before_metrics={}, after_metrics={})

    def test_get_stats(self):
        platform = SelfHealingPlatform()
        stats = platform.get_stats()
        assert stats["mode"] == "supervised"
        assert stats["total_incidents"] == 0

    def test_register_unknown_handler_raises(self):
        platform = SelfHealingPlatform()
        with pytest.raises(SelfHealingError, match="Unknown recovery action"):
            platform.register_handler("unknown_action", lambda t: None)

    def test_singleton(self):
        assert get_self_healing() is get_self_healing()


# ═══ DatabaseOptimizationManager ═══
class TestDatabaseOptimizationManager:
    def test_get_optimization_plan(self):
        mgr = DatabaseOptimizationManager()
        plan = mgr.get_optimization_plan()
        assert plan["total_optimizations"] == 3
        assert "materialized_views" in plan["optimizations"]
        assert "pg_trgm" in plan["optimizations"]
        assert "pgbouncer" in plan["optimizations"]

    def test_validate_optimization(self):
        mgr = DatabaseOptimizationManager()
        result = mgr.validate_optimization("pg_trgm")
        assert result["valid"] is True
        assert result["risk"] == "low"

    def test_validate_unknown_optimization(self):
        mgr = DatabaseOptimizationManager()
        result = mgr.validate_optimization("unknown")
        assert result["valid"] is False

    def test_get_materialized_views(self):
        mgr = DatabaseOptimizationManager()
        views = mgr.get_materialized_views()
        assert len(views) == 3
        assert any(v["name"] == "mv_document_stats" for v in views)

    def test_get_pg_trgm_config(self):
        mgr = DatabaseOptimizationManager()
        config = mgr.get_pg_trgm_config()
        assert len(config["indexes"]) == 2
        assert "10-50x" in config["expected_improvement"]

    def test_get_pgbouncer_config(self):
        mgr = DatabaseOptimizationManager()
        config = mgr.get_pgbouncer_config()
        assert config["pool_mode"] == "transaction"
        assert config["max_client_conn"] == 1000

    def test_performance_comparison(self):
        mgr = DatabaseOptimizationManager()
        mgr.record_performance("before", {"latency_ms": 150, "connections": 100})
        mgr.record_performance("after", {"latency_ms": 25, "connections": 25})
        comparison = mgr.compare_performance()
        assert "latency_ms" in comparison["improvements"]
        assert comparison["improvements"]["latency_ms"]["change_pct"] < 0

    def test_singleton(self):
        assert get_db_optimizer() is get_db_optimizer()


# ═══ OptimizationObservationPeriod ═══
class TestOptimizationObservation:
    def test_start_observation(self):
        period = OptimizationObservationPeriod()
        result = period.start_observation()
        assert result["status"] == "observation_started"
        assert result["duration_days"] == 30

    def test_collect_recommendation(self):
        period = OptimizationObservationPeriod()
        period.collect_recommendation({"type": "scale_up", "was_correct": True})

    def test_generate_daily_report(self):
        period = OptimizationObservationPeriod()
        period.collect_recommendation({"type": "scale_up", "was_correct": True})
        report = period.generate_daily_report(1)
        assert report["day_number"] == 1
        assert report["mode"] == "recommendation"

    def test_daily_report_day_30_evaluates(self):
        period = OptimizationObservationPeriod()
        report = period.generate_daily_report(30)
        assert report["recommendation"] in ("READY_FOR_AUTONOMOUS_MODE", "EXTEND_OBSERVATION")

    def test_get_observation_status_not_started(self):
        period = OptimizationObservationPeriod()
        status = period.get_observation_status()
        assert status["status"] == "not_started"

    def test_generate_validation_incomplete(self):
        period = OptimizationObservationPeriod()
        period.generate_daily_report(1)
        result = period.generate_validation_report()
        assert result["status"] == "incomplete"

    def test_generate_validation_complete(self):
        period = OptimizationObservationPeriod()
        for _ in range(20):
            period.collect_recommendation({"type": "scale_up", "was_correct": True})
        for day in range(1, 31):
            period.generate_daily_report(day)
        result = period.generate_validation_report()
        assert result["status"] == "complete"
        assert result["readiness_decision"] == "READY_FOR_AUTONOMOUS_MODE"

    def test_singleton(self):
        assert get_opt_observation() is get_opt_observation()
