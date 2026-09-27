import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest


_MODULE_NAME = "_hsaai_smart_responses_service_test"


def _load_service():
    """
    Load the real smart_responses/service.py while isolating only its
    database/schema collaborators.

    Local Termux uses Pydantic v1, while HSAAI CI/production uses Pydantic v2.
    Importing backend_core.smart_responses.models normally reaches
    backend_core.config and fails locally before service.py can execute.

    Production source remains unchanged.
    """
    existing = sys.modules.get(_MODULE_NAME)
    if existing is not None:
        return existing

    repo_root = Path(__file__).resolve().parents[2]
    source = (
        repo_root
        / "services"
        / "backend_core"
        / "smart_responses"
        / "service.py"
    )

    injected = {}

    # ------------------------------------------------------------------
    # Models boundary
    # ------------------------------------------------------------------
    models_name = "backend_core.smart_responses.models"
    old_models = sys.modules.get(models_name)

    models = types.ModuleType(models_name)

    class PlaceholderTemplate:
        pass

    class PlaceholderLog:
        pass

    models.SmartResponseTemplate = PlaceholderTemplate
    models.SmartResponseLog = PlaceholderLog

    sys.modules[models_name] = models
    injected[models_name] = old_models

    # ------------------------------------------------------------------
    # Schemas boundary
    # ------------------------------------------------------------------
    schemas_name = "backend_core.smart_responses.schemas"
    old_schemas = sys.modules.get(schemas_name)

    schemas = types.ModuleType(schemas_name)

    class SmartResponseCreate:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class SmartResponseUpdate:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

        def model_dump(self, exclude_unset=True):
            return dict(self.__dict__)

    schemas.SmartResponseCreate = SmartResponseCreate
    schemas.SmartResponseUpdate = SmartResponseUpdate

    sys.modules[schemas_name] = schemas
    injected[schemas_name] = old_schemas

    # ------------------------------------------------------------------
    # Matcher boundary
    # ------------------------------------------------------------------
    matcher_name = "backend_core.smart_responses.matcher"
    old_matcher = sys.modules.get(matcher_name)

    matcher = types.ModuleType(matcher_name)
    matcher.find_best_match = (
        lambda message, templates: None
    )

    sys.modules[matcher_name] = matcher
    injected[matcher_name] = old_matcher

    try:
        spec = importlib.util.spec_from_file_location(
            _MODULE_NAME,
            source,
        )

        if spec is None or spec.loader is None:
            raise RuntimeError(
                f"Unable to load smart response service: {source}"
            )

        module = importlib.util.module_from_spec(spec)
        sys.modules[_MODULE_NAME] = module
        spec.loader.exec_module(module)

        return module

    finally:
        # Restore canonical dependency modules so this isolated test does not
        # interfere with the rest of the test suite.
        for name, previous in injected.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous


s = _load_service()


class Field:
    def __init__(self, name):
        self.name = name

    def __eq__(self, value):
        return ("eq", self.name, value)

    def __ne__(self, value):
        return ("ne", self.name, value)

    def is_(self, value):
        return ("is", self.name, value)


class FakeTemplate:
    tenant_id = Field("tenant_id")
    workspace_id = Field("workspace_id")
    enabled = Field("enabled")
    priority = Field("priority")
    intent = Field("intent")
    rule_name = Field("rule_name")
    usage_count = Field("usage_count")

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class FakeLog:
    tenant_id = Field("tenant_id")
    workspace_id = Field("workspace_id")
    response_source = Field("response_source")
    intent = Field("intent")
    id = Field("id")


class Query:
    def __init__(
        self,
        *,
        rows=None,
        first_value=None,
        counts=None,
    ):
        self.rows = list(rows or [])
        self.first_value = first_value
        self.counts = list(counts or [])
        self.filters = []
        self.limit_value = None

    def filter(self, *args):
        self.filters.extend(args)
        return self

    def filter_by(self, **kwargs):
        self.filters.append(
            ("filter_by", kwargs)
        )
        return self

    def order_by(self, *args):
        return self

    def group_by(self, *args):
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def first(self):
        return self.first_value

    def all(self):
        if self.limit_value is None:
            return list(self.rows)
        return list(self.rows[: self.limit_value])

    def count(self):
        if self.counts:
            return self.counts.pop(0)
        return len(self.rows)


class DB:
    def __init__(self, query=None):
        self.query_obj = query or Query()
        self.added = []
        self.deleted = []
        self.commits = 0
        self.refreshed = []

    def query(self, *args):
        return self.query_obj

    def add(self, obj):
        self.added.append(obj)

    def delete(self, obj):
        self.deleted.append(obj)

    def commit(self):
        self.commits += 1

    def refresh(self, obj):
        self.refreshed.append(obj)


def _patch_sql_helpers(monkeypatch):
    monkeypatch.setattr(
        s,
        "SmartResponseTemplate",
        FakeTemplate,
    )
    monkeypatch.setattr(
        s,
        "SmartResponseLog",
        FakeLog,
    )
    monkeypatch.setattr(
        s,
        "desc",
        lambda value: value,
    )
    monkeypatch.setattr(
        s,
        "and_",
        lambda *values: values,
    )


def test_seed_defaults_existing_does_nothing(
    monkeypatch,
):
    _patch_sql_helpers(monkeypatch)

    existing = FakeTemplate(id=1)
    db = DB(
        Query(first_value=existing)
    )

    cleared = []
    monkeypatch.setattr(
        s,
        "clear_cache",
        lambda: cleared.append(True),
    )

    s.seed_defaults(
        db,
        tenant_id="t1",
        workspace_id="w1",
    )

    assert db.added == []
    assert db.commits == 0
    assert cleared == []


def test_seed_defaults_creates_defaults(
    monkeypatch,
):
    _patch_sql_helpers(monkeypatch)

    monkeypatch.setattr(
        s,
        "DEFAULT_RESPONSES",
        [
            {
                "rule_name": "Greeting",
                "intent": "greeting",
                "keywords": ["hello", "مرحبا"],
                "match_type": "keyword",
                "response_text": "Hello",
                "priority": 100,
            }
        ],
    )

    cleared = []
    monkeypatch.setattr(
        s,
        "clear_cache",
        lambda: cleared.append(True),
    )

    db = DB(Query(first_value=None))

    s.seed_defaults(
        db,
        tenant_id="tenant-a",
        workspace_id="workspace-a",
    )

    assert len(db.added) == 1

    row = db.added[0]

    assert row.tenant_id == "tenant-a"
    assert row.workspace_id == "workspace-a"
    assert row.created_by == "system"
    assert row.enabled is True
    assert row.language == "ar"
    assert db.commits == 1
    assert cleared == [True]


def test_list_templates_filters_workspace_and_disabled(
    monkeypatch,
):
    _patch_sql_helpers(monkeypatch)

    rows = [
        FakeTemplate(id=1),
        FakeTemplate(id=2),
    ]
    query = Query(rows=rows)
    db = DB(query)

    result = s.list_templates(
        db,
        tenant_id="t1",
        workspace_id="w1",
        include_disabled=False,
    )

    assert result == rows

    # tenant + workspace + enabled
    assert len(query.filters) == 3


def test_active_templates_cache_hit(
    monkeypatch,
):
    _patch_sql_helpers(monkeypatch)

    cached_rows = [
        FakeTemplate(id=7)
    ]

    monkeypatch.setattr(
        s,
        "_cache",
        {
            ("t1", "w1"): (
                100.0,
                cached_rows,
            )
        },
    )
    monkeypatch.setattr(
        s.time,
        "time",
        lambda: 101.0,
    )

    class ExplodingDB:
        def query(self, *args):
            raise AssertionError(
                "database must not be queried "
                "on a valid cache hit"
            )

    result = s._active_templates(
        ExplodingDB(),
        "t1",
        "w1",
    )

    assert result is cached_rows


def test_active_templates_cache_miss(
    monkeypatch,
):
    _patch_sql_helpers(monkeypatch)

    rows = [
        FakeTemplate(id=1),
        FakeTemplate(id=2),
    ]

    query = Query(rows=rows)
    db = DB(query)

    monkeypatch.setattr(s, "_cache", {})
    monkeypatch.setattr(
        s.time,
        "time",
        lambda: 500.0,
    )

    result = s._active_templates(
        db,
        "t1",
        "w1",
    )

    assert result == rows
    assert s._cache[
        ("t1", "w1")
    ][1] == rows


def test_create_template(
    monkeypatch,
):
    _patch_sql_helpers(monkeypatch)

    cleared = []
    monkeypatch.setattr(
        s,
        "clear_cache",
        lambda: cleared.append(True),
    )

    payload = SimpleNamespace(
        workspace_id="w1",
        rule_name="Unit Rule",
        intent="greeting",
        keywords=["hello"],
        match_type="keyword",
        regex_pattern=None,
        response_text="Hello",
        priority=20,
        enabled=True,
        language="en",
    )

    db = DB()

    result = s.create_template(
        db,
        payload,
        tenant_id="t1",
        actor="admin",
    )

    assert result.rule_name == "Unit Rule"
    assert result.tenant_id == "t1"
    assert result.updated_by == "admin"
    assert result.regex_pattern == ""

    assert db.added == [result]
    assert db.commits == 1
    assert db.refreshed == [result]
    assert cleared == [True]


def test_get_template_success_and_not_found(
    monkeypatch,
):
    _patch_sql_helpers(monkeypatch)

    row = FakeTemplate(id=10)

    result = s.get_template(
        DB(Query(first_value=row)),
        10,
        "tenant-a",
    )

    assert result is row

    with pytest.raises(
        s.HTTPException
    ) as exc:
        s.get_template(
            DB(Query(first_value=None)),
            999,
            "tenant-a",
        )

    assert exc.value.status_code == 404


def test_update_template_keywords_and_regular_field(
    monkeypatch,
):
    template = SimpleNamespace(
        keywords_json="[]",
        priority=1,
        updated_by="old",
    )

    monkeypatch.setattr(
        s,
        "get_template",
        lambda *args, **kwargs: template,
    )

    cleared = []
    monkeypatch.setattr(
        s,
        "clear_cache",
        lambda: cleared.append(True),
    )

    class Payload:
        def model_dump(
            self,
            exclude_unset=True,
        ):
            assert exclude_unset is True
            return {
                "keywords": ["alpha", "beta"],
                "priority": 900,
            }

    db = DB()

    result = s.update_template(
        db,
        template_id=1,
        payload=Payload(),
        tenant_id="t1",
        actor="editor",
    )

    assert (
        result.keywords_json
        == '["alpha", "beta"]'
    )
    assert result.priority == 900
    assert result.updated_by == "editor"

    assert db.commits == 1
    assert db.refreshed == [template]
    assert cleared == [True]


def test_delete_template(
    monkeypatch,
):
    template = SimpleNamespace(id=5)

    monkeypatch.setattr(
        s,
        "get_template",
        lambda *args, **kwargs: template,
    )

    cleared = []
    monkeypatch.setattr(
        s,
        "clear_cache",
        lambda: cleared.append(True),
    )

    db = DB()

    result = s.delete_template(
        db,
        5,
        "t1",
    )

    assert result is None
    assert db.deleted == [template]
    assert db.commits == 1
    assert cleared == [True]


def test_analytics_with_workspace(
    monkeypatch,
):
    _patch_sql_helpers(monkeypatch)

    class CountExpr:
        def label(self, name):
            return self

    fake_func = SimpleNamespace(
        count=lambda value: CountExpr()
    )

    monkeypatch.setattr(
        s,
        "func",
        fake_func,
    )

    top_rules = [
        SimpleNamespace(
            id=1,
            rule_name="Greeting",
            intent="greeting",
            usage_count=7,
        ),
        SimpleNamespace(
            id=2,
            rule_name="FAQ",
            intent="faq",
            usage_count=3,
        ),
    ]

    base_query = Query(
        counts=[10, 7, 3]
    )
    template_query = Query(
        rows=top_rules
    )
    intent_query = Query(
        rows=[
            ("greeting", 6),
            ("faq", 4),
        ]
    )

    class AnalyticsDB:
        def query(self, *args):
            if len(args) == 2:
                return intent_query

            if args[0] is FakeLog:
                return base_query

            if args[0] is FakeTemplate:
                return template_query

            raise AssertionError(
                f"unexpected query: {args}"
            )

    result = s.analytics(
        AnalyticsDB(),
        tenant_id="t1",
        workspace_id="w1",
    )

    assert result["total_requests"] == 10
    assert result["smart_response_hits"] == 7
    assert result["llm_fallbacks"] == 3
    assert result["match_rate"] == 0.7
    assert result["llm_fallback_rate"] == 0.3

    assert result["top_rules"][0] == {
        "id": 1,
        "rule_name": "Greeting",
        "intent": "greeting",
        "usage_count": 7,
    }

    assert result["top_intents"] == [
        {
            "intent": "greeting",
            "count": 6,
        },
        {
            "intent": "faq",
            "count": 4,
        },
    ]


def test_analytics_zero_total(
    monkeypatch,
):
    _patch_sql_helpers(monkeypatch)

    class CountExpr:
        def label(self, name):
            return self

    monkeypatch.setattr(
        s,
        "func",
        SimpleNamespace(
            count=lambda value: CountExpr()
        ),
    )

    base_query = Query(
        counts=[0, 0, 0]
    )
    template_query = Query(rows=[])
    intent_query = Query(rows=[])

    class AnalyticsDB:
        def query(self, *args):
            if len(args) == 2:
                return intent_query
            if args[0] is FakeLog:
                return base_query
            return template_query

    result = s.analytics(
        AnalyticsDB(),
        tenant_id="t1",
    )

    assert result["total_requests"] == 0
    assert result["match_rate"] == 0
    assert result["llm_fallback_rate"] == 0


def test_export_rows(
    monkeypatch,
):
    templates = [
        SimpleNamespace(id=1),
        SimpleNamespace(id=2),
    ]

    monkeypatch.setattr(
        s,
        "list_templates",
        lambda *args, **kwargs: templates,
    )

    monkeypatch.setattr(
        s,
        "to_dict",
        lambda row: {
            "id": row.id
        },
    )

    result = s.export_rows(
        DB(),
        "t1",
        "w1",
    )

    assert result == [
        {"id": 1},
        {"id": 2},
    ]


@pytest.mark.asyncio
async def test_parse_upload_excel(
    monkeypatch,
):
    fake_openpyxl = types.ModuleType(
        "openpyxl"
    )

    class Sheet:
        def iter_rows(
            self,
            values_only=True,
        ):
            assert values_only is True
            return iter(
                [
                    (
                        "rule_name",
                        "intent",
                    ),
                    (
                        "Greeting",
                        "greeting",
                    ),
                    (
                        "FAQ",
                        "faq",
                    ),
                ]
            )

    workbook = SimpleNamespace(
        active=Sheet()
    )

    fake_openpyxl.load_workbook = (
        lambda *args, **kwargs: workbook
    )

    monkeypatch.setitem(
        sys.modules,
        "openpyxl",
        fake_openpyxl,
    )

    class File:
        async def read(self):
            return b"fake-xlsx-bytes"

    rows = await s.parse_upload(
        File(),
        "excel",
    )

    assert rows == [
        {
            "rule_name": "Greeting",
            "intent": "greeting",
        },
        {
            "rule_name": "FAQ",
            "intent": "faq",
        },
    ]


@pytest.mark.asyncio
async def test_parse_upload_excel_empty(
    monkeypatch,
):
    fake_openpyxl = types.ModuleType(
        "openpyxl"
    )

    class Sheet:
        def iter_rows(
            self,
            values_only=True,
        ):
            return iter([])

    fake_openpyxl.load_workbook = (
        lambda *args, **kwargs:
        SimpleNamespace(
            active=Sheet()
        )
    )

    monkeypatch.setitem(
        sys.modules,
        "openpyxl",
        fake_openpyxl,
    )

    class File:
        async def read(self):
            return b"empty-xlsx"

    assert (
        await s.parse_upload(
            File(),
            "excel",
        )
        == []
    )


@pytest.mark.asyncio
async def test_parse_upload_excel_dependency_failure(
    monkeypatch,
):
    # Force `from openpyxl import ...`
    # to fail inside parse_upload.
    monkeypatch.setitem(
        sys.modules,
        "openpyxl",
        None,
    )

    class File:
        async def read(self):
            return b"x"

    with pytest.raises(
        s.HTTPException
    ) as exc:
        await s.parse_upload(
            File(),
            "excel",
        )

    assert exc.value.status_code == 500
    assert "openpyxl" in str(
        exc.value.detail
    )
