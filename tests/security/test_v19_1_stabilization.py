"""HSAAI v19.1 — DB Migrations + Critical Remediation + AIOps Supervision Tests"""
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

from backend_core.observability.v19_1_stabilization import (  # noqa: E402
    AIOpsSupervisionPeriod, CriticalRiskRemediation, CriticalRiskRemediationError,
    DatabaseMaturityMigrations,
    get_aiops_supervision, get_critical_remediation, get_db_migrations,
)

@pytest.fixture(autouse=True)
def reset_singletons():
    import backend_core.observability.v19_1_stabilization as mod
    mod._db_migrations = None
    mod._critical_remediation = None
    mod._aiops_supervision = None
    yield


# ═══ DatabaseMaturityMigrations ═══
class TestDatabaseMigrations:
    def test_7_migrations_defined(self):
        mgr = DatabaseMaturityMigrations()
        assert len(mgr.MIGRATIONS) == 7

    def test_all_migrations_have_required_fields(self):
        mgr = DatabaseMaturityMigrations()
        required = {"id", "name", "description", "risk", "operations", "rollback"}
        for m in mgr.MIGRATIONS:
            missing = required - set(m.keys())
            assert not missing, f"Migration {m.get('id')} missing: {missing}"

    def test_all_migrations_have_rollback(self):
        mgr = DatabaseMaturityMigrations()
        for m in mgr.MIGRATIONS:
            assert len(m["rollback"]) > 0, f"Migration {m['id']} has no rollback"

    def test_validate_migration_valid(self):
        mgr = DatabaseMaturityMigrations()
        result = mgr.validate_migration(mgr.MIGRATIONS[0])
        assert result["valid"] is True

    def test_validate_all(self):
        mgr = DatabaseMaturityMigrations()
        result = mgr.validate_all()
        assert result["total_migrations"] == 7
        assert result["valid_migrations"] == 7

    def test_simulate_apply(self):
        mgr = DatabaseMaturityMigrations()
        result = mgr.simulate_apply("001_add_indexes")
        assert result["status"] == "applied"

    def test_simulate_apply_unknown_raises(self):
        mgr = DatabaseMaturityMigrations()
        result = mgr.simulate_apply("unknown")
        assert result["status"] == "error"

    def test_simulate_rollback(self):
        mgr = DatabaseMaturityMigrations()
        result = mgr.simulate_rollback("001_add_indexes")
        assert result["status"] == "rolled_back"

    def test_apply_all(self):
        mgr = DatabaseMaturityMigrations()
        results = mgr.apply_all()
        assert len(results) == 7
        assert all(r["status"] == "applied" for r in results)

    def test_get_summary(self):
        mgr = DatabaseMaturityMigrations()
        mgr.apply_all()
        summary = mgr.get_summary()
        assert summary["total_migrations"] == 7
        assert summary["applied"] == 7

    def test_singleton(self):
        assert get_db_migrations() is get_db_migrations()


# ═══ CriticalRiskRemediation ═══
class TestCriticalRiskRemediation:
    @pytest.mark.asyncio
    async def test_request_approval_creates_pending(self):
        mgr = CriticalRiskRemediation()
        result = mgr.request_approval(
            "rollback_config", "svc-1",
            incident={"issue": "bad config"},
            rca={"root_cause": "misconfiguration"},
            prediction={"governance_approved": True, "confidence": 0.95, "risk_level": "critical"},
            abac_decision={"decision": "ALLOW"},
            rollback_plan="restore previous config",
            requester="auto-remediation-engine",
        )
        assert result["status"] == "pending_approval"
        assert result["action"] == "rollback_config"

    @pytest.mark.asyncio
    async def test_request_approval_abac_denied_raises(self):
        mgr = CriticalRiskRemediation()
        with pytest.raises(CriticalRiskRemediationError, match="ABAC denied"):
            mgr.request_approval(
                "rollback_config", "svc",
                incident={}, rca={}, prediction={"governance_approved": True},
                abac_decision={"decision": "DENY"},
                rollback_plan="plan", requester="system",
            )

    @pytest.mark.asyncio
    async def test_request_approval_unapproved_prediction_raises(self):
        mgr = CriticalRiskRemediation()
        with pytest.raises(CriticalRiskRemediationError, match="not governance-approved"):
            mgr.request_approval(
                "rollback_config", "svc",
                incident={}, rca={}, prediction={"governance_approved": False},
                abac_decision={"decision": "ALLOW"},
                rollback_plan="plan", requester="system",
            )

    @pytest.mark.asyncio
    async def test_request_approval_no_rollback_plan_raises(self):
        mgr = CriticalRiskRemediation()
        with pytest.raises(CriticalRiskRemediationError, match="Rollback plan required"):
            mgr.request_approval(
                "rollback_config", "svc",
                incident={}, rca={}, prediction={"governance_approved": True},
                abac_decision={"decision": "ALLOW"},
                rollback_plan="", requester="system",
            )

    @pytest.mark.asyncio
    async def test_execute_with_approval(self):
        mgr = CriticalRiskRemediation()
        async def handler(t): return {"success": True, "message": "Rolled back"}
        mgr.register_handler("rollback_config", handler)
        approval = mgr.request_approval(
            "rollback_config", "svc-1",
            incident={"issue": "bad config"}, rca={"root_cause": "misconfiguration"},
            prediction={"governance_approved": True, "confidence": 0.95, "risk_level": "critical"},
            abac_decision={"decision": "ALLOW"},
            rollback_plan="restore previous config",
            requester="system",
        )
        result = await mgr.execute_with_approval(approval["approval_id"], approver="admin@hsaai.group")
        assert result["status"] == "completed"
        assert result["post_incident_review_required"] is True

    @pytest.mark.asyncio
    async def test_execute_without_approval_raises(self):
        mgr = CriticalRiskRemediation()
        with pytest.raises(CriticalRiskRemediationError, match="not found"):
            await mgr.execute_with_approval("nonexistent", approver="admin")

    @pytest.mark.asyncio
    async def test_execute_without_approver_raises(self):
        mgr = CriticalRiskRemediation()
        approval = mgr.request_approval(
            "rollback_config", "svc",
            incident={}, rca={}, prediction={"governance_approved": True},
            abac_decision={"decision": "ALLOW"},
            rollback_plan="plan", requester="system",
        )
        with pytest.raises(CriticalRiskRemediationError, match="MANDATORY"):
            await mgr.execute_with_approval(approval["approval_id"], approver="")

    def test_cancel_approval(self):
        mgr = CriticalRiskRemediation()
        approval = mgr.request_approval(
            "rollback_config", "svc",
            incident={}, rca={}, prediction={"governance_approved": True},
            abac_decision={"decision": "ALLOW"},
            rollback_plan="plan", requester="system",
        )
        result = mgr.cancel_approval(approval["approval_id"], cancelled_by="admin")
        assert result["status"] == "cancelled"

    def test_get_pending_approvals(self):
        mgr = CriticalRiskRemediation()
        mgr.request_approval(
            "rollback_config", "svc",
            incident={}, rca={}, prediction={"governance_approved": True},
            abac_decision={"decision": "ALLOW"},
            rollback_plan="plan", requester="system",
        )
        pending = mgr.get_pending_approvals()
        assert len(pending) == 1

    def test_get_stats(self):
        mgr = CriticalRiskRemediation()
        stats = mgr.get_stats()
        assert stats["max_per_day"] == 2
        assert "rollback_config" in stats["allowed_actions"]

    def test_singleton(self):
        assert get_critical_remediation() is get_critical_remediation()


# ═══ AIOpsSupervisionPeriod ═══
class TestAIOpsSupervision:
    def test_start_supervision(self):
        period = AIOpsSupervisionPeriod()
        result = period.start_supervision()
        assert result["status"] == "supervision_started"
        assert result["duration_days"] == 30
        assert result["mode"] == "supervised_autonomous"

    def test_generate_daily_report(self):
        period = AIOpsSupervisionPeriod()
        report = period.generate_daily_report(1)
        assert report["day_number"] == 1
        assert report["mode"] == "supervised_autonomous"
        assert "infrastructure" in report
        assert "application" in report
        assert "ai_platform" in report
        assert "security" in report
        assert "operations" in report

    def test_daily_report_day_30_recommends(self):
        period = AIOpsSupervisionPeriod()
        report = period.generate_daily_report(30)
        assert report["recommendation"] in ("READY_FOR_FULL_AUTONOMOUS", "EXTEND_SUPERVISION")

    def test_get_supervision_status_not_started(self):
        period = AIOpsSupervisionPeriod()
        status = period.get_supervision_status()
        assert status["status"] == "not_started"

    def test_get_supervision_status_in_progress(self):
        period = AIOpsSupervisionPeriod()
        period.start_supervision()
        status = period.get_supervision_status()
        assert status["status"] == "in_progress"

    def test_generate_supervision_summary_incomplete(self):
        period = AIOpsSupervisionPeriod()
        period.generate_daily_report(1)
        summary = period.generate_supervision_summary()
        assert summary["status"] == "incomplete"

    def test_generate_supervision_summary_complete(self):
        period = AIOpsSupervisionPeriod()
        for day in range(1, 31):
            period.generate_daily_report(day)
        summary = period.generate_supervision_summary()
        assert summary["status"] == "complete"
        assert summary["readiness_recommendation"] == "READY_FOR_FULL_AUTONOMOUS"

    def test_human_interventions_tracked(self):
        period = AIOpsSupervisionPeriod()
        period.start_supervision()
        period.record_human_intervention({"reason": "manual override", "by": "operator"})
        status = period.get_supervision_status()
        assert status["human_interventions"] == 1

    def test_high_intervention_rate_extends_supervision(self):
        period = AIOpsSupervisionPeriod()
        for day in range(1, 31):
            period.generate_daily_report(day)
            if day % 3 == 0:  # Intervene every 3 days = ~10 interventions
                period.record_human_intervention({"reason": "test"})
        summary = period.generate_supervision_summary()
        assert summary["readiness_recommendation"] == "EXTEND_SUPERVISION"

    def test_singleton(self):
        assert get_aiops_supervision() is get_aiops_supervision()
