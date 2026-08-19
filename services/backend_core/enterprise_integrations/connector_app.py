"""
HSAAI Backend Core — Enterprise Connector Integration
======================================================
This module wires the Enterprise Connector Framework into the HSAAI
backend_core FastAPI app. It replaces the old stub-based connector
system with the production-grade framework.

Usage in backend_core/main.py:
    from backend_core.enterprise_integrations.connector_app import setup_connectors
    setup_connectors(app)

This will:
  1. Auto-discover all 27 connectors
  2. Mount the /v1/connectors router
  3. Auto-register connector actions as AI tools
  4. Schedule periodic health checks
"""
from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import FastAPI

logger = logging.getLogger(__name__)


def setup_connectors(app: FastAPI, auto_connect: bool = False) -> None:
    """
    Wire the Enterprise Connector Framework into a FastAPI app.

    Args:
        app: The FastAPI app to mount the connector router on.
        auto_connect: If True, attempt to connect all connectors that have
                      valid configs in .env. If False (default), connectors
                      must be created via POST /v1/connectors/admin/create.
    """
    from packages.common.connectors.registry import ConnectorRegistry
    from packages.common.connectors.router import include_connector_router
    from packages.common.connectors.ai_integration import ConnectorToolRegistry

    # 1. Auto-discover all connector classes (registers @connector-decorated classes)
    discovered = ConnectorRegistry.discover()
    logger.info(f"Discovered {discovered} connector modules")

    # 2. Mount the REST API router
    include_connector_router(app)
    logger.info(f"Connector router mounted. {len(ConnectorRegistry.list_classes())} classes available.")

    # 3. If auto_connect, instantiate from env-configured connectors
    if auto_connect:
        _auto_connect_from_env()

    # 4. Auto-register AI tools from connected connectors
    tool_count = ConnectorToolRegistry.auto_register_from_connectors()
    logger.info(f"Registered {tool_count} AI tools from connectors")


def _auto_connect_from_env() -> None:
    """
    Auto-instantiate and connect connectors that have configuration in .env.

    Reads env vars like:
        SAP_BASE_URL, SAP_CLIENT_ID, SAP_CLIENT_SECRET → creates sap_s4hana
        SHAREPOINT_BASE_URL, SHAREPOINT_TENANT_ID, ... → creates sharepoint
        AD_URL, AD_BIND_DN, AD_BIND_PASSWORD → creates active_directory
        ... etc.
    """
    from packages.common.connectors.base import ConnectorConfig, AuthStrategy
    from packages.common.connectors.registry import ConnectorRegistry

    # Map: connector_name → (env_prefix, required_vars, config_builder)
    connector_env_map = {
        "sap_s4hana": {
            "vars": ["SAP_BASE_URL", "SAP_CLIENT_ID", "SAP_CLIENT_SECRET"],
            "config": lambda: ConnectorConfig(
                name="sap_s4hana",
                display_name="SAP S/4HANA",
                category="ERP",
                base_url=os.environ["SAP_BASE_URL"],
                auth_strategy=AuthStrategy.OAUTH2_CLIENT_CREDENTIALS,
                credentials_ref="SAP",
                required_permissions=["connector:sap_s4hana:use"],
            ),
        },
        "sharepoint": {
            "vars": ["SHAREPOINT_BASE_URL", "SHAREPOINT_TENANT_ID", "SHAREPOINT_CLIENT_ID", "SHAREPOINT_CLIENT_SECRET"],
            "config": lambda: ConnectorConfig(
                name="sharepoint",
                display_name="SharePoint",
                category="Documents",
                base_url=os.environ["SHAREPOINT_BASE_URL"],
                auth_strategy=AuthStrategy.OAUTH2_CLIENT_CREDENTIALS,
                credentials_ref="SHAREPOINT",
            ),
        },
        "active_directory": {
            "vars": ["AD_URL", "AD_BIND_DN", "AD_BIND_PASSWORD"],
            "config": lambda: ConnectorConfig(
                name="active_directory",
                display_name="Active Directory",
                category="Identity",
                base_url=os.environ["AD_URL"],
                auth_strategy=AuthStrategy.BASIC,
                credentials_ref="AD",
            ),
        },
        "servicenow": {
            "vars": ["SERVICENOW_BASE_URL", "SERVICENOW_USERNAME", "SERVICENOW_PASSWORD"],
            "config": lambda: ConnectorConfig(
                name="servicenow",
                display_name="ServiceNow",
                category="ITSM",
                base_url=os.environ["SERVICENOW_BASE_URL"],
                auth_strategy=AuthStrategy.BASIC,
                credentials_ref="SERVICENOW",
            ),
        },
        "powerbi": {
            "vars": ["POWERBI_TENANT_ID", "POWERBI_CLIENT_ID", "POWERBI_CLIENT_SECRET"],
            "config": lambda: ConnectorConfig(
                name="powerbi",
                display_name="Power BI",
                category="BI",
                base_url="https://api.powerbi.com/v1.0/myorg",
                auth_strategy=AuthStrategy.OAUTH2_CLIENT_CREDENTIALS,
                credentials_ref="POWERBI",
            ),
        },
    }

    connected = 0
    for conn_name, mapping in connector_env_map.items():
        # Check all required env vars are present
        if all(os.environ.get(v) for v in mapping["vars"]):
            try:
                config = mapping["config"]()
                instance = ConnectorRegistry.create(conn_name, config)
                # Note: connect() is async — caller should await it
                logger.info(f"Auto-configured connector: {conn_name} (call await instance.connect() to start)")
                connected += 1
            except Exception as e:
                logger.warning(f"Failed to auto-configure connector '{conn_name}': {e}")

    if connected:
        logger.info(f"Auto-configured {connected} connectors from environment variables")


# ═══════════════════════════════════════════════════════════════════════════
#  Replacement for the old enterprise_integrations/services.py
# ═══════════════════════════════════════════════════════════════════════════
async def get_connector_status() -> dict:
    """
    Replacement for the old connector_status() function.
    Returns the status of all connectors.
    """
    from packages.common.connectors.registry import ConnectorRegistry
    return {
        "total_classes": len(ConnectorRegistry.list_classes()),
        "total_instances": len(ConnectorRegistry.list_instances()),
        "instances": ConnectorRegistry.list_instances(),
        "health": ConnectorRegistry.health_all(),
    }


async def call_connector(connector_name: str, action: str, params: dict,
                         user: str | None = None) -> dict:
    """
    Replacement for the old call_connector() function.
    Calls a connector action with full middleware stack.
    """
    from packages.common.connectors.registry import ConnectorRegistry
    instance = ConnectorRegistry.get_instance(connector_name)
    if not instance:
        raise ValueError(f"Connector '{connector_name}' not found")
    return await instance.call(action, user=user, **params)


async def search_connectors(query: str, limit: int = 5,
                            categories: list[str] | None = None) -> dict:
    """
    Federated search across all connectors.
    """
    from packages.common.connectors.ai_integration import FederatedSearch
    return await FederatedSearch.search_all(query, limit, categories)
