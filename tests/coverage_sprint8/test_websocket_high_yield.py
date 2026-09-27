import importlib.util
import sys
import types
from pathlib import Path

import pytest
from fastapi import HTTPException, WebSocketDisconnect


_MODULE = "_hsaai_websocket_ws_test"


def _m():
    existing = sys.modules.get(_MODULE)
    if existing is not None:
        return existing

    repo_root = Path(__file__).resolve().parents[2]
    source = (
        repo_root
        / "services"
        / "backend_core"
        / "websocket"
        / "ws.py"
    )

    names = [
        "backend_core",
        "backend_core.core",
        "backend_core.core.engine",
        "common",
        "common.auth",
        "common.auth.service_auth",
    ]

    old = {
        name: sys.modules.get(name)
        for name in names
    }

    try:
        backend = types.ModuleType("backend_core")
        backend.__path__ = []

        core = types.ModuleType(
            "backend_core.core"
        )
        core.__path__ = []

        engine = types.ModuleType(
            "backend_core.core.engine"
        )
        engine.process_message = (
            lambda user_id, message, **kwargs: {
                "user_id": user_id,
                "message": message,
                **kwargs,
            }
        )

        common = types.ModuleType("common")
        common.__path__ = []

        auth = types.ModuleType("common.auth")
        auth.__path__ = []

        service_auth = types.ModuleType(
            "common.auth.service_auth"
        )
        service_auth.verify_jwt = (
            lambda token: {
                "sub": "user-1",
                "tenant_id": "tenant-1",
                "workspace_id": "workspace-1",
                "roles": ["user"],
            }
        )

        sys.modules["backend_core"] = backend
        sys.modules["backend_core.core"] = core
        sys.modules[
            "backend_core.core.engine"
        ] = engine

        sys.modules["common"] = common
        sys.modules["common.auth"] = auth
        sys.modules[
            "common.auth.service_auth"
        ] = service_auth

        spec = importlib.util.spec_from_file_location(
            _MODULE,
            source,
        )

        if spec is None or spec.loader is None:
            raise RuntimeError(
                f"Cannot load {source}"
            )

        module = importlib.util.module_from_spec(spec)
        sys.modules[_MODULE] = module
        spec.loader.exec_module(module)

        return module

    finally:
        for name, previous in old.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous


class FakeWebSocket:
    def __init__(
        self,
        *,
        token=None,
        protocol="",
        messages=None,
        receive_error=None,
        close_error=False,
    ):
        self.query_params = {}
        if token is not None:
            self.query_params["token"] = token

        self.headers = {}
        if protocol:
            self.headers[
                "sec-websocket-protocol"
            ] = protocol

        self.messages = list(messages or [])
        self.receive_error = receive_error
        self.close_error = close_error

        self.accepted = False
        self.closed = []
        self.sent = []

    async def accept(self):
        self.accepted = True

    async def close(self, code, reason):
        self.closed.append(
            (code, reason)
        )
        if self.close_error:
            raise RuntimeError(
                "close failed"
            )

    async def receive_text(self):
        if self.messages:
            return self.messages.pop(0)

        if self.receive_error is not None:
            raise self.receive_error

        raise WebSocketDisconnect()

    async def send_json(self, value):
        self.sent.append(value)


@pytest.mark.asyncio
async def test_missing_token_closes_4401():
    m = _m()
    ws = FakeWebSocket()

    await m.websocket_endpoint(ws)

    assert ws.accepted is False
    assert ws.closed == [
        (
            4401,
            "Missing authentication token",
        )
    ]


@pytest.mark.asyncio
async def test_protocol_header_token_success(
    monkeypatch,
):
    m = _m()

    seen_tokens = []

    monkeypatch.setattr(
        m,
        "verify_jwt",
        lambda token: (
            seen_tokens.append(token)
            or {
                "sub": "u1",
                "tenant_id": "t1",
                "workspace_id": "w1",
            }
        ),
    )

    calls = []

    monkeypatch.setattr(
        m,
        "process_message",
        lambda user_id, msg, **kwargs: (
            calls.append(
                (user_id, msg, kwargs)
            )
            or {"answer": "ok"}
        ),
    )

    ws = FakeWebSocket(
        protocol="chat, auth.header-token",
        messages=["hello"],
    )

    await m.websocket_endpoint(ws)

    assert seen_tokens == ["header-token"]
    assert ws.accepted is True
    assert ws.sent == [{"answer": "ok"}]

    assert calls == [
        (
            "u1",
            "hello",
            {
                "tenant_id": "t1",
                "workspace_id": "w1",
            },
        )
    ]


@pytest.mark.asyncio
async def test_query_token_uses_claim_defaults(
    monkeypatch,
):
    m = _m()

    monkeypatch.setattr(
        m,
        "verify_jwt",
        lambda token: {},
    )

    calls = []

    monkeypatch.setattr(
        m,
        "process_message",
        lambda user_id, msg, **kwargs: (
            calls.append(
                (user_id, msg, kwargs)
            )
            or {"ok": True}
        ),
    )

    ws = FakeWebSocket(
        token="query-token",
        messages=["message"],
    )

    await m.websocket_endpoint(ws)

    assert ws.accepted is True

    assert calls[0] == (
        "unknown",
        "message",
        {
            "tenant_id": "default",
            "workspace_id": "default",
        },
    )


@pytest.mark.asyncio
async def test_http_exception_token_failure(
    monkeypatch,
):
    m = _m()

    def reject(token):
        raise HTTPException(
            status_code=401,
            detail="invalid",
        )

    monkeypatch.setattr(
        m,
        "verify_jwt",
        reject,
    )

    ws = FakeWebSocket(
        token="bad-token"
    )

    await m.websocket_endpoint(ws)

    assert ws.accepted is False
    assert ws.closed == [
        (
            4401,
            "Invalid or expired token",
        )
    ]


@pytest.mark.asyncio
async def test_generic_token_failure(
    monkeypatch,
):
    m = _m()

    def reject(token):
        raise RuntimeError(
            "verification broke"
        )

    monkeypatch.setattr(
        m,
        "verify_jwt",
        reject,
    )

    ws = FakeWebSocket(
        token="broken-token"
    )

    await m.websocket_endpoint(ws)

    assert ws.closed == [
        (
            4401,
            "Token verification failed",
        )
    ]


@pytest.mark.asyncio
async def test_runtime_error_closes_1011(
    monkeypatch,
):
    m = _m()

    monkeypatch.setattr(
        m,
        "verify_jwt",
        lambda token: {
            "sub": "u",
        },
    )

    ws = FakeWebSocket(
        token="valid",
        receive_error=RuntimeError(
            "socket failure"
        ),
    )

    await m.websocket_endpoint(ws)

    assert ws.accepted is True
    assert ws.closed == [
        (
            1011,
            "Internal server error",
        )
    ]


@pytest.mark.asyncio
async def test_close_failure_is_swallowed(
    monkeypatch,
):
    m = _m()

    monkeypatch.setattr(
        m,
        "verify_jwt",
        lambda token: {
            "sub": "u",
        },
    )

    ws = FakeWebSocket(
        token="valid",
        receive_error=RuntimeError(
            "socket failure"
        ),
        close_error=True,
    )

    # The endpoint must remain non-fatal even
    # if graceful close itself fails.
    await m.websocket_endpoint(ws)

    assert ws.accepted is True
    assert ws.closed
