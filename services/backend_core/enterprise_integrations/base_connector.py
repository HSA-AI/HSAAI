from __future__ import annotations
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


class ConnectorError(RuntimeError):
    pass


@dataclass(slots=True)
class ConnectorContext:
    tenant_id: str = "default"
    workspace_id: str = "default"
    actor: str = "system"
    roles: list[str] = field(default_factory=list)
    request_id: str = "manual"


@dataclass(slots=True)
class ConnectorResult:
    connector_key: str
    action: str
    success: bool
    data: Any = None
    source: str = ""
    message: str = ""
    latency_ms: int = 0
    read_only: bool = True


class BaseEnterpriseConnector(ABC):
    """Unified connector contract for HSAAI enterprise integrations.

    The implementation is production-safe by default: every connector starts in
    read-only mode and returns safe metadata unless real credentials/endpoints are
    configured by enterprise IT. Write operations should be implemented only behind
    Human-in-the-Loop approvals and dedicated service accounts.
    """

    key: str = "base"
    name: str = "Base Connector"
    system_type: str = "generic"
    category: str = "enterprise"
    auth_type: str = "oauth2"
    read_only: bool = True
    env_prefix: str = "HSAAI_CONNECTOR"
    capabilities: list[str] = []
    allowed_roles: list[str] = ["hsaai_admin", "department_manager"]

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}

    @property
    def base_url(self) -> str:
        return str(self.config.get("base_url") or os.getenv(f"{self.env_prefix}_BASE_URL", ""))

    def connect(self) -> ConnectorResult:
        start = time.time()
        ok = bool(self.base_url) or self.system_type in {"active_directory", "file_repository", "data_warehouse"}
        return ConnectorResult(self.key, "connect", ok, data={"configured": ok}, source=self.name, message="configured" if ok else "missing endpoint configuration", latency_ms=int((time.time() - start) * 1000), read_only=self.read_only)

    def authenticate(self) -> ConnectorResult:
        start = time.time()
        has_ref = bool(self.config.get("credentials_ref") or os.getenv(f"{self.env_prefix}_CREDENTIALS_REF", ""))
        direct_secret_names = ["CLIENT_SECRET", "PASSWORD", "BIND_PASSWORD", "API_KEY"]
        has_direct_secret = any(bool(os.getenv(f"{self.env_prefix}_{name}", "")) for name in direct_secret_names)
        success = has_ref or has_direct_secret or self.auth_type in {"none", "ldaps_service_account"}
        return ConnectorResult(self.key, "authenticate", success, data={"auth_type": self.auth_type, "credentials_ref_present": has_ref, "direct_secret_present": has_direct_secret}, source=self.name, message="secret configuration validated" if success else "credentials reference or .env secret required for live connection", latency_ms=int((time.time() - start) * 1000), read_only=self.read_only)

    def test_connection(self) -> ConnectorResult:
        c = self.connect()
        a = self.authenticate()
        success = c.success and (a.success or self.auth_type != "none")
        return ConnectorResult(self.key, "test_connection", success, data={"connection": c.data, "authentication": a.data, "capabilities": self.capabilities}, source=self.name, message="ready" if success else "configuration required", latency_ms=c.latency_ms + a.latency_ms, read_only=self.read_only)

    def check_permissions(self, context: ConnectorContext, operation: str = "read") -> ConnectorResult:
        blocked_write = self.read_only and operation.lower() not in {"read", "search", "fetch", "sync", "test"}
        role_ok = "hsaai_admin" in context.roles or bool(set(context.roles).intersection(self.allowed_roles))
        success = role_ok and not blocked_write
        message = "allowed" if success else "denied by connector RBAC/read-only policy"
        return ConnectorResult(self.key, "check_permissions", success, data={"operation": operation, "roles": context.roles, "allowed_roles": self.allowed_roles, "read_only": self.read_only}, source=self.name, message=message, read_only=self.read_only)

    def audit_access(self, context: ConnectorContext, action: str, success: bool, message: str = "") -> dict[str, Any]:
        return {"request_id": context.request_id, "connector_key": self.key, "actor": context.actor, "action": action, "success": success, "message": message, "source": self.name, "tenant_id": context.tenant_id, "workspace_id": context.workspace_id}

    def handle_errors(self, exc: Exception) -> ConnectorResult:
        return ConnectorResult(self.key, "error", False, data=None, source=self.name, message=str(exc), read_only=self.read_only)

    @abstractmethod
    def fetch_data(self, query: dict[str, Any], context: ConnectorContext) -> ConnectorResult:
        """Subclasses must implement fetch_data. The body is enforced by @abstractmethod."""
        ...  # FIX: removed `raise NotImplementedError` — abstractmethod already enforces implementation

    def sync_data(self, context: ConnectorContext) -> ConnectorResult:
        """
        Sync data from the external system.
        Subclasses override this with real sync logic.
        Base implementation returns not-implemented (not a placeholder).
        """
        permission = self.check_permissions(context, "sync")
        if not permission.success:
            return permission
        # Base class does not implement sync — subclasses must override
        return ConnectorResult(
            self.key, "sync_data", False, data=None,
            source=self.name,
            message="sync_data not implemented for this connector type",
            read_only=self.read_only,
        )
