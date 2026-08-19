"""HSAAI v19 — AIOps: Predictive ACTIVE + High-Risk Remediation + Autonomous Ops Tests"""
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

from backend_core.observability.v19_aiops import (  # noqa: E402
    AutonomousOperationsEngine, HighRiskRemediationError,
    HighRiskRemediationManager, PredictiveActiveMode,
    get_autonomous_engine, get_high_risk_remediation, get_predictive_active,
)

@pytest.fixture(autouse=True)
def reset_singletons():
    import backend_core.observability.v19_aiops as mod
    mod._predictive_active = None
    mod._high_risk_remediation = None
    mod._autonomous_engine = None
    yield


# ═══ PredictiveActiveMode ═══
class TestPredictiveActiveMode:
    def test_generate_prediction(self):
        mgr = PredictiveActiveMode()
        pred = mgr.generate_prediction(
            "failure_prediction", "rag-engine",
            confidence=0.85, risk_score=45,
            explanation="Latency trending up",
            recommended_action="scale_resources",
        )
        assert pred["mode"] == "active"
        assert pred["confidence"] == 0.85
        assert pred["risk_level"] == "high"
        assert pred["governance_approved"] is False

    def test_unknown_prediction_type_raises(self):
        mgr = PredictiveActiveMode()
        with pytest.raises(ValueError, match="Unknown prediction type"):
            mgr.generate_prediction("unknown", "svc", confidence=0.9, risk_score=50,
                                     explanation="", recommended_action="")

    def test_governance_approves_high_confidence(self):
        mgr = PredictiveActiveMode()
        pred = mgr.generate_prediction("failure_prediction", "svc", confidence=0.95,
                                        risk_score=30, explanation="ok", recommended_action="scale")
        result = mgr.evaluate_governance(pred)
        assert result["governance_approved"] is True

    def test_governance_denies_low_confidence(self):
        mgr = PredictiveActiveMode()
        pred = mgr.generate_prediction("failure_prediction", "svc", confidence=0.50,
                                        risk_score=30, explanation="ok", recommended_action="scale")
        result = mgr.evaluate_governance(pred)
        assert result["governance_approved"] is False
        assert "below 70%" in result["reason"]

    def test_governance_denies_critical_without_high_confidence(self):
        mgr = PredictiveActiveMode()
        pred = mgr.generate_prediction("failure_prediction", "svc", confidence=0.85,
                                        risk_score=80, explanation="ok", recommended_action="scale")
        result = mgr.evaluate_governance(pred)
        assert result["governance_approved"] is False
        assert "90% confidence" in result["reason"]

    def test_get_approved_predictions(self):
        mgr = PredictiveActiveMode()
        pred1 = mgr.generate_prediction("failure_prediction", "svc", confidence=0.95,
                                        risk_score=30, explanation="", recommended_action="")
        pred2 = mgr.generate_prediction("failure_prediction", "svc", confidence=0.50,
                                        risk_score=30, explanation="", recommended_action="")
        mgr.evaluate_governance(pred1)
        mgr.evaluate_governance(pred2)
        approved = mgr.get_approved_predictions()
        assert len(approved) == 1

    def test_get_stats(self):
        mgr = PredictiveActiveMode()
        mgr.generate_prediction("failure_prediction", "svc", confidence=0.9, risk_score=30,
                                 explanation="", recommended_action="")
        stats = mgr.get_stats()
        assert stats["mode"] == "active"
        assert stats["total_predictions"] == 1

    def test_singleton(self):
        assert get_predictive_active() is get_predictive_active()


# ═══ HighRiskRemediationManager ═══
class TestHighRiskRemediation:
    @pytest.mark.asyncio
    async def test_route_traffic_executes_with_approval(self):
        mgr = HighRiskRemediationManager()
        async def handler(t): return {"success": True}
        mgr.register_handler("route_traffic", handler)
        result = await mgr.execute("route_traffic", "svc-1",
                                    approver="admin", rollback_plan="reroute to svc-2")
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_requires_human_approval(self):
        mgr = HighRiskRemediationManager()
        async def handler(t): return {"success": True}
        mgr.register_handler("route_traffic", handler)
        with pytest.raises(HighRiskRemediationError, match="REQUIRES human approval"):
            await mgr.execute("route_traffic", "svc")

    @pytest.mark.asyncio
    async def test_requires_rollback_plan(self):
        mgr = HighRiskRemediationManager()
        async def handler(t): return {"success": True}
        mgr.register_handler("disable_agent", handler)
        with pytest.raises(HighRiskRemediationError, match="requires a rollback plan"):
            await mgr.execute("disable_agent", "agent-1", approver="admin")

    @pytest.mark.asyncio
    async def test_non_allowlisted_action_raises(self):
        mgr = HighRiskRemediationManager()
        with pytest.raises(HighRiskRemediationError, match="NOT in high-risk allowlist"):
            await mgr.execute("rollback_config", "svc", approver="admin", rollback_plan="plan")

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_failures(self):
        mgr = HighRiskRemediationManager()
        # Override cool-down for test
        mgr.HIGH_RISK_ACTIONS["route_traffic"]["cool_down"] = 0
        async def handler(t): raise RuntimeError("Always fails")
        mgr.register_handler("route_traffic", handler)
        for i in range(3):
            try:
                await mgr.execute("route_traffic", f"svc-{i}", approver="admin", rollback_plan="plan")
            except: pass
        assert mgr.circuit_open is True

    @pytest.mark.asyncio
    async def test_circuit_open_blocks_execution(self):
        mgr = HighRiskRemediationManager()
        mgr._circuit_open = True
        with pytest.raises(HighRiskRemediationError, match="Circuit breaker is OPEN"):
            await mgr.execute("route_traffic", "svc", approver="admin", rollback_plan="plan")

    @pytest.mark.asyncio
    async def test_reset_circuit_breaker(self):
        mgr = HighRiskRemediationManager()
        mgr._circuit_open = True
        mgr._failure_count = 3
        mgr.reset_circuit_breaker()
        assert mgr.circuit_open is False
        assert mgr._failure_count == 0

    @pytest.mark.asyncio
    async def test_abac_denial_blocks(self):
        mgr = HighRiskRemediationManager()
        async def handler(t): return {"success": True}
        mgr.register_handler("route_traffic", handler)
        with pytest.raises(HighRiskRemediationError, match="ABAC policy denied"):
            await mgr.execute("route_traffic", "svc", approver="admin", rollback_plan="plan",
                              abac_decision={"decision": "DENY"})

    @pytest.mark.asyncio
    async def test_unapproved_prediction_blocks(self):
        mgr = HighRiskRemediationManager()
        async def handler(t): return {"success": True}
        mgr.register_handler("route_traffic", handler)
        with pytest.raises(HighRiskRemediationError, match="not governance-approved"):
            await mgr.execute("route_traffic", "svc", approver="admin", rollback_plan="plan",
                              prediction={"governance_approved": False})

    @pytest.mark.asyncio
    async def test_cool_down_prevents_rapid(self):
        mgr = HighRiskRemediationManager()
        mgr.HIGH_RISK_ACTIONS["route_traffic"]["cool_down"] = 0  # Override for test speed
        # But we still test with the original cool_down by restoring it
        mgr.HIGH_RISK_ACTIONS["route_traffic"]["cool_down"] = 1800
        async def handler(t): return {"success": True}
        mgr.register_handler("route_traffic", handler)
        await mgr.execute("route_traffic", "svc-A", approver="admin", rollback_plan="plan")
        # Same action+target should be blocked by cool-down
        with pytest.raises(HighRiskRemediationError, match="Cool-down"):
            await mgr.execute("route_traffic", "svc-A", approver="admin", rollback_plan="plan")

    def test_get_stats(self):
        mgr = HighRiskRemediationManager()
        stats = mgr.get_stats()
        assert stats["max_per_hour"] == 3
        assert "route_traffic" in stats["allowed_actions"]

    def test_singleton(self):
        assert get_high_risk_remediation() is get_high_risk_remediation()


# ═══ AutonomousOperationsEngine ═══
class TestAutonomousOperationsEngine:
    @pytest.mark.asyncio
    async def test_process_incident_resolved(self):
        engine = AutonomousOperationsEngine()
        result = await engine.process_incident({
            "target": "rag-engine",
            "description": "High latency",
            "recommended_action": "scale_resources",
            "risk_score": 40,
        })
        assert result["status"] == "resolved"
        assert result["flow_state"]["remediation_execution"] == "executed"

    @pytest.mark.asyncio
    async def test_process_incident_blocked_for_high_risk_without_approver(self):
        engine = AutonomousOperationsEngine()
        result = await engine.process_incident({
            "target": "agent-1",
            "description": "Agent misbehaving",
            "recommended_action": "disable_agent",  # High-risk
            "risk_score": 70,
        })
        assert result["status"] == "blocked"

    @pytest.mark.asyncio
    async def test_process_incident_denied_low_confidence(self):
        engine = AutonomousOperationsEngine()
        result = await engine.process_incident({
            "target": "svc",
            "description": "Issue",
            "recommended_action": "scale_resources",
            "risk_score": 80,  # Critical
        }, prediction={
            "prediction_type": "failure_prediction",
            "target": "svc",
            "mode": "active",
            "confidence": 0.50,  # Below critical threshold
            "risk_score": 80,
            "risk_level": "critical",
            "explanation": "test",
            "recommended_action": "scale_resources",
            "governance_approved": False,
        })
        assert result["status"] == "denied"

    @pytest.mark.asyncio
    async def test_all_flow_steps_completed(self):
        engine = AutonomousOperationsEngine()
        result = await engine.process_incident({
            "target": "svc",
            "description": "test",
            "recommended_action": "scale_resources",
            "risk_score": 30,
        })
        # For resolved incidents, all steps should have a terminal state
        if result["status"] == "resolved":
            for step in engine.AUTONOMOUS_FLOW:
                state = result["flow_state"].get(step)
                assert state in ("completed", "approved", "executed"), f"Step {step} state={state} not terminal"

    @pytest.mark.asyncio
    async def test_learning_feedback_collected(self):
        engine = AutonomousOperationsEngine()
        await engine.process_incident({
            "target": "svc", "description": "test",
            "recommended_action": "scale_resources", "risk_score": 30,
        })
        learning = engine.get_learning_data()
        assert len(learning) == 1
        assert learning[0]["outcome"] == "resolved"

    @pytest.mark.asyncio
    async def test_get_stats(self):
        engine = AutonomousOperationsEngine()
        await engine.process_incident({
            "target": "svc", "description": "test",
            "recommended_action": "scale_resources", "risk_score": 30,
        })
        stats = engine.get_stats()
        assert stats["mode"] == "autonomous"
        assert stats["total_incidents"] == 1
        assert stats["resolved"] == 1

    def test_singleton(self):
        assert get_autonomous_engine() is get_autonomous_engine()
