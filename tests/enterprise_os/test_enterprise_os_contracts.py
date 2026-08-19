def test_enterprise_os_router_contracts_exist():
    from backend_core.enterprise_os.router import router
    paths = {route.path for route in router.routes}
    required = {"/api/agents", "/api/supervisor/route", "/api/approvals", "/api/knowledge-graph", "/api/enterprise-search", "/api/finops/usage", "/api/monitoring"}
    assert required.issubset(paths)


def test_sensitive_action_policy():
    from backend_core.enterprise_os.router import SENSITIVE_ACTIONS
    assert "delete_document" in SENSITIVE_ACTIONS
    assert "modify_permissions" in SENSITIVE_ACTIONS
    assert "financial_action" in SENSITIVE_ACTIONS
