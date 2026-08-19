from __future__ import annotations
from typing import Any
from pydantic import BaseModel, Field

class IntegrationConfigureIn(BaseModel):
    key: str = Field(..., examples=["sap_s4hana"])
    base_url: str = ""
    auth_type: str = "oauth2"
    credentials_ref: str = ""
    enabled: bool = True
    metadata: dict[str, Any] = {}

class ConnectorFetchIn(BaseModel):
    query: dict[str, Any] = {}

class AgentSourceIn(BaseModel):
    agent_key: str

class WorkflowSourceIn(BaseModel):
    template_key: str
