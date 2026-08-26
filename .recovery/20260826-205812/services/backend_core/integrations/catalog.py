from backend_core.connectors.hsa_integrations import connector_status


def integration_catalog() -> dict:
    return {
        "platform": "HSAAI",
        "organization": "Hayel Saeed Anam Group",
        "principles": [
            "Internal-only by default",
            "Read-only enterprise integrations during pilot",
            "User permissions are inherited from source systems",
            "Every enterprise query is audited",
            "No external AI provider is allowed in strict mode",
        ],
        "connectors": connector_status(),
    }
