def test_platform_world_class_contracts_exist():
    from backend_core.enterprise_os.router import router
    paths = {route.path for route in router.routes}
    required = {
        "/api/platform/modules",
        "/api/platform/readiness",
        "/api/enterprise-search/facets",
        "/api/approvals/inbox",
        "/api/finops/forecast",
        "/api/security/posture",
        "/api/onboarding/checklist",
    }
    assert required.issubset(paths)


def test_supervisor_routes_new_enterprise_domains():
    from backend_core.enterprise_os.router import _route_agent
    assert _route_agent("اعرض مؤشرات الإدارة العليا و ROI للربع الحالي")[0] == "executive"
    assert _route_agent("راجع MFA و Zero Trust وسياسات الأمن")[0] == "security"
    assert _route_agent("حلل تشغيل المصنع وخط الإنتاج")[0] == "operations"


def test_critical_actions_have_executive_chain():
    from backend_core.enterprise_os.router import _approval_chain, _risk_level
    assert _risk_level("modify_permissions", "تعديل صلاحيات المستخدم") == "critical"
    assert "executive" in _approval_chain("critical", "IT")
