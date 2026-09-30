import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest


class FakeHTTPException(Exception):
    def __init__(self, status_code, detail=None):
        super().__init__(str(detail))
        self.status_code = status_code
        self.detail = detail


class FakeAPIRouter:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def get(self, *args, **kwargs):
        def decorator(func):
            return func
        return decorator

    def post(self, *args, **kwargs):
        def decorator(func):
            return func
        return decorator


def _depends(value=None):
    return value


def _header(default=None, **kwargs):
    return default


class FakeDB:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class Payload(SimpleNamespace):
    def dict(self):
        return dict(vars(self))


def _install_fake_fastapi():
    fake = types.ModuleType("fastapi")
    fake.APIRouter = FakeAPIRouter
    fake.Depends = _depends
    fake.Header = _header
    fake.HTTPException = FakeHTTPException
    return fake


def _load_enterprise_router():
    module_name = "_hsaai_enterprise_router_testpkg.router"

    if module_name in sys.modules:
        return sys.modules[module_name]

    root = Path(__file__).resolve().parents[2]
    source_dir = (
        root
        / "services"
        / "backend_core"
        / "enterprise_upgrade"
    )

    package_name = "_hsaai_enterprise_router_testpkg"

    pkg = types.ModuleType(package_name)
    pkg.__path__ = [str(source_dir)]
    pkg.__package__ = package_name
    sys.modules[package_name] = pkg

    schemas = types.ModuleType(
        f"{package_name}.schemas"
    )

    for name in (
        "AgentRouteRequest",
        "WorkflowStartRequest",
        "ConnectorConfigIn",
        "ApprovalRequestIn",
        "ApprovalDecisionIn",
    ):
        setattr(schemas, name, Payload)

    services = types.ModuleType(
        f"{package_name}.services"
    )

    services.supervisor_service = SimpleNamespace()
    services.workflow_service = SimpleNamespace()
    services.connector_service = SimpleNamespace(
        SUPPORTED=["sap", "oracle"]
    )
    services.observability_service = SimpleNamespace()
    services.approval_service = SimpleNamespace()

    sys.modules[schemas.__name__] = schemas
    sys.modules[services.__name__] = services

    fake_fastapi = _install_fake_fastapi()

    db_pkg = types.ModuleType("backend_core.db")
    db_pkg.__path__ = []

    db_mod = types.ModuleType(
        "backend_core.db.database"
    )
    db_mod.SessionLocal = lambda: FakeDB()

    security_pkg = types.ModuleType(
        "backend_core.security"
    )
    security_pkg.__path__ = []

    rbac = types.ModuleType(
        "backend_core.security.rbac"
    )
    rbac.require_permission = (
        lambda permission: (
            lambda: permission
        )
    )
    rbac.get_current_claims = lambda: {}

    replacements = {
        "fastapi": fake_fastapi,
        "backend_core.db": db_pkg,
        "backend_core.db.database": db_mod,
        "backend_core.security": security_pkg,
        "backend_core.security.rbac": rbac,
    }

    old = {
        name: sys.modules.get(name)
        for name in replacements
    }

    sys.modules.update(replacements)

    try:
        source = source_dir / "router.py"

        spec = importlib.util.spec_from_file_location(
            module_name,
            source,
        )

        if spec is None or spec.loader is None:
            raise RuntimeError(
                f"Unable to load {source}"
            )

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        return module

    finally:
        for name, previous in old.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous


def _load_maturity_router():
    module_name = "_hsaai_maturity_router_testpkg.router"

    if module_name in sys.modules:
        return sys.modules[module_name]

    root = Path(__file__).resolve().parents[2]
    source_dir = (
        root
        / "services"
        / "backend_core"
        / "maturity_upgrade"
    )

    package_name = "_hsaai_maturity_router_testpkg"

    pkg = types.ModuleType(package_name)
    pkg.__path__ = [str(source_dir)]
    pkg.__package__ = package_name
    sys.modules[package_name] = pkg

    schemas = types.ModuleType(
        f"{package_name}.schemas"
    )

    for name in (
        "AgentRouteRequest",
        "WorkflowStartRequest",
        "WorkflowActionRequest",
        "ConnectorRuntimeRequest",
        "ObservabilityEventIn",
    ):
        setattr(schemas, name, Payload)

    agent_module = types.ModuleType(
        f"{package_name}.agent_orchestration"
    )
    agent_module.agent_orchestrator = (
        SimpleNamespace()
    )

    workflow_module = types.ModuleType(
        f"{package_name}.workflow_runtime"
    )
    workflow_module.workflow_engine = (
        SimpleNamespace()
    )

    connector_module = types.ModuleType(
        f"{package_name}.connectors_runtime"
    )
    connector_module.connector_runtime = (
        SimpleNamespace()
    )

    obs_module = types.ModuleType(
        f"{package_name}.observability"
    )
    obs_module.observability_service = (
        SimpleNamespace()
    )

    for module in (
        schemas,
        agent_module,
        workflow_module,
        connector_module,
        obs_module,
    ):
        sys.modules[module.__name__] = module

    fake_fastapi = _install_fake_fastapi()

    db_pkg = types.ModuleType("backend_core.db")
    db_pkg.__path__ = []

    db_mod = types.ModuleType(
        "backend_core.db.database"
    )
    db_mod.SessionLocal = lambda: FakeDB()

    security_pkg = types.ModuleType(
        "backend_core.security"
    )
    security_pkg.__path__ = []

    rbac = types.ModuleType(
        "backend_core.security.rbac"
    )
    rbac.require_permission = (
        lambda permission: (
            lambda: permission
        )
    )
    rbac.get_current_claims = lambda: {}

    replacements = {
        "fastapi": fake_fastapi,
        "backend_core.db": db_pkg,
        "backend_core.db.database": db_mod,
        "backend_core.security": security_pkg,
        "backend_core.security.rbac": rbac,
    }

    old = {
        name: sys.modules.get(name)
        for name in replacements
    }

    sys.modules.update(replacements)

    try:
        source = source_dir / "router.py"

        spec = importlib.util.spec_from_file_location(
            module_name,
            source,
        )

        if spec is None or spec.loader is None:
            raise RuntimeError(
                f"Unable to load {source}"
            )

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        return module

    finally:
        for name, previous in old.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous


def _db_factory(module):
    created = []

    def factory():
        db = FakeDB()
        created.append(db)
        return db

    module.SessionLocal = factory
    return created


def test_enterprise_scope_defaults_and_values():
    m = _load_enterprise_router()

    assert m.scope({}) == (
        "default",
        "default",
    )

    assert m.scope(
        {
            "tenant_id": "tenant-1",
            "workspace_id": "finance",
        }
    ) == (
        "tenant-1",
        "finance",
    )


def test_enterprise_router_happy_paths():
    m = _load_enterprise_router()
    databases = _db_factory(m)

    calls = []

    m.supervisor_service = SimpleNamespace(
        registry=lambda db, tenant, workspace: [
            "agent-1"
        ],
        health=lambda db, tenant, workspace: {
            "healthy": 1
        },
        route=lambda db, **kwargs: {
            "selected_agent": "finance",
            **kwargs,
        },
    )

    m.workflow_service = SimpleNamespace(
        templates=lambda db, tenant, workspace: [
            "template-1"
        ],
        start=lambda db, **kwargs: {
            "execution_id": "wf-1",
            **kwargs,
        },
        executions=lambda db, tenant, workspace: [
            "wf-1"
        ],
    )

    def create_connector(
        db,
        data,
        tenant,
        workspace,
    ):
        calls.append(
            (
                "connector_create",
                data,
                tenant,
                workspace,
            )
        )
        return {"status": "created"}

    m.connector_service = SimpleNamespace(
        SUPPORTED=[
            "sap",
            "oracle",
        ],
        list=lambda db, tenant, workspace: [
            "sap-prod"
        ],
        create=create_connector,
        test=lambda db, key, tenant, workspace: {
            "key": key,
            "health_status": "healthy",
        },
    )

    m.observability_service = SimpleNamespace(
        dashboard=lambda db, tenant, workspace: {
            "tenant": tenant,
            "workspace": workspace,
        }
    )

    m.approval_service = SimpleNamespace(
        create=lambda db, **kwargs: {
            "approval_id": "a1",
            **kwargs,
        },
        queue=lambda db, tenant, workspace: [
            "a1"
        ],
        decide=lambda db, approval_id, status,
        comment, claims, tenant, workspace: {
            "approval_id": approval_id,
            "status": status,
            "comment": comment,
        },
    )

    claims = {
        "tenant_id": "tenant-1",
        "workspace_id": "finance",
        "sub": "user-1",
        "roles": ["admin"],
    }

    assert m.agent_registry(
        claims
    ) == {
        "agents": ["agent-1"]
    }

    route_payload = Payload(
        message="Route finance question",
        workspace_id="finance-special",
        session_id="session-1",
    )

    route = m.supervisor_route(
        route_payload,
        claims,
    )

    assert route["selected_agent"] == "finance"
    assert route["tenant_id"] == "tenant-1"
    assert (
        route["workspace_id"]
        == "finance-special"
    )
    assert (
        route["session_id"]
        == "session-1"
    )

    assert m.agent_health(
        claims
    ) == {"healthy": 1}

    assert m.workflow_templates(
        claims
    ) == {
        "templates": ["template-1"]
    }

    start_payload = Payload(
        template_key="purchase",
        payload={"amount": 100},
        requested_by="",
    )

    start = m.workflow_start(
        start_payload,
        claims,
    )

    assert start["execution_id"] == "wf-1"
    assert (
        start["requested_by"]
        == "user-1"
    )

    assert m.workflow_executions(
        claims
    ) == {
        "executions": ["wf-1"]
    }

    connectors = m.connectors(claims)

    assert connectors["supported"] == [
        "sap",
        "oracle",
    ]
    assert connectors["connectors"] == [
        "sap-prod"
    ]

    connector_payload = Payload(
        key="sap-prod",
        name="SAP",
        connector_type="sap",
    )

    assert m.connector_create(
        connector_payload,
        claims,
    ) == {
        "status": "created"
    }

    assert calls[0][0] == "connector_create"
    assert (
        calls[0][1]["connector_type"]
        == "sap"
    )

    tested = m.connector_test(
        "sap-prod",
        claims,
    )

    assert (
        tested["health_status"]
        == "healthy"
    )

    dashboard = (
        m.observability_dashboard(
            claims
        )
    )

    assert dashboard["tenant"] == "tenant-1"
    assert dashboard["workspace"] == "finance"

    approval_payload = Payload(
        title="Review invoice",
        action_type="approve",
        resource_type="invoice",
        resource_id="inv-1",
    )

    created = m.approval_create(
        approval_payload,
        claims,
    )

    assert (
        created["approval_id"]
        == "a1"
    )

    assert m.approval_queue(
        claims
    ) == {
        "approvals": ["a1"]
    }

    decision_payload = Payload(
        comment="approved"
    )

    approved = m.approval_approve(
        "a1",
        decision_payload,
        claims,
    )

    assert approved["status"] == "approved"

    rejected = m.approval_reject(
        "a1",
        decision_payload,
        claims,
    )

    assert rejected["status"] == "rejected"

    assert databases
    assert all(
        db.closed
        for db in databases
    )


def test_enterprise_workflow_start_value_error():
    m = _load_enterprise_router()
    databases = _db_factory(m)

    def fail(*args, **kwargs):
        raise ValueError(
            "workflow missing"
        )

    m.workflow_service = SimpleNamespace(
        start=fail
    )

    with pytest.raises(
        FakeHTTPException,
    ) as exc:
        m.workflow_start(
            Payload(
                template_key="missing",
                payload={},
                requested_by="user",
            ),
            {
                "tenant_id": "t",
                "workspace_id": "w",
            },
        )

    assert exc.value.status_code == 404
    assert "workflow missing" in (
        exc.value.detail
    )
    assert databases[-1].closed


def test_enterprise_connector_errors():
    m = _load_enterprise_router()

    def create_fail(*args, **kwargs):
        raise ValueError(
            "unsupported connector"
        )

    m.connector_service = SimpleNamespace(
        SUPPORTED=[],
        create=create_fail,
        test=create_fail,
    )

    databases = _db_factory(m)

    claims = {
        "tenant_id": "t",
        "workspace_id": "w",
    }

    with pytest.raises(
        FakeHTTPException,
    ) as create_exc:
        m.connector_create(
            Payload(
                connector_type="bad"
            ),
            claims,
        )

    assert create_exc.value.status_code == 400
    assert databases[-1].closed

    with pytest.raises(
        FakeHTTPException,
    ) as test_exc:
        m.connector_test(
            "missing",
            claims,
        )

    assert test_exc.value.status_code == 404
    assert databases[-1].closed


@pytest.mark.parametrize(
    "method,error_type,status_code",
    [
        (
            "approval_approve",
            PermissionError,
            403,
        ),
        (
            "approval_approve",
            ValueError,
            404,
        ),
        (
            "approval_reject",
            PermissionError,
            403,
        ),
        (
            "approval_reject",
            ValueError,
            404,
        ),
    ],
)
def test_enterprise_approval_errors(
    method,
    error_type,
    status_code,
):
    m = _load_enterprise_router()
    databases = _db_factory(m)

    def fail(*args, **kwargs):
        raise error_type(
            "approval failure"
        )

    m.approval_service = (
        SimpleNamespace(
            decide=fail
        )
    )

    func = getattr(m, method)

    with pytest.raises(
        FakeHTTPException,
    ) as exc:
        func(
            "a1",
            Payload(comment="x"),
            {
                "tenant_id": "t",
                "workspace_id": "w",
            },
        )

    assert (
        exc.value.status_code
        == status_code
    )
    assert databases[-1].closed


def test_maturity_scope_and_simple_routes():
    m = _load_maturity_router()

    assert m._scope({}) == (
        "default",
        "default",
    )

    assert m._scope(
        {
            "tenant_id": "t1",
            "workspace_id": "w1",
        }
    ) == (
        "t1",
        "w1",
    )

    m.agent_orchestrator = SimpleNamespace(
        registry=lambda: ["agent"]
    )

    m.workflow_engine = SimpleNamespace(
        templates=lambda: ["workflow"]
    )

    assert m.agents_registry() == [
        "agent"
    ]

    assert m.workflow_templates() == [
        "workflow"
    ]


def test_maturity_router_happy_paths():
    m = _load_maturity_router()
    databases = _db_factory(m)

    m.agent_orchestrator = (
        SimpleNamespace(
            registry=lambda: ["agent-1"],
            route=lambda db, payload: {
                "tenant_id":
                    payload.tenant_id,
                "workspace_id":
                    payload.workspace_id,
                "roles":
                    payload.roles,
                "user_id":
                    payload.user_id,
            },
            performance=(
                lambda db, tenant, workspace: {
                    "performance": "healthy"
                }
            ),
        )
    )

    m.workflow_engine = (
        SimpleNamespace(
            templates=lambda: [
                "template-1"
            ],
            start=lambda db, payload: {
                "requested_by":
                    payload.requested_by
            },
            action=lambda db, payload: {
                "actor": payload.actor
            },
            list=lambda db, tenant, workspace: [
                "execution-1"
            ],
        )
    )

    m.connector_runtime = (
        SimpleNamespace(
            health_matrix=(
                lambda db, tenant, workspace: {
                    "sap": "healthy"
                }
            ),
            run_probe=(
                lambda db, key, claims,
                tenant, workspace: {
                    "connector_key": key
                }
            ),
        )
    )

    m.observability_service = (
        SimpleNamespace(
            record=lambda db, event: {
                "recorded": event.name
            },
            dashboard=(
                lambda db, tenant, workspace: {
                    "availability": 99.9
                }
            ),
        )
    )

    claims = {
        "tenant_id": "tenant-1",
        "workspace_id": "finance",
        "roles": ["finance"],
        "sub": "user-1",
    }

    overview = m.overview(claims)

    assert (
        overview["maturity_level"]
        == "advanced_enterprise_ai_platform"
    )
    assert overview["agents"] == [
        "agent-1"
    ]
    assert overview["workflows"] == [
        "template-1"
    ]
    assert (
        overview["connectors"]["sap"]
        == "healthy"
    )

    route_payload = Payload(
        tenant_id="old",
        workspace_id="old",
        roles=None,
        user_id=None,
    )

    routed = m.route_agent(
        route_payload,
        claims,
    )

    assert (
        routed["tenant_id"]
        == "tenant-1"
    )
    assert (
        routed["workspace_id"]
        == "finance"
    )
    assert routed["roles"] == [
        "finance"
    ]
    assert routed["user_id"] == "user-1"

    assert m.agent_performance(
        claims
    ) == {
        "performance": "healthy"
    }

    start_payload = Payload(
        tenant_id="x",
        workspace_id="x",
        requested_by="system",
    )

    started = m.start_workflow(
        start_payload,
        claims,
    )

    assert (
        started["requested_by"]
        == "user-1"
    )
    assert (
        start_payload.tenant_id
        == "tenant-1"
    )
    assert (
        start_payload.workspace_id
        == "finance"
    )

    action_payload = Payload(
        actor="system"
    )

    acted = m.workflow_action(
        action_payload,
        claims,
    )

    assert acted["actor"] == "user-1"

    assert m.workflow_executions(
        claims
    ) == ["execution-1"]

    assert m.connectors_health(
        claims
    ) == {
        "sap": "healthy"
    }

    probe = m.connectors_probe(
        Payload(
            connector_key="sap-prod"
        ),
        claims,
    )

    assert (
        probe["connector_key"]
        == "sap-prod"
    )

    event = Payload(
        name="agent_runs"
    )

    assert m.record_observability(
        event
    ) == {
        "recorded": "agent_runs"
    }

    assert (
        m.observability_dashboard(
            claims
        )["availability"]
        == 99.9
    )

    assert databases
    assert all(
        db.closed
        for db in databases
    )


def test_maturity_workflow_start_error():
    m = _load_maturity_router()
    databases = _db_factory(m)

    def fail(*args, **kwargs):
        raise ValueError(
            "cannot start"
        )

    m.workflow_engine = (
        SimpleNamespace(
            start=fail
        )
    )

    with pytest.raises(
        FakeHTTPException,
    ) as exc:
        m.start_workflow(
            Payload(
                tenant_id="",
                workspace_id="",
                requested_by="system",
            ),
            {
                "tenant_id": "t",
                "workspace_id": "w",
                "sub": "u",
            },
        )

    assert exc.value.status_code == 400
    assert databases[-1].closed


def test_maturity_workflow_action_error():
    m = _load_maturity_router()
    databases = _db_factory(m)

    def fail(*args, **kwargs):
        raise ValueError(
            "execution missing"
        )

    m.workflow_engine = (
        SimpleNamespace(
            action=fail
        )
    )

    with pytest.raises(
        FakeHTTPException,
    ) as exc:
        m.workflow_action(
            Payload(
                actor="system"
            ),
            {
                "sub": "u",
            },
        )

    assert exc.value.status_code == 404
    assert databases[-1].closed


def test_maturity_preserves_explicit_payload_identity():
    m = _load_maturity_router()
    _db_factory(m)

    m.agent_orchestrator = (
        SimpleNamespace(
            route=lambda db, payload: {
                "roles": payload.roles,
                "user_id": payload.user_id,
            }
        )
    )

    payload = Payload(
        tenant_id="old",
        workspace_id="old",
        roles=["auditor"],
        user_id="explicit-user",
    )

    result = m.route_agent(
        payload,
        {
            "tenant_id": "t",
            "workspace_id": "w",
            "roles": ["admin"],
            "sub": "claims-user",
        },
    )

    assert result["roles"] == [
        "auditor"
    ]
    assert (
        result["user_id"]
        == "explicit-user"
    )

    m.workflow_engine = (
        SimpleNamespace(
            start=lambda db, payload: {
                "requested_by":
                    payload.requested_by
            },
            action=lambda db, payload: {
                "actor": payload.actor
            },
        )
    )

    started = m.start_workflow(
        Payload(
            tenant_id="",
            workspace_id="",
            requested_by="explicit",
        ),
        {
            "tenant_id": "t",
            "workspace_id": "w",
            "sub": "claims-user",
        },
    )

    assert (
        started["requested_by"]
        == "explicit"
    )

    acted = m.workflow_action(
        Payload(
            actor="explicit-actor"
        ),
        {
            "sub": "claims-user"
        },
    )

    assert (
        acted["actor"]
        == "explicit-actor"
    )
