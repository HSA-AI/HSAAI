import importlib.util
import sys
import types
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace


MODULE = "_hsaai_executive_service_test"


class Field:
    def __init__(self, name):
        self.name = name

    def __eq__(self, other):
        return (
            "eq",
            self.name,
            other,
        )

    def desc(self):
        return self


class Message:
    pass


class AuditLog:
    pass


class KnowledgeDocument:
    pass


class KnowledgeAnalyticsEvent:
    pass


class ExecutiveAlert:
    severity = Field("severity")
    status = Field("status")
    created_at = Field("created_at")

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class DepartmentMetric:
    adoption_score = Field(
        "adoption_score"
    )


class Query:
    def __init__(
        self,
        rows=None,
        count_value=None,
    ):
        self.rows = list(rows or [])
        self.count_value = count_value
        self.filters = []

    def filter(self, *filters):
        self.filters.extend(filters)
        return self

    def count(self):
        if self.count_value is not None:
            return self.count_value
        return len(self.rows)

    def all(self):
        return list(self.rows)

    def order_by(self, *args):
        return self

    def limit(self, value):
        self.rows = self.rows[:value]
        return self


class ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar(self):
        return self.value


class RowsResult:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows


class DB:
    def __init__(self):
        self.queries = {}
        self.execute_results = []
        self.added = []
        self.commits = 0
        self.refreshed = []

    def query(self, model):
        value = self.queries.get(
            model,
            Query(),
        )

        if callable(value):
            return value()

        return value

    def execute(self, query):
        value = self.execute_results.pop(0)

        if isinstance(
            value,
            Exception,
        ):
            raise value

        return value

    def add(self, row):
        self.added.append(row)

    def commit(self):
        self.commits += 1

    def refresh(self, row):
        self.refreshed.append(row)
        if not hasattr(row, "id"):
            row.id = 99


def _load():
    existing = sys.modules.get(MODULE)

    if existing is not None:
        return existing

    root = Path(__file__).resolve().parents[2]

    source = (
        root
        / "services/backend_core/executive/service.py"
    )

    sqlalchemy = types.ModuleType(
        "sqlalchemy"
    )
    sqlalchemy.text = lambda q: q

    orm = types.ModuleType(
        "sqlalchemy.orm"
    )
    orm.Session = object

    db_pkg = types.ModuleType(
        "backend_core.db"
    )
    db_pkg.__path__ = []

    models = types.ModuleType(
        "backend_core.db.models"
    )

    for name, value in {
        "Message": Message,
        "AuditLog": AuditLog,
        "KnowledgeDocument":
            KnowledgeDocument,
        "KnowledgeAnalyticsEvent":
            KnowledgeAnalyticsEvent,
        "ExecutiveAlert":
            ExecutiveAlert,
        "DepartmentMetric":
            DepartmentMetric,
    }.items():
        setattr(
            models,
            name,
            value,
        )

    replacements = {
        "sqlalchemy": sqlalchemy,
        "sqlalchemy.orm": orm,
        "backend_core.db": db_pkg,
        "backend_core.db.models":
            models,
    }

    old = {
        name: sys.modules.get(name)
        for name in replacements
    }

    sys.modules.update(replacements)

    try:
        spec = (
            importlib.util.spec_from_file_location(
                MODULE,
                source,
            )
        )

        module = (
            importlib.util.module_from_spec(
                spec
            )
        )
        sys.modules[MODULE] = module
        spec.loader.exec_module(module)

        return module

    finally:
        for name, previous in old.items():
            if previous is None:
                sys.modules.pop(
                    name,
                    None,
                )
            else:
                sys.modules[name] = previous


def test_count_and_safe_count():
    m = _load()
    db = DB()

    db.queries[Message] = Query(
        count_value=4
    )

    service = (
        m.ExecutiveAnalyticsService(
            db
        )
    )

    assert service._count(
        Message,
        "filter-1",
    ) == 4

    db.execute_results = [
        ScalarResult(8)
    ]

    assert (
        service._safe_count(
            "SELECT COUNT(*)"
        )
        == 8
    )

    db.execute_results = [
        RuntimeError("db down")
    ]

    assert (
        service._safe_count(
            "SELECT bad"
        )
        == 0
    )


def test_overview_live():
    m = _load()
    db = DB()

    departments = [
        SimpleNamespace(
            active_users=3,
        ),
        SimpleNamespace(
            active_users=4,
        ),
    ]

    db.queries[
        m.DepartmentMetric
    ] = Query(departments)

    db.queries[m.Message] = Query(
        count_value=5
    )

    db.queries[
        m.KnowledgeDocument
    ] = Query(
        count_value=2
    )

    db.queries[
        m.KnowledgeAnalyticsEvent
    ] = Query(
        count_value=6
    )

    db.queries[
        m.AuditLog
    ] = Query(
        count_value=7
    )

    db.queries[
        m.ExecutiveAlert
    ] = Query(
        count_value=1
    )

    service = (
        m.ExecutiveAnalyticsService(
            db
        )
    )

    service._safe_count = (
        lambda query:
        9 if "agent_logs" in query
        else 11
    )

    service.usage_trend = (
        lambda: [
            {
                "day": "2026-09-27",
                "value": 5,
            }
        ]
    )

    result = service.overview()

    assert (
        result["cards"][
            "active_users"
        ]
        == 7
    )

    assert (
        result["cards"][
            "total_chats"
        ]
        == 5
    )

    assert (
        result["cards"][
            "agent_executions"
        ]
        == 9
    )

    assert (
        result["cards"][
            "workflow_executions"
        ]
        == 11
    )

    assert (
        result["data_source"]
        == "live"
    )


def test_departments_and_knowledge():
    m = _load()
    db = DB()

    row = SimpleNamespace(
        department="finance",
        active_users=10,
        chats=20,
        knowledge_searches=30,
        agent_runs=40,
        workflow_runs=50,
        adoption_score=0.9,
    )

    db.queries[
        m.DepartmentMetric
    ] = Query([row])

    service = (
        m.ExecutiveAnalyticsService(
            db
        )
    )

    departments = (
        service.departments()
    )

    assert departments[0][
        "department"
    ] == "finance"

    service._count = (
        lambda model:
        12
        if model is m.KnowledgeDocument
        else 3
    )

    knowledge = service.knowledge()

    assert knowledge[
        "documents"
    ] == 12

    assert knowledge[
        "searches"
    ] == 3

    assert knowledge[
        "data_source"
    ] == "live"


def test_agents_success_zero_and_error():
    m = _load()

    db = DB()
    db.execute_results = [
        ScalarResult(10),
        ScalarResult(8),
    ]

    service = (
        m.ExecutiveAnalyticsService(
            db
        )
    )

    result = service.agents()

    assert result[
        "total_runs"
    ] == 10
    assert result[
        "successful_runs"
    ] == 8
    assert result[
        "success_rate"
    ] == 80.0
    assert result[
        "data_source"
    ] == "live"

    db.execute_results = [
        ScalarResult(0),
        ScalarResult(0),
    ]

    zero = service.agents()

    assert zero[
        "success_rate"
    ] == 0
    assert zero[
        "data_source"
    ] == "empty"

    db.execute_results = [
        RuntimeError("missing table")
    ]

    failed = service.agents()

    assert failed[
        "total_runs"
    ] == 0
    assert failed[
        "data_source"
    ] == "empty"


def test_workflows_success_zero_and_error():
    m = _load()

    db = DB()
    service = (
        m.ExecutiveAnalyticsService(
            db
        )
    )

    db.execute_results = [
        ScalarResult(20),
        ScalarResult(5),
    ]

    result = service.workflows()

    assert result[
        "executions"
    ] == 20
    assert result[
        "failures"
    ] == 5
    assert result[
        "success_rate"
    ] == 75.0

    db.execute_results = [
        ScalarResult(0),
        ScalarResult(0),
    ]

    assert service.workflows()[
        "success_rate"
    ] == 0

    db.execute_results = [
        RuntimeError("boom")
    ]

    failed = service.workflows()

    assert failed[
        "executions"
    ] == 0
    assert failed[
        "data_source"
    ] == "empty"


def test_infrastructure():
    m = _load()

    result = (
        m.ExecutiveAnalyticsService(
            DB()
        ).infrastructure()
    )

    assert result[
        "cpu_usage"
    ] is None
    assert result[
        "gpu_usage"
    ] is None
    assert result[
        "data_source"
    ] == "empty"


def test_alerts_and_create_alert():
    m = _load()
    db = DB()

    created_at = datetime(
        2026,
        9,
        27,
        1,
        2,
        3,
    )

    alert = SimpleNamespace(
        id=1,
        severity="critical",
        category="platform",
        title="Outage",
        description="Service down",
        status="open",
        owner="ops",
        created_at=created_at,
    )

    db.queries[
        m.ExecutiveAlert
    ] = Query([alert])

    service = (
        m.ExecutiveAnalyticsService(
            db
        )
    )

    rows = service.alerts()

    assert rows[0][
        "created_at"
    ] == created_at.isoformat()

    payload = SimpleNamespace(
        dict=lambda: {
            "severity": "warning",
            "category": "ai",
            "title": "Latency",
            "description": "High latency",
            "status": "open",
            "owner": "platform",
        }
    )

    result = service.create_alert(
        payload
    )

    assert result == {
        "id": 99,
        "status": "created",
    }

    assert len(db.added) == 1
    assert db.commits == 1
    assert db.refreshed


def test_usage_trend_rows_empty_and_error():
    m = _load()
    db = DB()

    service = (
        m.ExecutiveAnalyticsService(
            db
        )
    )

    db.execute_results = [
        RowsResult(
            [
                (
                    "2026-09-26",
                    4,
                ),
                (
                    "2026-09-27",
                    7,
                ),
            ]
        )
    ]

    assert service.usage_trend() == [
        {
            "day": "2026-09-26",
            "value": 4,
        },
        {
            "day": "2026-09-27",
            "value": 7,
        },
    ]

    db.execute_results = [
        RowsResult([])
    ]

    assert service.usage_trend() == []

    db.execute_results = [
        RuntimeError("db error")
    ]

    assert service.usage_trend() == []
