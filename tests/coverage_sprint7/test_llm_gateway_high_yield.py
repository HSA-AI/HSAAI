import importlib
from types import SimpleNamespace

import pytest


def _module():
    import sys
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]
    service_dir = repo_root / "services" / "llm_gateway"

    service_dir_str = str(service_dir)
    if service_dir_str not in sys.path:
        sys.path.insert(0, service_dir_str)

    return importlib.import_module(
        "services.llm_gateway.main"
    )


def _request():
    return SimpleNamespace(
        system="You are HSAAI",
        prompt="Explain enterprise AI",
        temperature=0.2,
        max_tokens=128,
    )


class FakeResponse:
    def __init__(
        self,
        *,
        status_code=200,
        payload=None,
    ):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


def _install_client(
    monkeypatch,
    m,
    response,
    captured,
):
    class Client:
        def __init__(self, *args, **kwargs):
            captured["client_kwargs"] = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, **kwargs):
            captured["url"] = url
            captured["kwargs"] = kwargs
            return response

    monkeypatch.setattr(
        m.httpx,
        "AsyncClient",
        Client,
    )


def test_consume_token_budget_disabled_and_missing_client(
    monkeypatch,
):
    m = _module()

    monkeypatch.setattr(
        m,
        "ENABLE_TOKEN_BUDGET",
        False,
    )

    # Must return before touching Redis.
    monkeypatch.setattr(
        m,
        "_get_redis_client",
        lambda url: (_ for _ in ()).throw(
            AssertionError("Redis should not be used")
        ),
    )

    m._consume_token_budget(
        "tenant-a",
        25,
    )

    monkeypatch.setattr(
        m,
        "ENABLE_TOKEN_BUDGET",
        True,
    )

    monkeypatch.setattr(
        m,
        "_get_redis_client",
        lambda url: None,
    )

    m._consume_token_budget(
        "tenant-a",
        25,
    )


def test_consume_token_budget_pipeline_success(monkeypatch):
    m = _module()

    monkeypatch.setattr(
        m,
        "ENABLE_TOKEN_BUDGET",
        True,
    )

    calls = []

    class Pipe:
        def incrby(self, key, value):
            calls.append(
                ("incrby", key, value)
            )

        def expireat(self, key, when):
            calls.append(
                ("expireat", key, when)
            )

        def execute(self):
            calls.append(
                ("execute",)
            )

    class Redis:
        def pipeline(self):
            return Pipe()

    monkeypatch.setattr(
        m,
        "_get_redis_client",
        lambda url: Redis(),
    )

    m._consume_token_budget(
        "tenant-a",
        37,
    )

    assert any(
        item[0] == "incrby"
        and "tenant-a" in item[1]
        and item[2] == 37
        for item in calls
    )

    assert any(
        item[0] == "expireat"
        for item in calls
    )

    assert ("execute",) in calls


def test_consume_token_budget_redis_failure_is_nonfatal(
    monkeypatch,
):
    m = _module()

    monkeypatch.setattr(
        m,
        "ENABLE_TOKEN_BUDGET",
        True,
    )

    class Redis:
        def pipeline(self):
            raise RuntimeError("redis unavailable")

    monkeypatch.setattr(
        m,
        "_get_redis_client",
        lambda url: Redis(),
    )

    # The accounting path is deliberately fail-open.
    m._consume_token_budget(
        "tenant-a",
        10,
    )


@pytest.mark.asyncio
async def test_external_generate_openai_success(monkeypatch):
    m = _module()

    monkeypatch.setenv(
        "OPENAI_API_KEY",
        "openai-test-key",
    )

    captured = {}

    _install_client(
        monkeypatch,
        m,
        FakeResponse(
            payload={
                "choices": [
                    {
                        "message": {
                            "content": "OpenAI answer"
                        }
                    }
                ]
            }
        ),
        captured,
    )

    result = await m.external_generate(
        _request(),
        {
            "provider": "openai",
            "model": "gpt-test",
        },
    )

    assert result == "OpenAI answer"
    assert "openai.com" in captured["url"]
    assert (
        captured["kwargs"]["headers"][
            "Authorization"
        ]
        == "Bearer openai-test-key"
    )


@pytest.mark.asyncio
async def test_external_generate_openai_key_and_http_failures(
    monkeypatch,
):
    m = _module()

    monkeypatch.delenv(
        "OPENAI_API_KEY",
        raising=False,
    )

    captured = {}

    _install_client(
        monkeypatch,
        m,
        FakeResponse(),
        captured,
    )

    with pytest.raises(m.HTTPException) as exc:
        await m.external_generate(
            _request(),
            {
                "provider": "openai",
                "model": "gpt-test",
            },
        )

    assert exc.value.status_code == 503

    monkeypatch.setenv(
        "OPENAI_API_KEY",
        "test-key",
    )

    _install_client(
        monkeypatch,
        m,
        FakeResponse(
            status_code=429,
        ),
        captured,
    )

    with pytest.raises(m.HTTPException) as exc:
        await m.external_generate(
            _request(),
            {
                "provider": "openai",
                "model": "gpt-test",
            },
        )

    assert exc.value.status_code == 429


@pytest.mark.asyncio
async def test_external_generate_anthropic_success(monkeypatch):
    m = _module()

    monkeypatch.setenv(
        "ANTHROPIC_API_KEY",
        "anthropic-test-key",
    )

    captured = {}

    _install_client(
        monkeypatch,
        m,
        FakeResponse(
            payload={
                "content": [
                    {
                        "type": "text",
                        "text": "Part A",
                    },
                    {
                        "type": "tool_use",
                        "text": "ignored",
                    },
                    {
                        "type": "text",
                        "text": " Part B",
                    },
                ]
            }
        ),
        captured,
    )

    result = await m.external_generate(
        _request(),
        {
            "provider": "anthropic",
            "model": "claude-test",
        },
    )

    assert result == "Part A Part B"
    assert "anthropic.com" in captured["url"]
    assert (
        captured["kwargs"]["headers"]["x-api-key"]
        == "anthropic-test-key"
    )


@pytest.mark.asyncio
async def test_external_generate_anthropic_missing_key(
    monkeypatch,
):
    m = _module()

    monkeypatch.delenv(
        "ANTHROPIC_API_KEY",
        raising=False,
    )

    captured = {}

    _install_client(
        monkeypatch,
        m,
        FakeResponse(),
        captured,
    )

    with pytest.raises(m.HTTPException) as exc:
        await m.external_generate(
            _request(),
            {
                "provider": "anthropic",
                "model": "claude-test",
            },
        )

    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_external_generate_google_success_and_empty(
    monkeypatch,
):
    m = _module()

    monkeypatch.setenv(
        "GEMINI_API_KEY",
        "gemini-test-key",
    )
    monkeypatch.delenv(
        "GOOGLE_API_KEY",
        raising=False,
    )

    captured = {}

    _install_client(
        monkeypatch,
        m,
        FakeResponse(
            payload={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {"text": "Gemini"},
                                {"text": " answer"},
                            ]
                        }
                    }
                ]
            }
        ),
        captured,
    )

    result = await m.external_generate(
        _request(),
        {
            "provider": "google",
            "model": "gemini-test",
        },
    )

    assert result == "Gemini answer"
    assert (
        captured["kwargs"]["headers"][
            "x-goog-api-key"
        ]
        == "gemini-test-key"
    )

    _install_client(
        monkeypatch,
        m,
        FakeResponse(
            payload={"candidates": []}
        ),
        captured,
    )

    result = await m.external_generate(
        _request(),
        {
            "provider": "google",
            "model": "gemini-test",
        },
    )

    assert result == ""


@pytest.mark.asyncio
async def test_external_generate_google_missing_key(
    monkeypatch,
):
    m = _module()

    monkeypatch.delenv(
        "GEMINI_API_KEY",
        raising=False,
    )
    monkeypatch.delenv(
        "GOOGLE_API_KEY",
        raising=False,
    )

    captured = {}

    _install_client(
        monkeypatch,
        m,
        FakeResponse(),
        captured,
    )

    with pytest.raises(m.HTTPException) as exc:
        await m.external_generate(
            _request(),
            {
                "provider": "google",
                "model": "gemini-test",
            },
        )

    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_external_generate_unsupported_provider(
    monkeypatch,
):
    m = _module()

    captured = {}

    _install_client(
        monkeypatch,
        m,
        FakeResponse(),
        captured,
    )

    with pytest.raises(m.HTTPException) as exc:
        await m.external_generate(
            _request(),
            {
                "provider": "unsupported",
                "model": "unknown",
            },
        )

    assert exc.value.status_code == 400
    assert "Unsupported provider" in str(
        exc.value.detail
    )
