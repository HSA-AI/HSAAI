"""
HSAAI Enterprise AI Platform — Enterprise Upgrade Schemas Test Suite (v7.0)
============================================================================
Comprehensive tests for `services/backend_core/enterprise_upgrade/schemas.py`.

Coverage targets:
  - AgentRouteRequest (required message, defaults)
  - AgentRouteResponse (all fields required — output model)
  - WorkflowTemplateIn (key/name required, defaults)
  - WorkflowStartRequest (template_key required, defaults)
  - ConnectorConfigIn (Literal auth_type, defaults)
  - ApprovalRequestIn (Literal risk_level, defaults)
  - ApprovalDecisionIn (single optional comment)

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

from backend_core.enterprise_upgrade.schemas import (  # noqa: E402
    AgentRouteRequest,
    AgentRouteResponse,
    ApprovalDecisionIn,
    ApprovalRequestIn,
    ConnectorConfigIn,
    WorkflowStartRequest,
    WorkflowTemplateIn,
)


# ═══════════════════════════════════════════════════════════════════════
# AgentRouteRequest
# ═══════════════════════════════════════════════════════════════════════
class TestAgentRouteRequest:
    """Tests for AgentRouteRequest."""

    def test_default_values(self):
        r = AgentRouteRequest(message="hello")
        assert r.workspace_id == "default"
        assert r.session_id == "default"
        assert r.context == {}

    def test_positive_full_payload(self):
        r = AgentRouteRequest(
            message="analyze",
            workspace_id="w1",
            session_id="s1",
            context={"user": "u1", "role": "manager"},
        )
        assert r.workspace_id == "w1"
        assert r.context["role"] == "manager"

    def test_negative_missing_message_raises(self):
        with pytest.raises(ValidationError):
            AgentRouteRequest()  # type: ignore[call-arg]

    def test_default_factory_context_independent(self):
        a = AgentRouteRequest(message="a")
        b = AgentRouteRequest(message="b")
        a.context["k"] = "v"
        assert b.context == {}

    def test_boundary_empty_message(self):
        r = AgentRouteRequest(message="")
        assert r.message == ""

    def test_arabic_message_accepted(self):
        r = AgentRouteRequest(message="حلل التقرير المالي")
        assert r.message == "حلل التقرير المالي"

    def test_serialization_roundtrip(self):
        r = AgentRouteRequest(message="m", context={"k": "v"})
        assert AgentRouteRequest(**r.model_dump()) == r


# ═══════════════════════════════════════════════════════════════════════
# AgentRouteResponse
# ═══════════════════════════════════════════════════════════════════════
class TestAgentRouteResponse:
    """Tests for AgentRouteResponse — output model with all fields required."""

    def test_positive_full_payload(self):
        r = AgentRouteResponse(
            supervisor_decision="route_to_agent",
            selected_agent="finance",
            selected_department="finance",
            confidence=0.92,
            reason="financial keywords detected",
            allowed=True,
            required_roles=["hsaai_admin", "department_manager"],
            next_steps=["invoke finance agent", "log audit"],
        )
        assert r.selected_agent == "finance"
        assert r.confidence == 0.92
        assert r.allowed is True

    @pytest.mark.parametrize("missing_field", [
        "supervisor_decision", "selected_agent", "selected_department",
        "confidence", "reason", "allowed", "required_roles", "next_steps",
    ])
    def test_negative_missing_required_field_raises(self, missing_field: str):
        kwargs = {
            "supervisor_decision": "d", "selected_agent": "a", "selected_department": "dep",
            "confidence": 0.5, "reason": "r", "allowed": True,
            "required_roles": [], "next_steps": [],
        }
        del kwargs[missing_field]
        with pytest.raises(ValidationError):
            AgentRouteResponse(**kwargs)  # type: ignore[arg-type]

    def test_boundary_confidence_zero(self):
        r = AgentRouteResponse(
            supervisor_decision="d", selected_agent="a", selected_department="dep",
            confidence=0.0, reason="r", allowed=False,
            required_roles=[], next_steps=[],
        )
        assert r.confidence == 0.0

    def test_boundary_confidence_one(self):
        r = AgentRouteResponse(
            supervisor_decision="d", selected_agent="a", selected_department="dep",
            confidence=1.0, reason="r", allowed=True,
            required_roles=[], next_steps=[],
        )
        assert r.confidence == 1.0

    def test_boundary_empty_lists(self):
        """required_roles and next_steps can be empty lists."""
        r = AgentRouteResponse(
            supervisor_decision="d", selected_agent="a", selected_department="dep",
            confidence=0.5, reason="r", allowed=True,
            required_roles=[], next_steps=[],
        )
        assert r.required_roles == []
        assert r.next_steps == []

    def test_serialization_roundtrip(self):
        r = AgentRouteResponse(
            supervisor_decision="d", selected_agent="a", selected_department="dep",
            confidence=0.5, reason="r", allowed=True,
            required_roles=["role1"], next_steps=["step1"],
        )
        assert AgentRouteResponse(**r.model_dump()) == r


# ═══════════════════════════════════════════════════════════════════════
# WorkflowTemplateIn
# ═══════════════════════════════════════════════════════════════════════
class TestWorkflowTemplateIn:
    """Tests for WorkflowTemplateIn."""

    def test_default_values(self):
        t = WorkflowTemplateIn(key="k", name="N")
        assert t.description == ""
        assert t.category == "general"
        assert t.definition == {}
        assert t.enabled is True

    def test_positive_full_payload(self):
        t = WorkflowTemplateIn(
            key="purchase_request", name="Purchase Request",
            description="PR workflow", category="procurement",
            definition={"steps": ["approval", "execute"]}, enabled=False,
        )
        assert t.category == "procurement"
        assert t.enabled is False

    @pytest.mark.parametrize("missing_field", ["key", "name"])
    def test_negative_missing_required_field_raises(self, missing_field: str):
        kwargs = {"key": "k", "name": "N"}
        del kwargs[missing_field]
        with pytest.raises(ValidationError):
            WorkflowTemplateIn(**kwargs)  # type: ignore[arg-type]

    def test_default_factory_definition_independent(self):
        a = WorkflowTemplateIn(key="a", name="A")
        b = WorkflowTemplateIn(key="b", name="B")
        a.definition["k"] = "v"
        assert b.definition == {}

    def test_serialization_roundtrip(self):
        t = WorkflowTemplateIn(key="k", name="N", definition={"step": 1})
        assert WorkflowTemplateIn(**t.model_dump()) == t


# ═══════════════════════════════════════════════════════════════════════
# WorkflowStartRequest
# ═══════════════════════════════════════════════════════════════════════
class TestWorkflowStartRequest:
    """Tests for WorkflowStartRequest."""

    def test_default_values(self):
        r = WorkflowStartRequest(template_key="purchase_request")
        assert r.payload == {}
        assert r.requested_by == "system"

    def test_positive_full_payload(self):
        r = WorkflowStartRequest(
            template_key="leave_request", payload={"user": "u1"},
            requested_by="user-1",
        )
        assert r.payload["user"] == "u1"

    def test_negative_missing_template_key_raises(self):
        with pytest.raises(ValidationError):
            WorkflowStartRequest()  # type: ignore[call-arg]

    def test_default_factory_payload_independent(self):
        a = WorkflowStartRequest(template_key="t")
        b = WorkflowStartRequest(template_key="t")
        a.payload["k"] = "v"
        assert b.payload == {}

    def test_serialization_roundtrip(self):
        r = WorkflowStartRequest(template_key="t", payload={"k": "v"})
        assert WorkflowStartRequest(**r.model_dump()) == r


# ═══════════════════════════════════════════════════════════════════════
# ConnectorConfigIn
# ═══════════════════════════════════════════════════════════════════════
class TestConnectorConfigIn:
    """Tests for ConnectorConfigIn — Literal auth_type."""

    @pytest.mark.parametrize("auth_type", ["oauth2", "oidc", "api_key", "service_account", "basic", "none"])
    def test_positive_all_auth_type_values(self, auth_type: str):
        c = ConnectorConfigIn(key="k", name="N", connector_type="sap", auth_type=auth_type)
        assert c.auth_type == auth_type

    def test_default_values(self):
        c = ConnectorConfigIn(key="k", name="N", connector_type="sap")
        assert c.auth_type == "none"
        assert c.base_url == ""
        assert c.schedule == "manual"
        assert c.secrets_ref == ""
        assert c.enabled is True
        assert c.metadata == {}

    def test_negative_invalid_auth_type_rejected(self):
        with pytest.raises(ValidationError):
            ConnectorConfigIn(key="k", name="N", connector_type="sap", auth_type="invalid")  # type: ignore[arg-type]

    @pytest.mark.parametrize("missing_field", ["key", "name", "connector_type"])
    def test_negative_missing_required_field_raises(self, missing_field: str):
        kwargs = {"key": "k", "name": "N", "connector_type": "sap"}
        del kwargs[missing_field]
        with pytest.raises(ValidationError):
            ConnectorConfigIn(**kwargs)  # type: ignore[arg-type]

    def test_default_factory_metadata_independent(self):
        a = ConnectorConfigIn(key="a", name="A", connector_type="t")
        b = ConnectorConfigIn(key="b", name="B", connector_type="t")
        a.metadata["k"] = "v"
        assert b.metadata == {}

    def test_serialization_roundtrip(self):
        c = ConnectorConfigIn(key="k", name="N", connector_type="sap", auth_type="oauth2",
                              base_url="https://e", metadata={"k": "v"})
        assert ConnectorConfigIn(**c.model_dump()) == c


# ═══════════════════════════════════════════════════════════════════════
# ApprovalRequestIn
# ═══════════════════════════════════════════════════════════════════════
class TestApprovalRequestIn:
    """Tests for ApprovalRequestIn — Literal risk_level."""

    @pytest.mark.parametrize("risk_level", ["low", "medium", "high", "critical"])
    def test_positive_all_risk_level_values(self, risk_level: str):
        a = ApprovalRequestIn(
            title="T", action_type="create", resource_type="document",
            resource_id="d1", recommendation="approve", risk_level=risk_level,
        )
        assert a.risk_level == risk_level

    def test_default_values(self):
        a = ApprovalRequestIn(
            title="T", action_type="create", resource_type="document",
            resource_id="d1", recommendation="approve",
        )
        assert a.risk_level == "medium"
        assert a.required_roles == []
        assert a.payload == {}

    def test_negative_invalid_risk_level_rejected(self):
        with pytest.raises(ValidationError):
            ApprovalRequestIn(
                title="T", action_type="create", resource_type="document",
                resource_id="d1", recommendation="approve", risk_level="unknown",  # type: ignore[arg-type]
            )

    @pytest.mark.parametrize("missing_field", ["title", "action_type", "resource_type",
                                                 "resource_id", "recommendation"])
    def test_negative_missing_required_field_raises(self, missing_field: str):
        kwargs = {
            "title": "T", "action_type": "create", "resource_type": "document",
            "resource_id": "d1", "recommendation": "approve",
        }
        del kwargs[missing_field]
        with pytest.raises(ValidationError):
            ApprovalRequestIn(**kwargs)  # type: ignore[arg-type]

    def test_default_factory_required_roles_independent(self):
        a = ApprovalRequestIn(
            title="T", action_type="a", resource_type="d",
            resource_id="1", recommendation="r",
        )
        b = ApprovalRequestIn(
            title="T", action_type="a", resource_type="d",
            resource_id="1", recommendation="r",
        )
        a.required_roles.append("role")
        assert b.required_roles == []

    def test_serialization_roundtrip(self):
        a = ApprovalRequestIn(
            title="T", action_type="create", resource_type="document",
            resource_id="d1", recommendation="approve", risk_level="high",
            required_roles=["manager"], payload={"amount": 1000},
        )
        assert ApprovalRequestIn(**a.model_dump()) == a


# ═══════════════════════════════════════════════════════════════════════
# ApprovalDecisionIn
# ═══════════════════════════════════════════════════════════════════════
class TestApprovalDecisionIn:
    """Tests for ApprovalDecisionIn — single optional comment field."""

    def test_default_comment_empty(self):
        d = ApprovalDecisionIn()
        assert d.comment == ""

    def test_positive_explicit_comment(self):
        d = ApprovalDecisionIn(comment="Approved by manager")
        assert d.comment == "Approved by manager"

    def test_arabic_comment_accepted(self):
        d = ApprovalDecisionIn(comment="تمت الموافقة من المدير")
        assert d.comment == "تمت الموافقة من المدير"

    def test_boundary_empty_comment(self):
        d = ApprovalDecisionIn(comment="")
        assert d.comment == ""

    def test_serialization_roundtrip(self):
        d = ApprovalDecisionIn(comment="test")
        assert ApprovalDecisionIn(**d.model_dump()) == d
