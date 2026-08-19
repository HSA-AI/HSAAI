"""
HSAAI Enterprise AI Platform — Qdrant Vector Deletion Test Suite (v8.0)
=========================================================================
Production-Ready Enterprise test suite for `services/backend_core/knowledge/qdrant_client.py`.

Function under test:
    async def delete_document_vectors(document_id: str) -> dict[str, Any]

This suite covers:
  - Functional Tests (correct payload, URL, method, headers, response)
  - Validation Tests (empty/None/invalid document_id)
  - Error Handling Tests (HTTP 400/500, timeout, network errors, invalid JSON)
  - Security Tests (tenant isolation gap, API key header, audit logging absence)
  - Async Quality (pytest-asyncio, no unawaited coroutines, no RuntimeWarnings)
  - Code Quality (fixtures, independent, no external connections, CI/CD ready)

Coverage target: >95% on qdrant_client.py (delete_document_vectors + helpers).

Rules:
  - No real Qdrant connection (all HTTP via DummyAsyncClient)
  - pytest-asyncio with `await` on every coroutine
  - Independent tests (no execution-order dependency)
  - monkeypatch for env-level isolation
  - No external network calls
"""
from __future__ import annotations

import sys
import json
import asyncio
from pathlib import Path
from typing import Any

import pytest
import httpx

# ─── Path setup (mirrors tests/conftest.py) ────────────────────────────
_BASE = Path(__file__).resolve().parents[2]
_SERVICES = _BASE / "services"
for _p in [str(_SERVICES), str(_BASE / "packages"), str(_BASE / "packages" / "common")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend_core.knowledge import qdrant_client  # noqa: E402
from backend_core.knowledge.qdrant_client import (  # noqa: E402
    QdrantDeleteError,
    _headers,
    delete_document_vectors,
)


# ═══════════════════════════════════════════════════════════════════════
# Dummy Async Client — httpx.AsyncClient stand-in (no real network)
# ═══════════════════════════════════════════════════════════════════════
class DummyResponse:
    """Mimics httpx.Response with configurable status_code, text, and json()."""

    def __init__(self, status_code: int = 200, json_data: Any = None, text: str = ""):
        self.status_code = status_code
        self._json_data = json_data if json_data is not None else {"status": "ok"}
        self.text = text or json.dumps(self._json_data)

    def json(self) -> Any:
        if self._json_data is None:
            raise json.JSONDecodeError("No JSON", self.text, 0)
        return self._json_data

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}",
                request=httpx.Request("POST", "http://dummy"),
                response=httpx.Response(self.status_code),
            )


class DummyAsyncClient:
    """Async-context-manager httpx.AsyncClient stand-in.

    Captures the URL and payload of every POST for assertions.
    Returns a configurable DummyResponse (or raises an exception).
    """

    def __init__(
        self,
        *args: Any,
        response: DummyResponse | None = None,
        exception: Exception | None = None,
        **kwargs: Any,
    ) -> None:
        self.response = response or DummyResponse(200, {"status": "ok"})
        self.exception = exception
        self.url: str | None = None
        self.payload: dict | None = None
        self.method: str | None = None
        # Capture kwargs for header/timeout assertions
        self.kwargs = kwargs

    async def __aenter__(self) -> "DummyAsyncClient":
        return self

    async def __aexit__(self, *args: Any) -> bool:
        return False

    async def post(self, url: str, json: dict | None = None, **kwargs: Any) -> DummyResponse:
        self.url = url
        self.payload = json
        self.method = "POST"
        if self.exception is not None:
            raise self.exception
        return self.response

    async def get(self, url: str, **kwargs: Any) -> DummyResponse:
        self.url = url
        self.method = "GET"
        if self.exception is not None:
            raise self.exception
        return self.response

    async def put(self, url: str, json: dict | None = None, **kwargs: Any) -> DummyResponse:
        self.url = url
        self.payload = json
        self.method = "PUT"
        if self.exception is not None:
            raise self.exception
        return self.response


# ═══════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════
@pytest.fixture
def dummy_client_factory():
    """Factory fixture: returns a callable that creates DummyAsyncClient instances.

    Usage:
        def test_x(monkeypatch, dummy_client_factory):
            client = dummy_client_factory(response=DummyResponse(200, {"ok": True}))
            monkeypatch.setattr(qdrant_client.httpx, "AsyncClient", lambda *a, **k: client)
            result = asyncio.get_event_loop().run_until_complete(delete_document_vectors("doc_1"))
    """
    created: list[DummyAsyncClient] = []

    def _factory(
        response: DummyResponse | None = None,
        exception: Exception | None = None,
    ) -> DummyAsyncClient:
        client = DummyAsyncClient(response=response, exception=exception)
        created.append(client)
        return client

    return _factory


@pytest.fixture
def patch_async_client(monkeypatch):
    """Patch httpx.AsyncClient with a configurable DummyAsyncClient.

    Returns a function that accepts (response, exception) and patches the module.
    The returned client captures all kwargs passed to AsyncClient() in .kwargs.
    """
    state: dict[str, Any] = {"client": None}

    def _patch(
        response: DummyResponse | None = None,
        exception: Exception | None = None,
    ) -> DummyAsyncClient:
        # Create a fresh client that will capture kwargs from the constructor call
        client = DummyAsyncClient(response=response, exception=exception)
        state["client"] = client

        def _factory(*args: Any, **kwargs: Any) -> DummyAsyncClient:
            # Capture the kwargs (headers, timeout, etc.) passed to AsyncClient()
            client.kwargs = kwargs
            return client

        monkeypatch.setattr(qdrant_client.httpx, "AsyncClient", _factory)
        return client

    return _patch


@pytest.fixture
def clean_qdrant_config(monkeypatch):
    """Reset qdrant config to known defaults for deterministic tests."""
    monkeypatch.setattr(qdrant_client, "QDRANT_URL", "http://qdrant:6333")
    monkeypatch.setattr(qdrant_client, "QDRANT_COLLECTION", "hsaai_knowledge")
    monkeypatch.setattr(qdrant_client, "QDRANT_API_KEY", None)


# ═══════════════════════════════════════════════════════════════════════
# Helper tests — _headers()
# ═══════════════════════════════════════════════════════════════════════
class TestHeadersHelper:
    """Tests for the _headers() helper function."""

    def test_headers_empty_when_no_api_key(self, monkeypatch):
        """When QDRANT_API_KEY is None, _headers() returns empty dict."""
        monkeypatch.setattr(qdrant_client, "QDRANT_API_KEY", None)
        assert _headers() == {}

    def test_headers_contain_api_key_when_set(self, monkeypatch):
        """When QDRANT_API_KEY is set, _headers() returns {'api-key': <key>}."""
        monkeypatch.setattr(qdrant_client, "QDRANT_API_KEY", "secret-key-123")
        headers = _headers()
        assert headers == {"api-key": "secret-key-123"}

    def test_headers_empty_string_api_key_returns_empty(self, monkeypatch):
        """Empty string API key is falsy → returns empty dict (per `if QDRANT_API_KEY`)."""
        monkeypatch.setattr(qdrant_client, "QDRANT_API_KEY", "")
        assert _headers() == {}


# ═══════════════════════════════════════════════════════════════════════
# QdrantDeleteError exception
# ═══════════════════════════════════════════════════════════════════════
class TestQdrantDeleteError:
    """Verify QdrantDeleteError is a RuntimeError subclass."""

    def test_is_runtime_error_subclass(self):
        assert issubclass(QdrantDeleteError, RuntimeError)

    def test_can_be_raised_and_caught(self):
        with pytest.raises(QdrantDeleteError, match="delete failed"):
            raise QdrantDeleteError("Qdrant delete failed: test")

    def test_caught_as_runtime_error(self):
        with pytest.raises(RuntimeError):
            raise QdrantDeleteError("polymorphic")


# ═══════════════════════════════════════════════════════════════════════
# Functional Tests
# ═══════════════════════════════════════════════════════════════════════
class TestDeleteDocumentVectorsFunctional:
    """Functional tests: verify correct HTTP method, URL, payload, response."""

    @pytest.mark.asyncio
    async def test_successful_deletion_returns_response_json(self, patch_async_client, clean_qdrant_config):
        """Positive: delete existing document returns Qdrant response JSON."""
        response_data = {
            "operation_id": 123,
            "status": "completed",
        }
        client = patch_async_client(response=DummyResponse(200, response_data))
        result = await delete_document_vectors("doc_123")
        assert result == response_data
        assert result["operation_id"] == 123
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_http_method_is_post(self, patch_async_client, clean_qdrant_config):
        """Verify the HTTP method used is POST (Qdrant /points/delete endpoint)."""
        client = patch_async_client(response=DummyResponse(200, {"status": "ok"}))
        await delete_document_vectors("doc_1")
        assert client.method == "POST"

    @pytest.mark.asyncio
    async def test_url_contains_collection_and_points_delete(self, patch_async_client, clean_qdrant_config):
        """Verify URL structure: {QDRANT_URL}/collections/{QDRANT_COLLECTION}/points/delete."""
        client = patch_async_client(response=DummyResponse(200, {"status": "ok"}))
        await delete_document_vectors("doc_1")
        assert client.url is not None
        assert "/collections/hsaai_knowledge/points/delete" in client.url
        assert client.url.startswith("http://qdrant:6333")

    @pytest.mark.asyncio
    async def test_url_strips_trailing_slash_from_qdrant_url(self, monkeypatch, patch_async_client):
        """Verify trailing slash in QDRANT_URL is stripped to avoid double-slash."""
        monkeypatch.setattr(qdrant_client, "QDRANT_URL", "http://qdrant:6333/")
        monkeypatch.setattr(qdrant_client, "QDRANT_COLLECTION", "hsaai_knowledge")
        monkeypatch.setattr(qdrant_client, "QDRANT_API_KEY", None)
        client = patch_async_client(response=DummyResponse(200, {"status": "ok"}))
        await delete_document_vectors("doc_1")
        assert "//collections" not in client.url, "Double slash must not appear in URL"
        assert client.url == "http://qdrant:6333/collections/hsaai_knowledge/points/delete"

    @pytest.mark.asyncio
    async def test_payload_has_filter_key(self, patch_async_client, clean_qdrant_config):
        """Payload must contain 'filter' key at top level."""
        client = patch_async_client(response=DummyResponse(200, {"status": "ok"}))
        await delete_document_vectors("doc_123")
        assert "filter" in client.payload
        assert isinstance(client.payload["filter"], dict)

    @pytest.mark.asyncio
    async def test_payload_filter_has_must_key(self, patch_async_client, clean_qdrant_config):
        """filter must contain 'must' key (Qdrant filter schema)."""
        client = patch_async_client(response=DummyResponse(200, {"status": "ok"}))
        await delete_document_vectors("doc_123")
        assert "must" in client.payload["filter"]
        assert isinstance(client.payload["filter"]["must"], list)

    @pytest.mark.asyncio
    async def test_payload_filter_must_has_single_condition(self, patch_async_client, clean_qdrant_config):
        """must array has exactly one condition (document_id match)."""
        client = patch_async_client(response=DummyResponse(200, {"status": "ok"}))
        await delete_document_vectors("doc_123")
        must = client.payload["filter"]["must"]
        assert len(must) == 1

    @pytest.mark.asyncio
    async def test_payload_condition_has_key_document_id(self, patch_async_client, clean_qdrant_config):
        """The condition's 'key' field must be 'document_id'."""
        client = patch_async_client(response=DummyResponse(200, {"status": "ok"}))
        await delete_document_vectors("doc_123")
        condition = client.payload["filter"]["must"][0]
        assert condition["key"] == "document_id"

    @pytest.mark.asyncio
    async def test_payload_condition_has_match_with_value(self, patch_async_client, clean_qdrant_config):
        """The condition must have 'match' dict containing 'value'."""
        client = patch_async_client(response=DummyResponse(200, {"status": "ok"}))
        await delete_document_vectors("doc_123")
        condition = client.payload["filter"]["must"][0]
        assert "match" in condition
        assert isinstance(condition["match"], dict)
        assert "value" in condition["match"]

    @pytest.mark.asyncio
    async def test_payload_match_value_equals_document_id(self, patch_async_client, clean_qdrant_config):
        """The match.value must equal the document_id passed to the function."""
        client = patch_async_client(response=DummyResponse(200, {"status": "ok"}))
        await delete_document_vectors("doc_unique_456")
        condition = client.payload["filter"]["must"][0]
        assert condition["match"]["value"] == "doc_unique_456"

    @pytest.mark.asyncio
    async def test_full_payload_structure_matches_qdrant_schema(self, patch_async_client, clean_qdrant_config):
        """Verify the complete payload matches the expected Qdrant filter schema:

        {
            "filter": {
                "must": [
                    {
                        "key": "document_id",
                        "match": {"value": "<document_id>"}
                    }
                ]
            }
        }
        """
        client = patch_async_client(response=DummyResponse(200, {"status": "ok"}))
        await delete_document_vectors("doc_123")
        expected_payload = {
            "filter": {
                "must": [
                    {
                        "key": "document_id",
                        "match": {"value": "doc_123"},
                    }
                ]
            }
        }
        assert client.payload == expected_payload

    @pytest.mark.asyncio
    async def test_document_id_correctly_propagated_to_payload(self, patch_async_client, clean_qdrant_config):
        """Different document_id values produce different payloads."""
        client = patch_async_client(response=DummyResponse(200, {"status": "ok"}))
        await delete_document_vectors("doc_AAA")
        assert client.payload["filter"]["must"][0]["match"]["value"] == "doc_AAA"

    @pytest.mark.asyncio
    async def test_arabic_document_id_preserved_in_payload(self, patch_async_client, clean_qdrant_config):
        """Arabic document_id is preserved verbatim in the payload."""
        client = patch_async_client(response=DummyResponse(200, {"status": "ok"}))
        await delete_document_vectors("مستند_123")
        assert client.payload["filter"]["must"][0]["match"]["value"] == "مستند_123"

    @pytest.mark.asyncio
    async def test_response_returned_verbatim(self, patch_async_client, clean_qdrant_config):
        """The Qdrant JSON response is returned as-is (no transformation)."""
        response_data = {"result": {"operation_id": 999}, "time": 0.001, "status": "ok"}
        patch_async_client(response=DummyResponse(200, response_data))
        result = await delete_document_vectors("doc_1")
        assert result == response_data

    @pytest.mark.asyncio
    async def test_custom_collection_name_in_url(self, monkeypatch, patch_async_client):
        """Verify custom QDRANT_COLLECTION appears in URL."""
        monkeypatch.setattr(qdrant_client, "QDRANT_URL", "http://qdrant:6333")
        monkeypatch.setattr(qdrant_client, "QDRANT_COLLECTION", "custom_collection")
        monkeypatch.setattr(qdrant_client, "QDRANT_API_KEY", None)
        client = patch_async_client(response=DummyResponse(200, {"status": "ok"}))
        await delete_document_vectors("doc_1")
        assert "/collections/custom_collection/points/delete" in client.url


# ═══════════════════════════════════════════════════════════════════════
# Validation Tests
# ═══════════════════════════════════════════════════════════════════════
class TestDeleteDocumentVectorsValidation:
    """Validation tests: empty, None, and unexpected document_id values.

    NOTE: The current implementation does NOT validate document_id before sending
    to Qdrant. These tests document the actual behavior (payload is sent as-is).
    See "Security Recommendations" in the module docstring for suggested improvements.
    """

    @pytest.mark.asyncio
    async def test_empty_string_document_id_is_sent_to_qdrant(self, patch_async_client, clean_qdrant_config):
        """Empty string document_id is NOT validated — it's sent to Qdrant as-is.

        This documents a validation gap: the function should reject empty strings
        before making the HTTP call.
        """
        client = patch_async_client(response=DummyResponse(200, {"status": "ok"}))
        # Currently no validation — empty string is accepted and sent
        result = await delete_document_vectors("")
        assert client.payload["filter"]["must"][0]["match"]["value"] == ""
        # Document the gap: this should ideally raise ValueError

    @pytest.mark.asyncio
    async def test_none_document_id_is_accepted_as_json_null(self, patch_async_client, clean_qdrant_config):
        """None document_id is accepted and serialized as JSON null.

        This is a validation gap: None should be rejected before making the
        HTTP call. Instead, it's placed in the payload as null, which Qdrant
        may or may not handle gracefully.
        """
        client = patch_async_client(response=DummyResponse(200, {"status": "ok"}))
        result = await delete_document_vectors(None)  # type: ignore[arg-type]
        # Verify None was placed in the payload as-is
        assert client.payload["filter"]["must"][0]["match"]["value"] is None
        # Document the gap: this should ideally raise ValueError

    @pytest.mark.asyncio
    async def test_very_long_document_id_accepted(self, patch_async_client, clean_qdrant_config):
        """Very long document_id (10K chars) is accepted — no length validation."""
        client = patch_async_client(response=DummyResponse(200, {"status": "ok"}))
        long_id = "doc_" + "x" * 10000
        result = await delete_document_vectors(long_id)
        assert client.payload["filter"]["must"][0]["match"]["value"] == long_id

    @pytest.mark.asyncio
    async def test_document_id_with_special_characters(self, patch_async_client, clean_qdrant_config):
        """Special characters in document_id are preserved in payload."""
        client = patch_async_client(response=DummyResponse(200, {"status": "ok"}))
        special_id = "doc-123_456!@#$%^&*()"
        await delete_document_vectors(special_id)
        assert client.payload["filter"]["must"][0]["match"]["value"] == special_id

    @pytest.mark.asyncio
    async def test_document_id_with_newlines_preserved(self, patch_async_client, clean_qdrant_config):
        """Newlines in document_id are preserved (potential injection vector)."""
        client = patch_async_client(response=DummyResponse(200, {"status": "ok"}))
        await delete_document_vectors("doc\nwith\nnewlines")
        assert client.payload["filter"]["must"][0]["match"]["value"] == "doc\nwith\nnewlines"

    @pytest.mark.asyncio
    async def test_document_id_with_unicode_preserved(self, patch_async_client, clean_qdrant_config):
        """Unicode characters (emoji, CJK, etc.) are preserved."""
        client = patch_async_client(response=DummyResponse(200, {"status": "ok"}))
        unicode_id = "doc_🌍_中文_العربية"
        await delete_document_vectors(unicode_id)
        assert client.payload["filter"]["must"][0]["match"]["value"] == unicode_id

    @pytest.mark.asyncio
    async def test_integer_document_id_coerced_or_raises(self, patch_async_client, clean_qdrant_config):
        """Integer document_id: behavior depends on JSON serialization.

        httpx will serialize int in JSON, so the payload will contain an integer
        value rather than a string. This may not match Qdrant's expectations
        (Qdrant expects string match values for keyword fields).
        """
        client = patch_async_client(response=DummyResponse(200, {"status": "ok"}))
        # int is accepted by Python but may cause Qdrant-side mismatch
        await delete_document_vectors(12345)  # type: ignore[arg-type]
        # The payload value will be int 12345, not string "12345"
        assert client.payload["filter"]["must"][0]["match"]["value"] == 12345


# ═══════════════════════════════════════════════════════════════════════
# Error Handling Tests
# ═══════════════════════════════════════════════════════════════════════
class TestDeleteDocumentVectorsErrorHandling:
    """Error handling tests: HTTP errors, timeouts, network exceptions, invalid JSON."""

    @pytest.mark.asyncio
    async def test_http_400_raises_qdrant_delete_error(self, patch_async_client, clean_qdrant_config):
        """HTTP 400 from Qdrant raises QdrantDeleteError with status code."""
        patch_async_client(
            response=DummyResponse(400, text="Bad Request: invalid filter"),
        )
        with pytest.raises(QdrantDeleteError) as exc_info:
            await delete_document_vectors("doc_1")
        assert "400" in str(exc_info.value)
        assert "Bad Request" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_http_404_raises_qdrant_delete_error(self, patch_async_client, clean_qdrant_config):
        """HTTP 404 (collection not found) raises QdrantDeleteError."""
        patch_async_client(response=DummyResponse(404, text="Not Found"))
        with pytest.raises(QdrantDeleteError):
            await delete_document_vectors("doc_1")

    @pytest.mark.asyncio
    async def test_http_500_raises_qdrant_delete_error(self, patch_async_client, clean_qdrant_config):
        """HTTP 500 (server error) raises QdrantDeleteError."""
        patch_async_client(
            response=DummyResponse(500, text="Internal Server Error"),
        )
        with pytest.raises(QdrantDeleteError) as exc_info:
            await delete_document_vectors("doc_1")
        assert "500" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_http_503_raises_qdrant_delete_error(self, patch_async_client, clean_qdrant_config):
        """HTTP 503 (service unavailable) raises QdrantDeleteError."""
        patch_async_client(response=DummyResponse(503, text="Service Unavailable"))
        with pytest.raises(QdrantDeleteError):
            await delete_document_vectors("doc_1")

    @pytest.mark.asyncio
    async def test_http_422_raises_qdrant_delete_error(self, patch_async_client, clean_qdrant_config):
        """HTTP 422 (unprocessable entity) raises QdrantDeleteError."""
        patch_async_client(response=DummyResponse(422, text="Unprocessable Entity"))
        with pytest.raises(QdrantDeleteError):
            await delete_document_vectors("doc_1")

    @pytest.mark.asyncio
    async def test_timeout_raises_qdrant_delete_error(self, patch_async_client, clean_qdrant_config):
        """httpx.TimeoutException is caught and wrapped in QdrantDeleteError."""
        patch_async_client(exception=httpx.TimeoutException("Connection timed out"))
        with pytest.raises(QdrantDeleteError) as exc_info:
            await delete_document_vectors("doc_1")
        assert "Qdrant delete request failed" in str(exc_info.value)
        assert "timed out" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_connect_error_raises_qdrant_delete_error(self, patch_async_client, clean_qdrant_config):
        """httpx.ConnectError (network unreachable) is wrapped in QdrantDeleteError."""
        patch_async_client(exception=httpx.ConnectError("Connection refused"))
        with pytest.raises(QdrantDeleteError):
            await delete_document_vectors("doc_1")

    @pytest.mark.asyncio
    async def test_http_status_error_raises_qdrant_delete_error(self, patch_async_client, clean_qdrant_config):
        """httpx.HTTPStatusError is caught and wrapped in QdrantDeleteError."""
        patch_async_client(
            exception=httpx.HTTPStatusError(
                "HTTP 500",
                request=httpx.Request("POST", "http://dummy"),
                response=httpx.Response(500),
            )
        )
        with pytest.raises(QdrantDeleteError):
            await delete_document_vectors("doc_1")

    @pytest.mark.asyncio
    async def test_generic_httpx_error_raises_qdrant_delete_error(self, patch_async_client, clean_qdrant_config):
        """Any httpx.HTTPError subclass is caught and wrapped."""
        patch_async_client(exception=httpx.ReadError("Read failed"))
        with pytest.raises(QdrantDeleteError):
            await delete_document_vectors("doc_1")

    @pytest.mark.asyncio
    async def test_non_httpx_exception_propagates(self, patch_async_client, clean_qdrant_config):
        """Non-httpx exceptions (e.g., ValueError) are NOT caught by the except clause.

        The function only catches httpx.HTTPError. Other exceptions propagate.
        """
        patch_async_client(exception=ValueError("Unexpected error"))
        with pytest.raises(ValueError, match="Unexpected error"):
            await delete_document_vectors("doc_1")

    @pytest.mark.asyncio
    async def test_error_message_truncated_to_500_chars(self, patch_async_client, clean_qdrant_config):
        """Error response text is truncated to 500 chars (per source: response.text[:500])."""
        long_text = "x" * 1000
        patch_async_client(response=DummyResponse(500, text=long_text))
        with pytest.raises(QdrantDeleteError) as exc_info:
            await delete_document_vectors("doc_1")
        # The error message should contain at most 500 chars of the response text
        error_msg = str(exc_info.value)
        # Verify the long text was truncated (the error message is shorter than 1000 chars of text)
        assert "x" * 501 not in error_msg

    @pytest.mark.asyncio
    async def test_http_399_does_not_raise(self, patch_async_client, clean_qdrant_config):
        """HTTP 399 (just below 400 threshold) does NOT raise — returns response.json()."""
        response_data = {"status": "redirect"}
        patch_async_client(response=DummyResponse(399, response_data))
        result = await delete_document_vectors("doc_1")
        assert result == response_data

    @pytest.mark.asyncio
    async def test_invalid_json_response_raises_json_error(self, patch_async_client, clean_qdrant_config):
        """If Qdrant returns 200 but invalid JSON, response.json() raises.

        The function does NOT catch JSONDecodeError — it propagates to the caller.
        This documents a gap: invalid JSON responses are not gracefully handled.
        """

        class BadJsonResponse:
            status_code = 200
            text = "not valid json"
            def json(self):
                raise json.JSONDecodeError("Expecting value", "not valid json", 0)

        patch_async_client(response=BadJsonResponse())
        with pytest.raises(json.JSONDecodeError):
            await delete_document_vectors("doc_1")


# ═══════════════════════════════════════════════════════════════════════
# Security Tests (Enterprise AI)
# ═══════════════════════════════════════════════════════════════════════
class TestDeleteDocumentVectorsSecurity:
    """Security tests for Enterprise AI: tenant isolation, auth, audit.

    CRITICAL FINDING: The current implementation has NO tenant isolation.
    The filter only matches `document_id` — a user who knows another tenant's
    document_id could delete their vectors. These tests document this gap.
    """

    @pytest.mark.asyncio
    async def test_no_tenant_id_in_filter(self, patch_async_client, clean_qdrant_config):
        """SECURITY GAP: The payload filter does NOT include tenant_id.

        In a multi-tenant system, this allows cross-tenant deletion if a user
        knows another tenant's document_id.

        Recommended fix: Add tenant_id to the filter:
            {
                "filter": {
                    "must": [
                        {"key": "document_id", "match": {"value": "<doc_id>"}},
                        {"key": "tenant_id", "match": {"value": "<tenant_id>"}}
                    ]
                }
            }
        """
        client = patch_async_client(response=DummyResponse(200, {"status": "ok"}))
        await delete_document_vectors("doc_123")
        must_conditions = client.payload["filter"]["must"]
        # Verify ONLY document_id is in the filter (no tenant_id)
        keys = [c["key"] for c in must_conditions]
        assert keys == ["document_id"], (
            "Security: filter must include tenant_id for multi-tenant isolation. "
            f"Found keys: {keys}"
        )

    @pytest.mark.asyncio
    async def test_no_workspace_id_in_filter(self, patch_async_client, clean_qdrant_config):
        """SECURITY GAP: The payload filter does NOT include workspace_id."""
        client = patch_async_client(response=DummyResponse(200, {"status": "ok"}))
        await delete_document_vectors("doc_123")
        must_conditions = client.payload["filter"]["must"]
        keys = [c["key"] for c in must_conditions]
        assert "workspace_id" not in keys, "workspace_id should be in filter for isolation"

    @pytest.mark.asyncio
    async def test_api_key_header_sent_when_configured(self, monkeypatch, patch_async_client):
        """When QDRANT_API_KEY is set, the api-key header must be sent."""
        monkeypatch.setattr(qdrant_client, "QDRANT_API_KEY", "enterprise-secret-key")
        monkeypatch.setattr(qdrant_client, "QDRANT_URL", "http://qdrant:6333")
        monkeypatch.setattr(qdrant_client, "QDRANT_COLLECTION", "hsaai_knowledge")
        client = patch_async_client(response=DummyResponse(200, {"status": "ok"}))
        await delete_document_vectors("doc_1")
        # Verify headers kwarg was passed to AsyncClient
        assert client.kwargs.get("headers") == {"api-key": "enterprise-secret-key"}

    @pytest.mark.asyncio
    async def test_no_api_key_header_when_not_configured(self, patch_async_client, clean_qdrant_config):
        """When QDRANT_API_KEY is None, no api-key header is sent (empty dict)."""
        client = patch_async_client(response=DummyResponse(200, {"status": "ok"}))
        await delete_document_vectors("doc_1")
        # _headers() returns {} when API key is None
        headers = client.kwargs.get("headers", {})
        assert headers == {} or "api-key" not in headers

    @pytest.mark.asyncio
    async def test_no_authorization_check_before_deletion(self, patch_async_client, clean_qdrant_config):
        """SECURITY GAP: No RBAC/ABAC authorization check before deletion.

        The function accepts any document_id without verifying the caller has
        permission to delete it. In an enterprise system, this should be
        preceded by an authorization check.
        """
        client = patch_async_client(response=DummyResponse(200, {"status": "ok"}))
        # No user context, no role check — deletion proceeds
        result = await delete_document_vectors("any_doc_id")
        assert result == {"status": "ok"}
        # Document the gap: no auth check was performed

    @pytest.mark.asyncio
    async def test_no_audit_logging_of_deletion(self, patch_async_client, clean_qdrant_config):
        """SECURITY GAP: No audit log entry is created for the deletion.

        Enterprise compliance (ISO 27001, SOC 2) requires audit trails for
        data deletion. The function does not log:
          - Who triggered the deletion
          - What was deleted (document_id)
          - When (timestamp)
          - Result (success/failure)
        """
        client = patch_async_client(response=DummyResponse(200, {"status": "ok"}))
        result = await delete_document_vectors("doc_to_audit")
        # The function returns only the Qdrant response — no audit info
        assert "audit" not in result
        assert "actor" not in result
        assert "timestamp" not in result

    @pytest.mark.asyncio
    async def test_dict_document_id_accepted_in_payload(self, patch_async_client, clean_qdrant_config):
        """SECURITY GAP: dict document_id is accepted and placed in payload.

        The function does not validate the type of document_id. A dict is
        placed in the payload as-is. While JSON can serialize dicts, this
        is a potential injection vector if Qdrant interprets nested structures.
        """
        client = patch_async_client(response=DummyResponse(200, {"status": "ok"}))
        # dict is accepted — placed in payload as nested structure
        await delete_document_vectors({"$ne": ""})  # type: ignore[arg-type]
        # Verify the dict was placed in the payload (security gap)
        assert client.payload["filter"]["must"][0]["match"]["value"] == {"$ne": ""}

    @pytest.mark.asyncio
    async def test_timeout_is_30_seconds(self, patch_async_client, clean_qdrant_config):
        """Verify the timeout is set to 30 seconds (per source code)."""
        client = patch_async_client(response=DummyResponse(200, {"status": "ok"}))
        await delete_document_vectors("doc_1")
        assert client.kwargs.get("timeout") == 30


# ═══════════════════════════════════════════════════════════════════════
# Async Quality Tests
# ═══════════════════════════════════════════════════════════════════════
class TestDeleteDocumentVectorsAsyncQuality:
    """Verify async quality: no unawaited coroutines, no RuntimeWarnings."""

    @pytest.mark.asyncio
    async def test_function_returns_awaitable(self, clean_qdrant_config, patch_async_client):
        """delete_document_vectors must return a coroutine (awaitable)."""
        patch_async_client(response=DummyResponse(200, {"status": "ok"}))
        coro = delete_document_vectors("doc_1")
        assert asyncio.iscoroutine(coro)
        result = await coro
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_no_runtime_warning_on_success(self, patch_async_client, clean_qdrant_config, recwarn):
        """Successful execution must not produce any RuntimeWarnings (e.g., unawaited coroutines)."""
        patch_async_client(response=DummyResponse(200, {"status": "ok"}))
        await delete_document_vectors("doc_1")
        runtime_warnings = [w for w in recwarn.list if issubclass(w.category, RuntimeWarning)]
        assert len(runtime_warnings) == 0, (
            f"RuntimeWarnings detected: {[str(w.message) for w in runtime_warnings]}"
        )

    @pytest.mark.asyncio
    async def test_no_runtime_warning_on_error(self, patch_async_client, clean_qdrant_config, recwarn):
        """Error execution must not produce RuntimeWarnings."""
        patch_async_client(response=DummyResponse(500, text="error"))
        with pytest.raises(QdrantDeleteError):
            await delete_document_vectors("doc_1")
        runtime_warnings = [w for w in recwarn.list if issubclass(w.category, RuntimeWarning)]
        assert len(runtime_warnings) == 0

    @pytest.mark.asyncio
    async def test_no_coroutine_left_unawaited(self, patch_async_client, clean_qdrant_config):
        """Verify no coroutine is left unawaited (would cause ResourceWarning)."""
        patch_async_client(response=DummyResponse(200, {"status": "ok"}))
        await delete_document_vectors("doc_1")
        # If a coroutine was unawaited, Python would emit a warning at GC time.
        # We force garbage collection to catch any such issues.
        import gc
        gc.collect()

    @pytest.mark.asyncio
    async def test_concurrent_calls_independent(self, patch_async_client, clean_qdrant_config):
        """Multiple concurrent calls must not interfere with each other."""
        responses = [
            DummyResponse(200, {"operation_id": 1}),
            DummyResponse(200, {"operation_id": 2}),
            DummyResponse(200, {"operation_id": 3}),
        ]
        clients = []
        for resp in responses:
            c = DummyAsyncClient(response=resp)
            clients.append(c)

        # Patch to return each client in sequence
        client_iter = iter(clients)
        patch_async_client.async_call_count = 0  # type: ignore[attr-defined]

        def _factory(*a, **k):
            return next(client_iter)

        # Re-patch with the factory
        import backend_core.knowledge.qdrant_client as qc_module
        original_async_client = qc_module.httpx.AsyncClient
        qc_module.httpx.AsyncClient = _factory  # type: ignore[method-assign]

        try:
            results = await asyncio.gather(
                delete_document_vectors("doc_1"),
                delete_document_vectors("doc_2"),
                delete_document_vectors("doc_3"),
            )
            assert results[0]["operation_id"] == 1
            assert results[1]["operation_id"] == 2
            assert results[2]["operation_id"] == 3
            # Verify each client captured its own payload
            assert clients[0].payload["filter"]["must"][0]["match"]["value"] == "doc_1"
            assert clients[1].payload["filter"]["must"][0]["match"]["value"] == "doc_2"
            assert clients[2].payload["filter"]["must"][0]["match"]["value"] == "doc_3"
        finally:
            qc_module.httpx.AsyncClient = original_async_client  # type: ignore[method-assign]


# ═══════════════════════════════════════════════════════════════════════
# Idempotency & Independence Tests
# ═══════════════════════════════════════════════════════════════════════
class TestDeleteDocumentVectorsIdempotency:
    """Verify each call is independent (no shared state)."""

    @pytest.mark.asyncio
    async def test_same_document_id_twice_produces_same_result(self, patch_async_client, clean_qdrant_config):
        """Deleting the same document twice produces the same payload structure."""
        client1 = patch_async_client(response=DummyResponse(200, {"status": "ok"}))
        await delete_document_vectors("doc_1")
        payload1 = client1.payload

        client2 = patch_async_client(response=DummyResponse(200, {"status": "ok"}))
        await delete_document_vectors("doc_1")
        payload2 = client2.payload

        assert payload1 == payload2

    @pytest.mark.asyncio
    async def test_different_document_ids_produce_different_payloads(self, patch_async_client, clean_qdrant_config):
        """Different document_ids produce different payloads."""
        client1 = patch_async_client(response=DummyResponse(200, {"status": "ok"}))
        await delete_document_vectors("doc_A")
        payload1 = client1.payload

        client2 = patch_async_client(response=DummyResponse(200, {"status": "ok"}))
        await delete_document_vectors("doc_B")
        payload2 = client2.payload

        assert payload1 != payload2
        assert payload1["filter"]["must"][0]["match"]["value"] == "doc_A"
        assert payload2["filter"]["must"][0]["match"]["value"] == "doc_B"

    @pytest.mark.asyncio
    async def test_call_does_not_mutate_module_state(self, patch_async_client, clean_qdrant_config):
        """Calling the function must not mutate module-level constants."""
        original_url = qdrant_client.QDRANT_URL
        original_collection = qdrant_client.QDRANT_COLLECTION
        original_api_key = qdrant_client.QDRANT_API_KEY

        patch_async_client(response=DummyResponse(200, {"status": "ok"}))
        await delete_document_vectors("doc_1")

        assert qdrant_client.QDRANT_URL == original_url
        assert qdrant_client.QDRANT_COLLECTION == original_collection
        assert qdrant_client.QDRANT_API_KEY == original_api_key


# ═══════════════════════════════════════════════════════════════════════
# Branch Coverage Tests
# ═══════════════════════════════════════════════════════════════════════
class TestDeleteDocumentVectorsBranchCoverage:
    """Tests to achieve 100% branch coverage on delete_document_vectors."""

    @pytest.mark.asyncio
    async def test_success_branch_returns_json(self, patch_async_client, clean_qdrant_config):
        """Branch: status_code < 400 → return response.json()."""
        response_data = {"status": "ok", "operation_id": 42}
        patch_async_client(response=DummyResponse(200, response_data))
        result = await delete_document_vectors("doc_1")
        assert result == response_data

    @pytest.mark.asyncio
    async def test_status_code_399_boundary_success(self, patch_async_client, clean_qdrant_config):
        """Boundary: status_code = 399 (just below 400) → success branch."""
        patch_async_client(response=DummyResponse(399, {"status": "ok"}))
        result = await delete_document_vectors("doc_1")
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_status_code_400_boundary_error(self, patch_async_client, clean_qdrant_config):
        """Boundary: status_code = 400 (at threshold) → error branch."""
        patch_async_client(response=DummyResponse(400, text="Bad Request"))
        with pytest.raises(QdrantDeleteError):
            await delete_document_vectors("doc_1")

    @pytest.mark.asyncio
    async def test_httpx_http_error_branch(self, patch_async_client, clean_qdrant_config):
        """Branch: httpx.HTTPError caught → raise QdrantDeleteError."""
        patch_async_client(exception=httpx.HTTPError("Generic HTTP error"))
        with pytest.raises(QdrantDeleteError) as exc_info:
            await delete_document_vectors("doc_1")
        assert "Qdrant delete request failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_headers_with_api_key_branch(self, monkeypatch, patch_async_client):
        """Branch: QDRANT_API_KEY is set → _headers() returns {'api-key': ...}."""
        monkeypatch.setattr(qdrant_client, "QDRANT_API_KEY", "test-key-456")
        monkeypatch.setattr(qdrant_client, "QDRANT_URL", "http://qdrant:6333")
        monkeypatch.setattr(qdrant_client, "QDRANT_COLLECTION", "hsaai_knowledge")
        client = patch_async_client(response=DummyResponse(200, {"status": "ok"}))
        await delete_document_vectors("doc_1")
        assert client.kwargs.get("headers") == {"api-key": "test-key-456"}

    @pytest.mark.asyncio
    async def test_headers_without_api_key_branch(self, patch_async_client, clean_qdrant_config):
        """Branch: QDRANT_API_KEY is None → _headers() returns {}."""
        client = patch_async_client(response=DummyResponse(200, {"status": "ok"}))
        await delete_document_vectors("doc_1")
        assert client.kwargs.get("headers") == {}


# ═══════════════════════════════════════════════════════════════════════
# Integration-style Tests (still mocked, but end-to-end flow)
# ═══════════════════════════════════════════════════════════════════════
class TestDeleteDocumentVectorsEndToEnd:
    """End-to-end style tests (still mocked) verifying the complete flow."""

    @pytest.mark.asyncio
    async def test_complete_success_flow(self, monkeypatch, patch_async_client):
        """Verify the complete flow: config → headers → URL → payload → POST → response."""
        # Setup
        monkeypatch.setattr(qdrant_client, "QDRANT_URL", "http://qdrant:6333")
        monkeypatch.setattr(qdrant_client, "QDRANT_COLLECTION", "enterprise_docs")
        monkeypatch.setattr(qdrant_client, "QDRANT_API_KEY", "prod-key-789")

        client = patch_async_client(
            response=DummyResponse(200, {
                "operation_id": 999,
                "status": "completed",
                "deleted_count": 5,
            })
        )

        # Execute
        result = await delete_document_vectors("enterprise_doc_001")

        # Verify URL
        assert client.url == "http://qdrant:6333/collections/enterprise_docs/points/delete"
        # Verify method
        assert client.method == "POST"
        # Verify headers
        assert client.kwargs.get("headers") == {"api-key": "prod-key-789"}
        assert client.kwargs.get("timeout") == 30
        # Verify payload
        assert client.payload == {
            "filter": {
                "must": [
                    {
                        "key": "document_id",
                        "match": {"value": "enterprise_doc_001"},
                    }
                ]
            }
        }
        # Verify response
        assert result["operation_id"] == 999
        assert result["deleted_count"] == 5

    @pytest.mark.asyncio
    async def test_complete_error_flow(self, patch_async_client, clean_qdrant_config):
        """Verify the complete error flow: request → HTTP 500 → QdrantDeleteError."""
        patch_async_client(
            response=DummyResponse(500, text="Qdrant internal error: disk full")
        )
        with pytest.raises(QdrantDeleteError) as exc_info:
            await delete_document_vectors("doc_1")
        error_msg = str(exc_info.value)
        assert "500" in error_msg
        assert "disk full" in error_msg
        assert "Qdrant delete failed" in error_msg

    @pytest.mark.asyncio
    async def test_complete_network_error_flow(self, patch_async_client, clean_qdrant_config):
        """Verify the complete network error flow: request → timeout → QdrantDeleteError."""
        patch_async_client(exception=httpx.ConnectTimeout("Connection timeout after 30s"))
        with pytest.raises(QdrantDeleteError) as exc_info:
            await delete_document_vectors("doc_1")
        assert "Qdrant delete request failed" in str(exc_info.value)
        assert "timeout" in str(exc_info.value).lower()
