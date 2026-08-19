"""HSAAI v16.1 — Full ABAC + Predictive Activation + Security Control Plane Tests"""
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

from backend_core.security.full_abac_v16_1 import (  # noqa: E402
    FullABACEnforcement, PredictiveActivationManager, SecurityControlPlane,
    get_full_abac, get_predictive_mgr, get_security_cp,
)

@pytest.fixture(autouse=True)
def reset_singletons():
    import backend_core.security.full_abac_v16_1 as mod
    mod._full_abac = None
    mod._predictive_mgr = None
    mod._security_cp = None
    yield


# ═══ FullABACEnforcement ═══
class TestFullABAC:
    def test_full_abac_mode(self):
        abac = FullABACEnforcement()
        assert abac.mode == "full_abac"
        assert abac.rbac_deprecated is True

    def test_deny_by_default_no_policy(self):
        abac = FullABACEnforcement()
        result = abac.evaluate({}, {}, "read")
        assert result["decision"] == "DENY"
        assert result["source"] == "abac_full"
        assert result["rbac_used"] is False

    def test_allow_when_policy_matches(self):
        abac = FullABACEnforcement()
        abac.register_policy("p1", {
            "enabled": True,
            "effect": "ALLOW",
            "conditions": [
                {"source": "subject", "attribute": "department", "operator": "eq", "value": "finance"},
                {"source": "resource", "attribute": "classification", "operator": "eq", "value": "internal"},
            ],
        })
        result = abac.evaluate(
            {"department": "finance", "clearance": 3},
            {"classification": "internal"},
            "read",
        )
        assert result["decision"] == "ALLOW"
        assert result["policy_id"] == "p1"

    def test_deny_when_condition_not_met(self):
        abac = FullABACEnforcement()
        abac.register_policy("p1", {
            "enabled": True,
            "effect": "ALLOW",
            "conditions": [
                {"source": "subject", "attribute": "clearance", "operator": "ge", "value": 5},
            ],
        })
        result = abac.evaluate({"clearance": 3}, {}, "read")
        assert result["decision"] == "DENY"

    def test_rbac_role_converted_to_attributes(self):
        abac = FullABACEnforcement()
        attrs = abac.convert_rbac_role_to_attributes("hsaai_admin")
        assert attrs["clearance"] == 5
        assert attrs["trust_score"] == 1.0

        attrs = abac.convert_rbac_role_to_attributes("ai_user")
        assert attrs["clearance"] == 2

    def test_subject_enriched_from_role(self):
        abac = FullABACEnforcement()
        abac.register_policy("p1", {
            "enabled": True,
            "effect": "ALLOW",
            "conditions": [
                {"source": "subject", "attribute": "clearance", "operator": "ge", "value": 4},
            ],
        })
        # Subject has role but no clearance — should be auto-enriched
        result = abac.evaluate({"role": "knowledge_admin"}, {}, "read")
        assert result["decision"] == "ALLOW"
        assert result["subject_attributes"]["clearance"] == 4

    def test_disabled_policy_skipped(self):
        abac = FullABACEnforcement()
        abac.register_policy("p1", {
            "enabled": False,
            "effect": "ALLOW",
            "conditions": [],
        })
        result = abac.evaluate({}, {}, "read")
        assert result["decision"] == "DENY"

    def test_simulate_returns_result_without_side_effects(self):
        abac = FullABACEnforcement()
        result = abac.simulate({}, {}, "read")
        assert result["simulation"] is True

    def test_migration_stats(self):
        abac = FullABACEnforcement()
        abac.register_policy("p1", {"enabled": True, "effect": "ALLOW", "conditions": []})
        abac.evaluate({}, {}, "read")  # ALLOW
        abac.evaluate({}, {}, "write")  # ALLOW (same policy)
        stats = abac.get_migration_stats()
        assert stats["mode"] == "full_abac"
        assert stats["rbac_deprecated"] is True
        assert stats["total_decisions"] == 2
        assert stats["allowed"] == 2
        assert stats["rbac_fallbacks"] == 0

    def test_singleton(self):
        assert get_full_abac() is get_full_abac()


# ═══ PredictiveActivationManager ═══
class TestPredictiveActivation:
    def test_initial_mode_is_observation(self):
        mgr = PredictiveActivationManager()
        assert mgr.mode == "observation_only"
        assert mgr.approval_status == "pending"

    def test_submit_baseline_report(self):
        mgr = PredictiveActivationManager()
        result = mgr.submit_baseline_report({"data_quality": {"score": 90}, "total_metrics": 500})
        assert result["status"] == "submitted"
        assert result["approval_status"] == "under_review"

    def test_approve_without_baseline_fails(self):
        mgr = PredictiveActivationManager()
        result = mgr.approve_activation(approver="admin")
        assert result["approved"] is False

    def test_approve_without_accuracy_validation_fails(self):
        mgr = PredictiveActivationManager()
        mgr.submit_baseline_report({"data_quality": {"score": 90}})
        result = mgr.approve_activation(approver="admin")
        assert result["approved"] is False
        assert "accuracy" in result["reason"].lower()

    def test_validate_accuracy_passes(self):
        mgr = PredictiveActivationManager()
        predictions = [{"predicted": True}, {"predicted": False}, {"predicted": True}]
        actuals = [{"actual": True}, {"actual": False}, {"actual": True}]
        result = mgr.validate_accuracy(predictions, actuals)
        assert result["valid"] is True
        assert result["accuracy"] == 1.0

    def test_validate_accuracy_fails_below_threshold(self):
        mgr = PredictiveActivationManager()
        predictions = [{"predicted": True}] * 10
        actuals = [{"actual": False}] * 10  # All wrong
        result = mgr.validate_accuracy(predictions, actuals)
        assert result["valid"] is False
        assert result["accuracy"] == 0.0

    def test_approve_after_validation(self):
        mgr = PredictiveActivationManager()
        mgr.submit_baseline_report({"data_quality": {"score": 90}, "total_metrics": 500})
        mgr.validate_accuracy([{"predicted": True}], [{"actual": True}])
        result = mgr.approve_activation(approver="governance", mode="monitoring")
        assert result["approved"] is True
        assert result["mode"] == "monitoring"

    def test_generate_prediction_in_observation_mode_returns_none(self):
        mgr = PredictiveActivationManager()
        result = mgr.generate_prediction("svc", "failure", 50)
        assert result is None

    def test_generate_prediction_in_monitoring_mode(self):
        mgr = PredictiveActivationManager()
        mgr.submit_baseline_report({"data_quality": {"score": 90}})
        mgr.validate_accuracy([{"predicted": True}], [{"actual": True}])
        mgr.approve_activation(approver="admin", mode="monitoring")
        result = mgr.generate_prediction("svc", "failure", 75, recommendation="Scale up")
        assert result is not None
        assert result["risk_level"] == "critical"
        assert result["recommendation"] == ""  # Monitoring mode suppresses recommendations

    def test_generate_prediction_in_active_mode(self):
        mgr = PredictiveActivationManager()
        mgr.submit_baseline_report({"data_quality": {"score": 90}})
        mgr.validate_accuracy([{"predicted": True}], [{"actual": True}])
        mgr.approve_activation(approver="admin", mode="active")
        result = mgr.generate_prediction("svc", "failure", 45, recommendation="Investigate")
        assert result is not None
        assert result["risk_level"] == "high"
        assert result["recommendation"] == "Investigate"

    def test_get_status(self):
        mgr = PredictiveActivationManager()
        mgr.submit_baseline_report({"data_quality": {"score": 90}})
        status = mgr.get_status()
        assert status["baseline_available"] is True
        assert status["mode"] == "observation_only"

    def test_singleton(self):
        assert get_predictive_mgr() is get_predictive_mgr()


# ═══ SecurityControlPlane ═══
class TestSecurityControlPlane:
    def test_initial_threat_level_normal(self):
        scp = SecurityControlPlane()
        assert scp.threat_level == "normal"

    def test_set_threat_level(self):
        scp = SecurityControlPlane()
        scp.set_threat_level("elevated")
        assert scp.threat_level == "elevated"

    def test_set_invalid_threat_level_raises(self):
        scp = SecurityControlPlane()
        with pytest.raises(ValueError, match="Invalid threat level"):
            scp.set_threat_level("invalid")

    def test_authorize_injects_threat_level(self):
        scp = SecurityControlPlane()
        scp.set_threat_level("elevated")
        scp.register_policy("p1", {
            "enabled": True,
            "effect": "ALLOW",
            "conditions": [
                {"source": "environment", "attribute": "threat_level", "operator": "eq", "value": "elevated"},
            ],
        })
        result = scp.authorize({}, {}, "read")
        assert result["decision"] == "ALLOW"
        assert result["environment_attributes"]["risk_level"] == "elevated"

    def test_detect_threat_records_event(self):
        scp = SecurityControlPlane()
        event = scp.detect_threat("prompt_injection", {"input": "malicious"})
        assert event["event_type"] == "THREAT_DETECTED"
        assert event["threat_type"] == "prompt_injection"
        assert event["severity"] == "high"

    def test_critical_threat_escalates_level(self):
        scp = SecurityControlPlane()
        assert scp.threat_level == "normal"
        scp.detect_threat("jailbreak_attempt", {"input": "jailbreak"})
        assert scp.threat_level == "elevated"

    def test_get_security_events(self):
        scp = SecurityControlPlane()
        scp.detect_threat("prompt_injection", {"input": "test"})
        events = scp.get_security_events()
        assert len(events) >= 1

    def test_get_security_status(self):
        scp = SecurityControlPlane()
        scp.register_policy("p1", {"enabled": True, "effect": "ALLOW", "conditions": []})
        scp.detect_threat("prompt_injection", {"input": "test"})
        status = scp.get_security_status()
        assert status["threat_level"] == "normal" or status["threat_level"] == "elevated"
        assert status["abac_mode"] == "full_abac"
        assert status["rbac_deprecated"] is True
        assert status["policies_registered"] == 1

    def test_singleton(self):
        assert get_security_cp() is get_security_cp()
