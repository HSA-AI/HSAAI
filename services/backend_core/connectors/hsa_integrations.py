"""HSAAI enterprise connector status catalog.

This module is intentionally dependency-light so the core backend can boot even
before real SAP, Windows Server, AD, SharePoint, BI, HR, or ITSM credentials are
provided by the enterprise IT team. Real connector clients live under
``backend.integrations`` and should be enabled by environment variables.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, asdict
from typing import Literal

ConnectorState = Literal["configured", "not_configured", "disabled"]


@dataclass(frozen=True)
class ConnectorStatus:
    key: str
    name: str
    category: str
    state: ConnectorState
    mode: str
    endpoint_env: str | None = None
    security_note: str = "Read-only until enterprise approval."


def _state(required_env: str | None, enabled_env: str | None = None) -> ConnectorState:
    if enabled_env and os.getenv(enabled_env, "false").lower() not in {"1", "true", "yes"}:
        return "disabled"
    if not required_env:
        return "configured"
    return "configured" if os.getenv(required_env) else "not_configured"


def connector_status() -> list[dict]:
    """Return a safe status list for enterprise systems integration.

    The function never exposes secrets. It reports only whether required endpoint
    variables are present and whether the connector is enabled.
    """
    connectors = [
        ConnectorStatus("sap_s4hana", "SAP S/4HANA", "ERP", _state("SAP_S4HANA_BASE_URL", "SAP_S4HANA_ENABLED"), "OData/REST Read-Only", "SAP_S4HANA_BASE_URL"),
        ConnectorStatus("sap_bydesign", "SAP Business ByDesign", "ERP", _state("SAP_BYDESIGN_BASE_URL", "SAP_BYDESIGN_ENABLED"), "OData/SOAP Read-Only", "SAP_BYDESIGN_BASE_URL"),
        ConnectorStatus("active_directory", "Windows Server Active Directory", "Identity", _state("LDAP_SERVER_URL", "LDAP_ENABLED"), "LDAPS / Kerberos / NTLM", "LDAP_SERVER_URL", "Federate through Keycloak where possible."),
        ConnectorStatus("file_server", "Windows File Server / SMB", "Documents", _state("SMB_SERVER", "SMB_ENABLED"), "SMB 3.1.1 Read-Only Sync", "SMB_SERVER", "Must preserve NTFS ACL permissions."),
        ConnectorStatus("sharepoint", "SharePoint / DMS", "Documents", _state("SHAREPOINT_SITE_URL", "SHAREPOINT_ENABLED"), "Microsoft Graph Read-Only", "SHAREPOINT_SITE_URL"),
        ConnectorStatus("bi", "BI / Analytics", "Analytics", _state("BI_GATEWAY_URL", "BI_ENABLED"), "REST/OData Read-Only", "BI_GATEWAY_URL"),
        ConnectorStatus("hr", "HR System", "People", _state("HR_SYSTEM_BASE_URL", "HR_SYSTEM_ENABLED"), "REST/SOAP Read-Only", "HR_SYSTEM_BASE_URL", "HR data must remain role-restricted."),
        ConnectorStatus("itsm", "ITSM / Service Desk", "Operations", _state("ITSM_BASE_URL", "ITSM_ENABLED"), "REST API", "ITSM_BASE_URL"),
    ]
    return [asdict(c) for c in connectors]
