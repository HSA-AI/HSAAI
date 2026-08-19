"""
HSAAI v13 — ABAC Policy Engine & Bias Detection Scheduler Test Suite
=====================================================================
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import pytest

_BASE = Path(__file__).resolve().parents[2]
_SERVICES = _BASE / "services"
for _p in [str(_SERVICES), str(_BASE / "packages"), str(_BASE / "packages" / "common")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend_core.governance.abac_policy_engine_v13 import (  # noqa: E402
    ABACDecision,
    ABACPolicy,
    ABACPolicyEngine,
    ABACPolicyError,
    BiasDetectionScheduler,
    ContinuousResponsibleAIMonitor,
    get_abac_engine,
    get_bias_scheduler,
    get_responsible_ai_monitor,
)


@pytest.fixture(autouse=True)
def reset_singletons():
    import backend_core.governance.abac_policy_engine_v13 as mod
    mod._abac_engine = None
    mod._bias_scheduler = None
    mod._responsible_ai_monitor = None
    yield


# ═══════════════════════════════════════════════════════════════════════
# 1. ABAC Policy Tests
# ═══════════════════════════════════════════════════════════════════════
class TestABACPolicy:
    """Tests for ABACPolicy class."""

    def test_policy_allow_when_all_conditions_match(self):
        policy = ABACPolicy(
            policy_id="p1",
            name="Department access",
            description="Allow access within same department",
            effect=ABACDecision.ALLOW,
            conditions=[
                {"attribute_source": "subject", "attribute": "department", "operator": "eq", "value": "finance"},
                {"attribute_source": "resource", "attribute": "department", "operator": "eq", "value": "finance"},
            ],
        )
        result = policy.evaluate(
            subject={"department": "finance"},
            resource={"department": "finance"},
            action="read",
            environment={},
        )
        assert result == ABACDecision.ALLOW

    def test_policy_not_applicable_when_condition_fails(self):
        policy = ABACPolicy(
            policy_id="p1",
            name="Department access",
            description="Allow access within same department",
            effect=ABACDecision.ALLOW,
            conditions=[
                {"attribute_source": "subject", "attribute": "department", "operator": "eq", "value": "finance"},
            ],
        )
        result = policy.evaluate(
            subject={"department": "hr"},
            resource={},
            action="read",
            environment={},
        )
        assert result == ABACDecision.NOT_APPLICABLE

    def test_policy_disabled_returns_not_applicable(self):
        policy = ABACPolicy(
            policy_id="p1",
            name="Test",
            description="Test",
            effect=ABACDecision.ALLOW,
            conditions=[],
            enabled=False,
        )
        result = policy.evaluate({}, {}, "read", {})
        assert result == ABACDecision.NOT_APPLICABLE

    def test_policy_with_gt_operator(self):
        policy = ABACPolicy(
            policy_id="p1",
            name="Clearance check",
            description="Require clearance >= 3",
            effect=ABACDecision.ALLOW,
            conditions=[
                {"attribute_source": "subject", "attribute": "clearance", "operator": "ge", "value": 3},
            ],
        )
        assert policy.evaluate({"clearance": 5}, {}, "read", {}) == ABACDecision.ALLOW
        assert policy.evaluate({"clearance": 2}, {}, "read", {}) == ABACDecision.NOT_APPLICABLE

    def test_policy_with_in_operator(self):
        policy = ABACPolicy(
            policy_id="p1",
            name="Role check",
            description="Allow admin or manager",
            effect=ABACDecision.ALLOW,
            conditions=[
                {"attribute_source": "subject", "attribute": "role", "operator": "in", "value": ["admin", "manager"]},
            ],
        )
        assert policy.evaluate({"role": "admin"}, {}, "read", {}) == ABACDecision.ALLOW
        assert policy.evaluate({"role": "user"}, {}, "read", {}) == ABACDecision.NOT_APPLICABLE

    def test_policy_with_environment_attribute(self):
        policy = ABACPolicy(
            policy_id="p1",
            name="Trusted environment",
            description="Only allow from trusted environment",
            effect=ABACDecision.ALLOW,
            conditions=[
                {"attribute_source": "environment", "attribute": "trusted", "operator": "eq", "value": True},
            ],
        )
        assert policy.evaluate({}, {}, "read", {"trusted": True}) == ABACDecision.ALLOW
        assert policy.evaluate({}, {}, "read", {"trusted": False}) == ABACDecision.NOT_APPLICABLE


# ═══════════════════════════════════════════════════════════════════════
# 2. ABAC Policy Engine Tests
# ═══════════════════════════════════════════════════════════════════════
class TestABACPolicyEngine:
    """Tests for ABACPolicyEngine."""

    def _create_test_engine(self) -> ABACPolicyEngine:
        engine = ABACPolicyEngine()
        # Allow policy: same department + sufficient clearance
        engine.create_policy(ABACPolicy(
            policy_id="allow_dept",
            name="Department Access",
            description="Allow within department",
            effect=ABACDecision.ALLOW,
            priority=100,
            conditions=[
                {"attribute_source": "subject", "attribute": "department", "operator": "eq", "value": "finance"},
                {"attribute_source": "resource", "attribute": "department", "operator": "eq", "value": "finance"},
            ],
        ))
        # Deny policy: restricted classification without high clearance
        engine.create_policy(ABACPolicy(
            policy_id="deny_restricted",
            name="Deny Restricted",
            description="Deny restricted without clearance",
            effect=ABACDecision.DENY,
            priority=50,  # Higher priority (lower number)
            conditions=[
                {"attribute_source": "resource", "attribute": "classification", "operator": "eq", "value": "restricted"},
                {"attribute_source": "subject", "attribute": "clearance", "operator": "lt", "value": 5},
            ],
        ))
        return engine

    def test_deny_by_default_when_no_policy_matches(self):
        engine = ABACPolicyEngine()
        result = engine.evaluate(
            subject={"department": "unknown"},
            resource={"department": "other"},
            action="read",
            environment={},
        )
        assert result["decision"] == ABACDecision.DENY

    def test_allow_when_policy_matches(self):
        engine = self._create_test_engine()
        result = engine.evaluate(
            subject={"department": "finance", "clearance": 3},
            resource={"department": "finance", "classification": "internal"},
            action="read",
            environment={},
        )
        assert result["decision"] == ABACDecision.ALLOW

    def test_deny_when_deny_policy_matches(self):
        engine = self._create_test_engine()
        result = engine.evaluate(
            subject={"department": "finance", "clearance": 3},
            resource={"department": "finance", "classification": "restricted"},
            action="read",
            environment={},
        )
        assert result["decision"] == ABACDecision.DENY

    def test_deny_policy_takes_priority_over_allow(self):
        engine = self._create_test_engine()
        # Both policies match, but DENY has higher priority (lower number)
        result = engine.evaluate(
            subject={"department": "finance", "clearance": 3},
            resource={"department": "finance", "classification": "restricted"},
            action="read",
            environment={},
        )
        assert result["decision"] == ABACDecision.DENY
        assert result["policy_id"] == "deny_restricted"

    def test_create_duplicate_policy_raises(self):
        engine = ABACPolicyEngine()
        engine.create_policy(ABACPolicy("p1", "Test", "Test"))
        with pytest.raises(ABACPolicyError, match="already exists"):
            engine.create_policy(ABACPolicy("p1", "Test", "Test"))

    def test_update_policy_creates_new_version(self):
        engine = ABACPolicyEngine()
        engine.create_policy(ABACPolicy("p1", "Test", "Test", conditions=[]))
        result = engine.update_policy("p1", priority=50)
        assert result["version"] == 2
        versions = engine.get_policy_versions("p1")
        assert len(versions) == 2

    def test_delete_policy(self):
        engine = ABACPolicyEngine()
        engine.create_policy(ABACPolicy("p1", "Test", "Test"))
        result = engine.delete_policy("p1")
        assert result["status"] == "deleted"
        assert "p1" not in engine._policies

    def test_delete_nonexistent_raises(self):
        engine = ABACPolicyEngine()
        with pytest.raises(ABACPolicyError, match="not found"):
            engine.delete_policy("nonexistent")

    def test_simulate_returns_all_evaluations(self):
        engine = self._create_test_engine()
        result = engine.simulate(
            subject={"department": "finance", "clearance": 3},
            resource={"department": "finance", "classification": "internal"},
            action="read",
            environment={},
        )
        assert result["simulation"] is True
        assert len(result["all_evaluations"]) == 2

    def test_list_policies(self):
        engine = self._create_test_engine()
        policies = engine.list_policies()
        assert len(policies) == 2

    def test_get_policy_versions(self):
        engine = ABACPolicyEngine()
        engine.create_policy(ABACPolicy("p1", "Test", "Test"))
        engine.update_policy("p1", priority=50)
        versions = engine.get_policy_versions("p1")
        assert len(versions) == 2
        assert versions[0]["version"] == 1
        assert versions[1]["version"] == 2

    def test_get_policy_versions_nonexistent(self):
        engine = ABACPolicyEngine()
        assert engine.get_policy_versions("nonexistent") == []

    def test_singleton_returns_same_instance(self):
        e1 = get_abac_engine()
        e2 = get_abac_engine()
        assert e1 is e2


# ═══════════════════════════════════════════════════════════════════════
# 3. Bias Detection Scheduler Tests
# ═══════════════════════════════════════════════════════════════════════
class TestBiasDetectionScheduler:
    """Tests for BiasDetectionScheduler."""

    def test_schedule_daily_evaluation(self):
        scheduler = BiasDetectionScheduler()
        job = scheduler.schedule_daily_evaluation(
            "finance-model",
            ["gender", "ethnicity"],
            time="02:00",
        )
        assert job["target_model"] == "finance-model"
        assert job["protected_attributes"] == ["gender", "ethnicity"]
        assert job["status"] == "scheduled"
        assert "next_run" in job

    @pytest.mark.asyncio
    async def test_execute_evaluation(self):
        scheduler = BiasDetectionScheduler()
        job = scheduler.schedule_daily_evaluation("test-model", ["gender"])
        predictions = [
            {"gender": "male", "prediction": True, "actual": True},
            {"gender": "female", "prediction": True, "actual": True},
        ] * 25
        result = await scheduler.execute_evaluation(job["job_id"], predictions)
        assert result["target_model"] == "test-model"
        assert "gender" in result["results"]
        assert "risk_level" in result
        assert "recommendations" in result

    @pytest.mark.asyncio
    async def test_execute_evaluation_records_report(self):
        scheduler = BiasDetectionScheduler()
        job = scheduler.schedule_daily_evaluation("test-model", ["gender"])
        predictions = [{"gender": "male", "prediction": True, "actual": True}] * 50
        await scheduler.execute_evaluation(job["job_id"], predictions)
        reports = scheduler.get_reports()
        assert len(reports) == 1

    @pytest.mark.asyncio
    async def test_execute_unknown_job_raises(self):
        scheduler = BiasDetectionScheduler()
        with pytest.raises(ValueError, match="not found"):
            await scheduler.execute_evaluation("unknown", [])

    def test_get_job_status(self):
        scheduler = BiasDetectionScheduler()
        job = scheduler.schedule_daily_evaluation("model", ["gender"])
        status = scheduler.get_job_status(job["job_id"])
        assert status is not None
        assert status["target_model"] == "model"

    def test_get_job_status_not_found(self):
        scheduler = BiasDetectionScheduler()
        assert scheduler.get_job_status("unknown") is None

    def test_list_jobs(self):
        scheduler = BiasDetectionScheduler()
        scheduler.schedule_daily_evaluation("model1", ["gender"])
        scheduler.schedule_daily_evaluation("model2", ["ethnicity"])
        jobs = scheduler.list_jobs()
        assert len(jobs) == 2

    def test_get_report_template(self):
        scheduler = BiasDetectionScheduler()
        template = scheduler.get_report_template()
        assert "report_metadata" in template
        assert "evaluation_context" in template
        assert "bias_results" in template
        assert "fairness_metrics" in template
        assert "risk_assessment" in template
        assert "recommendations" in template

    def test_singleton_returns_same_instance(self):
        s1 = get_bias_scheduler()
        s2 = get_bias_scheduler()
        assert s1 is s2


# ═══════════════════════════════════════════════════════════════════════
# 4. Continuous Responsible AI Monitor Tests
# ═══════════════════════════════════════════════════════════════════════
class TestContinuousResponsibleAIMonitor:
    """Tests for ContinuousResponsibleAIMonitor."""

    def test_record_metric(self):
        monitor = ContinuousResponsibleAIMonitor()
        entry = monitor.record_metric("hallucination_rate", 0.03)
        assert entry["metric_name"] == "hallucination_rate"
        assert entry["value"] == 0.03

    def test_threshold_violation_generates_alert(self):
        monitor = ContinuousResponsibleAIMonitor()
        # Threshold is 0.05
        monitor.record_metric("hallucination_rate", 0.10)
        alerts = monitor.get_alerts()
        assert len(alerts) == 1
        assert alerts[0]["metric_name"] == "hallucination_rate"

    def test_no_alert_when_within_threshold(self):
        monitor = ContinuousResponsibleAIMonitor()
        monitor.record_metric("hallucination_rate", 0.03)
        alerts = monitor.get_alerts()
        assert len(alerts) == 0

    def test_get_metrics_summary(self):
        monitor = ContinuousResponsibleAIMonitor()
        monitor.record_metric("hallucination_rate", 0.03)
        monitor.record_metric("hallucination_rate", 0.04)
        summary = monitor.get_metrics_summary()
        assert summary["total_metrics"] == 2
        assert "hallucination_rate" in summary["by_metric"]

    def test_update_threshold(self):
        monitor = ContinuousResponsibleAIMonitor()
        monitor.update_threshold("hallucination_rate", 0.02)
        thresholds = monitor.get_thresholds()
        assert thresholds["hallucination_rate"] == 0.02

    def test_get_thresholds(self):
        monitor = ContinuousResponsibleAIMonitor()
        thresholds = monitor.get_thresholds()
        assert "hallucination_rate" in thresholds
        assert "csat_min" in thresholds

    def test_singleton_returns_same_instance(self):
        m1 = get_responsible_ai_monitor()
        m2 = get_responsible_ai_monitor()
        assert m1 is m2
