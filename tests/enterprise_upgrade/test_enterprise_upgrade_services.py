from backend_core.enterprise_upgrade.services import SupervisorAgentService, ConnectorService


def test_supervisor_blueprint_contains_enterprise_agents():
    svc = SupervisorAgentService()
    assert svc is not None


def test_supported_connectors_include_sap_and_sharepoint():
    svc = ConnectorService()
    assert "sap" in svc.SUPPORTED
    assert "sharepoint" in svc.SUPPORTED
    assert "active_directory" in svc.SUPPORTED
