from backend_core.enterprise_integrations.connector_registry import registry, AGENT_DATA_SOURCES
from backend_core.enterprise_integrations.base_connector import ConnectorContext


def test_supported_connectors_include_hsa_core_systems():
    keys = {item["key"] for item in registry.supported()}
    assert "sap_s4hana" in keys
    assert "successfactors" in keys
    assert "active_directory" in keys
    assert "outlook_exchange" in keys
    assert "sharepoint" in keys
    assert "powerbi" in keys
    assert "jira" in keys
    assert "service_desk" in keys
    assert "dms" in keys
    assert "data_warehouse" in keys


def test_data_warehouse_blocks_write_sql():
    connector = registry.create("data_warehouse")
    result = connector.fetch_data({"sql": "DROP TABLE employees"}, ConnectorContext(roles=["hsaai_admin"]))
    assert result.success is False
    assert "read-only" in result.message.lower()


def test_agent_data_source_mapping():
    assert AGENT_DATA_SOURCES["hr"] == ["successfactors", "sharepoint", "dms"]
    assert "sap_s4hana" in AGENT_DATA_SOURCES["finance"]
    assert "powerbi" in AGENT_DATA_SOURCES["executive"]


def test_connector_permission_enforces_role_policy():
    connector = registry.create("sap_s4hana")
    denied = connector.fetch_data({"subject": "monthly_purchases"}, ConnectorContext(roles=["ai_user"]))
    assert denied.success is False
    allowed = connector.fetch_data({"subject": "monthly_purchases"}, ConnectorContext(roles=["hsaai_admin"]))
    assert allowed.success is True
