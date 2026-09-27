import importlib.util
import json
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest


_PACKAGE = "_hsaai_enterprise_upgrade_testpkg"
_MODULE = f"{_PACKAGE}.services"


class Field:
    def __init__(self, name):
        self.name = name

    def asc(self):
        return self

    def desc(self):
        return self


class Agent:
    key = Field("key")

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class AgentAudit:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class WorkflowTemplate:
    key = Field("key")

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class WorkflowExecution:
    id = Field("id")

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class Connector:
    connector_type = Field("connector_type")

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class Metric:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class Approval:
    id = Field("id")

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class Query:
    def __init__(self, rows=None):
        self.rows = list(rows or [])
        self._limit = None

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

    def limit(self, value):
        q = Query(self.rows)
        q._limit = value
        return q

    def all(self):
        if self._limit is None:
            return list(self.rows)
        return list(self.rows[: self._limit])

    def first(self):
        return self.rows[0] if self.rows else None


class DB:
    def __init__(self):
        self.rows = {}
        self.added = []
        self.commits = 0

    def query(self, model):
        return Query(self.rows.get(model, []))

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.commits += 1


def _m():
    existing = sys.modules.get(_MODULE)
    if existing is not None:
        return existing

    repo_root = Path(__file__).resolve().parents[2]
    source_dir = (
        repo_root
        / "services"
        / "backend_core"
        / "enterprise_upgrade"
    )
    source = source_dir / "services.py"

    # Synthetic package for relative `.domain` import.
    pkg = types.ModuleType(_PACKAGE)
    pkg.__path__ = [str(source_dir)]
    pkg.__package__ = _PACKAGE
    sys.modules[_PACKAGE] = pkg

    domain = types.ModuleType(
        f"{_PACKAGE}.domain"
    )
    domain.DEFAULT_AGENT_BLUEPRINTS = []
    domain.EnterpriseAgentAuditLog = AgentAudit
    domain.EnterpriseAgentDefinition = Agent
    domain.WorkflowTemplate = WorkflowTemplate
    domain.WorkflowExecution = WorkflowExecution
    domain.EnterpriseConnector = Connector
    domain.EnterpriseMetricEvent = Metric
    domain.HumanApprovalRequest = Approval
    domain.to_json = lambda value: json.dumps(
        value,
        ensure_ascii=False,
    )
    domain.now_id = lambda prefix: f"{prefix}-unit-1"

    sys.modules[domain.__name__] = domain

    # Stub the absolute RBAC dependency only for this isolated loader.
    names = [
        "backend_core.security",
        "backend_core.security.rbac",
    ]
    old = {
        name: sys.modules.get(name)
        for name in names
    }

    security_pkg = types.ModuleType(
        "backend_core.security"
    )
    security_pkg.__path__ = []

    rbac = types.ModuleType(
        "backend_core.security.rbac"
    )
    rbac.has_permission = (
        lambda claims, permission: False
    )

    sys.modules[
        "backend_core.security"
    ] = security_pkg
    sys.modules[
        "backend_core.security.rbac"
    ] = rbac

    try:
        spec = importlib.util.spec_from_file_location(
            _MODULE,
            source,
        )

        if spec is None or spec.loader is None:
            raise RuntimeError(
                f"Unable to load {source}"
            )

        module = importlib.util.module_from_spec(spec)
        sys.modules[_MODULE] = module
        spec.loader.exec_module(module)

        # Ensure tests use our lightweight models.
        module.EnterpriseAgentAuditLog = AgentAudit
        module.EnterpriseAgentDefinition = Agent
        module.WorkflowTemplate = WorkflowTemplate
        module.WorkflowExecution = WorkflowExecution
        module.EnterpriseConnector = Connector
        module.EnterpriseMetricEvent = Metric
        module.HumanApprovalRequest = Approval

        return module

    finally:
        for name, previous in old.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous


def _blueprints():
    return [
        {
            "key": "finance",
            "name": "Finance Agent",
            "department": "finance",
            "capabilities": ["budget"],
            "roles": ["finance_user"],
            "tools": ["invoice_lookup"],
            "keywords": [
                "invoice",
                "budget",
            ],
        },
        {
            "key": "hr",
            "name": "HR Agent",
            "department": "hr",
            "capabilities": ["leave"],
            "roles": ["hr_user"],
            "tools": ["employee_lookup"],
            "keywords": [
                "employee",
                "leave",
            ],
        },
    ]


def test_json_success_and_fallback():
    m = _m()

    assert m._json(
        '{"a": 1}',
        {},
    ) == {"a": 1}

    assert m._json(
        "broken",
        {"fallback": True},
    ) == {"fallback": True}


def test_supervisor_ensure_defaults(
    monkeypatch,
):
    m = _m()

    monkeypatch.setattr(
        m,
        "DEFAULT_AGENT_BLUEPRINTS",
        _blueprints(),
    )

    db = DB()
    db.rows[Agent] = [
        Agent(
            key="finance",
            tenant_id="t1",
            workspace_id="w1",
        )
    ]

    svc = m.SupervisorAgentService()

    svc.ensure_defaults(
        db,
        "t1",
        "w1",
    )

    assert len(db.added) == 1

    row = db.added[0]

    assert row.key == "hr"
    assert row.name == "HR Agent"
    assert row.tenant_id == "t1"
    assert row.workspace_id == "w1"

    assert db.commits == 1


def test_supervisor_registry(
    monkeypatch,
):
    m = _m()

    svc = m.SupervisorAgentService()

    monkeypatch.setattr(
        svc,
        "ensure_defaults",
        lambda *args: None,
    )

    row = Agent(
        key="finance",
        name="Finance Agent",
        department="finance",
        capabilities_json='["budget"]',
        required_roles_json='["finance_user"]',
        tools_json='["invoice_lookup"]',
        status="active",
        health_status="healthy",
        avg_latency_ms=12,
        success_rate=0.98,
        tenant_id="t1",
        workspace_id="w1",
    )

    db = DB()
    db.rows[Agent] = [row]

    result = svc.registry(
        db,
        "t1",
        "w1",
    )

    assert result == [
        {
            "key": "finance",
            "name": "Finance Agent",
            "department": "finance",
            "capabilities": ["budget"],
            "required_roles": ["finance_user"],
            "tools": ["invoice_lookup"],
            "status": "active",
            "health_status": "healthy",
            "avg_latency_ms": 12,
            "success_rate": 0.98,
        }
    ]


def test_supervisor_route_keyword_and_role(
    monkeypatch,
):
    m = _m()

    monkeypatch.setattr(
        m,
        "DEFAULT_AGENT_BLUEPRINTS",
        _blueprints(),
    )

    monkeypatch.setattr(
        m,
        "has_permission",
        lambda claims, permission: False,
    )

    monkeypatch.setattr(
        m,
        "now_id",
        lambda prefix: "agent-route-1",
    )

    svc = m.SupervisorAgentService()

    monkeypatch.setattr(
        svc,
        "ensure_defaults",
        lambda *args: None,
    )

    agent = Agent(
        key="finance",
        department="finance",
        required_roles_json='["finance_user"]',
        tenant_id="t1",
        workspace_id="w1",
    )

    db = DB()
    db.rows[Agent] = [agent]

    result = svc.route(
        db,
        message="invoice budget invoice",
        claims={
            "sub": "user-1",
            "roles": ["finance_user"],
        },
        tenant_id="t1",
        workspace_id="w1",
    )

    assert result["run_id"] == "agent-route-1"
    assert result["selected_agent"] == "finance"
    assert result["selected_department"] == "finance"
    assert result["allowed"] is True
    assert result["reason"].startswith(
        "keyword_hits:"
    )

    assert len(db.added) == 1
    assert db.commits == 1


def test_supervisor_route_fallback_and_permission(
    monkeypatch,
):
    m = _m()

    monkeypatch.setattr(
        m,
        "DEFAULT_AGENT_BLUEPRINTS",
        _blueprints(),
    )

    monkeypatch.setattr(
        m,
        "has_permission",
        lambda claims, permission: True,
    )

    svc = m.SupervisorAgentService()

    monkeypatch.setattr(
        svc,
        "ensure_defaults",
        lambda *args: None,
    )

    db = DB()

    result = svc.route(
        db,
        message="unrelated question",
        claims={
            "sub": "admin",
            "roles": [],
        },
        tenant_id="t1",
        workspace_id="w1",
    )

    assert result["selected_agent"] == "supervisor"
    assert result["selected_department"] == "enterprise"
    assert result["reason"] == "fallback_supervisor"
    assert result["allowed"] is True
    assert result["required_roles"] == []


def test_supervisor_health(
    monkeypatch,
):
    m = _m()
    svc = m.SupervisorAgentService()

    monkeypatch.setattr(
        svc,
        "registry",
        lambda *args: [
            {
                "health_status": "healthy",
            },
            {
                "health_status": "down",
            },
            {
                "health_status": "healthy",
            },
        ],
    )

    result = svc.health(
        DB(),
        "t1",
        "w1",
    )

    assert result["agents_total"] == 3
    assert result["healthy"] == 2


def test_workflow_ensure_templates(
    monkeypatch,
):
    m = _m()

    svc = m.WorkflowAutomationService()

    monkeypatch.setattr(
        svc,
        "DEFAULT_TEMPLATES",
        [
            {
                "key": "existing",
                "name": "Existing",
                "category": "x",
                "steps": ["submit"],
            },
            {
                "key": "approval-flow",
                "name": "Approval Flow",
                "category": "ops",
                "steps": [
                    "submit",
                    "review",
                    "approval",
                    "notify",
                ],
            },
        ],
    )

    db = DB()
    db.rows[WorkflowTemplate] = [
        WorkflowTemplate(
            key="existing",
            tenant_id="t1",
            workspace_id="w1",
        )
    ]

    svc.ensure_templates(
        db,
        "t1",
        "w1",
    )

    assert len(db.added) == 1

    row = db.added[0]

    definition = json.loads(
        row.definition_json
    )

    assert row.key == "approval-flow"
    assert (
        definition["nodes"][1]["type"]
        == "approval"
    )
    assert (
        definition["nodes"][2]["type"]
        == "approval"
    )
    assert (
        definition["nodes"][0]["type"]
        == "task"
    )

    assert db.commits == 1


def test_workflow_templates(
    monkeypatch,
):
    m = _m()

    svc = m.WorkflowAutomationService()

    monkeypatch.setattr(
        svc,
        "ensure_templates",
        lambda *args: None,
    )

    row = WorkflowTemplate(
        key="purchase",
        name="Purchase",
        category="procurement",
        enabled=True,
        definition_json='{"edges":["submit"]}',
        tenant_id="t1",
        workspace_id="w1",
    )

    db = DB()
    db.rows[WorkflowTemplate] = [row]

    result = svc.templates(
        db,
        "t1",
        "w1",
    )

    assert result[0]["key"] == "purchase"
    assert result[0]["enabled"] is True
    assert result[0]["definition"] == {
        "edges": ["submit"]
    }


def test_workflow_start_success(
    monkeypatch,
):
    m = _m()

    svc = m.WorkflowAutomationService()

    monkeypatch.setattr(
        svc,
        "ensure_templates",
        lambda *args: None,
    )

    monkeypatch.setattr(
        m,
        "now_id",
        lambda prefix: "wf-1",
    )

    template = WorkflowTemplate(
        key="purchase",
        enabled=True,
        definition_json=(
            '{"edges":["review","approval"]}'
        ),
        tenant_id="t1",
        workspace_id="w1",
    )

    db = DB()
    db.rows[WorkflowTemplate] = [template]

    result = svc.start(
        db,
        template_key="purchase",
        payload={"amount": 100},
        requested_by="user-1",
        tenant_id="t1",
        workspace_id="w1",
    )

    assert result == {
        "execution_id": "wf-1",
        "template_key": "purchase",
        "status": "running",
        "current_step": "review",
        "sla_tracking": "enabled",
    }

    assert len(db.added) == 1

    execution = db.added[0]

    assert execution.current_step == "review"
    assert execution.requested_by == "user-1"
    assert json.loads(
        execution.payload_json
    ) == {"amount": 100}

    assert db.commits == 1


def test_workflow_start_missing_template(
    monkeypatch,
):
    m = _m()

    svc = m.WorkflowAutomationService()

    monkeypatch.setattr(
        svc,
        "ensure_templates",
        lambda *args: None,
    )

    with pytest.raises(
        ValueError,
        match="Workflow template",
    ):
        svc.start(
            DB(),
            template_key="missing",
            payload={},
            requested_by="u",
            tenant_id="t",
            workspace_id="w",
        )


def test_workflow_executions():
    m = _m()

    rows = [
        WorkflowExecution(
            execution_id=f"wf-{i}",
            template_key="purchase",
            status="running",
            current_step="review",
            requested_by="u",
            tenant_id="t1",
            workspace_id="w1",
        )
        for i in range(3)
    ]

    db = DB()
    db.rows[WorkflowExecution] = rows

    result = (
        m.WorkflowAutomationService()
        .executions(
            db,
            "t1",
            "w1",
        )
    )

    assert len(result) == 3
    assert result[0]["template_key"] == "purchase"


def test_connector_list():
    m = _m()

    row = Connector(
        key="sap-prod",
        name="SAP",
        connector_type="sap",
        auth_type="oauth",
        enabled=True,
        health_status="healthy",
        last_sync_status="completed",
        tenant_id="t1",
        workspace_id="w1",
    )

    db = DB()
    db.rows[Connector] = [row]

    result = m.ConnectorService().list(
        db,
        "t1",
        "w1",
    )

    assert result[0]["key"] == "sap-prod"
    assert result[0]["type"] == "sap"
    assert result[0]["health_status"] == "healthy"


def test_connector_create_supported_and_unsupported():
    m = _m()
    svc = m.ConnectorService()

    with pytest.raises(
        ValueError,
        match="Unsupported connector_type",
    ):
        svc.create(
            DB(),
            {
                "key": "bad",
                "name": "Bad",
                "connector_type": "unknown",
            },
            "t1",
            "w1",
        )

    db = DB()

    result = svc.create(
        db,
        {
            "key": "sap-prod",
            "name": "SAP",
            "connector_type": "sap",
            "auth_type": "oauth",
            "base_url": "https://sap.example",
            "schedule": "hourly",
            "secrets_ref": "vault/sap",
            "enabled": True,
            "metadata": {
                "region": "me",
            },
        },
        "t1",
        "w1",
    )

    assert result == {
        "key": "sap-prod",
        "status": "created",
    }

    assert len(db.added) == 1
    assert db.commits == 1


@pytest.mark.parametrize(
    "connector_type,configured_url,expected",
    [
        (
            "sap",
            "https://sap.example",
            "healthy",
        ),
        (
            "sap",
            "",
            "configuration_required",
        ),
        (
            "active_directory",
            "",
            "healthy",
        ),
        (
            "file_repository",
            "",
            "healthy",
        ),
    ],
)
def test_connector_test_health_paths(
    connector_type,
    configured_url,
    expected,
):
    m = _m()

    row = Connector(
        key="conn-1",
        connector_type=connector_type,
        base_url=configured_url,
        tenant_id="t1",
        workspace_id="w1",
    )

    db = DB()
    db.rows[Connector] = [row]

    result = m.ConnectorService().test(
        db,
        "conn-1",
        "t1",
        "w1",
    )

    assert result["health_status"] == expected
    assert row.health_status == expected
    assert db.commits == 1


def test_connector_test_missing():
    m = _m()

    with pytest.raises(
        ValueError,
        match="Connector not found",
    ):
        m.ConnectorService().test(
            DB(),
            "missing",
            "t1",
            "w1",
        )


def test_observability_record_and_dashboard():
    m = _m()

    db = DB()

    svc = m.ObservabilityService()

    svc.record(
        db,
        metric_type="counter",
        name="agent_runs",
        value=2.5,
        tenant_id="t1",
        workspace_id="w1",
        labels={"agent": "finance"},
    )

    assert len(db.added) == 1
    assert db.commits == 1

    db.rows[Metric] = [
        Metric(
            name="agent_runs",
            value=2.5,
            tenant_id="t1",
            workspace_id="w1",
        ),
        Metric(
            name="agent_runs",
            value=1.5,
            tenant_id="t1",
            workspace_id="w1",
        ),
        Metric(
            name="errors",
            value=1,
            tenant_id="t1",
            workspace_id="w1",
        ),
    ]

    result = svc.dashboard(
        db,
        "t1",
        "w1",
    )

    assert result["ai_usage"] == {
        "agent_runs": 4.0,
        "errors": 1.0,
    }

    assert (
        result["executive_dashboard"][
            "risk_level"
        ]
        == "controlled"
    )

    assert "latency" in result["panels"]


def test_approval_create_and_queue(
    monkeypatch,
):
    m = _m()

    monkeypatch.setattr(
        m,
        "now_id",
        lambda prefix: "approval-1",
    )

    svc = m.HumanInLoopService()
    db = DB()

    result = svc.create(
        db,
        data={
            "title": "Approve invoice",
            "action_type": "approve",
            "resource_type": "invoice",
            "resource_id": "inv-1",
            "risk_level": "high",
            "required_roles": [
                "finance_manager"
            ],
            "payload": {
                "amount": 100,
            },
        },
        claims={
            "sub": "requester-1",
        },
        tenant_id="t1",
        workspace_id="w1",
    )

    assert result == {
        "approval_id": "approval-1",
        "status": "pending",
    }

    assert len(db.added) == 1
    assert db.commits == 1

    row = Approval(
        approval_id="approval-2",
        title="Review",
        action_type="review",
        risk_level="medium",
        status="pending",
        required_roles_json='["auditor"]',
        tenant_id="t1",
        workspace_id="w1",
    )

    db.rows[Approval] = [row]

    queue = svc.queue(
        db,
        "t1",
        "w1",
    )

    assert queue == [
        {
            "approval_id": "approval-2",
            "title": "Review",
            "action_type": "review",
            "risk_level": "medium",
            "status": "pending",
            "required_roles": ["auditor"],
        }
    ]


def test_approval_decide_missing():
    m = _m()

    with pytest.raises(
        ValueError,
        match="Approval not found",
    ):
        m.HumanInLoopService().decide(
            DB(),
            "missing",
            "approved",
            "",
            {
                "sub": "u",
                "roles": ["admin"],
            },
            "t1",
            "w1",
        )


def test_approval_decide_unauthorized():
    m = _m()

    row = Approval(
        approval_id="a1",
        required_roles_json='["finance_manager"]',
        status="pending",
        tenant_id="t1",
        workspace_id="w1",
    )

    db = DB()
    db.rows[Approval] = [row]

    with pytest.raises(
        PermissionError,
        match="authorized approver",
    ):
        m.HumanInLoopService().decide(
            db,
            "a1",
            "approved",
            "ok",
            {
                "sub": "user-1",
                "roles": ["employee"],
            },
            "t1",
            "w1",
        )


@pytest.mark.parametrize(
    "roles",
    [
        ["finance_manager"],
        ["hsaai_admin"],
    ],
)
def test_approval_decide_authorized(
    roles,
):
    m = _m()

    row = Approval(
        approval_id="a1",
        required_roles_json='["finance_manager"]',
        status="pending",
        tenant_id="t1",
        workspace_id="w1",
    )

    db = DB()
    db.rows[Approval] = [row]

    result = (
        m.HumanInLoopService().decide(
            db,
            "a1",
            "approved",
            "looks good",
            {
                "sub": "reviewer-1",
                "roles": roles,
            },
            "t1",
            "w1",
        )
    )

    assert result == {
        "approval_id": "a1",
        "status": "approved",
        "reviewed_by": "reviewer-1",
    }

    assert row.status == "approved"
    assert row.reviewed_by == "reviewer-1"
    assert row.review_comment == "looks good"
    assert row.updated_at is not None

    assert db.commits == 1
