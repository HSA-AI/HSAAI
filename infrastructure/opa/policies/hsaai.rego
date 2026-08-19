package hsaai.authz

# HSAAI OPA Policy — Tenant Isolation + Tool Permissions
# ========================================================
# Every request must pass these policies.

# ─── Default Deny ───────────────────────────────────────────
default allow = false

# ─── Allow if user has valid token and tenant matches ───────
allow {
    input.user.tenant_id == input.resource.tenant_id
    valid_role
}

# ─── Role-based access control ──────────────────────────────
valid_role {
    input.user.role == "admin"
}

valid_role {
    input.user.role == "user"
    not admin_only_action
}

# ─── Admin-only actions ─────────────────────────────────────
admin_only_action {
    input.action == "delete_tenant"
}

admin_only_action {
    input.action == "modify_budget"
}

admin_only_action {
    input.action == "activate_kill_switch"
}

# ─── Tool permission scoping (LLM08) ────────────────────────
tool_allowed {
    input.tool.name in user_tool_permissions[input.user.role]
}

user_tool_permissions := {
    "admin": [
        "read_data", "write_file", "call_external_api",
        "create_record", "search_internal", "web_search",
        "rag_query", "send_external_email", "modify_config",
        # Admin-only (Severity 1) — requires two-person approval
        "delete_production_data", "execute_wire_transfer",
        "modify_payroll", "approve_large_contract",
    ],
    "user": [
        "read_data", "search_internal", "web_search",
        "rag_query", "create_record", "call_external_api",
    ],
    "governance": [
        "read_data", "search_internal", "audit_query",
        "activate_kill_switch", "modify_budget",
    ],
}

# ─── PII handling rules ─────────────────────────────────────
pii_redaction_required {
    input.tool.name == "call_external_api"
    input.tool.args.contains_pii == true
}
