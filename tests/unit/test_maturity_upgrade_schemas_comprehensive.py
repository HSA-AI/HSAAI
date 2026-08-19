"""
HSAAI Enterprise AI Platform — Maturity Upgrade Schemas Test Suite (v7.0)
==========================================================================
Comprehensive tests for `services/backend_core/maturity_upgrade/schemas.py`.

Coverage targets:
  - AgentRouteRequest (Literal roles, defaults)
  - AgentRouteResponse (Literal selected_agent, required fields)
  - WorkflowStartRequest (Literal template_key, required title)
  - WorkflowActionRequest (Literal action)
  - ConnectorRuntimeRequest (Literal action, defaults)
  - ObservabilityEventIn (many optional fields, defaults)

Test categories: positive, negative, boundary, validation, serialization, defaults, edge cases.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

_BASE = Path(__file__).resolve().parents[2]
for _p in [str(_BASE / "services"), str(_BASE / "packages"), str(_BASE / "packages" / "common")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend_core.maturity_upgrade.schemas import (  # noqa: E402
    AgentRouteRequest,
    AgentRouteResponse,
    ConnectorRuntimeRequest,
    ObservabilityEventIn,
    WorkflowActionRequest,
    WorkflowStartRequest,
)


# ═══════════════════════════════════════════════════════════════════════
# AgentRouteRequest (maturity_upgrade variant)
# ═══════════════════════════════════════════════════════════════════════
class TestAgentRouteRequestMaturity:
    """Tests for maturity_upgrade.AgentRouteRequest — different from enterprise_upgrade variant."""

    def test_default_values(self):
        r = AgentRouteRequest(message="hello")
        assert r.user_id == "system"
        assert r.tenant_id == "default"
        assert r.workspace_id == "default"
        assert r.roles == []
        assert r.department is None
        assert r.context == {}

    def test_positive_full_payload(self):
        r = AgentRouteRequest(
            message="m", user_id="u1", tenant_id="t1", workspace_id="w1",
            roles=["manager"], department="finance", context={"k": "v"},
        )
        assert r.department == "finance"
        assert r.roles == ["manager"]

    def test_negative_missing_message_raises(self):
        with pytest.raises(ValidationError):
            AgentRouteRequest()  # type: ignore[call-arg]

    def test_default_factory_roles_independent(self):
        a = AgentRouteRequest(message="a")
        b = AgentRouteRequest(message="b")
        a.roles.append("r")
        assert b.roles == []

    def test_default_factory_context_independent(self):
        a = AgentRouteRequest(message="a")
        b = AgentRouteRequest(message="b")
        a.context["k"] = "v"
        assert b.context == {}

    def test_department_optional_none(self):
        r = AgentRouteRequest(message="m")
        assert r.department is None

    def test_boundary_empty_message(self):
        r = AgentRouteRequest(message="")
        assert r.message == ""

    def test_serialization_roundtrip(self):
        r = AgentRouteRequest(message="m", department="hr", roles=["admin"])
        assert AgentRouteRequest(**r.model_dump()) == r


# ═══════════════════════════════════════════════════════════════════════
# AgentRouteResponse (maturity_upgrade variant)
# ═══════════════════════════════════════════════════════════════════════
class TestAgentRouteResponseMaturity:
    """Tests for maturity_upgrade.AgentRouteResponse — Literal selected_agent."""

    @pytest.mark.parametrize("agent", ["supervisor", "hr", "finance", "it", "legal", "executive"])
    def test_positive_all_agent_values(self, agent: str):
        r = AgentRouteResponse(
            request_id="r1", supervisor_decision="d", selected_agent=agent,
            confidence=0.5, plan=["step1"], required_connectors=["c1"],
            permission_status="allowed", audit_event_id="a1", latency_ms=100,
        )
        assert r.selected_agent == agent

    def test_negative_invalid_agent_rejected(self):
        with pytest.raises(ValidationError):
            AgentRouteResponse(
                request_id="r1", supervisor_decision="d", selected_agent="invalid",  # type: ignore[arg-type]
                confidence=0.5, plan=[], required_connectors=[],
                permission_status="allowed", audit_event_id="a1", latency_ms=100,
            )

    @pytest.mark.parametrize("missing_field", [
        "request_id", "supervisor_decision", "selected_agent", "confidence",
        "plan", "required_connectors", "permission_status", "audit_event_id", "latency_ms",
    ])
    def test_negative_missing_required_field_raises(self, missing_field: str):
        kwargs = {
            "request_id": "r1", "supervisor_decision": "d", "selected_agent": "supervisor",
            "confidence": 0.5, "plan": [], "required_connectors": [],
            "permission_status": "allowed", "audit_event_id": "a1", "latency_ms": 100,
        }
        del kwargs[missing_field]
        with pytest.raises(ValidationError):
            AgentRouteResponse(**kwargs)  # type: ignore[arg-type]

    def test_boundary_confidence_zero(self):
        r = AgentRouteResponse(
            request_id="r1", supervisor_decision="d", selected_agent="supervisor",
            confidence=0.0, plan=[], required_connectors=[],
            permission_status="denied", audit_event_id="a1", latency_ms=100,
        )
        assert r.confidence == 0.0

    def test_boundary_empty_plan_list(self):
        r = AgentRouteResponse(
            request_id="r1", supervisor_decision="d", selected_agent="supervisor",
            confidence=0.5, plan=[], required_connectors=["c1"],
            permission_status="allowed", audit_event_id="a1", latency_ms=100,
        )
        assert r.plan == []

    def test_serialization_roundtrip(self):
        r = AgentRouteResponse(
            request_id="r1", supervisor_decision="d", selected_agent="finance",
            confidence=0.92, plan=["s1", "s2"], required_connectors=["sap"],
            permission_status="allowed", audit_event_id="a1", latency_ms=234,
        )
        assert AgentRouteResponse(**r.model_dump()) == r


# ═══════════════════════════════════════════════════════════════════════
# WorkflowStartRequest (maturity_upgrade variant)
# ═══════════════════════════════════════════════════════════════════════
class TestWorkflowStartRequestMaturity:
    """Tests for maturity_upgrade.WorkflowStartRequest — Literal template_key."""

    @pytest.mark.parametrize("template", ["purchase_request", "document_review", "leave_request", "support_ticket"])
    def test_positive_all_template_values(self, template: str):
        r = WorkflowStartRequest(template_key=template, title="T")
        assert r.template_key == template

    def test_default_values(self):
        r = WorkflowStartRequest(template_key="leave_request", title="T")
        assert r.requested_by == "system"
        assert r.tenant_id == "default"
        assert r.workspace_id == "default"
        assert r.payload == {}

    def test_negative_invalid_template_rejected(self):
        with pytest.raises(ValidationError):
            WorkflowStartRequest(template_key="invalid", title="T")  # type: ignore[arg-type]

    @pytest.mark.parametrize("missing_field", ["template_key", "title"])
    def test_negative_missing_required_field_raises(self, missing_field: str):
        kwargs = {"template_key": "leave_request", "title": "T"}
        del kwargs[missing_field]
        with pytest.raises(ValidationError):
            WorkflowStartRequest(**kwargs)  # type: ignore[arg-type]

    def test_default_factory_payload_independent(self):
        a = WorkflowStartRequest(template_key="leave_request", title="A")
        b = WorkflowStartRequest(template_key="leave_request", title="B")
        a.payload["k"] = "v"
        assert b.payload == {}

    def test_serialization_roundtrip(self):
        r = WorkflowStartRequest(
            template_key="purchase_request", title="T",
            payload={"amount": 500}, requested_by="u1",
        )
        assert WorkflowStartRequest(**r.model_dump()) == r


# ═══════════════════════════════════════════════════════════════════════
# WorkflowActionRequest
# ═══════════════════════════════════════════════════════════════════════
class TestWorkflowActionRequest:
    """Tests for WorkflowActionRequest — Literal action."""

    @pytest.mark.parametrize("action", ["approve", "reject", "complete_step", "escalate"])
    def test_positive_all_action_values(self, action: str):
        r = WorkflowActionRequest(execution_id="e1", action=action)
        assert r.action == action

    def test_default_values(self):
        r = WorkflowActionRequest(execution_id="e1", action="approve")
        assert r.actor == "system"
        assert r.comment == ""

    def test_negative_invalid_action_rejected(self):
        with pytest.raises(ValidationError):
            WorkflowActionRequest(execution_id="e1", action="invalid")  # type: ignore[arg-type]

    def test_negative_missing_execution_id_raises(self):
        with pytest.raises(ValidationError):
            WorkflowActionRequest(action="approve")  # type: ignore[call-arg]

    def test_negative_missing_action_raises(self):
        with pytest.raises(ValidationError):
            WorkflowActionRequest(execution_id="e1")  # type: ignore[call-arg]

    def test_boundary_empty_comment(self):
        r = WorkflowActionRequest(execution_id="e1", action="approve", comment="")
        assert r.comment == ""

    def test_arabic_comment_accepted(self):
        r = WorkflowActionRequest(execution_id="e1", action="approve", comment="موافقة")
        assert r.comment == "موافقة"

    def test_serialization_roundtrip(self):
        r = WorkflowActionRequest(execution_id="e1", action="reject", actor="u1", comment="no")
        assert WorkflowActionRequest(**r.model_dump()) == r


# ═══════════════════════════════════════════════════════════════════════
# ConnectorRuntimeRequest
# ═══════════════════════════════════════════════════════════════════════
class TestConnectorRuntimeRequest:
    """Tests for ConnectorRuntimeRequest."""

    @pytest.mark.parametrize("action", ["test", "sync", "health", "fetch"])
    def test_positive_all_action_values(self, action: str):
        r = ConnectorRuntimeRequest(connector_key="sap", action=action)
        assert r.action == action

    def test_default_values(self):
        r = ConnectorRuntimeRequest(connector_key="sap")
        assert r.action == "health"
        assert r.query == {}

    def test_negative_invalid_action_rejected(self):
        with pytest.raises(ValidationError):
            ConnectorRuntimeRequest(connector_key="sap", action="invalid")  # type: ignore[arg-type]

    def test_negative_missing_connector_key_raises(self):
        with pytest.raises(ValidationError):
            ConnectorRuntimeRequest()  # type: ignore[call-arg]

    def test_default_factory_query_independent(self):
        a = ConnectorRuntimeRequest(connector_key="a")
        b = ConnectorRuntimeRequest(connector_key="b")
        a.query["k"] = "v"
        assert b.query == {}

    def test_serialization_roundtrip(self):
        r = ConnectorRuntimeRequest(connector_key="sap", action="fetch", query={"filter": "active"})
        assert ConnectorRuntimeRequest(**r.model_dump()) == r


# ═══════════════════════════════════════════════════════════════════════
# ObservabilityEventIn
# ═══════════════════════════════════════════════════════════════════════
class TestObservabilityEventIn:
    """Tests for ObservabilityEventIn — many optional fields with defaults."""

    def test_minimal_required_fields(self):
        e = ObservabilityEventIn(event_type="agent_run", component="agent_runtime")
        assert e.event_type == "agent_run"
        assert e.component == "agent_runtime"
        # Defaults
        assert e.status == "ok"
        assert e.latency_ms == 0
        assert e.tokens == 0
        assert e.model == ""
        assert e.agent == ""
        assert e.workflow == ""
        assert e.connector == ""
        assert e.error_message == ""
        assert e.tenant_id == "default"
        assert e.workspace_id == "default"

    def test_positive_full_payload(self):
        e = ObservabilityEventIn(
            event_type="llm_call", component="llm_gateway", status="ok",
            latency_ms=234, tokens=150, model="qwen2.5:7b-instruct",
            agent="finance", workflow="wf-1", connector="sap",
            error_message="", tenant_id="t1", workspace_id="w1",
        )
        assert e.tokens == 150
        assert e.agent == "finance"
        assert e.connector == "sap"

    @pytest.mark.parametrize("missing_field", ["event_type", "component"])
    def test_negative_missing_required_field_raises(self, missing_field: str):
        kwargs = {"event_type": "e", "component": "c"}
        del kwargs[missing_field]
        with pytest.raises(ValidationError):
            ObservabilityEventIn(**kwargs)  # type: ignore[arg-type]

    def test_boundary_zero_latency(self):
        e = ObservabilityEventIn(event_type="e", component="c", latency_ms=0)
        assert e.latency_ms == 0

    def test_boundary_zero_tokens(self):
        e = ObservabilityEventIn(event_type="e", component="c", tokens=0)
        assert e.tokens == 0

    def test_error_message_defaults_empty(self):
        e = ObservabilityEventIn(event_type="e", component="c")
        assert e.error_message == ""

    def test_arabic_error_message_accepted(self):
        e = ObservabilityEventIn(event_type="e", component="c", error_message="خطأ في الاتصال")
        assert e.error_message == "خطأ في الاتصال"

    def test_serialization_roundtrip(self):
        e = ObservabilityEventIn(
            event_type="e", component="c", status="error",
            latency_ms=500, tokens=100, model="llama3",
        )
        dumped = e.model_dump()
        assert ObservabilityEventIn(**dumped) == e
