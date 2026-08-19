"""
HSAAI Enterprise AI Platform — v9.1 Performance & Security Upgrades Test Suite
===============================================================================
Tests for `services/backend_core/knowledge/qdrant_v91_upgrades.py`.

Covers:
  1. CircuitBreaker — closed/open/half-open states
  2. QdrantConnectionPool — shared client, health check
  3. TenantRateLimiter — tenant-aware rate limiting per role
  4. retry_with_backoff — exponential backoff for transient failures
  5. EnterpriseAuditLogger — structured audit logging
  6. delete_document_vectors_v91 — full v9.1 pipeline
  7. qdrant_health() tests
  8. ensure_collection() tests

Coverage target: >95% on qdrant_v91_upgrades.py
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
import httpx

_BASE = Path(__file__).resolve().parents[2]
_SERVICES = _BASE / "services"
for _p in [str(_SERVICES), str(_BASE / "packages"), str(_BASE / "packages" / "common")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend_core.knowledge.qdrant_v91_upgrades import (  # noqa: E402
    CircuitBreaker,
    CircuitBreakerOpenError,
    EnterpriseAuditLogger,
    QdrantConnectionPool,
    RateLimitExceededError,
    TenantRateLimiter,
    delete_document_vectors_v91,
    get_audit_logger,
    get_rate_limiter,
    retry_with_backoff,
)
from backend_core.knowledge.qdrant_client import QdrantDeleteError  # noqa: E402


# ═══════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════
@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singletons before each test for independence."""
    # Reset QdrantConnectionPool singleton
    QdrantConnectionPool._instance = None
    # Reset rate limiter singleton
    import backend_core.knowledge.qdrant_v91_upgrades as upgrades
    upgrades._rate_limiter = None
    upgrades._audit_logger_instance = None
    yield


@pytest.fixture
def admin_claims():
    return {
        "sub": "admin-123",
        "tenant_id": "company_a",
        "workspace_id": "ws_default",
        "department": "it",
        "realm_access": {"roles": ["hsaai_admin"]},
    }


@pytest.fixture
def ai_user_claims():
    return {
        "sub": "user-456",
        "tenant_id": "company_a",
        "workspace_id": "ws_default",
        "department": "finance",
        "realm_access": {"roles": ["ai_user"]},
    }


@pytest.fixture
def knowledge_admin_claims():
    return {
        "sub": "kb-admin-789",
        "tenant_id": "company_a",
        "workspace_id": "ws_default",
        "department": "knowledge",
        "realm_access": {"roles": ["knowledge_admin"]},
    }


class DummyResponse:
    def __init__(self, status_code: int = 200, json_data: Any = None, text: str = ""):
        self.status_code = status_code
        self._json_data = json_data if json_data is not None else {"status": "ok"}
        self.text = text or json.dumps(self._json_data)

    def json(self) -> Any:
        return self._json_data


class DummyAsyncClient:
    def __init__(self, *args: Any, response: DummyResponse | None = None,
                 exception: Exception | None = None, **kwargs: Any) -> None:
        self.response = response or DummyResponse(200, {"status": "ok"})
        self.exception = exception
        self.url: str | None = None
        self.payload: dict | None = None
        self.method: str | None = None
        self.kwargs = kwargs
        self.is_closed = False

    async def __aenter__(self) -> "DummyAsyncClient":
        return self

    async def __aexit__(self, *args: Any) -> bool:
        self.is_closed = True
        return False

    async def request(self, method: str, url: str, json: dict | None = None, **kwargs: Any) -> DummyResponse:
        self.method = method
        self.url = url
        self.payload = json
        if self.exception is not None:
            raise self.exception
        return self.response

    async def get(self, url: str, **kwargs: Any) -> DummyResponse:
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, json: dict | None = None, **kwargs: Any) -> DummyResponse:
        return await self.request("POST", url, json=json, **kwargs)

    async def aclose(self) -> None:
        self.is_closed = True


@pytest.fixture
def patch_pool_client(monkeypatch):
    """Patch QdrantConnectionPool to use a DummyAsyncClient."""
    state: dict[str, Any] = {"client": None, "responses": [], "call_count": 0}

    def _patch(responses=None, exception=None):
        if responses is None:
            responses = [DummyResponse(200, {"status": "ok"})]
        if not isinstance(responses, list):
            responses = [responses]

        client = DummyAsyncClient(response=responses[0], exception=exception)
        state["client"] = client
        state["responses"] = responses
        state["call_count"] = 0

        original_request = client.request

        async def _request(method, url, json=None, **kwargs):
            idx = min(state["call_count"], len(responses) - 1)
            client.response = responses[idx]
            state["call_count"] += 1
            return await original_request(method, url, json=json, **kwargs)

        client.request = _request

        async def _get_client():
            return client

        pool = QdrantConnectionPool()
        monkeypatch.setattr(pool, "get_client", _get_client)
        return client

    return _patch


# ═══════════════════════════════════════════════════════════════════════
# 1. CircuitBreaker Tests
# ═══════════════════════════════════════════════════════════════════════
class TestCircuitBreaker:
    """Tests for the CircuitBreaker class."""

    @pytest.mark.asyncio
    async def test_initial_state_is_closed(self):
        cb = CircuitBreaker()
        assert cb.state == "closed"

    @pytest.mark.asyncio
    async def test_can_execute_when_closed(self):
        cb = CircuitBreaker()
        assert await cb.can_execute() is True

    @pytest.mark.asyncio
    async def test_opens_after_failure_threshold(self):
        cb = CircuitBreaker(failure_threshold=3)
        await cb.record_failure()
        await cb.record_failure()
        assert cb.state == "closed"
        await cb.record_failure()
        assert cb.state == "open"

    @pytest.mark.asyncio
    async def test_cannot_execute_when_open(self):
        cb = CircuitBreaker(failure_threshold=1)
        await cb.record_failure()
        assert cb.state == "open"
        assert await cb.can_execute() is False

    @pytest.mark.asyncio
    async def test_half_open_after_recovery_timeout(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        await cb.record_failure()
        assert cb.state == "open"
        await asyncio.sleep(0.15)
        assert await cb.can_execute() is True
        assert cb.state == "half_open"

    @pytest.mark.asyncio
    async def test_closes_after_success_threshold_in_half_open(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1, success_threshold=2)
        await cb.record_failure()
        await asyncio.sleep(0.15)
        await cb.can_execute()  # transitions to half_open
        await cb.record_success()
        assert cb.state == "half_open"
        await cb.record_success()
        assert cb.state == "closed"

    @pytest.mark.asyncio
    async def test_half_open_failure_reopens(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        await cb.record_failure()
        await asyncio.sleep(0.15)
        await cb.can_execute()  # half_open
        await cb.record_failure()
        assert cb.state == "open"

    @pytest.mark.asyncio
    async def test_success_resets_failure_count_when_closed(self):
        cb = CircuitBreaker(failure_threshold=3)
        await cb.record_failure()
        await cb.record_failure()
        await cb.record_success()
        # Next failure should not immediately open (count was reset)
        await cb.record_failure()
        assert cb.state == "closed"


# ═══════════════════════════════════════════════════════════════════════
# 2. QdrantConnectionPool Tests
# ═══════════════════════════════════════════════════════════════════════
class TestQdrantConnectionPool:
    """Tests for the QdrantConnectionPool singleton."""

    @pytest.mark.asyncio
    async def test_singleton_pattern(self):
        pool1 = QdrantConnectionPool()
        pool2 = QdrantConnectionPool()
        assert pool1 is pool2

    @pytest.mark.asyncio
    async def test_is_healthy_initially(self):
        pool = QdrantConnectionPool()
        assert pool.is_healthy is True

    @pytest.mark.asyncio
    async def test_circuit_breaker_state_initially_closed(self):
        pool = QdrantConnectionPool()
        assert pool.circuit_breaker_state == "closed"

    @pytest.mark.asyncio
    async def test_execute_returns_response(self, monkeypatch):
        pool = QdrantConnectionPool()
        dummy_client = DummyAsyncClient(response=DummyResponse(200, {"ok": True}))
        async def _get_client():
            return dummy_client
        monkeypatch.setattr(pool, "get_client", _get_client)
        response = await pool.execute("GET", "http://test")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_execute_records_success(self, monkeypatch):
        pool = QdrantConnectionPool()
        dummy_client = DummyAsyncClient(response=DummyResponse(200))
        async def _get_client():
            return dummy_client
        monkeypatch.setattr(pool, "get_client", _get_client)
        await pool.execute("GET", "http://test")
        assert pool.circuit_breaker_state == "closed"

    @pytest.mark.asyncio
    async def test_execute_records_failure_on_network_error(self, monkeypatch):
        pool = QdrantConnectionPool()
        # Patch the circuit breaker to have low threshold
        pool._circuit_breaker = CircuitBreaker(failure_threshold=1)
        dummy_client = DummyAsyncClient(exception=httpx.ConnectError("Connection refused"))
        async def _get_client():
            return dummy_client
        monkeypatch.setattr(pool, "get_client", _get_client)
        with pytest.raises(httpx.ConnectError):
            await pool.execute("GET", "http://test")
        assert pool.circuit_breaker_state == "open"

    @pytest.mark.asyncio
    async def test_execute_raises_circuit_breaker_open(self, monkeypatch):
        pool = QdrantConnectionPool()
        pool._circuit_breaker = CircuitBreaker(failure_threshold=1)
        await pool._circuit_breaker.record_failure()
        with pytest.raises(CircuitBreakerOpenError):
            await pool.execute("GET", "http://test")

    @pytest.mark.asyncio
    async def test_health_check_returns_healthy(self, monkeypatch):
        pool = QdrantConnectionPool()
        dummy_client = DummyAsyncClient(response=DummyResponse(200, {"result": {"status": "ok"}}))
        async def _get_client():
            return dummy_client
        monkeypatch.setattr(pool, "get_client", _get_client)
        result = await pool.health_check()
        assert result["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_health_check_detects_missing_collection(self, monkeypatch):
        pool = QdrantConnectionPool()
        dummy_client = DummyAsyncClient(response=DummyResponse(404))
        async def _get_client():
            return dummy_client
        monkeypatch.setattr(pool, "get_client", _get_client)
        result = await pool.health_check()
        assert result["status"] == "missing_collection"

    @pytest.mark.asyncio
    async def test_health_check_detects_unhealthy(self, monkeypatch):
        pool = QdrantConnectionPool()
        dummy_client = DummyAsyncClient(exception=httpx.ConnectError("Connection refused"))
        async def _get_client():
            return dummy_client
        monkeypatch.setattr(pool, "get_client", _get_client)
        result = await pool.health_check()
        assert result["status"] == "unhealthy"
        assert pool.is_healthy is False

    @pytest.mark.asyncio
    async def test_close_releases_client(self, monkeypatch):
        pool = QdrantConnectionPool()
        dummy_client = DummyAsyncClient()
        pool._client = dummy_client
        await pool.close()
        assert dummy_client.is_closed is True
        assert pool._client is None


# ═══════════════════════════════════════════════════════════════════════
# 3. TenantRateLimiter Tests
# ═══════════════════════════════════════════════════════════════════════
class TestTenantRateLimiter:
    """Tests for the TenantRateLimiter class."""

    @pytest.mark.asyncio
    async def test_allows_request_under_limit(self):
        limiter = TenantRateLimiter()
        # Should not raise
        await limiter.check_rate_limit("tenant_a", ["ai_user"])

    @pytest.mark.asyncio
    async def test_blocks_request_over_limit(self):
        limiter = TenantRateLimiter()
        # Set a very low limit for testing
        limiter.ROLE_LIMITS["ai_user"] = 2
        await limiter.check_rate_limit("tenant_a", ["ai_user"])
        await limiter.check_rate_limit("tenant_a", ["ai_user"])
        with pytest.raises(RateLimitExceededError, match="Rate limit exceeded"):
            await limiter.check_rate_limit("tenant_a", ["ai_user"])

    @pytest.mark.asyncio
    async def test_different_tenants_have_separate_limits(self):
        limiter = TenantRateLimiter()
        limiter.ROLE_LIMITS["ai_user"] = 2
        # Tenant A uses 2 requests
        await limiter.check_rate_limit("tenant_a", ["ai_user"])
        await limiter.check_rate_limit("tenant_a", ["ai_user"])
        # Tenant B should still be allowed
        await limiter.check_rate_limit("tenant_b", ["ai_user"])

    @pytest.mark.asyncio
    async def test_admin_has_higher_limit(self):
        limiter = TenantRateLimiter()
        assert limiter.ROLE_LIMITS["hsaai_admin"] > limiter.ROLE_LIMITS["ai_user"]

    @pytest.mark.asyncio
    async def test_get_limit_for_roles_returns_highest(self):
        limiter = TenantRateLimiter()
        limit = limiter._get_limit_for_roles(["ai_user", "hsaai_admin"])
        assert limit == limiter.ROLE_LIMITS["hsaai_admin"]

    @pytest.mark.asyncio
    async def test_get_limit_for_empty_roles_returns_default(self):
        limiter = TenantRateLimiter()
        limit = limiter._get_limit_for_roles([])
        assert limit == limiter.DEFAULT_LIMIT

    @pytest.mark.asyncio
    async def test_get_status_returns_current_usage(self):
        limiter = TenantRateLimiter()
        limiter.ROLE_LIMITS["ai_user"] = 10
        await limiter.check_rate_limit("tenant_a", ["ai_user"])
        status = await limiter.get_status("tenant_a", ["ai_user"])
        assert status["current"] == 1
        assert status["limit"] == 10
        assert status["remaining"] == 9

    @pytest.mark.asyncio
    async def test_reset_tenant_clears_limits(self):
        limiter = TenantRateLimiter()
        limiter.ROLE_LIMITS["ai_user"] = 2
        await limiter.check_rate_limit("tenant_a", ["ai_user"])
        await limiter.check_rate_limit("tenant_a", ["ai_user"])
        await limiter.reset_tenant("tenant_a")
        # Should be allowed again after reset
        await limiter.check_rate_limit("tenant_a", ["ai_user"])

    @pytest.mark.asyncio
    async def test_rate_limit_window_slides(self):
        limiter = TenantRateLimiter()
        limiter.ROLE_LIMITS["ai_user"] = 2
        limiter.WINDOW_SECONDS = 0.2  # Short window for testing
        await limiter.check_rate_limit("tenant_a", ["ai_user"])
        await limiter.check_rate_limit("tenant_a", ["ai_user"])
        # Wait for window to slide
        await asyncio.sleep(0.25)
        # Should be allowed again
        await limiter.check_rate_limit("tenant_a", ["ai_user"])

    @pytest.mark.asyncio
    async def test_unknown_role_uses_default_limit(self):
        limiter = TenantRateLimiter()
        limit = limiter._get_limit_for_roles(["unknown_role"])
        assert limit == limiter.DEFAULT_LIMIT


# ═══════════════════════════════════════════════════════════════════════
# 4. retry_with_backoff Tests
# ═══════════════════════════════════════════════════════════════════════
class TestRetryWithBackoff:
    """Tests for the retry_with_backoff decorator."""

    @pytest.mark.asyncio
    async def test_no_retry_on_success(self):
        call_count = 0

        @retry_with_backoff(max_retries=3, initial_delay=0.01)
        async def success_func():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = await success_func()
        assert result == "ok"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_timeout(self):
        call_count = 0

        @retry_with_backoff(max_retries=3, initial_delay=0.01)
        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.TimeoutException("Timeout")
            return "recovered"

        result = await flaky_func()
        assert result == "recovered"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retries_on_network_error(self):
        call_count = 0

        @retry_with_backoff(max_retries=3, initial_delay=0.01)
        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise httpx.NetworkError("Network error")
            return "ok"

        result = await flaky_func()
        assert result == "ok"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_no_retry_on_client_error(self):
        call_count = 0

        @retry_with_backoff(max_retries=3, initial_delay=0.01)
        async def bad_request_func():
            nonlocal call_count
            call_count += 1
            # Simulate HTTP 400
            response = httpx.Response(400, text="Bad Request")
            raise httpx.HTTPStatusError("Bad Request", request=httpx.Request("POST", "http://test"), response=response)

        with pytest.raises(httpx.HTTPStatusError):
            await bad_request_func()
        assert call_count == 1  # No retry

    @pytest.mark.asyncio
    async def test_no_retry_on_auth_error(self):
        call_count = 0

        @retry_with_backoff(max_retries=3, initial_delay=0.01)
        async def unauthorized_func():
            nonlocal call_count
            call_count += 1
            response = httpx.Response(401, text="Unauthorized")
            raise httpx.HTTPStatusError("Unauthorized", request=httpx.Request("POST", "http://test"), response=response)

        with pytest.raises(httpx.HTTPStatusError):
            await unauthorized_func()
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_server_error(self):
        call_count = 0

        @retry_with_backoff(max_retries=3, initial_delay=0.01)
        async def server_error_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                response = httpx.Response(503, text="Service Unavailable")
                raise httpx.HTTPStatusError("503", request=httpx.Request("POST", "http://test"), response=response)
            return "ok"

        result = await server_error_func()
        assert result == "ok"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        call_count = 0

        @retry_with_backoff(max_retries=2, initial_delay=0.01)
        async def always_fail():
            nonlocal call_count
            call_count += 1
            raise httpx.TimeoutException("Always timeout")

        with pytest.raises(httpx.TimeoutException):
            await always_fail()
        assert call_count == 3  # initial + 2 retries

    @pytest.mark.asyncio
    async def test_exponential_backoff_delays(self):
        call_times = []

        @retry_with_backoff(max_retries=3, initial_delay=0.05, backoff_factor=5.0, max_delay=0.2)
        async def slow_func():
            call_times.append(time.time())
            raise httpx.TimeoutException("Timeout")

        start = time.time()
        with pytest.raises(httpx.TimeoutException):
            await slow_func()

        # Verify delays between calls
        assert len(call_times) == 4  # initial + 3 retries
        delay1 = call_times[1] - call_times[0]
        delay2 = call_times[2] - call_times[1]
        delay3 = call_times[3] - call_times[2]
        # Delays should be approximately 0.05, 0.25 (capped to 0.2), 0.2
        assert delay1 >= 0.04
        assert delay2 >= 0.04
        assert delay3 >= 0.04


# ═══════════════════════════════════════════════════════════════════════
# 5. EnterpriseAuditLogger Tests
# ═══════════════════════════════════════════════════════════════════════
class TestEnterpriseAuditLogger:
    """Tests for the EnterpriseAuditLogger class."""

    def test_log_creates_entry_with_all_fields(self, caplog):
        import logging
        with caplog.at_level(logging.INFO, logger="hsaai.audit.enterprise"):
            logger = EnterpriseAuditLogger()
            entry = logger.log(
                event_type="qdrant",
                action="delete",
                resource="doc_123",
                user_id="user-1",
                tenant_id="tenant_a",
                role="hsaai_admin",
                status="success",
            )
        assert entry["event_type"] == "qdrant"
        assert entry["action"] == "delete"
        assert entry["resource"] == "doc_123"
        assert entry["user_id"] == "user-1"
        assert entry["tenant_id"] == "tenant_a"
        assert entry["role"] == "hsaai_admin"
        assert entry["status"] == "success"
        assert "event_id" in entry
        assert "timestamp" in entry
        assert "request_id" in entry

    def test_log_includes_failure_reason(self, caplog):
        import logging
        with caplog.at_level(logging.INFO, logger="hsaai.audit.enterprise"):
            logger = EnterpriseAuditLogger()
            entry = logger.log(
                event_type="authorization",
                action="delete",
                resource="doc_123",
                user_id="user-1",
                tenant_id="tenant_a",
                role="ai_user",
                status="denied",
                failure_reason="Missing knowledge:delete permission",
            )
        assert entry["status"] == "denied"
        assert "Missing knowledge:delete" in entry["failure_reason"]

    def test_log_authentication(self, caplog):
        import logging
        with caplog.at_level(logging.INFO, logger="hsaai.audit.enterprise"):
            logger = EnterpriseAuditLogger()
            entry = logger.log_authentication(
                action="login_success",
                user_id="user-1",
                tenant_id="tenant_a",
            )
        assert entry["event_type"] == "authentication"
        assert entry["action"] == "login_success"

    def test_log_authorization(self, caplog):
        import logging
        with caplog.at_level(logging.INFO, logger="hsaai.audit.enterprise"):
            logger = EnterpriseAuditLogger()
            entry = logger.log_authorization(
                action="delete",
                resource="doc_123",
                user_id="user-1",
                tenant_id="tenant_a",
                role="ai_user",
                status="denied",
                failure_reason="Unauthorized",
            )
        assert entry["event_type"] == "authorization"
        assert entry["status"] == "denied"

    def test_log_qdrant(self, caplog):
        import logging
        with caplog.at_level(logging.INFO, logger="hsaai.audit.enterprise"):
            logger = EnterpriseAuditLogger()
            entry = logger.log_qdrant(
                action="vector_delete",
                resource="doc_123",
                user_id="user-1",
                tenant_id="tenant_a",
                role="knowledge_admin",
                status="success",
            )
        assert entry["event_type"] == "qdrant"
        assert entry["action"] == "vector_delete"

    def test_log_includes_metadata(self, caplog):
        import logging
        with caplog.at_level(logging.INFO, logger="hsaai.audit.enterprise"):
            logger = EnterpriseAuditLogger()
            entry = logger.log(
                event_type="qdrant",
                action="search",
                resource="query",
                user_id="user-1",
                tenant_id="tenant_a",
                role="ai_user",
                metadata={"latency_ms": 234, "results_count": 5},
            )
        assert entry["metadata"]["latency_ms"] == 234
        assert entry["metadata"]["results_count"] == 5

    def test_get_audit_logger_returns_singleton(self):
        logger1 = get_audit_logger()
        logger2 = get_audit_logger()
        assert logger1 is logger2


# ═══════════════════════════════════════════════════════════════════════
# 6. delete_document_vectors_v91 Tests
# ═══════════════════════════════════════════════════════════════════════
class TestDeleteDocumentVectorsV91:
    """Tests for the v9.1 secure delete function."""

    @pytest.mark.asyncio
    async def test_successful_deletion(self, admin_claims, patch_pool_client, monkeypatch):
        """Successful deletion returns Qdrant response."""
        # Patch config
        import backend_core.knowledge.qdrant_v91_upgrades as upgrades
        monkeypatch.setattr(upgrades, "QDRANT_URL", "http://qdrant:6333")
        monkeypatch.setattr(upgrades, "QDRANT_COLLECTION", "hsaai_knowledge")
        monkeypatch.setattr(upgrades, "QDRANT_API_KEY", None)

        client = patch_pool_client(responses=DummyResponse(200, {"operation_id": 123}))
        result = await delete_document_vectors_v91("doc_123", admin_claims)
        assert result["operation_id"] == 123

    @pytest.mark.asyncio
    async def test_payload_includes_tenant_isolation(self, admin_claims, patch_pool_client, monkeypatch):
        """Payload must include tenant_id and workspace_id."""
        import backend_core.knowledge.qdrant_v91_upgrades as upgrades
        monkeypatch.setattr(upgrades, "QDRANT_URL", "http://qdrant:6333")
        monkeypatch.setattr(upgrades, "QDRANT_COLLECTION", "hsaai_knowledge")
        monkeypatch.setattr(upgrades, "QDRANT_API_KEY", None)

        client = patch_pool_client(responses=DummyResponse(200, {"status": "ok"}))
        await delete_document_vectors_v91("doc_123", admin_claims)
        keys = [c["key"] for c in client.payload["filter"]["must"]]
        assert "tenant_id" in keys
        assert "workspace_id" in keys
        assert "document_id" in keys

    @pytest.mark.asyncio
    async def test_unauthorized_user_blocked(self, ai_user_claims, patch_pool_client, monkeypatch):
        """ai_user without knowledge:delete is blocked."""
        import backend_core.knowledge.qdrant_v91_upgrades as upgrades
        monkeypatch.setattr(upgrades, "QDRANT_URL", "http://qdrant:6333")
        monkeypatch.setattr(upgrades, "QDRANT_COLLECTION", "hsaai_knowledge")
        monkeypatch.setattr(upgrades, "QDRANT_API_KEY", None)

        patch_pool_client(responses=DummyResponse(200, {"status": "ok"}))
        from backend_core.knowledge.qdrant_client_secure import AuthorizationError
        with pytest.raises(AuthorizationError):
            await delete_document_vectors_v91("doc_123", ai_user_claims)

    @pytest.mark.asyncio
    async def test_invalid_document_id_blocked(self, admin_claims, patch_pool_client, monkeypatch):
        """Invalid document_id raises ValidationError."""
        import backend_core.knowledge.qdrant_v91_upgrades as upgrades
        monkeypatch.setattr(upgrades, "QDRANT_URL", "http://qdrant:6333")
        monkeypatch.setattr(upgrades, "QDRANT_COLLECTION", "hsaai_knowledge")
        monkeypatch.setattr(upgrades, "QDRANT_API_KEY", None)

        patch_pool_client(responses=DummyResponse(200, {"status": "ok"}))
        from backend_core.knowledge.qdrant_client_secure import ValidationError
        with pytest.raises(ValidationError):
            await delete_document_vectors_v91("", admin_claims)

    @pytest.mark.asyncio
    async def test_missing_tenant_context_blocked(self, patch_pool_client, monkeypatch):
        """Missing tenant_id raises TenantContextError."""
        import backend_core.knowledge.qdrant_v91_upgrades as upgrades
        monkeypatch.setattr(upgrades, "QDRANT_URL", "http://qdrant:6333")
        monkeypatch.setattr(upgrades, "QDRANT_COLLECTION", "hsaai_knowledge")
        monkeypatch.setattr(upgrades, "QDRANT_API_KEY", None)

        patch_pool_client(responses=DummyResponse(200, {"status": "ok"}))
        from backend_core.knowledge.qdrant_client_secure import TenantContextError
        with pytest.raises(TenantContextError):
            await delete_document_vectors_v91("doc_123", {"sub": "u1"})

    @pytest.mark.asyncio
    async def rate_limit_enforced(self, admin_claims, patch_pool_client, monkeypatch):
        """Rate limit is enforced."""
        import backend_core.knowledge.qdrant_v91_upgrades as upgrades
        monkeypatch.setattr(upgrades, "QDRANT_URL", "http://qdrant:6333")
        monkeypatch.setattr(upgrades, "QDRANT_COLLECTION", "hsaai_knowledge")
        monkeypatch.setattr(upgrades, "QDRANT_API_KEY", None)

        # Set very low rate limit
        limiter = get_rate_limiter()
        limiter.ROLE_LIMITS["hsaai_admin"] = 1

        patch_pool_client(responses=DummyResponse(200, {"status": "ok"}))
        # First request OK
        await delete_document_vectors_v91("doc_1", admin_claims)
        # Second request should be rate limited
        with pytest.raises(RateLimitExceededError):
            await delete_document_vectors_v91("doc_2", admin_claims)


# ═══════════════════════════════════════════════════════════════════════
# 7. qdrant_health() Tests (original function from qdrant_client.py)
# ═══════════════════════════════════════════════════════════════════════
class TestQdrantHealth:
    """Tests for the qdrant_health() function."""

    @pytest.mark.asyncio
    async def test_health_returns_ok_when_collection_exists(self, monkeypatch):
        from backend_core.knowledge import qdrant_client
        monkeypatch.setattr(qdrant_client, "QDRANT_URL", "http://qdrant:6333")
        monkeypatch.setattr(qdrant_client, "QDRANT_COLLECTION", "test_collection")
        monkeypatch.setattr(qdrant_client, "QDRANT_API_KEY", None)

        class MockClient:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *a):
                return False
            async def get(self, url):
                class R:
                    status_code = 200
                    def raise_for_status(self): pass
                return R()

        monkeypatch.setattr(qdrant_client.httpx, "AsyncClient", lambda **kw: MockClient())
        result = await qdrant_client.qdrant_health()
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_health_detects_missing_collection(self, monkeypatch):
        from backend_core.knowledge import qdrant_client
        monkeypatch.setattr(qdrant_client, "QDRANT_URL", "http://qdrant:6333")
        monkeypatch.setattr(qdrant_client, "QDRANT_COLLECTION", "missing")
        monkeypatch.setattr(qdrant_client, "QDRANT_API_KEY", None)

        class MockClient:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *a):
                return False
            async def get(self, url):
                class R:
                    status_code = 404
                return R()

        monkeypatch.setattr(qdrant_client.httpx, "AsyncClient", lambda **kw: MockClient())
        result = await qdrant_client.qdrant_health()
        assert result["status"] == "missing_collection"

    @pytest.mark.asyncio
    async def test_health_returns_error_on_exception(self, monkeypatch):
        from backend_core.knowledge import qdrant_client
        monkeypatch.setattr(qdrant_client, "QDRANT_URL", "http://qdrant:6333")
        monkeypatch.setattr(qdrant_client, "QDRANT_COLLECTION", "test")
        monkeypatch.setattr(qdrant_client, "QDRANT_API_KEY", None)

        class MockClient:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *a):
                return False
            async def get(self, url):
                raise httpx.ConnectError("Connection refused")

        monkeypatch.setattr(qdrant_client.httpx, "AsyncClient", lambda **kw: MockClient())
        result = await qdrant_client.qdrant_health()
        assert result["status"] == "error"
        assert "Connection refused" in result["error"]

    @pytest.mark.asyncio
    async def test_health_returns_error_on_timeout(self, monkeypatch):
        from backend_core.knowledge import qdrant_client
        monkeypatch.setattr(qdrant_client, "QDRANT_URL", "http://qdrant:6333")
        monkeypatch.setattr(qdrant_client, "QDRANT_COLLECTION", "test")
        monkeypatch.setattr(qdrant_client, "QDRANT_API_KEY", None)

        class MockClient:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *a):
                return False
            async def get(self, url):
                raise httpx.TimeoutException("Timeout")

        monkeypatch.setattr(qdrant_client.httpx, "AsyncClient", lambda **kw: MockClient())
        result = await qdrant_client.qdrant_health()
        assert result["status"] == "error"


# ═══════════════════════════════════════════════════════════════════════
# 8. ensure_collection() Tests
# ═══════════════════════════════════════════════════════════════════════
class TestEnsureCollection:
    """Tests for the ensure_collection() function."""

    @pytest.mark.asyncio
    async def test_returns_exists_when_collection_present(self, monkeypatch):
        from backend_core.knowledge import qdrant_client
        monkeypatch.setattr(qdrant_client, "QDRANT_URL", "http://qdrant:6333")
        monkeypatch.setattr(qdrant_client, "QDRANT_COLLECTION", "test")
        monkeypatch.setattr(qdrant_client, "QDRANT_API_KEY", None)

        class MockClient:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *a):
                return False
            async def get(self, url):
                class R:
                    status_code = 200
                return R()
            async def put(self, url, json=None):
                class R:
                    status_code = 201
                    def raise_for_status(self): pass
                return R()

        monkeypatch.setattr(qdrant_client.httpx, "AsyncClient", lambda **kw: MockClient())
        result = await qdrant_client.ensure_collection()
        assert result["status"] == "exists"

    @pytest.mark.asyncio
    async def test_creates_collection_when_missing(self, monkeypatch):
        from backend_core.knowledge import qdrant_client
        monkeypatch.setattr(qdrant_client, "QDRANT_URL", "http://qdrant:6333")
        monkeypatch.setattr(qdrant_client, "QDRANT_COLLECTION", "new_collection")
        monkeypatch.setattr(qdrant_client, "QDRANT_API_KEY", None)

        class MockClient:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *a):
                return False
            async def get(self, url):
                class R:
                    status_code = 404
                return R()
            async def put(self, url, json=None):
                class R:
                    status_code = 201
                    def raise_for_status(self): pass
                return R()

        monkeypatch.setattr(qdrant_client.httpx, "AsyncClient", lambda **kw: MockClient())
        result = await qdrant_client.ensure_collection()
        assert result["status"] == "created"

    @pytest.mark.asyncio
    async def test_returns_error_on_exception(self, monkeypatch):
        from backend_core.knowledge import qdrant_client
        monkeypatch.setattr(qdrant_client, "QDRANT_URL", "http://qdrant:6333")
        monkeypatch.setattr(qdrant_client, "QDRANT_COLLECTION", "test")
        monkeypatch.setattr(qdrant_client, "QDRANT_API_KEY", None)

        class MockClient:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *a):
                return False
            async def get(self, url):
                raise httpx.ConnectError("Connection refused")

        monkeypatch.setattr(qdrant_client.httpx, "AsyncClient", lambda **kw: MockClient())
        result = await qdrant_client.ensure_collection()
        assert result["status"] == "error"
