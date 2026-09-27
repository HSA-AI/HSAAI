import importlib
from types import SimpleNamespace

import pytest


def _m():
    return importlib.import_module(
        "backend_core.workflow_runtime.service"
    )


def _reset(m):
    m.WorkflowExecutor._executions_today = 0
    m.WorkflowExecutor._successful_executions = 0
    m.WorkflowExecutor._total_runtime_sec = 0.0
    m.WorkflowExecutor._total_retries = 0
    m.WorkflowExecutor._execution_history = []


class FakeResponse:
    def __init__(
        self,
        *,
        status_code=200,
        payload=None,
        text="",
    ):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


def _install_async_client(
    monkeypatch,
    m,
    *,
    get_response=None,
    post_response=None,
    enter_error=None,
):
    calls = []

    class Client:
        def __init__(self, *args, **kwargs):
            calls.append(
                ("init", args, kwargs)
            )

        async def __aenter__(self):
            if enter_error:
                raise enter_error
            return self

        async def __aexit__(
            self,
            exc_type,
            exc,
            tb,
        ):
            return False

        async def get(self, url, **kwargs):
            calls.append(
                ("get", url, kwargs)
            )
            return get_response

        async def post(self, url, **kwargs):
            calls.append(
                ("post", url, kwargs)
            )
            return post_response

    monkeypatch.setattr(
        m.httpx,
        "AsyncClient",
        Client,
    )

    return calls


def test_retry_policy_known_and_default():
    m = _m()
    retry = m.RetryEngine()

    assert (
        retry.policy("rag")["max_attempts"]
        == 2
    )

    assert (
        retry.policy("unknown")["max_attempts"]
        == retry.POLICIES["agent"]["max_attempts"]
    )


@pytest.mark.asyncio
async def test_pending_success(monkeypatch):
    m = _m()

    response = FakeResponse(
        status_code=200,
        payload={
            "approvals": [
                {"id": "a1"},
                {"id": "a2"},
            ]
        },
    )

    calls = _install_async_client(
        monkeypatch,
        m,
        get_response=response,
    )

    result = await m.ApprovalEngine().pending()

    assert result == [
        {"id": "a1"},
        {"id": "a2"},
    ]

    get_calls = [
        x for x in calls
        if x[0] == "get"
    ]
    assert len(get_calls) == 1
    assert get_calls[0][1].endswith(
        "/v1/workflow-runtime/approvals"
    )


@pytest.mark.asyncio
async def test_pending_http_error_returns_empty(
    monkeypatch,
):
    m = _m()

    _install_async_client(
        monkeypatch,
        m,
        get_response=FakeResponse(
            status_code=503,
            payload={},
        ),
    )

    assert (
        await m.ApprovalEngine().pending()
        == []
    )


@pytest.mark.asyncio
async def test_pending_exception_returns_empty(
    monkeypatch,
):
    m = _m()

    _install_async_client(
        monkeypatch,
        m,
        enter_error=RuntimeError(
            "backend unavailable"
        ),
    )

    assert (
        await m.ApprovalEngine().pending()
        == []
    )


@pytest.mark.asyncio
async def test_start_completed_success(
    monkeypatch,
):
    m = _m()
    _reset(m)

    response = FakeResponse(
        status_code=200,
        payload={
            "status": "completed",
            "steps_completed": 3,
            "steps_total": 3,
            "step_results": [
                {"step": 1},
                {"step": 2},
                {"step": 3},
            ],
        },
    )

    calls = _install_async_client(
        monkeypatch,
        m,
        post_response=response,
    )

    executor = m.WorkflowExecutor()

    result = await executor.start(
        "invoice-approval",
        {
            "steps": ["a", "b", "c"],
            "workspace_id": "w1",
            "tenant_id": "t1",
            "input": "value",
        },
    )

    assert result["status"] == "completed"
    assert result["workflow_id"] == (
        "invoice-approval"
    )
    assert result["nodes_started"] == 3
    assert len(result["step_results"]) == 3
    assert result["external_ai_used"] is False
    assert result["execution_id"].startswith(
        "wf-run-"
    )

    assert (
        m.WorkflowExecutor._executions_today
        == 1
    )
    assert (
        m.WorkflowExecutor._successful_executions
        == 1
    )
    assert len(
        m.WorkflowExecutor._execution_history
    ) == 1

    post_calls = [
        x for x in calls
        if x[0] == "post"
    ]

    assert len(post_calls) == 1

    body = post_calls[0][2]["json"]

    assert body["name"] == "invoice-approval"
    assert body["workspace_id"] == "w1"
    assert body["tenant_id"] == "t1"
    assert body["structured_steps"] == [
        "a",
        "b",
        "c",
    ]


@pytest.mark.asyncio
async def test_start_success_noncompleted_status(
    monkeypatch,
):
    m = _m()
    _reset(m)

    _install_async_client(
        monkeypatch,
        m,
        post_response=FakeResponse(
            status_code=200,
            payload={
                "status": "running",
                "steps_completed": 1,
                "steps_total": 4,
            },
        ),
    )

    result = await m.WorkflowExecutor().start(
        "long-workflow"
    )

    assert result["status"] == "running"
    assert result["nodes_started"] == 1

    assert (
        m.WorkflowExecutor._executions_today
        == 1
    )
    assert (
        m.WorkflowExecutor._successful_executions
        == 0
    )


@pytest.mark.asyncio
async def test_start_http_failure_fallback(
    monkeypatch,
):
    m = _m()
    _reset(m)

    _install_async_client(
        monkeypatch,
        m,
        post_response=FakeResponse(
            status_code=500,
            payload={},
            text="engine failure",
        ),
    )

    result = await m.WorkflowExecutor().start(
        "broken-workflow",
        {"tenant_id": "t1"},
    )

    assert (
        result["status"]
        == "engine_unavailable"
    )
    assert result["nodes_started"] == 0
    assert "not reachable" in result["error"]

    assert (
        m.WorkflowExecutor._executions_today
        == 1
    )

    history = (
        m.WorkflowExecutor._execution_history
    )

    assert len(history) == 1
    assert (
        history[0]["status"]
        == "engine_unavailable"
    )


@pytest.mark.asyncio
async def test_start_exception_fallback(
    monkeypatch,
):
    m = _m()
    _reset(m)

    _install_async_client(
        monkeypatch,
        m,
        enter_error=RuntimeError(
            "connection refused"
        ),
    )

    result = await m.WorkflowExecutor().start(
        "offline-workflow"
    )

    assert (
        result["status"]
        == "engine_unavailable"
    )

    assert (
        result["payload"]
        == {}
    )

    assert (
        m.WorkflowExecutor._executions_today
        == 1
    )


def test_history_returns_last_50():
    m = _m()
    _reset(m)

    m.WorkflowExecutor._execution_history = [
        {"id": i}
        for i in range(75)
    ]

    result = m.WorkflowExecutor().history()

    assert len(result) == 50
    assert result[0]["id"] == 25
    assert result[-1]["id"] == 74


def test_schedules():
    m = _m()

    schedules = (
        m.WorkflowExecutor().schedules()
    )

    assert len(schedules) == 2

    assert {
        row["schedule_id"]
        for row in schedules
    } == {
        "sch-exec-daily-brief",
        "sch-weekly-compliance",
    }

    assert all(
        row["status"] == "active"
        for row in schedules
    )


@pytest.mark.asyncio
async def test_metrics_awaits_pending_approvals(
    monkeypatch,
):
    m = _m()
    _reset(m)

    m.WorkflowExecutor._executions_today = 4
    m.WorkflowExecutor._successful_executions = 3
    m.WorkflowExecutor._total_runtime_sec = 10.0
    m.WorkflowExecutor._total_retries = 2

    executor = m.WorkflowExecutor()

    calls = []

    async def fake_pending():
        calls.append(True)
        return [
            {"id": "approval-1"},
            {"id": "approval-2"},
        ]

    monkeypatch.setattr(
        executor.approvals,
        "pending",
        fake_pending,
    )

    result = await executor.metrics()

    assert calls == [True]
    assert result["executions_today"] == 4
    assert result["successful_executions"] == 3
    assert result["success_rate"] == 0.75
    assert result["avg_runtime_sec"] == 2.5
    assert result["retries"] == 2
    assert result["waiting_approvals"] == 2


@pytest.mark.asyncio
async def test_metrics_zero_execution_baseline(
    monkeypatch,
):
    m = _m()
    _reset(m)

    executor = m.WorkflowExecutor()

    async def fake_pending():
        return []

    monkeypatch.setattr(
        executor.approvals,
        "pending",
        fake_pending,
    )

    result = await executor.metrics()

    assert result["executions_today"] == 0
    assert result["successful_executions"] == 0
    assert result["success_rate"] == 0.0
    assert result["avg_runtime_sec"] == 0.0
    assert result["retries"] == 0
    assert result["waiting_approvals"] == 0
