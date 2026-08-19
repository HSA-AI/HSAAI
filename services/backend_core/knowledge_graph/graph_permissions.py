from fastapi import HTTPException

ROLE_GRAPH_PERMISSIONS = {
    "hsaai_admin": {"graph:read", "graph:write", "graph:admin", "graph:audit"},
    "knowledge_admin": {"graph:read", "graph:write", "graph:admin", "graph:audit"},
    "department_manager": {"graph:read", "graph:analytics"},
    "ai_user": {"graph:read"},
    "document_reviewer": {"graph:read"},
    "document_uploader": {"graph:read", "graph:write"},
    "auditor": {"graph:read", "graph:audit"},
    "agent": {"graph:read", "graph:context"},
    "admin": {"graph:read", "graph:write", "graph:admin", "graph:audit"},
}


def graph_scope(claims: dict) -> tuple[str, str, str]:
    return (claims.get("tenant_id") or "default", claims.get("workspace_id") or "default", claims.get("sub") or "system")


def has_graph_permission(claims: dict, permission: str) -> bool:
    roles = claims.get("roles") or ["ai_user"]
    allowed: set[str] = set()
    for role in roles:
        allowed |= ROLE_GRAPH_PERMISSIONS.get(str(role), set())
    return "graph:admin" in allowed or permission in allowed


def require_graph_permission(claims: dict, permission: str) -> None:
    if not has_graph_permission(claims, permission):
        raise HTTPException(status_code=403, detail=f"Knowledge Graph permission denied: {permission}")
