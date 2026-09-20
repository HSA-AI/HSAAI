
from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel, Field

class AgentRouteRequest(BaseModel):
    message: str
    workspace_id: str = "default"
    session_id: str = "default"
    context: dict[str, Any] = Field(default_factory=dict)

class AgentRouteResponse(BaseModel):
    supervisor_decision: str
    selected_agent: str
    selected_department: str
    confidence: float
    reason: str
    allowed: bool
    required_roles: list[str]
    next_steps: list[str]

class WorkflowTemplateIn(BaseModel):
    key: str
    name: str
    description: str = ""
    category: str = "general"
    definition: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True

class WorkflowStartRequest(BaseModel):
    template_key: str
    payload: dict[str, Any] = Field(default_factory=dict)
    requested_by: str = "system"

class ConnectorConfigIn(BaseModel):
    key: str
    name: str
    connector_type: str
    auth_type: Literal["oauth2", "oidc", "api_key", "service_account", "basic", "none"] = "none"
    base_url: str = ""
    schedule: str = "manual"
    secrets_ref: str = ""
    enabled: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)

class ApprovalRequestIn(BaseModel):
    title: str
    action_type: str
    resource_type: str
    resource_id: str
    recommendation: str
    risk_level: Literal["low", "medium", "high", "critical"] = "medium"
    required_roles: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)

class ApprovalDecisionIn(BaseModel):
    comment: str = ""
