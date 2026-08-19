
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Any, Literal

class RuntimeContext(BaseModel):
    tenant_id: str = "default"
    workspace_id: str = "default"
    user_id: str = "system"
    department: str = "general"

class AgentRunRequest(BaseModel):
    agent_id: str = Field(default="supervisor")
    task: str
    context: RuntimeContext = Field(default_factory=RuntimeContext)
    tools: list[str] = Field(default_factory=list)
    require_sources: bool = True

class WorkflowStep(BaseModel):
    id: str
    type: Literal["agent", "rag", "llm", "approval", "integration", "policy_check"] = "agent"
    name: str
    input: dict[str, Any] = Field(default_factory=dict)

class WorkflowRunRequest(BaseModel):
    workflow_id: str = "ad-hoc"
    goal: str
    context: RuntimeContext = Field(default_factory=RuntimeContext)
    steps: list[WorkflowStep] = Field(default_factory=list)

class ModelRouteRequest(BaseModel):
    task: str
    sensitivity: Literal["low", "medium", "high", "restricted"] = "medium"
    language: str = "ar"
    max_latency_ms: int | None = None
    require_local_only: bool = True

class EnterpriseSearchRequest(BaseModel):
    query: str
    context: RuntimeContext = Field(default_factory=RuntimeContext)
    sources: list[str] = Field(default_factory=lambda: ["rag", "agents", "integrations", "audit"])
    top_k: int = 8
    answer: bool = True

class ObservabilityEvent(BaseModel):
    event_type: str
    component: str
    tenant_id: str = "default"
    workspace_id: str = "default"
    latency_ms: int | None = None
    tokens_in: int = 0
    tokens_out: int = 0
    model: str | None = None
    success: bool = True
    risk_level: str = "low"
    metadata: dict[str, Any] = Field(default_factory=dict)
