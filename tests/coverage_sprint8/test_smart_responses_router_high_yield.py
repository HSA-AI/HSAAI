import builtins
import importlib.util
import json
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest


MODULE = "_hsaai_smart_responses_router_test"


class APIRouter:
    def __init__(self, *args, **kwargs):
        pass

    def get(self, *args, **kwargs):
        return lambda func: func

    def post(self, *args, **kwargs):
        return lambda func: func

    def put(self, *args, **kwargs):
        return lambda func: func

    def delete(self, *args, **kwargs):
        return lambda func: func

    def patch(self, *args, **kwargs):
        return lambda func: func


def Depends(value=None):
    return value


def File(default=None, **kwargs):
    return default


def Query(default=None, **kwargs):
    return default


class UploadFile:
    pass


class Response:
    def __init__(
        self,
        content="",
        media_type=None,
        headers=None,
        status_code=200,
    ):
        self.body = (
            content.encode()
            if isinstance(
                content,
                str,
            )
            else content
        )
        self.media_type = media_type
        self.headers = headers or {}
        self.status_code = status_code


class StreamingResponse(Response):
    def __init__(
        self,
        content,
        media_type=None,
        headers=None,
        status_code=200,
    ):
        super().__init__(
            b"",
            media_type,
            headers,
            status_code,
        )
        self.content = content


class Session:
    pass


class Payload(SimpleNamespace):
    def dict(self):
        return dict(vars(self))


class SmartResponseUpdate(Payload):
    pass


class SmartResponseCreate(Payload):
    pass


class PriorityUpdate(Payload):
    pass


def _load():
    existing = sys.modules.get(MODULE)
    if existing is not None:
        return existing

    root = Path(__file__).resolve().parents[2]

    source = (
        root
        / "services/backend_core/smart_responses/router.py"
    )

    fastapi = types.ModuleType("fastapi")

    for name, value in {
        "APIRouter": APIRouter,
        "Depends": Depends,
        "File": File,
        "Query": Query,
        "UploadFile": UploadFile,
    }.items():
        setattr(
            fastapi,
            name,
            value,
        )

    responses = types.ModuleType(
        "fastapi.responses"
    )
    responses.Response = Response
    responses.StreamingResponse = (
        StreamingResponse
    )

    sqlalchemy = types.ModuleType(
        "sqlalchemy"
    )

    orm = types.ModuleType(
        "sqlalchemy.orm"
    )
    orm.Session = Session

    db_pkg = types.ModuleType(
        "backend_core.db"
    )
    db_pkg.__path__ = []

    db = types.ModuleType(
        "backend_core.db.database"
    )
    db.get_db = lambda: None

    security_pkg = types.ModuleType(
        "backend_core.security"
    )
    security_pkg.__path__ = []

    rbac = types.ModuleType(
        "backend_core.security.rbac"
    )
    rbac.require_permission = (
        lambda permission:
        lambda: {}
    )

    smart_pkg = types.ModuleType(
        "backend_core.smart_responses"
    )
    smart_pkg.__path__ = []

    service = types.ModuleType(
        "backend_core.smart_responses.service"
    )

    schemas = types.ModuleType(
        "backend_core.smart_responses.schemas"
    )
    schemas.PriorityUpdate = (
        PriorityUpdate
    )
    schemas.SmartResponseCreate = (
        SmartResponseCreate
    )
    schemas.SmartResponseUpdate = (
        SmartResponseUpdate
    )

    smart_pkg.service = service

    replacements = {
        "fastapi": fastapi,
        "fastapi.responses": responses,
        "sqlalchemy": sqlalchemy,
        "sqlalchemy.orm": orm,
        "backend_core.db": db_pkg,
        "backend_core.db.database": db,
        "backend_core.security":
            security_pkg,
        "backend_core.security.rbac":
            rbac,
        "backend_core.smart_responses":
            smart_pkg,
        "backend_core.smart_responses.service":
            service,
        "backend_core.smart_responses.schemas":
            schemas,
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


def _service(module):
    calls = []

    templates = {
        1: SimpleNamespace(
            id=1,
            enabled=True,
        )
    }

    async def parse_upload(
        file,
        fmt,
    ):
        calls.append(
            (
                "parse",
                fmt,
            )
        )
        return [
            {
                "rule_name": "Imported"
            }
        ]

    fake = SimpleNamespace(
        seed_defaults=(
            lambda db, **kwargs:
            calls.append(
                (
                    "seed",
                    kwargs,
                )
            )
        ),
        list_templates=(
            lambda db, tenant,
            workspace, include:
            [
                SimpleNamespace(
                    id=1,
                    enabled=True,
                )
            ]
        ),
        to_dict=lambda item: (
            item
            if isinstance(item, dict)
            else dict(vars(item))
        ),
        create_template=(
            lambda db, payload,
            tenant, actor:
            SimpleNamespace(
                id=2,
                actor=actor,
            )
        ),
        analytics=(
            lambda db, tenant,
            workspace: {
                "total": 2
            }
        ),
        parse_upload=parse_upload,
        import_items=(
            lambda db, items,
            tenant, actor: {
                "imported": len(items)
            }
        ),
        export_rows=(
            lambda db, tenant,
            workspace: [
                {
                    "rule_name":
                        "Greeting",
                    "intent":
                        "hello",
                    "keywords":
                        ["hi", "hello"],
                    "response_text":
                        "Hello!",
                }
            ]
        ),
        get_template=(
            lambda db, template_id,
            tenant:
            templates[template_id]
        ),
        update_template=(
            lambda db, template_id,
            payload, tenant, actor:
            SimpleNamespace(
                id=template_id,
                enabled=getattr(
                    payload,
                    "enabled",
                    True,
                ),
                priority=getattr(
                    payload,
                    "priority",
                    1,
                ),
            )
        ),
        delete_template=(
            lambda db, template_id,
            tenant:
            calls.append(
                (
                    "delete",
                    template_id,
                )
            )
        ),
    )

    module.service = fake

    return calls


CLAIMS = {
    "tenant_id": "tenant-1",
    "sub": "admin-1",
    "workspace_id": "finance",
}


def test_ctx_defaults_and_values():
    m = _load()

    assert m._ctx({}) == (
        "default",
        "system",
    )

    assert m._ctx(CLAIMS) == (
        "tenant-1",
        "admin-1",
    )


def test_crud_analytics_and_listing():
    m = _load()
    calls = _service(m)

    db = object()

    items = m.list_smart_responses(
        workspace_id=None,
        include_disabled=True,
        db=db,
        claims=CLAIMS,
    )

    assert items[0]["id"] == 1
    assert calls[0][0] == "seed"

    created = m.create_smart_response(
        SmartResponseCreate(
            rule_name="New",
        ),
        db,
        CLAIMS,
    )

    assert created["id"] == 2
    assert created[
        "actor"
    ] == "admin-1"

    assert m.smart_response_analytics(
        None,
        db,
        CLAIMS,
    ) == {
        "total": 2
    }

    assert m.get_smart_response(
        1,
        db,
        CLAIMS,
    )["id"] == 1

    updated = (
        m.update_smart_response(
            1,
            SmartResponseUpdate(
                enabled=False
            ),
            db,
            CLAIMS,
        )
    )

    assert updated[
        "enabled"
    ] is False

    assert m.delete_smart_response(
        1,
        db,
        CLAIMS,
    ) == {
        "deleted": True
    }


@pytest.mark.asyncio
async def test_import():
    m = _load()
    _service(m)

    result = await (
        m.import_smart_responses(
            "json",
            object(),
            object(),
            CLAIMS,
        )
    )

    assert result == {
        "imported": 1
    }


def test_export_json_and_csv():
    m = _load()
    _service(m)

    json_response = m.export_json(
        None,
        object(),
        CLAIMS,
    )

    parsed = json.loads(
        json_response.body.decode()
    )

    assert parsed[0][
        "rule_name"
    ] == "Greeting"

    assert (
        json_response.media_type
        == "application/json"
    )

    csv_response = m.export_csv(
        None,
        object(),
        CLAIMS,
    )

    text = (
        csv_response.body.decode()
    )

    assert "rule_name" in text
    assert "Greeting" in text
    assert (
        csv_response.media_type
        == "text/csv"
    )


def test_export_csv_empty_rows():
    m = _load()
    _service(m)

    m.service.export_rows = (
        lambda *args: []
    )

    response = m.export_csv(
        None,
        object(),
        CLAIMS,
    )

    assert "rule_name" in (
        response.body.decode()
    )


def test_export_excel_success(
    monkeypatch,
):
    m = _load()
    _service(m)

    saved = {}

    class Sheet:
        def __init__(self):
            self.title = ""
            self.rows = []

        def append(self, row):
            self.rows.append(row)

    class Workbook:
        def __init__(self):
            self.active = Sheet()

        def save(self, buffer):
            saved[
                "rows"
            ] = list(
                self.active.rows
            )
            buffer.write(
                b"xlsx"
            )

    openpyxl = types.ModuleType(
        "openpyxl"
    )
    openpyxl.Workbook = Workbook

    monkeypatch.setitem(
        sys.modules,
        "openpyxl",
        openpyxl,
    )

    response = m.export_excel(
        None,
        object(),
        CLAIMS,
    )

    assert isinstance(
        response,
        StreamingResponse,
    )

    assert saved["rows"][0][
        0
    ] == "rule_name"

    assert (
        response.media_type
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


def test_export_excel_missing_dependency(
    monkeypatch,
):
    m = _load()
    _service(m)

    real_import = (
        builtins.__import__
    )

    def fake_import(
        name,
        globals=None,
        locals=None,
        fromlist=(),
        level=0,
    ):
        if name == "openpyxl":
            raise ImportError(
                "not installed"
            )

        return real_import(
            name,
            globals,
            locals,
            fromlist,
            level,
        )

    monkeypatch.setattr(
        builtins,
        "__import__",
        fake_import,
    )

    response = m.export_excel(
        None,
        object(),
        CLAIMS,
    )

    assert (
        response.status_code
        == 500
    )

    assert b"openpyxl is required" in (
        response.body
    )


def test_toggle_and_priority():
    m = _load()
    _service(m)

    toggled = (
        m.toggle_smart_response(
            1,
            object(),
            CLAIMS,
        )
    )

    assert (
        toggled["enabled"]
        is False
    )

    priority = m.update_priority(
        1,
        PriorityUpdate(
            priority=9
        ),
        object(),
        CLAIMS,
    )

    assert (
        priority["priority"]
        == 9
    )
