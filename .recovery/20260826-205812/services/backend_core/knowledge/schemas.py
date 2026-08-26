from datetime import datetime
from pydantic import BaseModel, Field
from typing import Any, Literal

DocumentStatus = Literal["draft", "pending_review", "approved", "rejected", "archived"]
MatchSensitivity = Literal["normal", "sensitive", "confidential", "restricted"]

class KnowledgeSpaceCreate(BaseModel):
    key: str = Field(..., min_length=2, max_length=80)
    name: str
    description: str = ""
    owner: str = "system"
    classification: str = "internal"
    tenant_id: str = "default"
    workspace_id: str = "default"

class KnowledgeCollectionCreate(BaseModel):
    space_key: str
    key: str
    name: str
    description: str = ""
    tenant_id: str = "default"
    workspace_id: str = "default"

class KnowledgeDocumentRegister(BaseModel):
    space_key: str
    collection_key: str
    filename: str
    title: str = ""
    content_type: str = "application/octet-stream"
    size_bytes: int = 0
    classification: str = "internal"
    sensitivity: MatchSensitivity = "normal"
    department: str = "general"
    tags: list[str] = []
    status: DocumentStatus | None = None
    metadata: dict[str, Any] = {}
    uploaded_by: str = "system"
    tenant_id: str = "default"
    workspace_id: str = "default"

class DocumentWorkflowRequest(BaseModel):
    reason: str = ""

class KnowledgePermissionGrant(BaseModel):
    resource_type: str
    resource_key: str
    principal_type: str = "role"
    principal: str
    permission: str

class KnowledgeSearchRequest(BaseModel):
    query: str
    space_key: str | None = None
    collection_key: str | None = None
    tenant_id: str = "default"
    workspace_id: str = "default"
    limit: int = 8

class KnowledgeSpaceOut(BaseModel):
    id: int
    key: str
    name: str
    description: str
    owner: str
    classification: str
    is_active: bool
    created_at: datetime | None = None
    class Config:
        from_attributes = True
