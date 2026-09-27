import importlib

import pytest


def _module():
    return importlib.import_module("common.tool_registry")


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


def _install_http(
    monkeypatch,
    m,
    *,
    status=200,
    payload=None,
    exc=None,
):
    calls = []

    class Client:
        def __init__(self, *args, **kwargs):
            calls.append(("init", args, kwargs))

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, **kwargs):
            calls.append(("get", url, kwargs))
            if exc:
                raise exc
            return FakeResponse(status, payload)

        async def post(self, url, **kwargs):
            calls.append(("post", url, kwargs))
            if exc:
                raise exc
            return FakeResponse(status, payload)

    monkeypatch.setattr(
        m.httpx,
        "AsyncClient",
        Client,
    )

    return calls


@pytest.mark.asyncio
async def test_rag_search_success_and_http_failure(monkeypatch):
    m = _module()

    calls = _install_http(
        monkeypatch,
        m,
        payload={
            "results": [
                {"id": 1},
                {"id": 2},
                {"id": 3},
            ],
            "count": 3,
        },
    )

    result = await m._rag_search(
        "enterprise AI",
        top_k=2,
        _context={
            "tenant_id": "tenant-a",
            "workspace_id": "workspace-a",
        },
    )

    assert result["success"] is True
    assert len(result["results"]) == 2
    assert result["count"] == 3

    post = [x for x in calls if x[0] == "post"][0]
    assert post[2]["json"]["tenant_id"] == "tenant-a"
    assert post[2]["json"]["workspace_id"] == "workspace-a"

    _install_http(
        monkeypatch,
        m,
        status=503,
    )

    failed = await m._rag_search("x")

    assert failed["success"] is False
    assert "HTTP 503" in failed["error"]


@pytest.mark.asyncio
async def test_policy_lookup_success_empty_and_failure(monkeypatch):
    m = _module()

    _install_http(
        monkeypatch,
        m,
        payload={
            "results": [
                {"name": "Policy A"},
                {"name": "Policy B"},
            ]
        },
    )

    result = await m._policy_lookup(
        "security",
        _context={"tenant_id": "t1"},
    )

    assert result["success"] is True
    assert result["policy"]["name"] == "Policy A"
    assert len(result["alternatives"]) == 1

    _install_http(
        monkeypatch,
        m,
        payload={"results": []},
    )

    empty = await m._policy_lookup("missing")
    assert empty["success"] is True
    assert empty["policy"] is None
    assert empty["alternatives"] == []

    _install_http(
        monkeypatch,
        m,
        status=500,
    )

    failed = await m._policy_lookup("broken")
    assert failed["success"] is False
    assert "HTTP 500" in failed["error"]


@pytest.mark.asyncio
async def test_long_summarizer_success_and_failure(monkeypatch):
    m = _module()

    long_text = "Enterprise AI governance. " * 20

    calls = _install_http(
        monkeypatch,
        m,
        payload={"text": " concise enterprise summary "},
    )

    result = await m._summarizer(
        long_text,
        max_length=120,
        _context={"tenant_id": "tenant-x"},
    )

    assert result["success"] is True
    assert result["summary"] == "concise enterprise summary"
    assert result["original_length"] == len(long_text)
    assert result["summary_length"] > 0

    post = [x for x in calls if x[0] == "post"][0]
    assert post[2]["json"]["tenant_id"] == "tenant-x"

    _install_http(
        monkeypatch,
        m,
        status=429,
    )

    failed = await m._summarizer(long_text)
    assert failed["success"] is False
    assert "HTTP 429" in failed["error"]


@pytest.mark.asyncio
async def test_invoice_lookup_all_paths(monkeypatch):
    m = _module()

    calls = _install_http(
        monkeypatch,
        m,
        payload={
            "vendor": "Vendor A",
            "amount": 123.4,
            "currency": "USD",
            "due_date": "2026-12-01",
            "status": "open",
        },
    )

    result = await m._invoice_lookup(
        "INV-1",
        _context={
            "tenant_id": "tenant-a",
            "token": "abc",
        },
    )

    assert result["success"] is True
    assert result["invoice_id"] == "INV-1"
    assert result["fields"]["vendor"] == "Vendor A"
    assert result["source"] == "sap_s4hana"

    get_call = [x for x in calls if x[0] == "get"][0]
    assert get_call[2]["headers"]["X-Tenant-Id"] == "tenant-a"

    _install_http(
        monkeypatch,
        m,
        status=404,
    )

    failed = await m._invoice_lookup("INV-X")
    assert failed["success"] is False
    assert failed["status"] == "error"

    _install_http(
        monkeypatch,
        m,
        exc=RuntimeError("connector offline"),
    )

    unavailable = await m._invoice_lookup("INV-Y")
    assert unavailable["success"] is False
    assert unavailable["status"] == "unavailable"
    assert "connector offline" in unavailable["error"]


@pytest.mark.asyncio
async def test_budget_summary_all_paths(monkeypatch):
    m = _module()

    _install_http(
        monkeypatch,
        m,
        payload={
            "period": "Q3",
            "budget": 1000,
            "actual": 700,
            "variance": 300,
            "utilization_pct": 70,
        },
    )

    result = await m._budget_summary(
        "finance",
        _context={
            "tenant_id": "t1",
            "token": "token",
        },
    )

    assert result["success"] is True
    assert result["department"] == "finance"
    assert result["budget"] == 1000
    assert result["actual"] == 700

    _install_http(
        monkeypatch,
        m,
        status=503,
    )

    failed = await m._budget_summary("hr")
    assert failed["success"] is False
    assert failed["status"] == "error"

    _install_http(
        monkeypatch,
        m,
        exc=RuntimeError("sap down"),
    )

    unavailable = await m._budget_summary("sales")
    assert unavailable["success"] is False
    assert unavailable["status"] == "unavailable"


@pytest.mark.asyncio
async def test_kpi_summary_success_http_failure_and_exception(monkeypatch):
    m = _module()

    _install_http(
        monkeypatch,
        m,
        payload={
            "tokens_today": 42,
            "active_agents": 7,
            "avg_latency_ms": 120,
        },
    )

    result = await m._kpi_summary(
        "executive",
        _context={"token": "abc"},
    )

    assert result["success"] is True
    assert result["kpis"]["ai_requests_today"] == 42
    assert result["kpis"]["active_agents"] == 7

    _install_http(
        monkeypatch,
        m,
        status=500,
    )

    failed = await m._kpi_summary("x")
    assert failed["success"] is False
    assert failed["kpis"] == {}

    _install_http(
        monkeypatch,
        m,
        exc=RuntimeError("analytics down"),
    )

    failed2 = await m._kpi_summary("x")
    assert failed2["success"] is False


@pytest.mark.asyncio
async def test_risk_analysis_success_http_failure_and_exception(monkeypatch):
    m = _module()

    _install_http(
        monkeypatch,
        m,
        payload={
            "entities": [
                {"id": 1},
                {"id": 2},
                {"id": 3},
            ]
        },
    )

    result = await m._risk_analysis(
        "finance",
        _context={
            "tenant_id": "t1",
            "workspace_id": "w1",
        },
    )

    assert result["success"] is True
    assert result["risks_identified"] == 3

    _install_http(
        monkeypatch,
        m,
        status=500,
    )

    failed = await m._risk_analysis("finance")
    assert failed["success"] is False
    assert failed["risks_identified"] == 0

    _install_http(
        monkeypatch,
        m,
        exc=RuntimeError("graph down"),
    )

    failed2 = await m._risk_analysis("finance")
    assert failed2["success"] is False


@pytest.mark.asyncio
async def test_document_extract_success_empty_and_http_failure(monkeypatch):
    m = _module()

    _install_http(
        monkeypatch,
        m,
        payload={
            "documents": [
                {
                    "doc_id": "doc-1",
                    "text": "content",
                }
            ]
        },
    )

    result = await m._document_extract(
        "doc-1",
        _context={
            "tenant_id": "t1",
            "workspace_id": "w1",
        },
    )

    assert result["success"] is True
    assert result["document"]["doc_id"] == "doc-1"

    _install_http(
        monkeypatch,
        m,
        payload={"documents": []},
    )

    empty = await m._document_extract("missing")
    assert empty["success"] is False
    assert empty["doc_id"] == "missing"

    _install_http(
        monkeypatch,
        m,
        status=404,
    )

    missing = await m._document_extract("missing2")
    assert missing["success"] is False


@pytest.mark.asyncio
async def test_citation_builder_formats_results():
    m = _module()

    result = await m._citation_builder(
        [
            {
                "doc_id": "d1",
                "filename": "a.pdf",
                "chunk_index": 2,
                "page": 3,
                "score": 0.95,
                "text": "A" * 300,
            },
            {},
        ]
    )

    assert result["success"] is True
    assert result["count"] == 2
    assert result["citations"][0]["index"] == 1
    assert len(result["citations"][0]["quote"]) == 200
    assert result["citations"][1]["doc_id"] == "unknown"


@pytest.mark.asyncio
async def test_employee_lookup_all_paths(monkeypatch):
    m = _module()

    calls = _install_http(
        monkeypatch,
        m,
        payload={
            "name": "Employee One",
            "department": "IT",
            "position": "Engineer",
            "manager": "Manager",
            "email": "employee@example.com",
        },
    )

    result = await m._employee_lookup(
        "E-1",
        _context={
            "tenant_id": "t1",
            "token": "secret",
        },
    )

    assert result["success"] is True
    assert result["employee_id"] == "E-1"
    assert result["fields"]["department"] == "IT"
    assert result["source"] == "sap_successfactors"

    get_call = [x for x in calls if x[0] == "get"][0]
    assert get_call[2]["headers"]["X-Tenant-Id"] == "t1"

    _install_http(
        monkeypatch,
        m,
        status=403,
    )

    denied = await m._employee_lookup("E-2")
    assert denied["success"] is False
    assert denied["status"] == "error"

    _install_http(
        monkeypatch,
        m,
        exc=RuntimeError("HR offline"),
    )

    unavailable = await m._employee_lookup("E-3")
    assert unavailable["success"] is False
    assert unavailable["status"] == "unavailable"
