from pydantic import BaseModel, Field
from typing import Any

class DepartmentAgentBase(BaseModel):
    key: str = Field(..., description="Stable agent key, e.g. hr, finance, it")
    name: str
    department: str = "general"
    description: str = ""
    system_prompt: str
    allowed_roles: list[str] = Field(default_factory=list)
    knowledge_scopes: list[str] = Field(default_factory=list)
    escalation_target: str = ""
    priority: int = 100
    enabled: bool = True

class DepartmentAgentCreate(DepartmentAgentBase):
    pass

class DepartmentAgentUpdate(BaseModel):
    name: str | None = None
    department: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    allowed_roles: list[str] | None = None
    knowledge_scopes: list[str] | None = None
    escalation_target: str | None = None
    priority: int | None = None
    enabled: bool | None = None

class DepartmentAgentOut(DepartmentAgentBase):
    id: int | None = None
    tenant_id: str = "default"
    workspace_id: str = "default"

class AgentRouteRequest(BaseModel):
    message: str
    tenant_id: str = "default"
    workspace_id: str = "default"
    user_roles: list[str] = Field(default_factory=list)
    department: str = "default"

class AgentRouteResult(BaseModel):
    matched: bool
    agent_key: str
    agent_name: str
    department: str
    score: float
    reason: str
    allowed: bool = True
    fallback_agent: str = "general"
    metadata: dict[str, Any] = Field(default_factory=dict)
