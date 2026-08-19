"""HSAAI v24 — AI Decision Engine + Self-Healing Validation + Capacity Validation + env.py Validation Tests"""
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

from backend_core.observability.v24_decision_engine import (  # noqa: E402
    AIDecisionEngine, EnvPyRefactorValidator, PredictiveCapacityValidator,
    SupervisedSelfHealingValidator,
    get_capacity_validator, get_decision_engine, get_env_validator, get_healing_validator,
)

@pytest.fixture(autouse=True)
def reset_singletons():
    import backend_core.observability.v24_decision_engine as mod
    mod._decision_engine = None
    mod._healing_validator = None
    mod._capacity_validator = None
    mod._env_validator = None
    yield


# ═══ AIDecisionEngine ═══
class TestAIDecisionEngine:
    def test_observe(self):
        engine = AIDecisionEngine()
        result = engine.observe("infrastructure", {"cpu": 75})
        assert result["domain"] == "infrastructure"

    def test_make_decision_recommended(self):
        engine = AIDecisionEngine()
        result = engine.make_decision(
            "resource_optimization",
            analysis={"cpu_trend": "increasing"},
            prediction={"forecast": "85% in 24h"},
            risk_level="medium",
            governance_approved=True,
            explanation="CPU trending high",
            recommended_action="scale_up",
            rollback_plan="scale_down",
        )
        assert result["status"] == "recommended"
        assert result["auto_executed"] is False

    def test_make_decision_executed_low_risk_autonomous(self):
        engine = AIDecisionEngine()
        engine._mode = "autonomous"
        result = engine.make_decision(
            "cost_optimization",
            analysis={"night_cpu": "15%"},
            prediction={"savings": "$500/month"},
            risk_level="low",
            governance_approved=True,
            explanation="Night CPU below 30%",
            recommended_action="scale_down_night",
            rollback_plan="scale_up_morning",
            auto_execute=True,
        )
        assert result["status"] == "executed"
        assert result["auto_executed"] is True

    def test_make_decision_abac_denied(self):
        engine = AIDecisionEngine()
        engine._mode = "autonomous"
        result = engine.make_decision(
            "resource_optimization",
            analysis={}, prediction={}, risk_level="low",
            governance_approved=True, explanation="test",
            recommended_action="scale", rollback_plan="plan",
            abac_decision={"decision": "DENY"}, auto_execute=True,
        )
        assert result["status"] == "recommended"
        assert result["governance_approved"] is False

    def test_unknown_decision_type_raises(self):
        engine = AIDecisionEngine()
        with pytest.raises(ValueError, match="Unknown decision type"):
            engine.make_decision("unknown", analysis={}, prediction={},
                                   risk_level="low", governance_approved=True,
                                   explanation="", recommended_action="", rollback_plan="")

    def test_verify_decision(self):
        engine = AIDecisionEngine()
        decision = engine.make_decision(
            "performance_optimization",
            analysis={}, prediction={}, risk_level="low",
            governance_approved=True, explanation="test",
            recommended_action="optimize", rollback_plan="plan",
        )
        verification = engine.verify_decision(decision["decision_id"], outcome={"success": True})
        assert verification["success"] is True

    def test_verify_unknown_decision_raises(self):
        engine = AIDecisionEngine()
        with pytest.raises(ValueError, match="not found"):
            engine.verify_decision("unknown", outcome={})

    def test_knowledge_base_updated(self):
        engine = AIDecisionEngine()
        decision = engine.make_decision(
            "cost_optimization", analysis={}, prediction={},
            risk_level="low", governance_approved=True, explanation="",
            recommended_action="", rollback_plan="",
        )
        engine.verify_decision(decision["decision_id"], outcome={"success": True})
        kb = engine.get_knowledge_base()
        assert len(kb) == 1

    def test_get_stats(self):
        engine = AIDecisionEngine()
        engine.make_decision("cost_optimization", analysis={}, prediction={},
                               risk_level="low", governance_approved=True, explanation="",
                               recommended_action="", rollback_plan="")
        stats = engine.get_stats()
        assert stats["total_decisions"] == 1

    def test_singleton(self):
        assert get_decision_engine() is get_decision_engine()


# ═══ SupervisedSelfHealingValidator ═══
class TestSupervisedSelfHealingValidator:
    def test_start_validation(self):
        v = SupervisedSelfHealingValidator()
        result = v.start_validation()
        assert result["status"] == "validation_started"
        assert result["duration_days"] == 30

    def test_record_recovery(self):
        v = SupervisedSelfHealingValidator()
        v.record_recovery({"action": "restart", "success": True})

    def test_record_human_intervention(self):
        v = SupervisedSelfHealingValidator()
        v.record_human_intervention({"reason": "manual override"})

    def test_generate_daily_report(self):
        v = SupervisedSelfHealingValidator()
        v.record_recovery({"action": "restart", "success": True})
        report = v.generate_daily_report(1)
        assert report["day_number"] == 1
        assert report["total_recoveries"] == 1

    def test_day_30_evaluates_readiness(self):
        v = SupervisedSelfHealingValidator()
        report = v.generate_daily_report(30)
        assert report["recommendation"] in ("READY_FOR_FULL_AUTONOMOUS", "EXTEND_SUPERVISION")

    def test_get_validation_status_not_started(self):
        v = SupervisedSelfHealingValidator()
        status = v.get_validation_status()
        assert status["status"] == "not_started"

    def test_generate_validation_incomplete(self):
        v = SupervisedSelfHealingValidator()
        v.generate_daily_report(1)
        result = v.generate_validation_report()
        assert result["status"] == "incomplete"

    def test_generate_validation_complete_ready(self):
        v = SupervisedSelfHealingValidator()
        for _ in range(20):
            v.record_recovery({"action": "scale", "success": True})
        for day in range(1, 31):
            v.generate_daily_report(day)
        result = v.generate_validation_report()
        assert result["status"] == "complete"
        assert result["readiness_decision"] == "READY_FOR_FULL_AUTONOMOUS"

    def test_generate_validation_complete_extend(self):
        v = SupervisedSelfHealingValidator()
        for _ in range(20):
            v.record_recovery({"action": "scale", "success": False})
        for day in range(1, 31):
            v.generate_daily_report(day)
            v.record_human_intervention({"reason": "failure"})
        result = v.generate_validation_report()
        assert result["readiness_decision"] == "EXTEND_SUPERVISION"

    def test_singleton(self):
        assert get_healing_validator() is get_healing_validator()


# ═══ PredictiveCapacityValidator ═══
class TestPredictiveCapacityValidator:
    def test_start_validation(self):
        v = PredictiveCapacityValidator()
        result = v.start_validation()
        assert result["status"] == "validation_started"
        assert result["duration_days"] == 14

    def test_record_prediction_and_actual(self):
        v = PredictiveCapacityValidator()
        v.record_prediction("cpu_percent", 75.0, "24h")
        v.record_actual("cpu_percent", 73.0)

    def test_generate_daily_report(self):
        v = PredictiveCapacityValidator()
        v.record_prediction("cpu", 75.0, "24h")
        v.record_actual("cpu", 73.0)
        report = v.generate_daily_report(1)
        assert report["day_number"] == 1
        assert "accuracy" in report

    def test_day_14_evaluates_readiness(self):
        v = PredictiveCapacityValidator()
        report = v.generate_daily_report(14)
        assert report["recommendation"] in ("APPROVED_FOR_PRODUCTION", "NEEDS_ADDITIONAL_TUNING")

    def test_get_validation_status_not_started(self):
        v = PredictiveCapacityValidator()
        status = v.get_validation_status()
        assert status["status"] == "not_started"

    def test_generate_validation_incomplete(self):
        v = PredictiveCapacityValidator()
        v.generate_daily_report(1)
        result = v.generate_validation_report()
        assert result["status"] == "incomplete"

    def test_generate_validation_complete(self):
        v = PredictiveCapacityValidator()
        for _ in range(10):
            v.record_prediction("cpu", 75.0, "24h")
            v.record_actual("cpu", 75.0)
        for day in range(1, 15):
            v.generate_daily_report(day)
        result = v.generate_validation_report()
        assert result["status"] == "complete"
        assert result["readiness_decision"] == "APPROVED_FOR_PRODUCTION"

    def test_singleton(self):
        assert get_capacity_validator() is get_capacity_validator()


# ═══ EnvPyRefactorValidator ═══
class TestEnvPyRefactorValidator:
    def test_validate_all_present(self):
        v = EnvPyRefactorValidator()
        content = """
        compare_type=True
        compare_server_default=True
        include_object=include_object
        NAMING_CONVENTION={}
        pool_pre_ping=True
        statement_timeout=300000
        sslmode=require
        app.tenant_id
        logging.getLogger
        os.getenv
        """
        result = v.validate(content)
        assert result["all_passed"] is True
        assert result["passed"] == 10

    def test_validate_missing_some(self):
        v = EnvPyRefactorValidator()
        content = "compare_type=True\npool_pre_ping=True"
        result = v.validate(content)
        assert result["all_passed"] is False
        assert result["failed"] > 0

    def test_get_summary(self):
        v = EnvPyRefactorValidator()
        v.validate("compare_type=True")
        summary = v.get_summary()
        assert summary["total_improvements"] == 10

    def test_singleton(self):
        assert get_env_validator() is get_env_validator()
