from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Any, Literal

AgentKey = Literal["supervisor", "hr", "finance", "it", "legal", "executive"]
WorkflowTemplateKey = Literal["purchase_request", "document_review", "leave_request", "support_ticket"]

class AgentRouteRequest(BaseModel):
    message: str
    user_id: str = "system"
    tenant_id: str = "default"
    workspace_id: str = "default"
    roles: list[str] = Field(default_factory=list)
    department: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)

class AgentRouteResponse(BaseModel):
    request_id: str
    supervisor_decision: str
    selected_agent: AgentKey
    confidence: float
    plan: list[str]
    required_connectors: list[str]
    permission_status: str
    audit_event_id: str
    latency_ms: int

class WorkflowStartRequest(BaseModel):
    template_key: WorkflowTemplateKey
    title: str
    requested_by: str = "system"
    tenant_id: str = "default"
    workspace_id: str = "default"
    payload: dict[str, Any] = Field(default_factory=dict)

class WorkflowActionRequest(BaseModel):
    execution_id: str
    action: Literal["approve", "reject", "complete_step", "escalate"]
    actor: str = "system"
    comment: str = ""

class ConnectorRuntimeRequest(BaseModel):
    connector_key: str
    action: Literal["test", "sync", "health", "fetch"] = "health"
    query: dict[str, Any] = Field(default_factory=dict)

class ObservabilityEventIn(BaseModel):
    event_type: str
    component: str
    status: str = "ok"
    latency_ms: int = 0
    tokens: int = 0
    model: str = ""
    agent: str = ""
    workflow: str = ""
    connector: str = ""
    error_message: str = ""
    tenant_id: str = "default"
    workspace_id: str = "default"
