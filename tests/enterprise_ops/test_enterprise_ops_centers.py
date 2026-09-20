from backend_core.enterprise_ops.service import enterprise_ops_service


def test_agent_control_center_has_supervisor():
    data = enterprise_ops_service.agent_control_center()
    assert data["summary"]["agents"] >= 5
    assert any(a["key"] == "supervisor" for a in data["agents"])


def test_workflow_center_contains_core_templates():
    data = enterprise_ops_service.workflow_center()
    keys = {w["key"] for w in data["workflows"]}
    assert {"purchase_request", "document_approval", "leave_request", "it_ticket"}.issubset(keys)


def test_integrations_monitoring_contains_enterprise_systems():
    data = enterprise_ops_service.integrations_monitoring()
    keys = {c["key"] for c in data["connectors"]}
    assert {"sap", "sharepoint", "powerbi", "jira", "ad"}.issubset(keys)


def test_ai_operations_analytics_contains_models():
    data = enterprise_ops_service.ai_operations_analytics()
    keys = {m["key"] for m in data["models"]}
    assert {"qwen3", "llama3", "mistral"}.issubset(keys)
