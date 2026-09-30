import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import services.backend_core.smart_responses.service as s


class FakeDB:
    def __init__(self):
        self.added = []
        self.deleted = []
        self.commits = 0
        self.refreshed = []

    def add(self, obj):
        self.added.append(obj)

    def delete(self, obj):
        self.deleted.append(obj)

    def commit(self):
        self.commits += 1

    def refresh(self, obj):
        self.refreshed.append(obj)


def test_keywords_helpers():
    assert json.loads(s._keywords_json(["a", "ب"])) == ["a", "ب"]

    good = SimpleNamespace(keywords_json='["x","y"]')
    bad = SimpleNamespace(keywords_json="{bad")

    assert s._keywords_list(good) == ["x", "y"]
    assert s._keywords_list(bad) == []


@pytest.mark.asyncio
async def test_parse_upload_json_list():
    class File:
        async def read(self):
            return b'[{"a": 1}, {"a": 2}]'

    rows = await s.parse_upload(File(), "json")
    assert rows == [{"a": 1}, {"a": 2}]


@pytest.mark.asyncio
async def test_parse_upload_json_object_items():
    class File:
        async def read(self):
            return b'{"items":[{"x":1}]}'

    rows = await s.parse_upload(File(), "json")
    assert rows == [{"x": 1}]


@pytest.mark.asyncio
async def test_parse_upload_csv():
    class File:
        async def read(self):
            return b"name,intent\nhello,greeting\n"

    rows = await s.parse_upload(File(), "csv")
    assert rows[0]["name"] == "hello"


@pytest.mark.asyncio
async def test_parse_upload_unsupported():
    class File:
        async def read(self):
            return b"test"

    with pytest.raises(HTTPException) as exc:
        await s.parse_upload(File(), "xml")

    assert exc.value.status_code == 400


def test_detect_response_no_match(monkeypatch):
    db = FakeDB()

    monkeypatch.setattr(s, "seed_defaults", lambda *a, **k: None)
    monkeypatch.setattr(s, "_active_templates", lambda *a, **k: [])
    monkeypatch.setattr(s, "find_best_match", lambda *a, **k: None)

    result = s.detect_response(
        db,
        "hello",
        "tenant",
        "workspace",
        "user",
    )

    assert result["matched"] is False
    assert result["source"] == "llm"
    assert db.commits == 1


def test_detect_response_match(monkeypatch):
    db = FakeDB()

    template = SimpleNamespace(
        id=7,
        intent="greeting",
        response_text="hello",
        usage_count=0,
        success_count=0,
    )

    match = SimpleNamespace(
        template=template,
        score=0.95,
    )

    monkeypatch.setattr(s, "seed_defaults", lambda *a, **k: None)
    monkeypatch.setattr(s, "_active_templates", lambda *a, **k: [template])
    monkeypatch.setattr(s, "find_best_match", lambda *a, **k: match)

    result = s.detect_response(
        db,
        "hello",
        "tenant",
        "workspace",
        "user",
    )

    assert result["matched"] is True
    assert result["rule_id"] == 7
    assert result["score"] == 0.95
    assert template.usage_count == 1
    assert template.success_count == 1


def test_import_items_success_and_error(monkeypatch):
    calls = []

    class Payload:
        def __init__(self, **kwargs):
            if kwargs["rule_name"] == "bad":
                raise ValueError("bad row")
            self.__dict__.update(kwargs)

    monkeypatch.setattr(s, "SmartResponseCreate", Payload)
    monkeypatch.setattr(
        s,
        "create_template",
        lambda db, payload, tenant_id, actor: calls.append(payload.rule_name),
    )

    result = s.import_items(
        FakeDB(),
        [
            {
                "rule_name": "good",
                "response_text": "ok",
            },
            {
                "rule_name": "bad",
                "response_text": "bad",
            },
        ],
        "tenant",
        "tester",
    )

    assert result["imported"] == 1
    assert result["skipped"] == 1
    assert calls == ["good"]


def test_to_dict():
    template = SimpleNamespace(
        id=1,
        tenant_id="t",
        workspace_id="w",
        rule_name="r",
        intent="i",
        keywords_json='["a"]',
        match_type="keyword",
        regex_pattern=None,
        response_text="response",
        priority=1,
        enabled=True,
        language="ar",
        usage_count=2,
        success_count=1,
        fallback_count=0,
        created_by="u",
        updated_by="u",
        created_at=None,
        updated_at=None,
    )

    result = s.to_dict(template)

    assert result["keywords"] == ["a"]
    assert result["regex_pattern"] == ""
    assert result["response_text"] == "response"
