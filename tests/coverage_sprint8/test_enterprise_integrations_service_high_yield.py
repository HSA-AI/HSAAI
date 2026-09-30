import importlib.util
import sys
import types
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest


_TEST_PACKAGE = "_hsaai_enterprise_integrations_testpkg"
_TEST_MODULE = f"{_TEST_PACKAGE}.services"


def _m():
    """
    Load the real enterprise_integrations/services.py in isolation.

    The local Termux environment has Pydantic v1 while the production/CI
    environment uses Pydantic v2. Importing through backend_core normally
    reaches backend_core.config and therefore fails locally before this
    service module can be tested.

    Only the service module's imported collaborators are replaced with
    lightweight test doubles. The production services.py source itself
    is executed unchanged, and coverage is attributed to its real path.
    """
    existing = sys.modules.get(_TEST_MODULE)
    if existing is not None:
        return existing

    repo_root = Path(__file__).resolve().parents[2]
    source_dir = (
        repo_root
        / "services"
        / "backend_core"
        / "enterprise_integrations"
    )
    source = source_dir / "services.py"

    # Private synthetic package: avoids importing backend_core.config and
    # avoids polluting/replacing the canonical backend_core package.
    pkg = types.ModuleType(_TEST_PACKAGE)
    pkg.__path__ = [str(source_dir)]
    pkg.__package__ = _TEST_PACKAGE
    sys.modules[_TEST_PACKAGE] = pkg

    # services.py imports these model classes. Their concrete SQLAlchemy
    # implementations are irrelevant to these isolated service tests because
    # each test patches the globals with the local Model test double.
    models = types.ModuleType(f"{_TEST_PACKAGE}.models")
    for name in (
        "IntegrationDefinition",
        "IntegrationAuditLog",
        "IntegrationSyncRun",
        "ConnectorSecurityPolicy",
    ):
        setattr(models, name, type(name, (), {}))
    sys.modules[models.__name__] = models

    # Stub only the connector registry boundary. Tests replace its methods
    # with deterministic behavior before exercising production service logic.
    connector_registry = types.ModuleType(
        f"{_TEST_PACKAGE}.connector_registry"
    )
    connector_registry.registry = SimpleNamespace(
        supported=lambda: [],
        create=lambda *args, **kwargs: None,
    )
    connector_registry.AGENT_DATA_SOURCES = {}
    connector_registry.WORKFLOW_CONNECTOR_MAP = {}
    sys.modules[connector_registry.__name__] = connector_registry

    base_connector = types.ModuleType(
        f"{_TEST_PACKAGE}.base_connector"
    )

    class PlaceholderConnectorContext:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    base_connector.ConnectorContext = PlaceholderConnectorContext
    sys.modules[base_connector.__name__] = base_connector

    spec = importlib.util.spec_from_file_location(
        _TEST_MODULE,
        source,
    )

    if spec is None or spec.loader is None:
        raise RuntimeError(
            f"Unable to load enterprise integration service: {source}"
        )

    module = importlib.util.module_from_spec(spec)
    sys.modules[_TEST_MODULE] = module
    spec.loader.exec_module(module)

    return module


class Field:
    def asc(self):
        return self

    def desc(self):
        return self


class Model:
    category = Field()
    name = Field()
    id = Field()

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class Context:
    def __init__(
        self,
        tenant_id,
        workspace_id,
        actor,
        roles,
        request_id,
    ):
        self.tenant_id = tenant_id
        self.workspace_id = workspace_id
        self.actor = actor
        self.roles = roles
        self.request_id = request_id


class Query:
    def __init__(self, rows):
        self.rows = list(rows)

    def filter_by(self, **kwargs):
        rows = [
            row
            for row in self.rows
            if all(
                getattr(row, key, None) == value
                for key, value in kwargs.items()
            )
        ]
        return Query(rows)

    def order_by(self, *args):
        return self

    def limit(self, limit):
        return Query(self.rows[:limit])

    def all(self):
        return list(self.rows)

    def first(self):
        return self.rows[0] if self.rows else None


class DB:
    def __init__(self):
        self.rows = {}
        self.added = []
        self.commits = 0

    def query(self, model):
        return Query(self.rows.get(model, []))

    def add(self, value):
        self.added.append(value)

    def commit(self):
        self.commits += 1


def _patch_models(monkeypatch, m):
    monkeypatch.setattr(
        m,
        "IntegrationDefinition",
        Model,
    )
    monkeypatch.setattr(
        m,
        "ConnectorSecurityPolicy",
        Model,
    )
    monkeypatch.setattr(
        m,
        "IntegrationSyncRun",
        Model,
    )
    monkeypatch.setattr(
        m,
        "IntegrationAuditLog",
        Model,
    )
    monkeypatch.setattr(
        m,
        "ConnectorContext",
        Context,
    )


def _row(**overrides):
    values = {
        "key": "sap_s4hana",
        "name": "SAP",
        "system_type": "erp",
        "category": "finance",
        "base_url": "",
        "auth_type": "oauth",
        "credentials_ref": "",
        "read_only": True,
        "enabled": False,
        "health_status": "not_configured",
        "last_sync_status": "",
        "last_sync_at": None,
        "capabilities_json": '["read"]',
        "allowed_roles_json": '["admin"]',
        "metadata_json": '{"x":1}',
        "tenant_id": "t1",
        "workspace_id": "w1",
    }
    values.update(overrides)
    return Model(**values)


def test_json_loads_request_id_and_serialize():
    m = _m()

    assert m._loads('{"a":1}', {}) == {"a": 1}
    assert m._loads("broken", {"x": 2}) == {"x": 2}
    assert m._json({"a": 1})
    assert m._request_id("unit").startswith("unit-")

    row = _row(
        last_sync_at=datetime(2026, 1, 1)
    )

    result = m.EnterpriseIntegrationService()._serialize(
        row
    )

    assert result["key"] == "sap_s4hana"
    assert result["capabilities"] == ["read"]
    assert result["allowed_roles"] == ["admin"]
    assert result["metadata"] == {"x": 1}
    assert result["last_sync_at"].startswith("2026-01-01")


def test_ensure_defaults_adds_only_missing(
    monkeypatch,
):
    m = _m()
    _patch_models(monkeypatch, m)

    db = DB()
    db.rows[Model] = [
        Model(
            key="existing",
            tenant_id="t1",
            workspace_id="w1",
        )
    ]

    monkeypatch.setattr(
        m.registry,
        "supported",
        lambda: [
            {
                "key": "existing",
                "name": "Existing",
                "system_type": "x",
                "category": "x",
                "auth_type": "none",
                "read_only": True,
                "capabilities": [],
                "allowed_roles": [],
            },
            {
                "key": "sap_s4hana",
                "name": "SAP",
                "system_type": "erp",
                "category": "finance",
                "auth_type": "oauth",
                "read_only": True,
                "capabilities": ["read"],
                "allowed_roles": ["admin"],
            },
        ],
    )

    svc = m.EnterpriseIntegrationService()
    svc.ensure_defaults(db, "t1", "w1")

    assert len(db.added) == 2
    assert db.commits == 1


def test_list_and_configure_success_and_unknown(
    monkeypatch,
):
    m = _m()
    _patch_models(monkeypatch, m)

    svc = m.EnterpriseIntegrationService()
    monkeypatch.setattr(
        svc,
        "ensure_defaults",
        lambda *args: None,
    )

    row = _row()
    db = DB()
    db.rows[Model] = [row]

    listed = svc.list_connectors(
        db,
        "t1",
        "w1",
    )
    assert listed[0]["key"] == "sap_s4hana"

    audits = []
    monkeypatch.setattr(
        svc,
        "_audit",
        lambda *args, **kwargs: audits.append(
            (args, kwargs)
        ),
    )

    result = svc.configure(
        db,
        {
            "key": "sap_s4hana",
            "base_url": "https://sap.example",
            "credentials_ref": "vault/sap",
            "enabled": True,
            "metadata": {"mode": "read"},
        },
        {"sub": "admin"},
        "t1",
        "w1",
    )

    assert result["enabled"] is True
    assert result["base_url_configured"] is True
    assert audits
    assert db.commits >= 1

    with pytest.raises(
        ValueError,
        match="Unsupported connector",
    ):
        svc.configure(
            db,
            {"key": "missing"},
            {},
            "t1",
            "w1",
        )


@pytest.mark.parametrize(
    "success,expected_health",
    [
        (True, "healthy"),
        (False, "configuration_required"),
    ],
)
def test_connection_paths(
    monkeypatch,
    success,
    expected_health,
):
    m = _m()
    _patch_models(monkeypatch, m)

    svc = m.EnterpriseIntegrationService()
    monkeypatch.setattr(
        svc,
        "ensure_defaults",
        lambda *args: None,
    )
    monkeypatch.setattr(
        svc,
        "_audit",
        lambda *args, **kwargs: None,
    )

    row = _row()
    db = DB()
    db.rows[Model] = [row]

    connector = SimpleNamespace(
        test_connection=lambda: SimpleNamespace(
            success=success,
            message="result",
            latency_ms=10,
        )
    )

    monkeypatch.setattr(
        m.registry,
        "create",
        lambda *args, **kwargs: connector,
    )

    result = svc.test_connection(
        db,
        "sap_s4hana",
        {},
        "t1",
        "w1",
    )

    assert result["health_status"] == expected_health


def test_connection_missing_connector(
    monkeypatch,
):
    m = _m()
    _patch_models(monkeypatch, m)

    svc = m.EnterpriseIntegrationService()
    monkeypatch.setattr(
        svc,
        "ensure_defaults",
        lambda *args: None,
    )

    db = DB()

    with pytest.raises(
        ValueError,
        match="Connector not found",
    ):
        svc.test_connection(
            db,
            "missing",
            {},
            "t1",
            "w1",
        )


def test_fetch_disabled_and_success(monkeypatch):
    m = _m()
    _patch_models(monkeypatch, m)

    svc = m.EnterpriseIntegrationService()
    monkeypatch.setattr(
        svc,
        "_audit",
        lambda *args, **kwargs: None,
    )

    row = _row(enabled=False)
    db = DB()
    db.rows[Model] = [row]

    with pytest.raises(ValueError):
        svc.fetch(
            db,
            "sap_s4hana",
            {},
            {},
            "t1",
            "w1",
        )

    row.enabled = True

    result_obj = SimpleNamespace(
        success=True,
        message="ok",
        latency_ms=5,
        source="sap",
        data={"value": 1},
    )

    connector = SimpleNamespace(
        fetch_data=lambda query, context: result_obj
    )

    monkeypatch.setattr(
        m.registry,
        "create",
        lambda *args, **kwargs: connector,
    )

    result = svc.fetch(
        db,
        "sap_s4hana",
        {"q": 1},
        {
            "sub": "u1",
            "roles": ["admin"],
        },
        "t1",
        "w1",
    )

    assert result["success"] is True
    assert result["audit_request_id"].startswith(
        "conn-"
    )
    assert result["show_source_in_answer"] is True


@pytest.mark.parametrize(
    "success,data,expected",
    [
        (True, {"records": 7}, "completed"),
        (False, {}, "failed"),
    ],
)
def test_sync_paths(
    monkeypatch,
    success,
    data,
    expected,
):
    m = _m()
    _patch_models(monkeypatch, m)

    svc = m.EnterpriseIntegrationService()
    monkeypatch.setattr(
        svc,
        "_audit",
        lambda *args, **kwargs: None,
    )

    row = _row(enabled=True)
    db = DB()
    db.rows[Model] = [row]

    result_obj = SimpleNamespace(
        success=success,
        message="sync",
        latency_ms=9,
        source="sap",
        data=data,
    )

    connector = SimpleNamespace(
        sync_data=lambda context: result_obj
    )

    monkeypatch.setattr(
        m.registry,
        "create",
        lambda *args, **kwargs: connector,
    )

    result = svc.sync(
        db,
        "sap_s4hana",
        {
            "sub": "u1",
            "roles": ["admin"],
        },
        "t1",
        "w1",
    )

    assert result["status"] == expected
    assert row.last_sync_status == expected
    assert db.added
    assert db.commits == 1


def test_sources_audit_logs_overview_and_audit(
    monkeypatch,
):
    m = _m()
    _patch_models(monkeypatch, m)

    monkeypatch.setattr(
        m,
        "AGENT_DATA_SOURCES",
        {"finance": ["sap_s4hana"]},
    )
    monkeypatch.setattr(
        m,
        "WORKFLOW_CONNECTOR_MAP",
        {"invoice": ["sap_s4hana"]},
    )

    svc = m.EnterpriseIntegrationService()

    assert svc.agent_sources(
        "finance"
    )["connectors"] == ["sap_s4hana"]

    assert svc.workflow_sources(
        "invoice"
    )["connectors"] == ["sap_s4hana"]

    logrow = Model(
        request_id="r1",
        connector_key="sap_s4hana",
        actor="u1",
        action="fetch",
        success=True,
        message="ok",
        data_source="sap",
        latency_ms=4,
        created_at=datetime(2026, 1, 1),
        tenant_id="t1",
        workspace_id="w1",
    )

    db = DB()
    db.rows[Model] = [logrow]

    logs = svc.audit_logs(
        db,
        "t1",
        "w1",
        limit=10,
    )
    assert logs[0]["request_id"] == "r1"

    monkeypatch.setattr(
        svc,
        "list_connectors",
        lambda *args: [
            {
                "enabled": True,
                "health_status": "healthy",
            },
            {
                "enabled": False,
                "health_status": "not_configured",
            },
        ],
    )

    overview = svc.overview(
        db,
        "t1",
        "w1",
    )

    assert overview["total"] == 2
    assert overview["enabled"] == 1
    assert overview["healthy"] == 1

    before = len(db.added)

    svc._audit(
        db,
        "sap_s4hana",
        {"sub": "u1"},
        "fetch",
        True,
        "ok",
        "t1",
        "w1",
        latency_ms=5,
        data_source="sap",
    )

    assert len(db.added) == before + 1
