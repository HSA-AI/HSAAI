from __future__ import annotations
from typing import Any
from .base_connector import BaseEnterpriseConnector
from .connectors import (
    SAPS4HANAConnector, SuccessFactorsConnector, ActiveDirectoryConnector,
    OutlookExchangeConnector, SharePointConnector, PowerBIConnector, JiraConnector,
    ServiceDeskConnector, DMSConnector, DataWarehouseConnector,
)

CONNECTOR_CLASSES: dict[str, type[BaseEnterpriseConnector]] = {
    c.key: c for c in [
        SAPS4HANAConnector, SuccessFactorsConnector, ActiveDirectoryConnector,
        OutlookExchangeConnector, SharePointConnector, PowerBIConnector, JiraConnector,
        ServiceDeskConnector, DMSConnector, DataWarehouseConnector,
    ]
}

AGENT_DATA_SOURCES = {
    "supervisor": ["sap_s4hana", "successfactors", "active_directory", "sharepoint", "powerbi", "jira", "service_desk", "dms", "data_warehouse"],
    "hr": ["successfactors", "sharepoint", "dms"],
    "finance": ["sap_s4hana", "powerbi", "data_warehouse"],
    "it": ["active_directory", "jira", "service_desk", "outlook_exchange"],
    "knowledge": ["sharepoint", "dms"],
    "executive": ["sap_s4hana", "powerbi", "data_warehouse"],
}

WORKFLOW_CONNECTOR_MAP = {
    "purchase_request": ["sap_s4hana"],
    "hr_request": ["successfactors", "outlook_exchange"],
    "it_support": ["service_desk", "jira"],
    "sensitive_document": ["dms", "sharepoint"],
}

class ConnectorRegistry:
    def supported(self) -> list[dict[str, Any]]:
        items = []
        for key, cls in CONNECTOR_CLASSES.items():
            connector = cls()
            items.append({
                "key": key,
                "name": connector.name,
                "system_type": connector.system_type,
                "category": connector.category,
                "auth_type": connector.auth_type,
                "read_only": connector.read_only,
                "capabilities": connector.capabilities,
                "allowed_roles": connector.allowed_roles,
            })
        return items

    def create(self, key: str, config: dict[str, Any] | None = None) -> BaseEnterpriseConnector:
        if key not in CONNECTOR_CLASSES:
            raise KeyError(f"Unsupported connector: {key}")
        return CONNECTOR_CLASSES[key](config=config or {})

    def for_agent(self, agent_key: str) -> list[dict[str, Any]]:
        return [self.create(k).__dict__ | {"key": k, "name": self.create(k).name, "capabilities": self.create(k).capabilities} for k in AGENT_DATA_SOURCES.get(agent_key, [])]

registry = ConnectorRegistry()
