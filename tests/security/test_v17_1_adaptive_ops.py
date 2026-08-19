"""HSAAI v17.1 — Medium-Risk Remediation + Predictive Monitoring + Architecture Compliance Tests"""
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

from backend_core.observability.v17_1_adaptive_ops import (  # noqa: E402
    ArchitectureComplianceValidator, MediumRiskRemediationError,
    MediumRiskRemediationManager, PredictiveMonitoringPeriod,
    get_arch_validator, get_medium_remediation, get_predictive_monitoring,
)

@pytest.fixture(autouse=True)
def reset_singletons():
    import backend_core.observability.v17_1_adaptive_ops as mod
    mod._medium_remediation = None
    mod._predictive_monitoring = None
    mod._arch_validator = None
    yield


# ═══ MediumRiskRemediationManager ═══
class TestMediumRiskRemediation:
    @pytest.mark.asyncio
    async def test_low_risk_action_executes(self):
        mgr = MediumRiskRemediationManager()
        async def handler(t): return {"success": True}
        mgr.register_handler("scale_resources", handler)
        result = await mgr.execute("scale_resources", "svc")
        assert result["status"] == "completed"
        assert result["risk"] == "low"

    @pytest.mark.asyncio
    async def test_medium_risk_action_executes(self):
        mgr = MediumRiskRemediationManager()
        async def handler(t): return {"success": True}
        mgr.register_handler("restart_service", handler)
        result = await mgr.execute("restart_service", "svc")
        assert result["status"] == "completed"
        assert result["risk"] == "medium"

    @pytest.mark.asyncio
    async def test_medium_risk_disabled_raises(self):
        mgr = MediumRiskRemediationManager()
        mgr.disable_medium_risk()
        async def handler(t): return {"success": True}
        mgr.register_handler("restart_service", handler)
        with pytest.raises(MediumRiskRemediationError, match="Medium-risk actions are disabled"):
            await mgr.execute("restart_service", "svc")

    @pytest.mark.asyncio
    async def test_non_allowlisted_action_raises(self):
        mgr = MediumRiskRemediationManager()
        with pytest.raises(MediumRiskRemediationError, match="NOT in allowlist"):
            await mgr.execute("rollback_config", "svc")

    @pytest.mark.asyncio
    async def test_abac_denial_blocks_execution(self):
        mgr = MediumRiskRemediationManager()
        async def handler(t): return {"success": True}
        mgr.register_handler("restart_service", handler)
        with pytest.raises(MediumRiskRemediationError, match="ABAC policy denied"):
            await mgr.execute("restart_service", "svc", abac_decision={"decision": "DENY"})

    @pytest.mark.asyncio
    async def test_cool_down_prevents_rapid_execution(self):
        mgr = MediumRiskRemediationManager()
        async def handler(t): return {"success": True}
        mgr.register_handler("restart_service", handler)
        await mgr.execute("restart_service", "svc")
        with pytest.raises(MediumRiskRemediationError, match="Cool-down active"):
            await mgr.execute("restart_service", "svc")

    @pytest.mark.asyncio
    async def test_handler_failure_increments_retry(self):
        mgr = MediumRiskRemediationManager()
        async def handler(t): raise RuntimeError("Failed")
        mgr.register_handler("restart_service", handler)
        await mgr.execute("restart_service", "svc")
        assert mgr._retry_counts["restart_service:svc"] == 1

    @pytest.mark.asyncio
    async def test_max_retries_exceeded_raises(self):
        mgr = MediumRiskRemediationManager()
        async def handler(t): raise RuntimeError("Always fails")
        mgr.register_handler("restart_service", handler)
        mgr._retry_counts["restart_service:svc"] = 2  # Already at max
        with pytest.raises(MediumRiskRemediationError, match="Max retries"):
            await mgr.execute("restart_service", "svc")

    @pytest.mark.asyncio
    async def test_approval_required(self):
        mgr = MediumRiskRemediationManager()
        async def handler(t): return {"success": True}
        mgr.register_handler("restart_service", handler)
        with pytest.raises(MediumRiskRemediationError, match="requires approval"):
            await mgr.execute("restart_service", "svc", require_approval=True)
        # With approver should work
        result = await mgr.execute("restart_service", "svc", require_approval=True, approver="admin")
        assert result["status"] == "completed"

    def test_get_allowlist_includes_medium_risk(self):
        mgr = MediumRiskRemediationManager()
        allowlist = mgr.get_allowlist()
        assert "scale_resources" in allowlist  # low
        assert "restart_service" in allowlist  # medium
        assert "recreate_pod" in allowlist  # medium

    def test_is_action_allowed_low_risk(self):
        mgr = MediumRiskRemediationManager()
        assert mgr.is_action_allowed("scale_resources") is True

    def test_is_action_allowed_medium_risk(self):
        mgr = MediumRiskRemediationManager()
        assert mgr.is_action_allowed("restart_service") is True
        mgr.disable_medium_risk()
        assert mgr.is_action_allowed("restart_service") is False

    def test_is_action_allowed_unknown(self):
        mgr = MediumRiskRemediationManager()
        assert mgr.is_action_allowed("unknown_action") is False

    def test_get_action_risk(self):
        mgr = MediumRiskRemediationManager()
        assert mgr.get_action_risk("scale_resources") == "low"
        assert mgr.get_action_risk("restart_service") == "medium"
        assert mgr.get_action_risk("unknown") is None

    @pytest.mark.asyncio
    async def test_get_stats(self):
        mgr = MediumRiskRemediationManager()
        async def handler(t): return {"success": True}
        mgr.register_handler("scale_resources", handler)
        mgr.register_handler("restart_service", handler)
        await mgr.execute("scale_resources", "svc-1")
        await mgr.execute("restart_service", "svc-2")
        stats = mgr.get_stats()
        assert stats["total_executions"] == 2
        assert stats["by_risk"]["low"] == 1
        assert stats["by_risk"]["medium"] == 1

    def test_singleton(self):
        assert get_medium_remediation() is get_medium_remediation()


# ═══ PredictiveMonitoringPeriod ═══
class TestPredictiveMonitoring:
    def test_start_monitoring(self):
        period = PredictiveMonitoringPeriod()
        result = period.start_monitoring()
        assert result["status"] == "monitoring_started"
        assert result["duration_days"] == 14

    def test_collect_prediction(self):
        period = PredictiveMonitoringPeriod()
        period.collect_prediction({"predicted": True, "actual": True, "confidence": 0.9})

    def test_generate_daily_report(self):
        period = PredictiveMonitoringPeriod()
        period.collect_prediction({"predicted": True, "actual": True, "confidence": 0.9})
        report = period.generate_daily_report(1)
        assert report["day_number"] == 1
        assert "prediction_confidence" in report
        assert "reliability_score" in report

    def test_daily_report_day_14_recommends_active(self):
        period = PredictiveMonitoringPeriod()
        # Add high-quality predictions
        for _ in range(20):
            period.collect_prediction({"predicted": True, "actual": True, "confidence": 0.95})
        report = period.generate_daily_report(14)
        assert report["recommendation"] == "READY_FOR_ACTIVE_MODE"

    def test_daily_report_day_14_extends_if_low_reliability(self):
        period = PredictiveMonitoringPeriod()
        # Add low-quality predictions
        for _ in range(20):
            period.collect_prediction({"predicted": True, "actual": False, "confidence": 0.3})
        report = period.generate_daily_report(14)
        assert report["recommendation"] == "EXTEND_MONITORING"

    def test_get_monitoring_status_not_started(self):
        period = PredictiveMonitoringPeriod()
        status = period.get_monitoring_status()
        assert status["status"] == "not_started"

    def test_get_monitoring_status_in_progress(self):
        period = PredictiveMonitoringPeriod()
        period.start_monitoring()
        status = period.get_monitoring_status()
        assert status["status"] == "in_progress"

    def test_generate_monitoring_summary_incomplete(self):
        period = PredictiveMonitoringPeriod()
        period.generate_daily_report(1)
        summary = period.generate_monitoring_summary()
        assert summary["status"] == "incomplete"

    def test_generate_monitoring_summary_complete(self):
        period = PredictiveMonitoringPeriod()
        for day in range(1, 15):
            for _ in range(10):
                period.collect_prediction({"predicted": True, "actual": True, "confidence": 0.9})
            period.generate_daily_report(day)
        summary = period.generate_monitoring_summary()
        assert summary["status"] == "complete"
        assert summary["readiness_recommendation"] == "READY_FOR_ACTIVE_MODE"

    def test_singleton(self):
        assert get_predictive_monitoring() is get_predictive_monitoring()


# ═══ ArchitectureComplianceValidator ═══
class TestArchitectureCompliance:
    def _valid_module(self):
        return {
            "name": "test-module",
            "name_en": "Test Module",
            "description": "A test module",
            "version": "1.0.0",
            "type": "test",
            "status": "production",
            "owner": "Test Team",
            "dependencies": ["other-module"],
            "interfaces": ["/api/test"],
            "health_endpoint": "/health",
            "metrics_endpoint": "/metrics",
            "security_level": "internal",
        }

    def test_valid_module_passes(self):
        validator = ArchitectureComplianceValidator()
        result = validator.validate_module(self._valid_module())
        assert result["valid"] is True
        assert result["error_count"] == 0

    def test_missing_fields_fails(self):
        validator = ArchitectureComplianceValidator()
        module = self._valid_module()
        del module["health_endpoint"]
        result = validator.validate_module(module)
        assert result["valid"] is False
        assert "Missing required fields" in result["errors"][0]

    def test_invalid_security_level_fails(self):
        validator = ArchitectureComplianceValidator()
        module = self._valid_module()
        module["security_level"] = "top_secret"
        result = validator.validate_module(module)
        assert result["valid"] is False

    def test_invalid_status_fails(self):
        validator = ArchitectureComplianceValidator()
        module = self._valid_module()
        module["status"] = "unknown"
        result = validator.validate_module(module)
        assert result["valid"] is False

    def test_self_dependency_detected(self):
        validator = ArchitectureComplianceValidator()
        module = self._valid_module()
        module["dependencies"] = ["test-module"]
        result = validator.validate_module(module)
        assert "Self-dependency" in result["errors"][0]

    def test_non_slash_endpoint_warns(self):
        validator = ArchitectureComplianceValidator()
        module = self._valid_module()
        module["health_endpoint"] = "health"
        result = validator.validate_module(module)
        assert result["warning_count"] > 0

    def test_validate_all_returns_summary(self):
        validator = ArchitectureComplianceValidator()
        modules = [self._valid_module(), self._valid_module()]
        modules[1]["name"] = "second-module"
        summary = validator.validate_all(modules)
        assert summary["total_modules"] == 2
        assert summary["valid_modules"] == 2
        assert summary["compliance_rate"] == 100.0

    def test_check_dependency_graph_finds_missing(self):
        validator = ArchitectureComplianceValidator()
        modules = [
            {"name": "a", "dependencies": ["b"]},
            {"name": "b", "dependencies": ["c"]},  # c doesn't exist
        ]
        result = validator.check_dependency_graph(modules)
        assert len(result["missing_dependencies"]) == 1
        assert result["missing_dependencies"][0]["missing_dependency"] == "c"

    def test_check_dependency_graph_no_issues(self):
        validator = ArchitectureComplianceValidator()
        modules = [
            {"name": "a", "dependencies": ["b"]},
            {"name": "b", "dependencies": []},
        ]
        result = validator.check_dependency_graph(modules)
        assert result["dependency_issues"] == 0

    def test_singleton(self):
        assert get_arch_validator() is get_arch_validator()
