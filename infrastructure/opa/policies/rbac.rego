# HSAAI RBAC Policy (v3.0)
# Baseline role-to-permission mapping. Loaded into OPA as data.

package hsaai.rbac

# Permission mapping (matches Python ROLE_PERMISSIONS in rbac.py)
role_permissions := {
    "hsaai_admin": {"*"},  # wildcard = all permissions
    "knowledge_admin": {
        "chat:write", "files:write", "knowledge:read", "knowledge:write",
        "knowledge:admin", "knowledge:review", "knowledge:delete",
        "audit:read", "analytics:read", "agents:read", "agents:admin",
        "agents:execute", "workflows:read", "observability:read",
        "approvals:create", "approvals:read", "graph:read", "graph:write",
        "graph:admin", "graph:audit", "executive:read",
    },
    "document_reviewer": {
        "chat:write", "knowledge:read", "knowledge:review",
        "audit:read", "agents:read", "agents:execute",
        "approvals:read", "approvals:decide", "executive:read",
    },
    "document_uploader": {
        "chat:write", "files:write", "knowledge:read", "knowledge:upload",
        "knowledge:write", "agents:read", "agents:execute", "approvals:create",
    },
    "department_manager": {
        "chat:write", "knowledge:read", "analytics:read", "reports:read",
        "agents:read", "agents:execute", "workflows:read", "workflows:execute",
        "approvals:create", "approvals:read", "approvals:decide",
        "connectors:read", "connectors:sync", "observability:read",
        "graph:read", "executive:read",
    },
    "ai_user": {
        "chat:write", "knowledge:read", "agents:read", "agents:execute",
        "approvals:create", "graph:read",
    },
    "auditor": {
        "knowledge:read", "audit:read", "analytics:read", "reports:read",
        "agents:read", "workflows:read", "connectors:read",
        "observability:read", "approvals:read", "graph:read", "graph:audit",
        "executive:read",
    },
    "executive": {
        "chat:write", "knowledge:read", "analytics:read", "reports:read",
        "executive:read", "executive:write",
    },
}

# Get all permissions for a list of roles
permissions_for_roles(roles) := perms {
    perms := {p |
        some role in roles
        some p
        role_permissions[role][p]
    }
}

# Check if user with given roles has a specific permission
has_permission(roles, permission) {
    role_permissions["hsaai_admin"][_] == "*"
    role in roles
    role == "hsaai_admin"
}

has_permission(roles, permission) {
    perms := permissions_for_roles(roles)
    permission in perms
}

# Wildcard check for hsaai_admin
has_permission(roles, permission) {
    "hsaai_admin" in roles
}
