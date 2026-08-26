from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    user: str  # SECURITY FIX: No default — user must be explicitly provided
    message: str
    workspace_id: str = "default"

class ChatResponse(BaseModel):
    response: str
    agent: str
    rag_found: int
    workspace_id: str
