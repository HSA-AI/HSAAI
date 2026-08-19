"""HSAAI v15.1 — ABAC Priority Mode + Safe Auto-Remediation + Baseline Tests"""
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

from backend_core.observability.v15_1_intelligent_ops import (  # noqa: E402
    ABACPriorityMode, SafeAutoRemediationError, SafeAutoRemediationManager,
    PredictiveBaselineCollector,
    get_abac_priority, get_baseline_collector, get_safe_remediation,
)

@pytest.fixture(autouse=True)
def reset_singletons():
    import backend_core.observability.v15_1_intelligent_ops as mod
    mod._abac_priority = None
    mod._safe_remediation = None
    mod._baseline_collector = None
    yield


# ═══ ABACPriorityMode ═══
class TestABACPriorityMode:
    def test_abac_overrides_rbac_when_policy_matches(self):
        mode = ABACPriorityMode()

        # Mock ABAC engine that returns ALLOW with a policy
        class MockABAC:
            def evaluate(self, subject, resource, action, env):
                return {"decision": "ALLOW", "policy_id": "policy-1", "policy_name": "test"}

        result = mode.evaluate(
            {"department": "finance"}, {"department": "finance"}, "read",
            abac_engine=MockABAC(),
            rbac_has_permission=lambda s, p: False,  # RBAC denies
        )
        assert result["decision"] == "ALLOW"
        assert result["source"] == "abac"
        assert result["rbac_evaluated"] is False

    def test_rbac_fallback_when_no_abac_policy(self):
        mode = ABACPriorityMode()

        class MockABAC:
            def evaluate(self, subject, resource, action, env):
                return {"decision": "DENY", "policy_id": None, "policy_name": "default-deny"}

        result = mode.evaluate(
            {"department": "finance"}, {}, "read",
            abac_engine=MockABAC(),
            rbac_has_permission=lambda s, p: True,  # RBAC allows
        )
        assert result["decision"] == "ALLOW"
        assert result["source"] == "rbac"

    def test_default_deny_when_both_deny(self):
        mode = ABACPriorityMode()

        class MockABAC:
            def evaluate(self, subject, resource, action, env):
                return {"decision": "DENY", "policy_id": None, "policy_name": "default-deny"}

        result = mode.evaluate(
            {}, {}, "read",
            abac_engine=MockABAC(),
            rbac_has_permission=lambda s, p: False,
        )
        assert result["decision"] == "DENY"
        assert result["source"] == "default_deny"

    def test_no_abac_engine_uses_rbac(self):
        mode = ABACPriorityMode()
        result = mode.evaluate(
            {}, {}, "read",
            abac_engine=None,
            rbac_has_permission=lambda s, p: True,
        )
        assert result["decision"] == "ALLOW"
        assert result["source"] == "rbac"

    def test_no_abac_no_rbac_denies(self):
        mode = ABACPriorityMode()
        result = mode.evaluate({}, {}, "read")
        assert result["decision"] == "DENY"
        assert result["source"] == "default_deny"

    def test_migration_stats(self):
        mode = ABACPriorityMode()

        class MockABAC:
            def evaluate(self, subject, resource, action, env):
                return {"decision": "ALLOW", "policy_id": "p1", "policy_name": "test"}

        # 3 ABAC decisions
        for _ in range(3):
            mode.evaluate({}, {}, "read", abac_engine=MockABAC())
        # 2 RBAC fallbacks
        for _ in range(2):
            mode.evaluate({}, {}, "write", rbac_has_permission=lambda s, p: True)

        stats = mode.get_migration_stats()
        assert stats["total_decisions"] == 5
        assert stats["abac_decisions"] == 3
        assert stats["rbac_fallbacks"] == 2
        assert stats["abac_coverage_pct"] == 60.0

    def test_singleton(self):
        assert get_abac_priority() is get_abac_priority()


# ═══ SafeAutoRemediationManager ═══
class TestSafeAutoRemediation:
    @pytest.mark.asyncio
    async def test_scale_resources_executes(self):
        mgr = SafeAutoRemediationManager()
        async def handler(target):
            return {"success": True, "message": f"Scaled {target}"}
        mgr.register_handler("scale_resources", handler)
        result = await mgr.execute("scale_resources", "rag-engine")
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_trigger_evaluation_executes(self):
        mgr = SafeAutoRemediationManager()
        async def handler(target):
            return {"success": True, "message": f"Eval triggered for {target}"}
        mgr.register_handler("trigger_evaluation", handler)
        result = await mgr.execute("trigger_evaluation", "finance-model")
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_non_allowlisted_action_raises(self):
        mgr = SafeAutoRemediationManager()
        with pytest.raises(SafeAutoRemediationError, match="NOT in production allowlist"):
            await mgr.execute("restart_service", "svc")

    @pytest.mark.asyncio
    async def test_register_non_allowlisted_handler_raises(self):
        mgr = SafeAutoRemediationManager()
        with pytest.raises(SafeAutoRemediationError, match="not in production allowlist"):
            mgr.register_handler("rollback_config", lambda t: None)

    @pytest.mark.asyncio
    async def test_disabled_raises(self):
        mgr = SafeAutoRemediationManager()
        mgr.disable()
        with pytest.raises(SafeAutoRemediationError, match="disabled"):
            await mgr.execute("scale_resources", "svc")

    @pytest.mark.asyncio
    async def test_loop_prevention(self):
        mgr = SafeAutoRemediationManager()
        async def handler(target):
            return {"success": True}
        mgr.register_handler("scale_resources", handler)
        await mgr.execute("scale_resources", "svc")
        with pytest.raises(SafeAutoRemediationError, match="Loop prevention"):
            await mgr.execute("scale_resources", "svc")

    @pytest.mark.asyncio
    async def test_rate_limiting(self):
        mgr = SafeAutoRemediationManager()
        mgr.LOOP_PREVENTION_WINDOW = 0  # Disable loop prevention for this test
        async def handler(target):
            return {"success": True}
        mgr.register_handler("scale_resources", handler)
        mgr.register_handler("trigger_evaluation", handler)
        for i in range(10):
            action = "scale_resources" if i % 2 == 0 else "trigger_evaluation"
            await mgr.execute(action, f"svc-{i}")
        with pytest.raises(SafeAutoRemediationError, match="Rate limit"):
            await mgr.execute("scale_resources", "svc-11")

    @pytest.mark.asyncio
    async def test_handler_failure_recorded(self):
        mgr = SafeAutoRemediationManager()
        async def handler(target):
            raise RuntimeError("Handler failed")
        mgr.register_handler("scale_resources", handler)
        result = await mgr.execute("scale_resources", "svc")
        assert result["status"] == "failed"

    @pytest.mark.asyncio
    async def test_no_handler_returns_failed(self):
        mgr = SafeAutoRemediationManager()
        result = await mgr.execute("trigger_evaluation", "svc")
        assert result["status"] == "failed"

    def test_is_action_allowed(self):
        mgr = SafeAutoRemediationManager()
        assert mgr.is_action_allowed("scale_resources") is True
        assert mgr.is_action_allowed("restart_service") is False

    def test_get_allowlist(self):
        mgr = SafeAutoRemediationManager()
        allowlist = mgr.get_allowlist()
        assert "scale_resources" in allowlist
        assert "trigger_evaluation" in allowlist
        assert allowlist["scale_resources"]["risk"] == "low"

    @pytest.mark.asyncio
    async def test_get_stats(self):
        mgr = SafeAutoRemediationManager()
        async def handler(target):
            return {"success": True}
        mgr.register_handler("scale_resources", handler)
        await mgr.execute("scale_resources", "svc")
        stats = mgr.get_stats()
        assert stats["total_executions"] == 1
        assert stats["successful"] == 1
        assert "scale_resources" in stats["by_action"]

    def test_singleton(self):
        assert get_safe_remediation() is get_safe_remediation()


# ═══ PredictiveBaselineCollector ═══
class TestPredictiveBaselineCollector:
    def test_start_observation(self):
        collector = PredictiveBaselineCollector()
        result = collector.start_observation()
        assert result["status"] == "observation_started"
        assert result["mode"] == "observation"

    def test_collect_metric(self):
        collector = PredictiveBaselineCollector()
        collector.start_observation()
        result = collector.collect_metric("infrastructure", "cpu_usage", 75.5)
        assert result["collected"] is True
        assert result["category"] == "infrastructure"
        assert result["metric"] == "cpu_usage"
        assert result["value"] == 75.5

    def test_collect_invalid_category_raises(self):
        collector = PredictiveBaselineCollector()
        with pytest.raises(ValueError, match="Invalid category"):
            collector.collect_metric("invalid", "metric", 100)

    def test_observation_status_not_started(self):
        collector = PredictiveBaselineCollector()
        status = collector.get_observation_status()
        assert status["status"] == "not_started"

    def test_observation_status_in_progress(self):
        collector = PredictiveBaselineCollector()
        collector.start_observation()
        collector.collect_metric("ai", "model_latency", 100)
        status = collector.get_observation_status()
        assert status["status"] == "in_progress"
        assert status["total_metrics_collected"] == 1

    def test_generate_baseline_incomplete(self):
        collector = PredictiveBaselineCollector()
        collector.start_observation()
        report = collector.generate_baseline_report()
        assert report["status"] == "observation_incomplete"

    def test_generate_baseline_complete_with_sufficient_data(self):
        collector = PredictiveBaselineCollector()
        collector.start_observation()
        # Manually set start time to 8 days ago
        from datetime import timedelta
        collector._start_time = collector._start_time - timedelta(days=8)
        # Collect enough metrics
        for i in range(100):
            collector.collect_metric("infrastructure", "cpu_usage", 50.0 + i * 0.1)
        report = collector.generate_baseline_report()
        assert report["status"] == "baseline_generated"
        assert "baselines" in report
        assert "infrastructure.cpu_usage" in report["baselines"]

    def test_baseline_includes_statistics(self):
        collector = PredictiveBaselineCollector()
        collector.start_observation()
        from datetime import timedelta
        collector._start_time = collector._start_time - timedelta(days=8)
        for i in range(50):
            collector.collect_metric("application", "api_latency", 100.0 + i)
        report = collector.generate_baseline_report()
        baseline = report["baselines"]["application.api_latency"]
        assert "min" in baseline
        assert "max" in baseline
        assert "mean" in baseline
        assert "median" in baseline
        assert "stdev" in baseline
        assert "p95" in baseline
        assert "p99" in baseline

    def test_data_quality_assessment(self):
        collector = PredictiveBaselineCollector()
        collector.start_observation()
        from datetime import timedelta
        collector._start_time = collector._start_time - timedelta(days=8)
        for _ in range(200):
            collector.collect_metric("ai", "model_latency", 100.0)
        report = collector.generate_baseline_report()
        assert "data_quality" in report
        assert report["data_quality"]["status"] in ("good", "fair", "poor")

    def test_get_collected_metrics(self):
        collector = PredictiveBaselineCollector()
        collector.start_observation()
        collector.collect_metric("infrastructure", "cpu", 50)
        collector.collect_metric("ai", "latency", 100)
        metrics = collector.get_collected_metrics()
        assert "infrastructure.cpu" in metrics
        assert "ai.latency" in metrics

    def test_singleton(self):
        assert get_baseline_collector() is get_baseline_collector()
