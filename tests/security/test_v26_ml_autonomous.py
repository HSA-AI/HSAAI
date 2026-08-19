"""HSAAI v26 — Predictive Incident Prevention + Self-Evolving Models + Low-Risk Executor + Internal Platform Tests"""
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

from backend_core.observability.v26_ml_autonomous import (  # noqa: E402
    AutonomousLowRiskExecutor, InternalEnterpriseAIPlatform,
    PredictiveIncidentPrevention, SelfEvolvingModelFramework,
    get_incident_prevention, get_internal_platform, get_low_risk_executor, get_model_framework,
)

@pytest.fixture(autouse=True)
def reset_singletons():
    import backend_core.observability.v26_ml_autonomous as mod
    mod._incident_prevention = None
    mod._model_framework = None
    mod._low_risk_executor = None
    mod._internal_platform = None
    yield


# ═══ PredictiveIncidentPrevention ═══
class TestPredictiveIncidentPrevention:
    def test_ingest_telemetry(self):
        pip = PredictiveIncidentPrevention()
        pip.ingest_telemetry("rag-engine", {"cpu": 75, "latency": 200})
        assert len(pip._telemetry_buffer["rag-engine"]) == 1

    def test_predict_incident(self):
        pip = PredictiveIncidentPrevention()
        result = pip.predict_incident(
            "service_failure", confidence=0.90, risk_score=65,
            explanation="Latency trending up", recommended_prevention="scale_resources",
            time_to_incident_hours=12,
        )
        assert result["target"] == "service_failure"
        assert result["confidence"] == 0.90
        assert result["risk_level"] == "high"

    def test_unknown_target_raises(self):
        pip = PredictiveIncidentPrevention()
        with pytest.raises(ValueError, match="Unknown prediction target"):
            pip.predict_incident("unknown", confidence=0.9, risk_score=50,
                                   explanation="", recommended_prevention="")

    def test_evaluate_prevention_auto_execute_low_risk(self):
        pip = PredictiveIncidentPrevention()
        prediction = pip.predict_incident(
            "capacity_shortage", confidence=0.90, risk_score=15,
            explanation="Storage growing", recommended_prevention="add_storage",
        )
        prevention = pip.evaluate_prevention(prediction, governance_approved=True, rollback_plan="remove storage")
        assert prevention["auto_executed"] is True
        assert prevention["status"] == "executed"

    def test_evaluate_prevention_high_risk_recommended(self):
        pip = PredictiveIncidentPrevention()
        prediction = pip.predict_incident(
            "service_failure", confidence=0.90, risk_score=65,
            explanation="Service degraded", recommended_prevention="restart_service",
        )
        prevention = pip.evaluate_prevention(prediction, governance_approved=True, rollback_plan="plan")
        assert prevention["auto_executed"] is False
        assert prevention["status"] == "recommended"

    def test_evaluate_prevention_abac_denied(self):
        pip = PredictiveIncidentPrevention()
        prediction = pip.predict_incident(
            "capacity_shortage", confidence=0.90, risk_score=15,
            explanation="test", recommended_prevention="add_storage",
        )
        prevention = pip.evaluate_prevention(prediction, governance_approved=True,
                                              abac_decision={"decision": "DENY"}, rollback_plan="plan")
        assert prevention["governance_approved"] is False

    def test_evaluate_prevention_no_rollback_blocks(self):
        pip = PredictiveIncidentPrevention()
        prediction = pip.predict_incident(
            "capacity_shortage", confidence=0.90, risk_score=15,
            explanation="test", recommended_prevention="add_storage",
        )
        prevention = pip.evaluate_prevention(prediction, governance_approved=True, rollback_plan="")
        assert prevention["auto_executed"] is False

    def test_get_stats(self):
        pip = PredictiveIncidentPrevention()
        pip.predict_incident("service_failure", confidence=0.9, risk_score=50,
                               explanation="", recommended_prevention="")
        stats = pip.get_stats()
        assert stats["total_predictions"] == 1

    def test_singleton(self):
        assert get_incident_prevention() is get_incident_prevention()


# ═══ SelfEvolvingModelFramework ═══
class TestSelfEvolvingModelFramework:
    def test_register_model(self):
        fw = SelfEvolvingModelFramework()
        model = fw.register_model("m1", name="Capacity Forecaster", model_type="linear_regression")
        assert model["model_id"] == "m1"
        assert model["lifecycle_stage"] == "training"

    def test_register_duplicate_raises(self):
        fw = SelfEvolvingModelFramework()
        fw.register_model("m1", name="Test", model_type="test")
        with pytest.raises(ValueError, match="already registered"):
            fw.register_model("m1", name="Test", model_type="test")

    def test_evaluate_model_passes(self):
        fw = SelfEvolvingModelFramework()
        fw.register_model("m1", name="Test", model_type="test")
        result = fw.evaluate_model("m1", accuracy=0.90, confidence=0.85, drift_score=0.05)
        assert result["gates_passed"] is True

    def test_evaluate_model_fails_low_accuracy(self):
        fw = SelfEvolvingModelFramework()
        fw.register_model("m1", name="Test", model_type="test")
        result = fw.evaluate_model("m1", accuracy=0.70, confidence=0.85, drift_score=0.05)
        assert result["gates_passed"] is False

    def test_evaluate_model_drift_alert(self):
        fw = SelfEvolvingModelFramework()
        fw.register_model("m1", name="Test", model_type="test")
        fw.evaluate_model("m1", accuracy=0.90, confidence=0.85, drift_score=0.15)
        alerts = fw.get_drift_alerts()
        assert len(alerts) == 1

    def test_deploy_model(self):
        fw = SelfEvolvingModelFramework()
        fw.register_model("m1", name="Test", model_type="test")
        fw.evaluate_model("m1", accuracy=0.90, confidence=0.85, drift_score=0.05)
        result = fw.deploy_model("m1", governance_approved=True, version="2.0.0")
        assert result["deployed"] is True
        assert result["new_version"] == "2.0.0"

    def test_deploy_without_governance_fails(self):
        fw = SelfEvolvingModelFramework()
        fw.register_model("m1", name="Test", model_type="test")
        fw.evaluate_model("m1", accuracy=0.90, confidence=0.85, drift_score=0.05)
        result = fw.deploy_model("m1", governance_approved=False, version="2.0.0")
        assert result["deployed"] is False

    def test_rollback_model(self):
        fw = SelfEvolvingModelFramework()
        fw.register_model("m1", name="Test", model_type="test", version="1.0.0")
        fw.evaluate_model("m1", accuracy=0.90, confidence=0.85, drift_score=0.05)
        fw.deploy_model("m1", governance_approved=True, version="2.0.0")
        result = fw.rollback_model("m1")
        assert result["rolled_back_to"] == "1.0.0"

    def test_rollback_no_previous_raises(self):
        fw = SelfEvolvingModelFramework()
        fw.register_model("m1", name="Test", model_type="test")
        with pytest.raises(ValueError, match="No previous version"):
            fw.rollback_model("m1")

    def test_get_version_history(self):
        fw = SelfEvolvingModelFramework()
        fw.register_model("m1", name="Test", model_type="test", version="1.0.0")
        fw.evaluate_model("m1", accuracy=0.90, confidence=0.85, drift_score=0.05)
        fw.deploy_model("m1", governance_approved=True, version="2.0.0")
        history = fw.get_version_history("m1")
        assert len(history) == 2

    def test_singleton(self):
        assert get_model_framework() is get_model_framework()


# ═══ AutonomousLowRiskExecutor ═══
class TestAutonomousLowRiskExecutor:
    def test_evaluate_allowed_action_executes(self):
        ex = AutonomousLowRiskExecutor()
        result = ex.evaluate_decision(
            "cache_optimization", confidence=0.90, model_version="1.0",
            input_features={"hit_rate": 0.5}, expected_impact="improved latency",
            rollback_plan="revert cache size",
        )
        assert result.get("auto_executed") is True
        assert result["status"] == "executed"

    def test_forbidden_action_rejected(self):
        ex = AutonomousLowRiskExecutor()
        result = ex.evaluate_decision(
            "data_deletion", confidence=0.99, model_version="1.0",
            input_features={}, expected_impact="",
            rollback_plan="plan",
        )
        assert result.get("rejected") is True
        assert "forbidden" in result["reason"]

    def test_unknown_action_rejected(self):
        ex = AutonomousLowRiskExecutor()
        result = ex.evaluate_decision(
            "unknown_action", confidence=0.90, model_version="1.0",
            input_features={}, expected_impact="",
            rollback_plan="plan",
        )
        assert result.get("rejected") is True

    def test_low_confidence_rejected(self):
        ex = AutonomousLowRiskExecutor()
        result = ex.evaluate_decision(
            "cache_optimization", confidence=0.50, model_version="1.0",
            input_features={}, expected_impact="",
            rollback_plan="plan",
        )
        assert result.get("rejected") is True
        assert "below threshold" in result["reason"]

    def test_no_rollback_rejected(self):
        ex = AutonomousLowRiskExecutor()
        result = ex.evaluate_decision(
            "cache_optimization", confidence=0.90, model_version="1.0",
            input_features={}, expected_impact="",
            rollback_plan="",
        )
        assert result.get("rejected") is True
        assert "Rollback" in result["reason"]

    def test_no_governance_rejected(self):
        ex = AutonomousLowRiskExecutor()
        result = ex.evaluate_decision(
            "cache_optimization", confidence=0.90, model_version="1.0",
            input_features={}, expected_impact="",
            rollback_plan="plan", governance_approved=False,
        )
        assert result.get("rejected") is True

    def test_get_stats(self):
        ex = AutonomousLowRiskExecutor()
        ex.evaluate_decision("cache_optimization", confidence=0.90, model_version="1.0",
                               input_features={}, expected_impact="", rollback_plan="plan")
        stats = ex.get_stats()
        assert stats["total_executions"] == 1
        assert "cache_optimization" in stats["allowed_actions"]

    def test_singleton(self):
        assert get_low_risk_executor() is get_low_risk_executor()


# ═══ InternalEnterpriseAIPlatform ═══
class TestInternalEnterpriseAIPlatform:
    def test_platform_identity(self):
        p = InternalEnterpriseAIPlatform()
        spec = p.get_platform_spec()
        assert spec["platform"] == "HSAAI Internal Enterprise AI Operating System"
        assert spec["version"] == "26.0.0"

    def test_core_services(self):
        p = InternalEnterpriseAIPlatform()
        assert len(p.CORE_SERVICES) == 11

    def test_department_agents(self):
        p = InternalEnterpriseAIPlatform()
        assert len(p.DEPARTMENT_AGENTS) == 6

    def test_operating_modes(self):
        p = InternalEnterpriseAIPlatform()
        modes = p.get_operating_modes()
        assert "SUPERVISED" in modes
        assert "ASSISTED" in modes
        assert "AUTONOMOUS" in modes

    def test_applications(self):
        p = InternalEnterpriseAIPlatform()
        apps = p.get_applications()
        assert "APP-ADMIN" in apps
        assert "APP-AI-STUDIO" in apps
        assert len(apps) == 6

    def test_security_model(self):
        p = InternalEnterpriseAIPlatform()
        security = p.get_security_model()
        assert security["authentication"]["mfa"] is True
        assert "RBAC" in security["authorization"]["models"]

    def test_priority_order(self):
        p = InternalEnterpriseAIPlatform()
        assert p.PRIORITY_ORDER[0] == "Security"
        assert p.PRIORITY_ORDER[1] == "Data Privacy"

    def test_backward_compatible(self):
        p = InternalEnterpriseAIPlatform()
        spec = p.get_platform_spec()
        assert spec["backward_compatible_with"] == "v7 architecture"

    def test_singleton(self):
        assert get_internal_platform() is get_internal_platform()
