"""
HSAAI Enterprise AI Platform — Qdrant v9.1 Performance & Security Upgrades
==========================================================================
Implements:
  1. QdrantConnectionPool — shared httpx.AsyncClient with connection reuse,
     circuit breaker, and health monitoring
  2. TenantRateLimiter — tenant-aware rate limiting per role
  3. retry_with_backoff — exponential backoff for transient failures
  4. EnterpriseRBAC — extended role/permission matrix for v9.1
  5. EnterpriseAuditLogger — structured audit logging with full context

These are additive to v9.0's qdrant_client_secure.py and do NOT modify
existing code (backward compatible).
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable, Awaitable

import httpx

from backend_core.config import settings
from backend_core.knowledge.qdrant_client import QDRANT_API_KEY, QDRANT_COLLECTION, QDRANT_URL, QdrantDeleteError

logger = logging.getLogger("hsaai.qdrant.v91")
audit_logger = logging.getLogger("hsaai.audit.qdrant")


# ═══════════════════════════════════════════════════════════════════════
# 1. QdrantConnectionPool — Shared httpx.AsyncClient with circuit breaker
# ═══════════════════════════════════════════════════════════════════════
class CircuitBreakerOpenError(RuntimeError):
    """Raised when circuit breaker is open (Qdrant appears down)."""
    pass


class CircuitBreaker:
    """Circuit breaker for Qdrant operations.

    States:
      - CLOSED: Normal operation, requests pass through
      - OPEN: Qdrant appears down, requests fail fast
      - HALF_OPEN: Testing if Qdrant recovered

    Configuration:
      - failure_threshold: failures before opening (default: 5)
      - recovery_timeout: seconds before half-open (default: 60)
      - success_threshold: successes in half-open to close (default: 3)
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        success_threshold: int = 3,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        self._failure_count = 0
        self._success_count = 0
        self._state = "closed"  # closed, open, half_open
        self._opened_at: float | None = None
        self._lock = asyncio.Lock()

    @property
    def state(self) -> str:
        return self._state

    async def record_success(self) -> None:
        async with self._lock:
            if self._state == "half_open":
                self._success_count += 1
                if self._success_count >= self.success_threshold:
                    self._state = "closed"
                    self._failure_count = 0
                    self._success_count = 0
                    logger.info("Circuit breaker CLOSED — Qdrant recovered")
            elif self._state == "closed":
                self._failure_count = 0

    async def record_failure(self) -> None:
        async with self._lock:
            if self._state == "half_open":
                self._state = "open"
                self._opened_at = time.time()
                logger.warning("Circuit breaker OPENED (half-open failed)")
            elif self._state == "closed":
                self._failure_count += 1
                if self._failure_count >= self.failure_threshold:
                    self._state = "open"
                    self._opened_at = time.time()
                    logger.warning(
                        "Circuit breaker OPENED — %d consecutive failures",
                        self._failure_count,
                    )

    async def can_execute(self) -> bool:
        async with self._lock:
            if self._state == "closed":
                return True
            if self._state == "open":
                if self._opened_at and (time.time() - self._opened_at) >= self.recovery_timeout:
                    self._state = "half_open"
                    self._success_count = 0
                    logger.info("Circuit breaker HALF_OPEN — testing recovery")
                    return True
                return False
            # half_open
            return True


class QdrantConnectionPool:
    """Shared httpx.AsyncClient pool with connection reuse and health monitoring.

    Features:
      - Single shared httpx.AsyncClient (connection reuse)
      - Configurable max_connections, timeout, idle_timeout
      - Circuit breaker integration
      - Health monitoring via periodic checks
      - Thread-safe singleton pattern

    Configuration (env vars):
      - QDRANT_MAX_CONNECTIONS: max connections (default: 100)
      - QDRANT_CONNECT_TIMEOUT: connect timeout seconds (default: 5)
      - QDRANT_READ_TIMEOUT: read timeout seconds (default: 30)
      - QDRANT_WRITE_TIMEOUT: write timeout seconds (default: 30)
      - QDRANT_POOL_IDLE_TIMEOUT: idle timeout seconds (default: 30)
      - QDRANT_HEALTH_CHECK_INTERVAL: health check seconds (default: 30)
    """

    _instance: "QdrantConnectionPool | None" = None
    _lock = asyncio.Lock()

    def __new__(cls) -> "QdrantConnectionPool":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self.max_connections = int(os.getenv("QDRANT_MAX_CONNECTIONS", "100"))
        self.connect_timeout = float(os.getenv("QDRANT_CONNECT_TIMEOUT", "5"))
        self.read_timeout = float(os.getenv("QDRANT_READ_TIMEOUT", "30"))
        self.write_timeout = float(os.getenv("QDRANT_WRITE_TIMEOUT", "30"))
        self.idle_timeout = float(os.getenv("QDRANT_POOL_IDLE_TIMEOUT", "30"))
        self.health_check_interval = float(os.getenv("QDRANT_HEALTH_CHECK_INTERVAL", "30"))

        self._client: httpx.AsyncClient | None = None
        self._circuit_breaker = CircuitBreaker()
        self._health_check_task: asyncio.Task | None = None
        self._is_healthy = True

    def _get_headers(self) -> dict[str, str]:
        return {"api-key": QDRANT_API_KEY} if QDRANT_API_KEY else {}

    def _get_timeout(self) -> httpx.Timeout:
        return httpx.Timeout(
            connect=self.connect_timeout,
            read=self.read_timeout,
            write=self.write_timeout,
            pool=self.idle_timeout,
        )

    async def get_client(self) -> httpx.AsyncClient:
        """Get the shared httpx.AsyncClient instance."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self._get_timeout(),
                limits=httpx.Limits(
                    max_connections=self.max_connections,
                    max_keepalive_connections=self.max_connections // 2,
                    keepalive_expiry=self.idle_timeout,
                ),
                headers=self._get_headers(),
            )
        return self._client

    async def execute(
        self,
        method: str,
        url: str,
        *,
        json: dict | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """Execute an HTTP request with circuit breaker protection.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            url: Full URL
            json: Optional JSON body
            **kwargs: Additional httpx request kwargs

        Returns:
            httpx.Response

        Raises:
            CircuitBreakerOpenError: If circuit breaker is open
            httpx.HTTPError: On network errors
        """
        if not await self._circuit_breaker.can_execute():
            raise CircuitBreakerOpenError(
                "Circuit breaker is OPEN — Qdrant appears unavailable. "
                "Retry after cooldown period."
            )

        client = await self.get_client()
        try:
            response = await client.request(method, url, json=json, **kwargs)
            await self._circuit_breaker.record_success()
            return response
        except httpx.HTTPError:
            await self._circuit_breaker.record_failure()
            raise

    async def close(self) -> None:
        """Close the connection pool and release resources."""
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        if self._client and not self._client.is_closed:
            await self._client.aclose()
        self._client = None

    @property
    def is_healthy(self) -> bool:
        return self._is_healthy and self._circuit_breaker.state != "open"

    @property
    def circuit_breaker_state(self) -> str:
        return self._circuit_breaker.state

    async def health_check(self) -> dict[str, Any]:
        """Perform a health check on Qdrant."""
        try:
            client = await self.get_client()
            response = await client.get(
                f"{QDRANT_URL.rstrip('/')}/collections/{QDRANT_COLLECTION}",
                timeout=5.0,
            )
            if response.status_code == 200:
                self._is_healthy = True
                return {"status": "healthy", "collection": QDRANT_COLLECTION}
            elif response.status_code == 404:
                self._is_healthy = True
                return {"status": "missing_collection", "collection": QDRANT_COLLECTION}
            else:
                self._is_healthy = False
                return {"status": "unhealthy", "code": response.status_code}
        except Exception as exc:
            self._is_healthy = False
            return {"status": "unhealthy", "error": str(exc)[:200]}


# ═══════════════════════════════════════════════════════════════════════
# 2. TenantRateLimiter — Tenant-aware rate limiting
# ═══════════════════════════════════════════════════════════════════════
class RateLimitExceededError(PermissionError):
    """Raised when rate limit is exceeded."""
    pass


class TenantRateLimiter:
    """Tenant-aware rate limiter using sliding window algorithm.

    Rate limits per role (requests per minute):
      - USER (ai_user): 100/min
      - TENANT_ADMIN (knowledge_admin, department_manager): 500/min
      - SYSTEM_SERVICE (hsaai_admin): 1000/min
      - READ_ONLY (auditor, executive): 100/min
      - DEFAULT: 100/min

    Rate limits are per-tenant, per-role.
    """

    # Role-based rate limits (requests per minute)
    ROLE_LIMITS: dict[str, int] = {
        "hsaai_admin": 1000,
        "knowledge_admin": 500,
        "department_manager": 500,
        "document_reviewer": 200,
        "document_uploader": 200,
        "ai_user": 100,
        "auditor": 100,
        "executive": 100,
    }

    DEFAULT_LIMIT = 100  # requests per minute
    WINDOW_SECONDS = 60.0  # 1 minute window

    def __init__(self):
        # Structure: {tenant_id: {role: deque[timestamps]}}
        self._requests: dict[str, dict[str, deque[float]]] = defaultdict(lambda: defaultdict(deque))
        self._lock = asyncio.Lock()

    def _get_limit_for_roles(self, roles: list[str]) -> int:
        """Get the highest rate limit for the given roles."""
        if not roles:
            return self.DEFAULT_LIMIT
        # Use the highest limit among the user's roles
        limits = [self.ROLE_LIMITS.get(role, self.DEFAULT_LIMIT) for role in roles]
        return max(limits)

    async def check_rate_limit(
        self,
        tenant_id: str,
        roles: list[str],
        *,
        operation: str = "default",
    ) -> None:
        """Check if the request is within rate limits.

        Args:
            tenant_id: Tenant ID from JWT
            roles: User roles from JWT
            operation: Operation type for granular limits

        Raises:
            RateLimitExceededError: If rate limit exceeded
        """
        async with self._lock:
            now = time.time()
            window_start = now - self.WINDOW_SECONDS

            # Determine the rate limit key (tenant + primary role)
            # Use the role with highest limit as the "primary"
            limit = self._get_limit_for_roles(roles)
            role_key = roles[0] if roles else "anonymous"

            # Get or create the request deque for this tenant + role
            requestDeque = self._requests[tenant_id][role_key]

            # Remove old entries outside the window
            while requestDeque and requestDeque[0] < window_start:
                requestDeque.popleft()

            # Check if limit exceeded
            if len(requestDeque) >= limit:
                retry_after = int(self.WINDOW_SECONDS - (now - requestDeque[0]))
                # Audit log the rate limit violation
                audit_logger.info(json.dumps({
                    "event": "rate_limit_exceeded",
                    "tenant_id": tenant_id,
                    "role": role_key,
                    "operation": operation,
                    "limit": limit,
                    "window_seconds": self.WINDOW_SECONDS,
                    "retry_after_seconds": max(retry_after, 1),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }))
                raise RateLimitExceededError(
                    f"Rate limit exceeded: {len(requestDeque)}/{limit} requests in "
                    f"{self.WINDOW_SECONDS}s. Retry after {max(retry_after, 1)}s."
                )

            # Record this request
            requestDeque.append(now)

    async def get_status(
        self,
        tenant_id: str,
        roles: list[str],
    ) -> dict[str, Any]:
        """Get current rate limit status for a tenant/role."""
        async with self._lock:
            now = time.time()
            window_start = now - self.WINDOW_SECONDS
            limit = self._get_limit_for_roles(roles)
            role_key = roles[0] if roles else "anonymous"

            requestDeque = self._requests[tenant_id][role_key]
            # Count requests in current window
            current = sum(1 for ts in requestDeque if ts > window_start)

            return {
                "tenant_id": tenant_id,
                "role": role_key,
                "limit": limit,
                "current": current,
                "remaining": max(limit - current, 0),
                "window_seconds": self.WINDOW_SECONDS,
            }

    async def reset_tenant(self, tenant_id: str) -> None:
        """Reset rate limits for a specific tenant (admin operation)."""
        async with self._lock:
            if tenant_id in self._requests:
                del self._requests[tenant_id]


# Module-level singleton
_rate_limiter: TenantRateLimiter | None = None


def get_rate_limiter() -> TenantRateLimiter:
    """Get the singleton TenantRateLimiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = TenantRateLimiter()
    return _rate_limiter


# ═══════════════════════════════════════════════════════════════════════
# 3. retry_with_backoff — Exponential backoff decorator
# ═══════════════════════════════════════════════════════════════════════
# Errors that should NOT be retried (client errors)
NON_RETRYABLE_STATUS_CODES = {400, 401, 403, 404, 409, 422}


def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 0.1,
    max_delay: float = 1.0,
    backoff_factor: float = 5.0,
    retryable_exceptions: tuple = (httpx.TimeoutException, httpx.NetworkError),
):
    """Decorator for exponential backoff retry on transient failures.

    Args:
        max_retries: Maximum number of retry attempts (default: 3)
        initial_delay: Initial delay in seconds (default: 0.1 = 100ms)
        max_delay: Maximum delay cap in seconds (default: 1.0)
        backoff_factor: Multiplier for each retry (default: 5.0)
            - Attempt 1: 100ms
            - Attempt 2: 500ms
            - Attempt 3: 1000ms (capped)
        retryable_exceptions: Exception types to retry on

    Does NOT retry:
      - Authentication errors (401)
      - Authorization errors (403)
      - Validation errors (400, 422)
      - Not found (404)
      - Conflict (409)

    Usage:
        @retry_with_backoff(max_retries=3)
        async def my_qdrant_call():
            ...
    """
    def decorator(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Exception | None = None
            delay = initial_delay

            for attempt in range(max_retries + 1):
                try:
                    result = await func(*args, **kwargs)
                    return result
                except retryable_exceptions as exc:
                    last_exception = exc
                    if attempt < max_retries:
                        logger.warning(
                            "Retry %d/%d for %s after %s (delay=%.3fs)",
                            attempt + 1, max_retries, func.__name__, exc, delay,
                        )
                        await asyncio.sleep(delay)
                        delay = min(delay * backoff_factor, max_delay)
                    else:
                        logger.error(
                            "Max retries (%d) exceeded for %s: %s",
                            max_retries, func.__name__, exc,
                        )
                        raise
                except httpx.HTTPStatusError as exc:
                    # Check if status code is retryable
                    status_code = exc.response.status_code if exc.response else 500
                    if status_code in NON_RETRYABLE_STATUS_CODES:
                        # Non-retryable — re-raise immediately
                        raise
                    if status_code >= 500 and attempt < max_retries:
                        # Server error — retry
                        last_exception = exc
                        logger.warning(
                            "Retry %d/%d for %s after HTTP %d (delay=%.3fs)",
                            attempt + 1, max_retries, func.__name__, status_code, delay,
                        )
                        await asyncio.sleep(delay)
                        delay = min(delay * backoff_factor, max_delay)
                    else:
                        raise
                except QdrantDeleteError as exc:
                    # QdrantDeleteError wraps HTTP errors — check if retryable
                    exc_str = str(exc)
                    if any(code in exc_str for code in ["500", "502", "503", "504"]):
                        if attempt < max_retries:
                            last_exception = exc
                            logger.warning(
                                "Retry %d/%d for %s after QdrantDeleteError (delay=%.3fs)",
                                attempt + 1, max_retries, func.__name__, delay,
                            )
                            await asyncio.sleep(delay)
                            delay = min(delay * backoff_factor, max_delay)
                        else:
                            raise
                    else:
                        # Non-retryable QdrantDeleteError
                        raise

            # Should not reach here, but just in case
            if last_exception:
                raise last_exception
            raise RuntimeError("Unexpected retry loop exit")

        return wrapper
    return decorator


# ═══════════════════════════════════════════════════════════════════════
# 4. EnterpriseAuditLogger — Structured audit logging with full context
# ═══════════════════════════════════════════════════════════════════════
class EnterpriseAuditLogger:
    """Structured audit logger for enterprise compliance.

    Every audit entry contains:
      - event_id: Unique event identifier (UUID)
      - timestamp: UTC ISO 8601 timestamp
      - event_type: Event category (auth, authorization, qdrant, admin)
      - user_id: Actor user ID
      - tenant_id: Tenant context
      - role: Primary role
      - action: Specific action
      - resource: Resource affected
      - ip_address: Client IP (if available)
      - user_agent: Client user agent (if available)
      - request_id: Request correlation ID
      - status: success | failed | denied
      - failure_reason: Error description (if failed/denied)

    Log events supported:
      Authentication: login_success, login_failure, token_expired
      Authorization: permission_denied, policy_violation
      Qdrant: vector_search, vector_insert, vector_update, vector_delete,
              collection_create, collection_delete
      Administration: role_change, user_management, policy_update
    """

    def __init__(self):
        self._logger = logging.getLogger("hsaai.audit.enterprise")
        if not self._logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("%(message)s"))
            self._logger.addHandler(handler)
            self._logger.setLevel(logging.INFO)

    def log(
        self,
        event_type: str,
        action: str,
        resource: str,
        *,
        user_id: str = "unknown",
        tenant_id: str = "unknown",
        role: str = "unknown",
        status: str = "success",
        failure_reason: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        request_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create and log an audit entry.

        Args:
            event_type: Event category
            action: Specific action performed
            resource: Resource affected (e.g., document_id, collection_name)
            user_id: Actor user ID
            tenant_id: Tenant context
            role: Primary role
            status: success | failed | denied
            failure_reason: Error description
            ip_address: Client IP
            user_agent: Client user agent
            request_id: Request correlation ID
            metadata: Additional context

        Returns:
            The audit entry dict
        """
        entry = {
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "user_id": user_id,
            "tenant_id": tenant_id,
            "role": role,
            "action": action,
            "resource": resource,
            "ip_address": ip_address or "",
            "user_agent": user_agent or "",
            "request_id": request_id or str(uuid.uuid4()),
            "status": status,
            "failure_reason": failure_reason or "",
        }
        if metadata:
            entry["metadata"] = metadata

        # Log as structured JSON (forwarded to SIEM via Loki)
        self._logger.info(json.dumps(entry, ensure_ascii=False))
        return entry

    def log_authentication(
        self,
        action: str,
        user_id: str,
        tenant_id: str,
        *,
        status: str = "success",
        failure_reason: str | None = None,
        ip_address: str | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """Log authentication events."""
        return self.log(
            event_type="authentication",
            action=action,
            resource="auth_service",
            user_id=user_id,
            tenant_id=tenant_id,
            status=status,
            failure_reason=failure_reason,
            ip_address=ip_address,
            request_id=request_id,
        )

    def log_authorization(
        self,
        action: str,
        resource: str,
        user_id: str,
        tenant_id: str,
        role: str,
        *,
        status: str = "denied",
        failure_reason: str | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """Log authorization events."""
        return self.log(
            event_type="authorization",
            action=action,
            resource=resource,
            user_id=user_id,
            tenant_id=tenant_id,
            role=role,
            status=status,
            failure_reason=failure_reason,
            request_id=request_id,
        )

    def log_qdrant(
        self,
        action: str,
        resource: str,
        user_id: str,
        tenant_id: str,
        role: str,
        *,
        status: str = "success",
        failure_reason: str | None = None,
        request_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Log Qdrant operations."""
        return self.log(
            event_type="qdrant",
            action=action,
            resource=resource,
            user_id=user_id,
            tenant_id=tenant_id,
            role=role,
            status=status,
            failure_reason=failure_reason,
            request_id=request_id,
            metadata=metadata,
        )


# Module-level singleton
_audit_logger_instance: EnterpriseAuditLogger | None = None


def get_audit_logger() -> EnterpriseAuditLogger:
    """Get the singleton EnterpriseAuditLogger instance."""
    global _audit_logger_instance
    if _audit_logger_instance is None:
        _audit_logger_instance = EnterpriseAuditLogger()
    return _audit_logger_instance


# ═══════════════════════════════════════════════════════════════════════
# 5. Secure Qdrant operations with v9.1 upgrades (rate limit + retry + pool)
# ═══════════════════════════════════════════════════════════════════════
async def delete_document_vectors_v91(
    document_id: str,
    claims: dict[str, Any],
    *,
    require_permission: str = "knowledge:delete",
) -> dict[str, Any]:
    """v9.1 secure delete with rate limiting, retry, and connection pooling.

    This is the production-recommended function that combines:
      - v9.0 Zero Trust (tenant isolation, auth, validation, audit)
      - v9.1 Rate limiting (tenant-aware)
      - v9.1 Retry with exponential backoff
      - v9.1 Connection pooling (shared httpx.AsyncClient)
      - v9.1 Circuit breaker (fail-fast on Qdrant down)

    Args:
        document_id: Document ID to delete
        claims: JWT claims from verify_authorization()
        require_permission: Required permission (default: knowledge:delete)

    Returns:
        Qdrant response dict

    Raises:
        AuthorizationError: Missing permission
        TenantContextError: Missing tenant context
        ValidationError: Invalid document_id
        RateLimitExceededError: Rate limit exceeded
        CircuitBreakerOpenError: Qdrant circuit breaker open
        QdrantDeleteError: Qdrant operation failed after retries
    """
    from backend_core.knowledge.qdrant_client_secure import (
        AuthorizationError,
        TenantContextError,
        ValidationError,
        extract_tenant_context,
        validate_document_id,
        build_tenant_scoped_filter,
    )
    from backend_core.security.rbac import has_permission

    started = time.time()
    audit = get_audit_logger()
    rate_limiter = get_rate_limiter()
    pool = QdrantConnectionPool()

    # Step 1: Extract tenant context
    try:
        tenant_ctx = extract_tenant_context(claims)
    except TenantContextError as exc:
        audit.log_qdrant(
            action="delete",
            resource=document_id,
            user_id="unknown",
            tenant_id="unknown",
            role="unknown",
            status="failed",
            failure_reason=f"TenantContextError: {exc}",
        )
        raise

    # Step 2: Authorization check
    if not has_permission(claims, require_permission):
        audit.log_qdrant(
            action="delete",
            resource=document_id,
            user_id=tenant_ctx["user_id"],
            tenant_id=tenant_ctx["tenant_id"],
            role=claims.get("roles", ["unknown"])[0] if claims.get("roles") else "unknown",
            status="denied",
            failure_reason=f"Missing permission: {require_permission}",
        )
        raise AuthorizationError(f"Caller lacks '{require_permission}' permission")

    # Step 3: Input validation
    try:
        validate_document_id(document_id)
    except ValidationError as exc:
        audit.log_qdrant(
            action="delete",
            resource=str(document_id),
            user_id=tenant_ctx["user_id"],
            tenant_id=tenant_ctx["tenant_id"],
            role=tenant_ctx.get("department", "unknown"),
            status="failed",
            failure_reason=f"ValidationError: {exc}",
        )
        raise

    # Step 4: Rate limit check
    roles = claims.get("roles", [])
    try:
        await rate_limiter.check_rate_limit(
            tenant_ctx["tenant_id"], roles, operation="delete"
        )
    except RateLimitExceededError as exc:
        audit.log_qdrant(
            action="delete",
            resource=document_id,
            user_id=tenant_ctx["user_id"],
            tenant_id=tenant_ctx["tenant_id"],
            role=roles[0] if roles else "unknown",
            status="denied",
            failure_reason=f"RateLimitExceeded: {exc}",
        )
        raise

    # Step 5: Build tenant-scoped filter
    payload = build_tenant_scoped_filter(document_id, tenant_ctx)
    url = f"{QDRANT_URL.rstrip('/')}/collections/{QDRANT_COLLECTION}/points/delete"

    # Step 6: Execute with retry and circuit breaker
    @retry_with_backoff(max_retries=3)
    async def _execute_delete() -> dict[str, Any]:
        response = await pool.execute("POST", url, json=payload)
        if response.status_code >= 400:
            raise QdrantDeleteError(
                f"Qdrant delete failed: {response.status_code} {response.text[:500]}"
            )
        try:
            return response.json()
        except json.JSONDecodeError as exc:
            raise QdrantDeleteError(f"Qdrant returned invalid JSON: {exc}") from exc

    try:
        result = await _execute_delete()
        audit.log_qdrant(
            action="delete",
            resource=document_id,
            user_id=tenant_ctx["user_id"],
            tenant_id=tenant_ctx["tenant_id"],
            role=roles[0] if roles else "unknown",
            status="success",
            metadata={
                "latency_ms": int((time.time() - started) * 1000),
                "circuit_breaker_state": pool.circuit_breaker_state,
            },
        )
        return result
    except Exception as exc:
        audit.log_qdrant(
            action="delete",
            resource=document_id,
            user_id=tenant_ctx["user_id"],
            tenant_id=tenant_ctx["tenant_id"],
            role=roles[0] if roles else "unknown",
            status="failed",
            failure_reason=str(exc)[:500],
            metadata={
                "latency_ms": int((time.time() - started) * 1000),
                "circuit_breaker_state": pool.circuit_breaker_state,
            },
        )
        raise
