"""HSAAI v20.1 — Full Autonomous Mode + Migration Executor + 90-Day Observation Tests"""
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

from backend_core.observability.v20_1_full_autonomous import (  # noqa: E402
    EnterpriseObservationPeriod, FullAutonomousMode, MigrationExecutor,
    get_enterprise_observation, get_full_autonomous, get_migration_executor,
)

@pytest.fixture(autouse=True)
def reset_singletons():
    import backend_core.observability.v20_1_full_autonomous as mod
    mod._full_autonomous = None
    mod._migration_executor = None
    mod._enterprise_observation = None
    yield


# ═══ FullAutonomousMode ═══
class TestFullAutonomousMode:
    def test_initial_state_disabled(self):
        mode = FullAutonomousMode()
        assert mode.is_enabled is False
        assert mode.mode == "full_autonomous"

    def test_activate_requires_all_prerequisites(self):
        mode = FullAutonomousMode()
        result = mode.activate(approval_data={
            "supervised_period_complete": False,
            "supervision_approved": True,
            "migrations_applied": 7,
            "security_tests_passed": True,
            "governance_approval": True,
        })
        assert result["activated"] is False
        assert "supervised_period_complete" in result["reason"]

    def test_activate_succeeds_with_all_prerequisites(self):
        mode = FullAutonomousMode()
        result = mode.activate(approval_data={
            "supervised_period_complete": True,
            "supervision_approved": True,
            "migrations_applied": 7,
            "security_tests_passed": True,
            "governance_approval": True,
            "approver": "governance-committee",
        })
        assert result["activated"] is True
        assert result["mode"] == "full_autonomous"
        assert len(result["capabilities"]) == 8

    def test_activate_requires_7_migrations(self):
        mode = FullAutonomousMode()
        result = mode.activate(approval_data={
            "supervised_period_complete": True,
            "supervision_approved": True,
            "migrations_applied": 6,  # Only 6
            "security_tests_passed": True,
            "governance_approval": True,
        })
        assert result["activated"] is False

    def test_record_autonomous_action(self):
        mode = FullAutonomousMode()
        mode.activate(approval_data={
            "supervised_period_complete": True, "supervision_approved": True,
            "migrations_applied": 7, "security_tests_passed": True, "governance_approval": True,
        })
        result = mode.record_autonomous_action({
            "action_type": "autonomous_scaling",
            "target": "rag-engine",
            "explanation": "Scaled up due to increased load",
        })
        assert "action_id" in result
        assert result["governance_enforced"] is True
        assert result["audit_logged"] is True

    def test_record_action_when_disabled_returns_false(self):
        mode = FullAutonomousMode()
        result = mode.record_autonomous_action({"action_type": "test"})
        assert result["recorded"] is False

    def test_get_stats(self):
        mode = FullAutonomousMode()
        mode.activate(approval_data={
            "supervised_period_complete": True, "supervision_approved": True,
            "migrations_applied": 7, "security_tests_passed": True, "governance_approval": True,
        })
        stats = mode.get_stats()
        assert stats["mode"] == "full_autonomous"
        assert stats["enabled"] is True
        assert stats["governance_enforced"] is True

    def test_singleton(self):
        assert get_full_autonomous() is get_full_autonomous()


# ═══ MigrationExecutor ═══
class TestMigrationExecutor:
    def _create_migrations(self):
        return [
            {"id": "001", "name": "Add Indexes", "risk": "low", "operations": ["CREATE INDEX"], "rollback": ["DROP INDEX"], "tables_affected": ["t1"]},
            {"id": "002", "name": "Enable RLS", "risk": "medium", "operations": ["ALTER TABLE ENABLE RLS"], "rollback": ["ALTER TABLE DISABLE RLS"], "tables_affected": ["t1"]},
            {"id": "003", "name": "Add CHECK", "risk": "low", "operations": ["ADD CONSTRAINT"], "rollback": ["DROP CONSTRAINT"], "tables_affected": ["t1"]},
        ]

    @pytest.mark.asyncio
    async def test_execute_all_success(self):
        executor = MigrationExecutor()
        for m in self._create_migrations():
            executor.register_migration(m)
        result = await executor.execute_all()
        assert result["total_migrations"] == 3
        assert result["executed"] == 3
        assert result["failed"] == 0
        assert result["halted"] is False

    @pytest.mark.asyncio
    async def test_reports_generated(self):
        executor = MigrationExecutor()
        for m in self._create_migrations():
            executor.register_migration(m)
        await executor.execute_all()
        reports = executor.get_reports()
        assert len(reports) == 3

    @pytest.mark.asyncio
    async def test_final_validation(self):
        executor = MigrationExecutor()
        for m in self._create_migrations():
            executor.register_migration(m)
        await executor.execute_all()
        final = executor.get_final_validation()
        assert final["all_passed"] is True
        assert final["successful"] == 3

    @pytest.mark.asyncio
    async def test_empty_migrations(self):
        executor = MigrationExecutor()
        result = await executor.execute_all()
        assert result["total_migrations"] == 0

    def test_singleton(self):
        assert get_migration_executor() is get_migration_executor()


# ═══ EnterpriseObservationPeriod ═══
class TestEnterpriseObservation:
    def test_start_observation(self):
        period = EnterpriseObservationPeriod()
        result = period.start_observation()
        assert result["status"] == "observation_started"
        assert result["duration_days"] == 90

    def test_generate_daily_report(self):
        period = EnterpriseObservationPeriod()
        period.start_observation()
        report = period.generate_daily_report(1)
        assert report["day_number"] == 1
        assert "infrastructure" in report
        assert "application" in report
        assert "ai_models" in report
        assert "security" in report
        assert "aiops" in report

    def test_weekly_report_generated_every_7_days(self):
        period = EnterpriseObservationPeriod()
        period.start_observation()
        period.generate_daily_report(7)
        assert len(period._weekly_reports) == 1

    def test_monthly_report_generated_every_30_days(self):
        period = EnterpriseObservationPeriod()
        period.start_observation()
        period.generate_daily_report(30)
        assert len(period._monthly_reports) == 1

    def test_day_90_evaluates_certification(self):
        period = EnterpriseObservationPeriod()
        period.start_observation()
        for day in range(1, 91):
            period.generate_daily_report(day)
        report = period._daily_reports[-1]
        assert "final_decision" in report
        assert report["final_decision"] in ("ENTERPRISE_CERTIFIED", "NEEDS_IMPROVEMENT")

    def test_get_observation_status_not_started(self):
        period = EnterpriseObservationPeriod()
        status = period.get_observation_status()
        assert status["status"] == "not_started"

    def test_get_observation_status_in_progress(self):
        period = EnterpriseObservationPeriod()
        period.start_observation()
        status = period.get_observation_status()
        assert status["status"] == "in_progress"

    def test_generate_90_day_summary_incomplete(self):
        period = EnterpriseObservationPeriod()
        period.generate_daily_report(1)
        summary = period.generate_90_day_summary()
        assert summary["status"] == "incomplete"

    def test_generate_90_day_summary_complete(self):
        period = EnterpriseObservationPeriod()
        period.start_observation()
        for day in range(1, 91):
            period.generate_daily_report(day)
        summary = period.generate_90_day_summary()
        assert summary["status"] == "complete"
        assert summary["decision"] == "ENTERPRISE_CERTIFIED"

    def test_singleton(self):
        assert get_enterprise_observation() is get_enterprise_observation()
