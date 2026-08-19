"""
HSAAI Enterprise AI Platform — Base Enterprise Connector Test Suite (v7.0)
============================================================================
Comprehensive tests for `services/backend_core/enterprise_integrations/base_connector.py`.

Coverage targets:
  - ConnectorError exception
  - ConnectorContext dataclass (4 fields, defaults, slots)
  - ConnectorResult dataclass (9 fields, defaults, slots)
  - BaseEnterpriseConnector abstract class:
      * Class attributes (key, name, system_type, category, auth_type, read_only,
        env_prefix, capabilities, allowed_roles)
      * __init__ with config dict
      * base_url property (config > env var)
      * connect() — base_url check + system_type whitelist
      * authenticate() — credentials_ref check + direct secret env vars + auth_type whitelist
      * test_connection() — combined connect + authenticate
      * check_permissions() — RBAC + read-only/write-blocking
      * audit_access() — returns audit dict
      * handle_errors() — wraps exception in ConnectorResult
      * sync_data() — base implementation returns not-implemented
      * fetch_data() — abstract method enforcement

Test categories:
  - Positive: each method's happy path
  - Negative: missing config, denied permissions, abstract instantiation
  - Boundary: empty config, empty roles, None values
  - Validation: read-only enforcement, role intersection logic
  - Serialization: ConnectorResult dataclass asdict round-trip
  - Defaults: every dataclass default verified
  - Edge cases: system_type whitelist, direct secret env vars

Rules:
  - Minimal Mocks (only os.getenv where needed for env-var tests)
  - Independent (each test creates its own connector instance)
  - Concrete subclass provided for abstract method testing
"""
from __future__ import annotations

import os
import sys
import time
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

import pytest

# ─── Path setup ────────────────────────────────────────────────────────
_BASE = Path(__file__).resolve().parents[2]
_SERVICES = _BASE / "services"
for _p in [str(_SERVICES), str(_BASE / "packages"), str(_BASE / "packages" / "common")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend_core.enterprise_integrations.base_connector import (  # noqa: E402
    BaseEnterpriseConnector,
    ConnectorContext,
    ConnectorError,
    ConnectorResult,
)


# ═══════════════════════════════════════════════════════════════════════
# Concrete test subclass (required because BaseEnterpriseConnector is ABC)
# ═══════════════════════════════════════════════════════════════════════
class _TestConnector(BaseEnterpriseConnector):
    """Minimal concrete subclass for testing the base class.

    Implements the abstract fetch_data method with a simple stub.
    """
    key = "test_connector"
    name = "Test Connector"
    system_type = "generic"

    def fetch_data(self, query, context):
        return ConnectorResult(
            connector_key=self.key,
            action="fetch_data",
            success=True,
            data=query,
            source=self.name,
            read_only=self.read_only,
        )


class _ReadOnlySystemConnector(BaseEnterpriseConnector):
    """Connector whose system_type is in the read-only whitelist."""
    key = "ad_connector"
    name = "Active Directory"
    system_type = "active_directory"
    auth_type = "ldaps_service_account"

    def fetch_data(self, query, context):
        return ConnectorResult(self.key, "fetch", True, data=query, source=self.name, read_only=self.read_only)


class _NoAuthConnector(BaseEnterpriseConnector):
    """Connector with auth_type='none' — should pass authenticate without secrets."""
    key = "file_repo"
    name = "File Repository"
    system_type = "file_repository"
    auth_type = "none"

    def fetch_data(self, query, context):
        return ConnectorResult(self.key, "fetch", True, data=query, source=self.name, read_only=self.read_only)


# ═══════════════════════════════════════════════════════════════════════
# ConnectorError
# ═══════════════════════════════════════════════════════════════════════
class TestConnectorError:
    """Verify ConnectorError is a RuntimeError subclass."""

    def test_is_runtime_error_subclass(self):
        assert issubclass(ConnectorError, RuntimeError)

    def test_can_be_raised_and_caught(self):
        with pytest.raises(ConnectorError, match="test error"):
            raise ConnectorError("test error")

    def test_caught_as_runtime_error(self):
        """ConnectorError can be caught as RuntimeError (polymorphism)."""
        with pytest.raises(RuntimeError):
            raise ConnectorError("polymorphic")


# ═══════════════════════════════════════════════════════════════════════
# ConnectorContext dataclass
# ═══════════════════════════════════════════════════════════════════════
class TestConnectorContext:
    """Tests for the ConnectorContext dataclass."""

    def test_default_values(self):
        ctx = ConnectorContext()
        assert ctx.tenant_id == "default"
        assert ctx.workspace_id == "default"
        assert ctx.actor == "system"
        assert ctx.roles == []
        assert ctx.request_id == "manual"

    def test_positive_explicit_values(self):
        ctx = ConnectorContext(
            tenant_id="t1",
            workspace_id="w1",
            actor="user-1",
            roles=["hsaai_admin", "department_manager"],
            request_id="req-123",
        )
        assert ctx.tenant_id == "t1"
        assert ctx.actor == "user-1"
        assert "hsaai_admin" in ctx.roles

    def test_default_factory_roles_independent(self):
        """default_factory=list creates new list per instance (no shared state)."""
        a = ConnectorContext()
        b = ConnectorContext()
        a.roles.append("role_a")
        assert b.roles == []

    def test_slots_prevents_new_attributes(self):
        """@dataclass(slots=True) prevents adding new attributes."""
        ctx = ConnectorContext()
        with pytest.raises(AttributeError):
            ctx.new_field = "value"  # type: ignore[attr-defined]

    def test_serialization_via_asdict(self):
        """dataclasses.asdict produces a serializable dict."""
        ctx = ConnectorContext(tenant_id="t1", roles=["r1"])
        d = asdict(ctx)
        assert d == {
            "tenant_id": "t1",
            "workspace_id": "default",
            "actor": "system",
            "roles": ["r1"],
            "request_id": "manual",
        }

    def test_boundary_empty_strings(self):
        """Empty strings accepted (no validation constraints)."""
        ctx = ConnectorContext(tenant_id="", workspace_id="", actor="")
        assert ctx.tenant_id == ""

    def test_boundary_empty_roles_list(self):
        """Empty roles list is the default and is valid."""
        ctx = ConnectorContext(roles=[])
        assert ctx.roles == []


# ═══════════════════════════════════════════════════════════════════════
# ConnectorResult dataclass
# ═══════════════════════════════════════════════════════════════════════
class TestConnectorResult:
    """Tests for the ConnectorResult dataclass."""

    def test_required_fields(self):
        """connector_key, action, success are required."""
        result = ConnectorResult(
            connector_key="test",
            action="connect",
            success=True,
        )
        assert result.connector_key == "test"
        assert result.action == "connect"
        assert result.success is True

    def test_default_values(self):
        """data, source, message, latency_ms, read_only have defaults."""
        result = ConnectorResult(connector_key="k", action="a", success=True)
        assert result.data is None
        assert result.source == ""
        assert result.message == ""
        assert result.latency_ms == 0
        assert result.read_only is True

    def test_positive_full_payload(self):
        result = ConnectorResult(
            connector_key="sap",
            action="fetch_data",
            success=True,
            data={"records": [1, 2, 3]},
            source="SAP S/4HANA",
            message="200 records fetched",
            latency_ms=234,
            read_only=False,
        )
        assert result.data["records"] == [1, 2, 3]
        assert result.latency_ms == 234
        assert result.read_only is False

    def test_slots_prevents_new_attributes(self):
        result = ConnectorResult(connector_key="k", action="a", success=True)
        with pytest.raises(AttributeError):
            result.new_field = "value"  # type: ignore[attr-defined]

    def test_serialization_via_asdict(self):
        """asdict round-trips the result (data preserved as Any)."""
        result = ConnectorResult(
            connector_key="k",
            action="a",
            success=False,
            data={"key": "value"},
            source="src",
            message="error",
            latency_ms=100,
            read_only=True,
        )
        d = asdict(result)
        assert d["success"] is False
        assert d["data"] == {"key": "value"}
        assert d["latency_ms"] == 100

    def test_boundary_zero_latency(self):
        """latency_ms=0 is valid (fast operations)."""
        result = ConnectorResult(connector_key="k", action="a", success=True, latency_ms=0)
        assert result.latency_ms == 0

    def test_boundary_none_data(self):
        """data=None is the default for failed/empty results."""
        result = ConnectorResult(connector_key="k", action="error", success=False, data=None)
        assert result.data is None

    def test_data_accepts_arbitrary_types(self):
        """data is Any — list, dict, str, int, None all valid."""
        for data_value in [[1, 2, 3], {"k": "v"}, "string", 42, None, True]:
            result = ConnectorResult(connector_key="k", action="a", success=True, data=data_value)
            assert result.data == data_value


# ═══════════════════════════════════════════════════════════════════════
# BaseEnterpriseConnector — class attributes & instantiation
# ═══════════════════════════════════════════════════════════════════════
class TestBaseEnterpriseConnectorAttributes:
    """Verify class attributes exist with documented defaults."""

    def test_class_attributes_exist(self):
        """All 9 documented class attributes exist on the base class."""
        assert hasattr(BaseEnterpriseConnector, "key")
        assert hasattr(BaseEnterpriseConnector, "name")
        assert hasattr(BaseEnterpriseConnector, "system_type")
        assert hasattr(BaseEnterpriseConnector, "category")
        assert hasattr(BaseEnterpriseConnector, "auth_type")
        assert hasattr(BaseEnterpriseConnector, "read_only")
        assert hasattr(BaseEnterpriseConnector, "env_prefix")
        assert hasattr(BaseEnterpriseConnector, "capabilities")
        assert hasattr(BaseEnterpriseConnector, "allowed_roles")

    def test_default_class_attribute_values(self):
        """Verify the documented default values."""
        assert BaseEnterpriseConnector.key == "base"
        assert BaseEnterpriseConnector.name == "Base Connector"
        assert BaseEnterpriseConnector.system_type == "generic"
        assert BaseEnterpriseConnector.category == "enterprise"
        assert BaseEnterpriseConnector.auth_type == "oauth2"
        assert BaseEnterpriseConnector.read_only is True
        assert BaseEnterpriseConnector.env_prefix == "HSAAI_CONNECTOR"
        assert BaseEnterpriseConnector.capabilities == []
        assert BaseEnterpriseConnector.allowed_roles == ["hsaai_admin", "department_manager"]

    def test_cannot_instantiate_abstract_class_directly(self):
        """ABC enforcement: cannot instantiate BaseEnterpriseConnector without fetch_data."""
        with pytest.raises(TypeError, match="abstract"):
            BaseEnterpriseConnector()  # type: ignore[abstract]

    def test_concrete_subclass_can_be_instantiated(self):
        """_TestConnector implements fetch_data — instantiation succeeds."""
        connector = _TestConnector()
        assert connector.key == "test_connector"

    def test_init_with_none_config(self):
        """__init__ accepts None config and defaults to empty dict."""
        connector = _TestConnector(config=None)
        assert connector.config == {}

    def test_init_with_empty_config(self):
        connector = _TestConnector(config={})
        assert connector.config == {}

    def test_init_with_config_dict(self):
        connector = _TestConnector(config={"base_url": "https://api.example.com"})
        assert connector.config["base_url"] == "https://api.example.com"


# ═══════════════════════════════════════════════════════════════════════
# base_url property
# ═══════════════════════════════════════════════════════════════════════
class TestBaseUrlProperty:
    """Verify base_url reads from config first, then env var."""

    def test_base_url_from_config(self):
        """Config takes precedence over env var."""
        connector = _TestConnector(config={"base_url": "https://config.example.com"})
        assert connector.base_url == "https://config.example.com"

    def test_base_url_from_env_when_config_missing(self, monkeypatch):
        """Env var {ENV_PREFIX}_BASE_URL is used when config has no base_url."""
        monkeypatch.setenv("HSAAI_CONNECTOR_BASE_URL", "https://env.example.com")
        connector = _TestConnector(config={})
        assert connector.base_url == "https://env.example.com"

    def test_base_url_empty_when_neither_config_nor_env(self, monkeypatch):
        """Returns empty string when neither config nor env is set."""
        monkeypatch.delenv("HSAAI_CONNECTOR_BASE_URL", raising=False)
        connector = _TestConnector(config={})
        assert connector.base_url == ""

    def test_config_takes_precedence_over_env(self, monkeypatch):
        """When both config and env are set, config wins."""
        monkeypatch.setenv("HSAAI_CONNECTOR_BASE_URL", "https://env.example.com")
        connector = _TestConnector(config={"base_url": "https://config.example.com"})
        assert connector.base_url == "https://config.example.com"

    def test_empty_config_base_url_falls_back_to_env(self, monkeypatch):
        """Empty string in config falls back to env var."""
        monkeypatch.setenv("HSAAI_CONNECTOR_BASE_URL", "https://env.example.com")
        connector = _TestConnector(config={"base_url": ""})
        assert connector.base_url == "https://env.example.com"


# ═══════════════════════════════════════════════════════════════════════
# connect()
# ═══════════════════════════════════════════════════════════════════════
class TestConnect:
    """Tests for the connect() method."""

    def test_connect_success_with_base_url(self):
        """connect() succeeds when base_url is set."""
        connector = _TestConnector(config={"base_url": "https://api.example.com"})
        result = connector.connect()
        assert result.success is True
        assert result.action == "connect"
        assert result.data["configured"] is True
        assert "configured" in result.message

    def test_connect_fails_without_base_url(self, monkeypatch):
        """connect() fails when base_url is empty (for generic system_type)."""
        monkeypatch.delenv("HSAAI_CONNECTOR_BASE_URL", raising=False)
        connector = _TestConnector(config={})
        result = connector.connect()
        assert result.success is False
        assert "missing endpoint" in result.message

    def test_connect_succeeds_for_active_directory_without_base_url(self, monkeypatch):
        """active_directory is whitelisted — connect succeeds even without base_url."""
        monkeypatch.delenv("HSAAI_CONNECTOR_BASE_URL", raising=False)
        connector = _ReadOnlySystemConnector(config={})
        result = connector.connect()
        assert result.success is True

    def test_connect_succeeds_for_file_repository_without_base_url(self, monkeypatch):
        """file_repository is whitelisted — connect succeeds even without base_url."""
        monkeypatch.delenv("HSAAI_CONNECTOR_BASE_URL", raising=False)

        class _FileRepoConnector(BaseEnterpriseConnector):
            key = "file_repo"
            system_type = "file_repository"
            auth_type = "none"
            def fetch_data(self, query, context):
                return ConnectorResult(self.key, "fetch", True, read_only=self.read_only)

        connector = _FileRepoConnector(config={})
        result = connector.connect()
        assert result.success is True

    def test_connect_returns_connector_result(self):
        """Return type is ConnectorResult."""
        connector = _TestConnector(config={"base_url": "https://api.example.com"})
        result = connector.connect()
        assert isinstance(result, ConnectorResult)

    def test_connect_latency_is_non_negative(self):
        """latency_ms must be >= 0."""
        connector = _TestConnector(config={"base_url": "https://api.example.com"})
        result = connector.connect()
        assert result.latency_ms >= 0

    def test_connect_preserves_read_only_flag(self):
        """read_only in result matches connector's read_only attribute."""
        connector = _TestConnector(config={"base_url": "https://api.example.com"})
        # _TestConnector inherits read_only=True from base
        result = connector.connect()
        assert result.read_only is True


# ═══════════════════════════════════════════════════════════════════════
# authenticate()
# ═══════════════════════════════════════════════════════════════════════
class TestAuthenticate:
    """Tests for the authenticate() method."""

    def test_authenticate_success_with_credentials_ref(self):
        """Succeeds when credentials_ref is in config."""
        connector = _TestConnector(config={"credentials_ref": "vault/sap/creds"})
        result = connector.authenticate()
        assert result.success is True
        assert result.data["credentials_ref_present"] is True

    def test_authenticate_fails_without_any_secret(self, monkeypatch):
        """Fails when no credentials_ref and no direct env secrets and auth_type is oauth2."""
        # Clear all direct secret env vars
        for name in ["CLIENT_SECRET", "PASSWORD", "BIND_PASSWORD", "API_KEY"]:
            monkeypatch.delenv(f"HSAAI_CONNECTOR_{name}", raising=False)
        monkeypatch.delenv("HSAAI_CONNECTOR_CREDENTIALS_REF", raising=False)
        connector = _TestConnector(config={})  # auth_type='oauth2' default
        result = connector.authenticate()
        assert result.success is False
        assert "credentials" in result.message.lower()

    def test_authenticate_succeeds_with_direct_client_secret(self, monkeypatch):
        """Succeeds when HSAAI_CONNECTOR_CLIENT_SECRET env var is set."""
        for name in ["CLIENT_SECRET", "PASSWORD", "BIND_PASSWORD", "API_KEY"]:
            monkeypatch.delenv(f"HSAAI_CONNECTOR_{name}", raising=False)
        monkeypatch.setenv("HSAAI_CONNECTOR_CLIENT_SECRET", "secret123")
        connector = _TestConnector(config={})
        result = connector.authenticate()
        assert result.success is True
        assert result.data["direct_secret_present"] is True

    def test_authenticate_succeeds_with_direct_password(self, monkeypatch):
        """Succeeds when HSAAI_CONNECTOR_PASSWORD env var is set."""
        for name in ["CLIENT_SECRET", "PASSWORD", "BIND_PASSWORD", "API_KEY"]:
            monkeypatch.delenv(f"HSAAI_CONNECTOR_{name}", raising=False)
        monkeypatch.setenv("HSAAI_CONNECTOR_PASSWORD", "pw123")
        connector = _TestConnector(config={})
        result = connector.authenticate()
        assert result.success is True

    def test_authenticate_succeeds_with_direct_bind_password(self, monkeypatch):
        """Succeeds when HSAAI_CONNECTOR_BIND_PASSWORD env var is set."""
        for name in ["CLIENT_SECRET", "PASSWORD", "BIND_PASSWORD", "API_KEY"]:
            monkeypatch.delenv(f"HSAAI_CONNECTOR_{name}", raising=False)
        monkeypatch.setenv("HSAAI_CONNECTOR_BIND_PASSWORD", "bind123")
        connector = _TestConnector(config={})
        result = connector.authenticate()
        assert result.success is True

    def test_authenticate_succeeds_with_direct_api_key(self, monkeypatch):
        """Succeeds when HSAAI_CONNECTOR_API_KEY env var is set."""
        for name in ["CLIENT_SECRET", "PASSWORD", "BIND_PASSWORD", "API_KEY"]:
            monkeypatch.delenv(f"HSAAI_CONNECTOR_{name}", raising=False)
        monkeypatch.setenv("HSAAI_CONNECTOR_API_KEY", "key123")
        connector = _TestConnector(config={})
        result = connector.authenticate()
        assert result.success is True

    def test_authenticate_succeeds_for_auth_type_none(self, monkeypatch):
        """auth_type='none' always succeeds (no secret needed)."""
        for name in ["CLIENT_SECRET", "PASSWORD", "BIND_PASSWORD", "API_KEY"]:
            monkeypatch.delenv(f"HSAAI_CONNECTOR_{name}", raising=False)
        monkeypatch.delenv("HSAAI_CONNECTOR_CREDENTIALS_REF", raising=False)
        connector = _NoAuthConnector(config={})
        result = connector.authenticate()
        assert result.success is True

    def test_authenticate_succeeds_for_ldaps_service_account(self, monkeypatch):
        """auth_type='ldaps_service_account' succeeds without secrets (per whitelist)."""
        for name in ["CLIENT_SECRET", "PASSWORD", "BIND_PASSWORD", "API_KEY"]:
            monkeypatch.delenv(f"HSAAI_CONNECTOR_{name}", raising=False)
        monkeypatch.delenv("HSAAI_CONNECTOR_CREDENTIALS_REF", raising=False)
        connector = _ReadOnlySystemConnector(config={})  # auth_type='ldaps_service_account'
        result = connector.authenticate()
        assert result.success is True

    def test_authenticate_data_includes_auth_type(self):
        """Result data includes the auth_type for audit logging."""
        connector = _TestConnector(config={"credentials_ref": "vault/creds"})
        result = connector.authenticate()
        assert result.data["auth_type"] == "oauth2"

    def test_authenticate_returns_connector_result(self):
        connector = _TestConnector(config={"credentials_ref": "vault/creds"})
        assert isinstance(connector.authenticate(), ConnectorResult)


# ═══════════════════════════════════════════════════════════════════════
# test_connection()
# ═══════════════════════════════════════════════════════════════════════
class TestTestConnection:
    """Tests for the combined test_connection() method."""

    def test_test_connection_success(self):
        """Succeeds when both connect and authenticate succeed."""
        connector = _TestConnector(config={
            "base_url": "https://api.example.com",
            "credentials_ref": "vault/creds",
        })
        result = connector.test_connection()
        assert result.success is True
        assert result.action == "test_connection"
        assert "ready" in result.message

    def test_test_connection_data_includes_connection_and_authentication(self):
        """Result data has 'connection' and 'authentication' sub-dicts."""
        connector = _TestConnector(config={
            "base_url": "https://api.example.com",
            "credentials_ref": "vault/creds",
        })
        result = connector.test_connection()
        assert "connection" in result.data
        assert "authentication" in result.data
        assert "capabilities" in result.data

    def test_test_connection_fails_without_config(self, monkeypatch):
        """Fails when neither base_url nor credentials are configured."""
        for name in ["CLIENT_SECRET", "PASSWORD", "BIND_PASSWORD", "API_KEY"]:
            monkeypatch.delenv(f"HSAAI_CONNECTOR_{name}", raising=False)
        monkeypatch.delenv("HSAAI_CONNECTOR_BASE_URL", raising=False)
        monkeypatch.delenv("HSAAI_CONNECTOR_CREDENTIALS_REF", raising=False)
        connector = _TestConnector(config={})
        result = connector.test_connection()
        assert result.success is False
        assert "configuration required" in result.message

    def test_test_connection_latency_is_sum_of_components(self):
        """latency_ms is the sum of connect() + authenticate() latencies."""
        connector = _TestConnector(config={
            "base_url": "https://api.example.com",
            "credentials_ref": "vault/creds",
        })
        connect_result = connector.connect()
        auth_result = connector.authenticate()
        test_result = connector.test_connection()
        # Allow small variance due to timing
        assert abs(test_result.latency_ms - (connect_result.latency_ms + auth_result.latency_ms)) < 5


# ═══════════════════════════════════════════════════════════════════════
# check_permissions()
# ═══════════════════════════════════════════════════════════════════════
class TestCheckPermissions:
    """Tests for RBAC + read-only enforcement."""

    def test_admin_role_always_allowed_for_read(self):
        """hsaai_admin role bypasses allowed_roles check."""
        connector = _TestConnector()
        ctx = ConnectorContext(roles=["hsaai_admin"])
        result = connector.check_permissions(ctx, "read")
        assert result.success is True
        assert result.message == "allowed"

    def test_allowed_role_in_allowed_roles_list(self):
        """Roles in allowed_roles list are permitted."""
        connector = _TestConnector()  # allowed_roles = ['hsaai_admin', 'department_manager']
        ctx = ConnectorContext(roles=["department_manager"])
        result = connector.check_permissions(ctx, "read")
        assert result.success is True

    def test_unauthorized_role_denied(self):
        """Role not in allowed_roles and not hsaai_admin is denied."""
        connector = _TestConnector()
        ctx = ConnectorContext(roles=["employee"])
        result = connector.check_permissions(ctx, "read")
        assert result.success is False
        assert "denied" in result.message

    def test_empty_roles_denied(self):
        """Empty roles list is denied."""
        connector = _TestConnector()
        ctx = ConnectorContext(roles=[])
        result = connector.check_permissions(ctx, "read")
        assert result.success is False

    def test_read_operation_allowed_on_read_only_connector(self):
        """read operations are allowed even on read-only connectors."""
        connector = _TestConnector()  # read_only=True
        ctx = ConnectorContext(roles=["hsaai_admin"])
        result = connector.check_permissions(ctx, "read")
        assert result.success is True

    def test_search_operation_allowed_on_read_only_connector(self):
        """search operations are allowed on read-only connectors (whitelisted)."""
        connector = _TestConnector()
        ctx = ConnectorContext(roles=["hsaai_admin"])
        result = connector.check_permissions(ctx, "search")
        assert result.success is True

    def test_fetch_operation_allowed_on_read_only_connector(self):
        """fetch operations are allowed on read-only connectors."""
        connector = _TestConnector()
        ctx = ConnectorContext(roles=["hsaai_admin"])
        result = connector.check_permissions(ctx, "fetch")
        assert result.success is True

    def test_sync_operation_allowed_on_read_only_connector(self):
        """sync operations are allowed on read-only connectors (whitelisted)."""
        connector = _TestConnector()
        ctx = ConnectorContext(roles=["hsaai_admin"])
        result = connector.check_permissions(ctx, "sync")
        assert result.success is True

    def test_test_operation_allowed_on_read_only_connector(self):
        """test operations are allowed on read-only connectors."""
        connector = _TestConnector()
        ctx = ConnectorContext(roles=["hsaai_admin"])
        result = connector.check_permissions(ctx, "test")
        assert result.success is True

    def test_write_operation_blocked_on_read_only_connector(self):
        """write operations are blocked on read-only connectors."""
        connector = _TestConnector()  # read_only=True
        ctx = ConnectorContext(roles=["hsaai_admin"])
        result = connector.check_permissions(ctx, "write")
        assert result.success is False
        assert "denied" in result.message

    def test_create_operation_blocked_on_read_only_connector(self):
        """create operations are blocked on read-only connectors."""
        connector = _TestConnector()
        ctx = ConnectorContext(roles=["hsaai_admin"])
        result = connector.check_permissions(ctx, "create")
        assert result.success is False

    def test_delete_operation_blocked_on_read_only_connector(self):
        """delete operations are blocked on read-only connectors."""
        connector = _TestConnector()
        ctx = ConnectorContext(roles=["hsaai_admin"])
        result = connector.check_permissions(ctx, "delete")
        assert result.success is False

    def test_update_operation_blocked_on_read_only_connector(self):
        """update operations are blocked on read-only connectors."""
        connector = _TestConnector()
        ctx = ConnectorContext(roles=["hsaai_admin"])
        result = connector.check_permissions(ctx, "update")
        assert result.success is False

    def test_operation_case_insensitive(self):
        """Operation matching is case-insensitive (per source: operation.lower())."""
        connector = _TestConnector()
        ctx = ConnectorContext(roles=["hsaai_admin"])
        result = connector.check_permissions(ctx, "READ")
        assert result.success is True

    def test_data_includes_operation_and_roles(self):
        """Result data includes the operation and roles for audit."""
        connector = _TestConnector()
        ctx = ConnectorContext(roles=["hsaai_admin", "employee"])
        result = connector.check_permissions(ctx, "read")
        assert result.data["operation"] == "read"
        assert "hsaai_admin" in result.data["roles"]
        assert result.data["read_only"] is True


# ═══════════════════════════════════════════════════════════════════════
# audit_access()
# ═══════════════════════════════════════════════════════════════════════
class TestAuditAccess:
    """Tests for the audit_access() method."""

    def test_returns_dict_with_all_fields(self):
        """Audit dict has all 9 documented fields."""
        connector = _TestConnector()
        ctx = ConnectorContext(
            tenant_id="t1",
            workspace_id="w1",
            actor="user-1",
            request_id="req-123",
        )
        audit = connector.audit_access(ctx, action="read", success=True, message="allowed")
        expected_keys = {
            "request_id", "connector_key", "actor", "action",
            "success", "message", "source", "tenant_id", "workspace_id",
        }
        assert set(audit.keys()) == expected_keys

    def test_audit_values_match_context(self):
        """Audit values are populated from context."""
        connector = _TestConnector()
        ctx = ConnectorContext(
            tenant_id="t1",
            workspace_id="w1",
            actor="user-1",
            request_id="req-123",
        )
        audit = connector.audit_access(ctx, action="fetch", success=True, message="ok")
        assert audit["request_id"] == "req-123"
        assert audit["actor"] == "user-1"
        assert audit["tenant_id"] == "t1"
        assert audit["workspace_id"] == "w1"
        assert audit["connector_key"] == "test_connector"
        assert audit["source"] == "Test Connector"
        assert audit["action"] == "fetch"
        assert audit["success"] is True
        assert audit["message"] == "ok"

    def test_message_defaults_to_empty_string(self):
        """message parameter defaults to empty string."""
        connector = _TestConnector()
        ctx = ConnectorContext()
        audit = connector.audit_access(ctx, action="read", success=True)
        assert audit["message"] == ""

    def test_capture_failure_state(self):
        """Audit can record failed operations."""
        connector = _TestConnector()
        ctx = ConnectorContext(actor="user-1")
        audit = connector.audit_access(ctx, action="write", success=False, message="denied")
        assert audit["success"] is False
        assert audit["message"] == "denied"


# ═══════════════════════════════════════════════════════════════════════
# handle_errors()
# ═══════════════════════════════════════════════════════════════════════
class TestHandleErrors:
    """Tests for the handle_errors() exception wrapper."""

    def test_returns_connector_result(self):
        connector = _TestConnector()
        result = connector.handle_errors(RuntimeError("test error"))
        assert isinstance(result, ConnectorResult)

    def test_result_success_is_false(self):
        connector = _TestConnector()
        result = connector.handle_errors(RuntimeError("test error"))
        assert result.success is False

    def test_action_is_error(self):
        connector = _TestConnector()
        result = connector.handle_errors(RuntimeError("test error"))
        assert result.action == "error"

    def test_message_contains_exception_text(self):
        connector = _TestConnector()
        result = connector.handle_errors(ValueError("specific error message"))
        assert "specific error message" in result.message

    def test_data_is_none(self):
        connector = _TestConnector()
        result = connector.handle_errors(RuntimeError("err"))
        assert result.data is None

    def test_preserves_read_only_flag(self):
        connector = _TestConnector()
        result = connector.handle_errors(RuntimeError("err"))
        assert result.read_only is True

    def test_handles_connector_error_subclass(self):
        """ConnectorError is a RuntimeError — handle_errors accepts it."""
        connector = _TestConnector()
        result = connector.handle_errors(ConnectorError("custom connector error"))
        assert "custom connector error" in result.message

    def test_preserves_connector_key(self):
        connector = _TestConnector()
        result = connector.handle_errors(RuntimeError("err"))
        assert result.connector_key == "test_connector"


# ═══════════════════════════════════════════════════════════════════════
# sync_data() — base implementation
# ═══════════════════════════════════════════════════════════════════════
class TestSyncData:
    """Tests for the base sync_data() implementation."""

    def test_returns_failure_when_not_overridden(self):
        """Base sync_data returns failure with not-implemented message."""
        connector = _TestConnector()
        ctx = ConnectorContext(roles=["hsaai_admin"])
        result = connector.sync_data(ctx)
        assert result.success is False
        assert "not implemented" in result.message

    def test_returns_connector_result(self):
        connector = _TestConnector()
        ctx = ConnectorContext(roles=["hsaai_admin"])
        assert isinstance(connector.sync_data(ctx), ConnectorResult)

    def test_action_is_sync_data(self):
        connector = _TestConnector()
        ctx = ConnectorContext(roles=["hsaai_admin"])
        result = connector.sync_data(ctx)
        assert result.action == "sync_data"

    def test_returns_permission_denied_when_unauthorized(self):
        """When permission check fails, sync_data returns the permission result."""
        connector = _TestConnector()
        ctx = ConnectorContext(roles=["employee"])  # not in allowed_roles
        result = connector.sync_data(ctx)
        assert result.success is False
        # The permission check fails first (before the not-implemented message)
        assert "denied" in result.message

    def test_uses_check_permissions_with_sync_operation(self):
        """sync_data calls check_permissions with operation='sync' (whitelisted)."""
        connector = _TestConnector()
        ctx = ConnectorContext(roles=["hsaai_admin"])
        # Should pass permission check (sync is whitelisted) then return not-implemented
        result = connector.sync_data(ctx)
        assert "not implemented" in result.message


# ═══════════════════════════════════════════════════════════════════════
# fetch_data() — abstract method enforcement
# ═══════════════════════════════════════════════════════════════════════
class TestFetchDataAbstract:
    """Verify fetch_data is properly abstract."""

    def test_fetch_data_is_abstract(self):
        """fetch_data must be marked abstract."""
        assert getattr(BaseEnterpriseConnector.fetch_data, "__isabstractmethod__", False) is True

    def test_subclass_without_fetch_data_cannot_instantiate(self):
        """Subclass without fetch_data implementation cannot be instantiated."""
        class _IncompleteConnector(BaseEnterpriseConnector):
            key = "incomplete"
            # fetch_data not implemented

        with pytest.raises(TypeError, match="abstract"):
            _IncompleteConnector()  # type: ignore[abstract]

    def test_subclass_with_fetch_data_works(self):
        """_TestConnector's fetch_data returns a ConnectorResult."""
        connector = _TestConnector()
        ctx = ConnectorContext(roles=["hsaai_admin"])
        result = connector.fetch_data({"filter": "active"}, ctx)
        assert isinstance(result, ConnectorResult)
        assert result.success is True
        assert result.data == {"filter": "active"}
        assert result.action == "fetch_data"
