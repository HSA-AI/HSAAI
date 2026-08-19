"""HSAAI v25 — ML Decision Framework + Cross-Domain Optimizer + AI Decision Validator + Migration Standard Tests"""
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

from backend_core.observability.v25_ml_optimization import (  # noqa: E402
    AIDecisionValidator, CrossDomainOptimizer, MLDecisionFramework,
    MigrationFrameworkStandard,
    get_ai_validator, get_cross_domain, get_ml_framework, get_migration_standard,
)

@pytest.fixture(autouse=True)
def reset_singletons():
    import backend_core.observability.v25_ml_optimization as mod
    mod._ml_framework = None
    mod._cross_domain = None
    mod._ai_validator = None
    mod._migration_standard = None
    yield


# ═══ MLDecisionFramework ═══
class TestMLDecisionFramework:
    def test_collect_features_infrastructure(self):
        fw = MLDecisionFramework()
        features = fw.collect_features("infrastructure", {"cpu": 75, "memory": 60, "storage_growth": 5, "requests": 1000})
        assert features["engineered_features"]["cpu_avg"] == 75

    def test_collect_features_application(self):
        fw = MLDecisionFramework()
        features = fw.collect_features("application", {"latency_p95": 200, "error_rate": 0.02, "throughput": 500})
        assert features["engineered_features"]["latency_p95"] == 200

    def test_collect_features_ai(self):
        fw = MLDecisionFramework()
        features = fw.collect_features("ai", {"model_latency": 1200, "tokens": 500, "rag_recall": 0.92})
        assert features["engineered_features"]["model_latency"] == 1200

    def test_run_ml_inference(self):
        fw = MLDecisionFramework()
        features = fw.collect_features("infrastructure", {"cpu": 75, "memory": 60, "storage_growth": 5, "requests": 1000})
        result = fw.run_ml_inference("capacity_forecaster", features)
        assert result["model_name"] == "capacity_forecaster"
        assert "prediction" in result
        assert "confidence" in result

    def test_run_ml_inference_unknown_model_raises(self):
        fw = MLDecisionFramework()
        with pytest.raises(ValueError, match="Unknown ML model"):
            fw.run_ml_inference("unknown_model", {})

    def test_make_ml_decision_recommended(self):
        fw = MLDecisionFramework()
        features = fw.collect_features("infrastructure", {"cpu": 75, "memory": 60, "storage_growth": 5, "requests": 1000})
        decision = fw.make_ml_decision(
            "capacity_forecaster", features,
            risk_level="medium", governance_approved=True,
            explanation="CPU trending high", rollback_plan="scale_down",
        )
        assert decision["status"] == "recommended"
        assert decision["auto_executed"] if "auto_executed" in decision else decision["status"] != "executed"

    def test_make_ml_decision_executed_low_risk_autonomous(self):
        fw = MLDecisionFramework()
        fw._mode = "autonomous"
        features = fw.collect_features("infrastructure", {"cpu": 20, "memory": 30, "storage_growth": 1, "requests": 100})
        decision = fw.make_ml_decision(
            "cost_optimizer", features,
            risk_level="low", governance_approved=True,
            explanation="Low CPU at night", rollback_plan="scale_up_morning",
        )
        assert decision["status"] == "executed"

    def test_make_ml_decision_abac_denied(self):
        fw = MLDecisionFramework()
        fw._mode = "autonomous"
        features = fw.collect_features("infrastructure", {"cpu": 20, "memory": 30, "storage_growth": 1, "requests": 100})
        decision = fw.make_ml_decision(
            "cost_optimizer", features,
            risk_level="low", governance_approved=True,
            explanation="test", rollback_plan="plan",
            abac_decision={"decision": "DENY"},
        )
        assert decision["governance_approved"] is False
        assert decision["status"] == "recommended"

    def test_record_outcome(self):
        fw = MLDecisionFramework()
        features = fw.collect_features("infrastructure", {"cpu": 75, "memory": 60, "storage_growth": 5, "requests": 1000})
        decision = fw.make_ml_decision("capacity_forecaster", features,
                                         risk_level="low", governance_approved=True,
                                         explanation="test", rollback_plan="plan")
        outcome = fw.record_outcome(decision["decision_id"], success=True, impact_metrics={"latency_reduction": 30})
        assert outcome["success"] is True

    def test_record_outcome_unknown_raises(self):
        fw = MLDecisionFramework()
        with pytest.raises(ValueError, match="not found"):
            fw.record_outcome("unknown", success=True, impact_metrics={})

    def test_learning_data_collected(self):
        fw = MLDecisionFramework()
        features = fw.collect_features("infrastructure", {"cpu": 75, "memory": 60, "storage_growth": 5, "requests": 1000})
        decision = fw.make_ml_decision("capacity_forecaster", features,
                                         risk_level="low", governance_approved=True,
                                         explanation="test", rollback_plan="plan")
        fw.record_outcome(decision["decision_id"], success=True, impact_metrics={})
        assert len(fw.get_learning_data()) == 1

    def test_get_model_status(self):
        fw = MLDecisionFramework()
        status = fw.get_model_status()
        assert "capacity_forecaster" in status["models"]
        assert status["mode"] == "supervised"

    def test_singleton(self):
        assert get_ml_framework() is get_ml_framework()


# ═══ CrossDomainOptimizer ═══
class TestCrossDomainOptimizer:
    def test_identify_optimization(self):
        opt = CrossDomainOptimizer()
        result = opt.identify_optimization("infrastructure", "scaling", data={"cpu": 80})
        assert result["domain"] == "infrastructure"
        assert result["type"] == "scaling"

    def test_unknown_domain_raises(self):
        opt = CrossDomainOptimizer()
        with pytest.raises(ValueError, match="Unknown domain"):
            opt.identify_optimization("unknown", "test", data={})

    def test_unknown_optimization_raises(self):
        opt = CrossDomainOptimizer()
        with pytest.raises(ValueError, match="Unknown optimization"):
            opt.identify_optimization("infrastructure", "unknown_opt", data={})

    def test_cross_domain_effects_analyzed(self):
        opt = CrossDomainOptimizer()
        result = opt.identify_optimization("infrastructure", "scaling", data={"cpu": 80})
        assert len(result["cross_domain_effects"]) > 0

    def test_database_optimization_affects_ai(self):
        opt = CrossDomainOptimizer()
        result = opt.identify_optimization("database", "query_optimization", data={})
        effects = result["cross_domain_effects"]
        assert any(e["affected_domain"] == "ai" for e in effects)

    def test_security_optimization_has_warning(self):
        opt = CrossDomainOptimizer()
        result = opt.identify_optimization("security", "threat_response", data={})
        effects = result["cross_domain_effects"]
        assert any(e["severity"] == "warning" for e in effects)

    def test_get_optimizations_filtered(self):
        opt = CrossDomainOptimizer()
        opt.identify_optimization("infrastructure", "scaling", data={})
        opt.identify_optimization("database", "query_optimization", data={})
        infra = opt.get_optimizations(domain="infrastructure")
        assert len(infra) == 1

    def test_get_stats(self):
        opt = CrossDomainOptimizer()
        opt.identify_optimization("infrastructure", "scaling", data={})
        opt.identify_optimization("database", "query_optimization", data={})
        stats = opt.get_stats()
        assert stats["total_optimizations"] == 2
        assert "infrastructure" in stats["by_domain"]

    def test_all_6_domains_supported(self):
        opt = CrossDomainOptimizer()
        assert len(opt.DOMAINS) == 6

    def test_singleton(self):
        assert get_cross_domain() is get_cross_domain()


# ═══ AIDecisionValidator ═══
class TestAIDecisionValidator:
    def test_start_validation(self):
        v = AIDecisionValidator()
        result = v.start_validation()
        assert result["status"] == "validation_started"
        assert result["duration_days"] == 30

    def test_record_decision(self):
        v = AIDecisionValidator()
        v.record_decision({"was_correct": True, "predicted": True})

    def test_record_human_approval(self):
        v = AIDecisionValidator()
        v.record_human_approval({"reason": "manual check"})

    def test_generate_daily_report(self):
        v = AIDecisionValidator()
        v.record_decision({"was_correct": True, "predicted": True})
        report = v.generate_daily_report(1)
        assert report["day_number"] == 1
        assert report["total_decisions"] == 1

    def test_day_30_evaluates_readiness(self):
        v = AIDecisionValidator()
        report = v.generate_daily_report(30)
        assert report["recommendation"] in ("READY_FOR_FULL_AUTONOMOUS", "EXTEND_SUPERVISION")

    def test_get_validation_status_not_started(self):
        v = AIDecisionValidator()
        status = v.get_validation_status()
        assert status["status"] == "not_started"

    def test_generate_validation_incomplete(self):
        v = AIDecisionValidator()
        v.generate_daily_report(1)
        result = v.generate_validation_report()
        assert result["status"] == "incomplete"

    def test_generate_validation_complete_ready(self):
        v = AIDecisionValidator()
        for _ in range(20):
            v.record_decision({"was_correct": True, "predicted": True})
        for day in range(1, 31):
            v.generate_daily_report(day)
        result = v.generate_validation_report()
        assert result["status"] == "complete"
        assert result["readiness_decision"] == "READY_FOR_FULL_AUTONOMOUS"

    def test_generate_validation_complete_extend(self):
        v = AIDecisionValidator()
        for _ in range(20):
            v.record_decision({"was_correct": False, "predicted": True})
        for day in range(1, 31):
            v.generate_daily_report(day)
        result = v.generate_validation_report()
        assert result["readiness_decision"] == "EXTEND_SUPERVISION"

    def test_singleton(self):
        assert get_ai_validator() is get_ai_validator()


# ═══ MigrationFrameworkStandard ═══
class TestMigrationFrameworkStandard:
    def test_validate_compliant_migration(self):
        std = MigrationFrameworkStandard()
        content = '''
"""Test migration
Purpose: Add index
Safety: Use CONCURRENTLY
Rollback: DROP INDEX
"""
from typing import Sequence, Union
revision: str = "abc123"
down_revision = "def456"
def upgrade() -> None:
    op.execute("CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_test ON t (c)")
def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_test")
'''
        result = std.validate_migration(content)
        assert result["all_passed"] is True

    def test_validate_non_compliant_migration(self):
        std = MigrationFrameworkStandard()
        content = "revision = 'abc'\ndef upgrade(): pass"
        result = std.validate_migration(content)
        assert result["all_passed"] is False
        assert result["failed"] > 0

    def test_get_summary(self):
        std = MigrationFrameworkStandard()
        std.validate_migration("revision: str = 'abc'\ndef upgrade() -> None: pass\ndef downgrade() -> None: pass")
        summary = std.get_summary()
        assert summary["total_validations"] == 1

    def test_singleton(self):
        assert get_migration_standard() is get_migration_standard()
