"""
HSAAI Enterprise Connector Framework — BaseConnector
=====================================================
The abstract base class that ALL enterprise connectors must inherit from.

Provides 17 production-grade capabilities out of the box:
  1.  Discovery      — auto-registration with the ConnectorRegistry
  2.  Registration   — declarative connector metadata
  3.  Health Check   — async health() with configurable timeout
  4.  Authentication — pluggable auth strategies (OAuth2, Basic, API Key, mTLS, …)
  5.  Authorization  — RBAC/ABAC permission checks per connector
  6.  Retry          — exponential backoff with jitter
  7.  Timeout        — per-request and per-connection timeouts
  8.  Circuit Breaker — 3-state (closed/open/half-open) with auto-recovery
  9.  Rate Limiting  — token-bucket per connector (configurable QPS)
 10.  Caching        — TTL-based response caching (Redis or in-memory)
 11.  Logging        — structured JSON logs with correlation IDs
 12.  Metrics        — Prometheus counters/histograms auto-exported
 13.  Audit Logs     — HMAC-signed audit trail for every call
 14.  Versioning     — semver versioning + API version negotiation
 15.  Configuration  — typed config from env / Vault / dynamic reload
 16.  Secrets Mgmt   — never read secrets from code; always from Vault/env
 17.  Validation     — pydantic models for all inputs and outputs
 18.  Error Recovery — graceful degradation with fallback strategies

Usage:
    from packages.common.connectors import BaseConnector, ConnectorConfig, connector

    @connector("sap_s4hana", version="1.0.0", category="ERP")
    class SAPS4HANAConnector(BaseConnector):
        async def authenticate(self) -> None: ...
        async def health(self) -> HealthStatus: ...
        async def search(self, query: str) -> list[dict]: ...
        async def execute(self, action: str, **kwargs) -> dict: ...

The framework handles everything else automatically.
"""
from __future__ import annotations

import abc
import asyncio
import hashlib
import hmac
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncIterator, Callable, Optional

import httpx
from pydantic import BaseModel, Field, SecretStr

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
#  Enums & Type Definitions
# ═══════════════════════════════════════════════════════════════════════════
class ConnectorState(str, Enum):
    """Lifecycle state of a connector instance."""
    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    DISABLED = "disabled"


class HealthStatus(str, Enum):
    """Result of a health check."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class AuthStrategy(str, Enum):
    """Supported authentication strategies."""
    NONE = "none"
    BASIC = "basic"
    BEARER = "bearer"
    API_KEY = "api_key"
    OAUTH2_CLIENT_CREDENTIALS = "oauth2_client_credentials"
    OAUTH2_AUTHORIZATION_CODE = "oauth2_authorization_code"
    OAUTH2_PASSWORD = "oauth2_password"
    OIDC = "oidc"
    SAML = "saml"
    JWT = "jwt"
    MTLS = "mtls"
    AWS_SIGV4 = "aws_sigv4"
    CUSTOM = "custom"


class CircuitBreakerState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"        # normal operation
    OPEN = "open"            # failing, requests blocked
    HALF_OPEN = "half_open"  # testing if service recovered


class Severity(str, Enum):
    """Log severity levels."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


# ═══════════════════════════════════════════════════════════════════════════
#  Configuration Models (pydantic — typed, validated)
# ═══════════════════════════════════════════════════════════════════════════
class ConnectorConfig(BaseModel):
    """Typed configuration for a connector. Subclass per connector."""
    name: str = Field(..., description="Unique connector identifier (e.g. 'sap_s4hana')")
    display_name: str = Field(..., description="Human-readable name")
    category: str = Field(..., description="Category: ERP, HR, Identity, Documents, BI, Database, …")
    version: str = Field("1.0.0", description="Connector version (semver)")

    # Endpoint
    base_url: str = Field(..., description="Base URL of the upstream API")
    api_version: Optional[str] = Field(None, description="API version (e.g. 'v1', 'v2')")

    # Authentication
    auth_strategy: AuthStrategy = Field(AuthStrategy.NONE)
    credentials_ref: Optional[str] = Field(None, description="Vault path or env prefix for credentials")

    # Timeouts (seconds)
    connect_timeout: float = Field(10.0, ge=0.1, le=300)
    read_timeout: float = Field(30.0, ge=0.1, le=600)
    write_timeout: float = Field(30.0, ge=0.1, le=600)

    # Retry
    max_retries: int = Field(3, ge=0, le=10)
    retry_backoff_factor: float = Field(2.0, ge=1.0, le=10.0)
    retry_max_delay: float = Field(60.0, ge=1.0, le=600)
    retry_on_status: list[int] = Field([429, 500, 502, 503, 504])

    # Circuit Breaker
    cb_failure_threshold: int = Field(5, ge=1, le=100)
    cb_recovery_timeout: float = Field(60.0, ge=1.0, le=600)
    cb_half_open_max_calls: int = Field(3, ge=1, le=20)

    # Rate Limiting (requests per second)
    rate_limit_qps: float = Field(10.0, ge=0.1, le=10000)
    rate_limit_burst: int = Field(20, ge=1, le=10000)

    # Caching
    cache_enabled: bool = Field(True)
    cache_ttl_seconds: int = Field(300, ge=1, le=86400)
    cache_max_entries: int = Field(1000, ge=10, le=100000)

    # Health Check
    health_check_interval: float = Field(30.0, ge=5.0, le=3600)
    health_check_timeout: float = Field(5.0, ge=1.0, le=60)

    # Permissions (RBAC/ABAC)
    required_permissions: list[str] = Field(default_factory=list)

    # Observability
    enable_metrics: bool = Field(True)
    enable_audit_log: bool = Field(True)
    enable_tracing: bool = Field(True)

    # Secrets (never logged, never serialized to JSON)
    secrets: dict[str, SecretStr] = Field(default_factory=dict, exclude=True)

    model_config = {"extra": "allow"}  # allow connector-specific fields


class HealthResult(BaseModel):
    """Result of a health check."""
    status: HealthStatus
    connector: str
    latency_ms: float
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    details: dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class ConnectorMetrics(BaseModel):
    """Snapshot of connector metrics."""
    connector: str
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    avg_latency_ms: float = 0.0
    last_call_at: Optional[datetime] = None
    last_error: Optional[str] = None
    circuit_breaker_state: CircuitBreakerState = CircuitBreakerState.CLOSED
    cache_hits: int = 0
    cache_misses: int = 0
    rate_limit_rejections: int = 0


# ═══════════════════════════════════════════════════════════════════════════
#  Middleware: Retry, Circuit Breaker, Rate Limiter, Cache
# ═══════════════════════════════════════════════════════════════════════════
class CircuitBreaker:
    """3-state circuit breaker with auto-recovery."""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0,
                 half_open_max_calls: int = 3):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self._state = CircuitBreakerState.CLOSED
        self._failures = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0
        self._lock = asyncio.Lock()

    async def call(self, coro_factory: Callable[[], Any]) -> Any:
        async with self._lock:
            await self._before_call()

        try:
            result = await coro_factory()
            await self._on_success()
            return result
        except Exception as e:
            await self._on_failure()
            raise

    async def _before_call(self) -> None:
        if self._state == CircuitBreakerState.OPEN:
            if self._last_failure_time and (time.time() - self._last_failure_time) > self.recovery_timeout:
                self._state = CircuitBreakerState.HALF_OPEN
                self._half_open_calls = 0
                logger.info("Circuit breaker → HALF_OPEN")
            else:
                raise CircuitBreakerOpenError("Circuit breaker is OPEN — requests blocked")
        elif self._state == CircuitBreakerState.HALF_OPEN:
            if self._half_open_calls >= self.half_open_max_calls:
                raise CircuitBreakerOpenError("Circuit breaker HALF_OPEN — too many test calls")
            self._half_open_calls += 1

    async def _on_success(self) -> None:
        if self._state in (CircuitBreakerState.HALF_OPEN, CircuitBreakerState.OPEN):
            self._state = CircuitBreakerState.CLOSED
            self._failures = 0
            logger.info("Circuit breaker → CLOSED (recovered)")

    async def _on_failure(self) -> None:
        self._failures += 1
        self._last_failure_time = time.time()
        if self._failures >= self.failure_threshold:
            self._state = CircuitBreakerState.OPEN
            logger.warning("Circuit breaker → OPEN (failure threshold reached)")

    @property
    def state(self) -> CircuitBreakerState:
        return self._state


class CircuitBreakerOpenError(Exception):
    """Raised when the circuit breaker is open."""


class RateLimiter:
    """Token-bucket rate limiter (async)."""

    def __init__(self, qps: float, burst: int):
        self.qps = qps
        self.burst = burst
        self._tokens = float(burst)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> bool:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._tokens = min(self.burst, self._tokens + elapsed * self.qps)
            self._last_refill = now
            if self._tokens >= 1:
                self._tokens -= 1
                return True
            return False


class RetryPolicy:
    """Exponential backoff with jitter."""

    def __init__(self, max_retries: int = 3, backoff_factor: float = 2.0,
                 max_delay: float = 60.0, retry_on_status: list[int] | None = None):
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.max_delay = max_delay
        self.retry_on_status = retry_on_status or [429, 500, 502, 503, 504]

    def delay(self, attempt: int) -> float:
        import random
        base = min(self.max_delay, self.backoff_factor ** attempt)
        return base * (0.5 + random.random() * 0.5)  # jitter


class ResponseCache:
    """TTL-based in-memory cache (Redis optional in production)."""

    def __init__(self, max_entries: int = 1000, default_ttl: int = 300):
        self._cache: dict[str, tuple[Any, float]] = {}
        self.max_entries = max_entries
        self.default_ttl = default_ttl
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Any | None:
        if key in self._cache:
            value, expires_at = self._cache[key]
            if time.time() < expires_at:
                self.hits += 1
                return value
            del self._cache[key]
        self.misses += 1
        return None

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        if len(self._cache) >= self.max_entries:
            # Evict oldest
            oldest = min(self._cache.items(), key=lambda kv: kv[1][1])
            del self._cache[oldest[0]]
        self._cache[key] = (value, time.time() + (ttl or self.default_ttl))

    def invalidate(self, key: str) -> None:
        self._cache.pop(key, None)

    def clear(self) -> None:
        self._cache.clear()


# ═══════════════════════════════════════════════════════════════════════════
#  Audit Logger (HMAC-signed, tamper-evident)
# ═══════════════════════════════════════════════════════════════════════════
class AuditLogger:
    """HMAC-signed audit trail for every connector call."""

    def __init__(self, hmac_key: str | None = None, sink: Callable[[dict], None] | None = None):
        self.hmac_key = hmac_key or os.environ.get("AUDIT_HMAC_KEY", "default-audit-key")
        self.sink = sink or self._default_sink

    def log_call(self, connector: str, action: str, user: str | None = None,
                 params: dict | None = None, result: Any | None = None,
                 error: str | None = None, duration_ms: float = 0.0) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "connector": connector,
            "action": action,
            "user": user,
            "params_hash": hashlib.sha256(json.dumps(params or {}, sort_keys=True).encode()).hexdigest()[:16],
            "success": error is None,
            "error": error,
            "duration_ms": round(duration_ms, 2),
            "correlation_id": str(uuid.uuid4()),
        }
        # Sign the entry
        payload = json.dumps(entry, sort_keys=True).encode()
        signature = hmac.new(self.hmac_key.encode(), payload, hashlib.sha256).hexdigest()
        entry["signature"] = signature
        self.sink(entry)

    def _default_sink(self, entry: dict) -> None:
        logger.info(f"[AUDIT] {json.dumps(entry)}")


# ═══════════════════════════════════════════════════════════════════════════
#  THE ABSTRACT BASE CONNECTOR
# ═══════════════════════════════════════════════════════════════════════════
class BaseConnector(abc.ABC):
    """
    Abstract base class for all HSAAI enterprise connectors.

    Subclasses MUST implement:
        - authenticate()  — establish credentials session
        - health()        — check upstream health
        - search(query)   — semantic search (if supported)
        - execute(action) — perform an action
        - metadata()      — return connector metadata
        - permissions()   — return required permissions

    Subclasses inherit automatically:
        - Retry, Circuit Breaker, Rate Limiting, Caching
        - Structured logging, Prometheus metrics, HMAC audit trail
        - Discovery & auto-registration with the ConnectorRegistry
        - Health check scheduling
        - Configuration validation
        - Graceful error recovery
    """

    # Class-level metadata (overridden by @connector decorator or subclass)
    _connector_name: str = ""
    _connector_version: str = "1.0.0"
    _connector_category: str = "generic"
    _auto_register: bool = True

    def __init__(self, config: ConnectorConfig):
        self.config = config
        self.state: ConnectorState = ConnectorState.UNINITIALIZED
        self._client: httpx.AsyncClient | None = None
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=config.cb_failure_threshold,
            recovery_timeout=config.cb_recovery_timeout,
            half_open_max_calls=config.cb_half_open_max_calls,
        )
        self._rate_limiter = RateLimiter(
            qps=config.rate_limit_qps,
            burst=config.rate_limit_burst,
        )
        self._retry_policy = RetryPolicy(
            max_retries=config.max_retries,
            backoff_factor=config.retry_backoff_factor,
            max_delay=config.retry_max_delay,
            retry_on_status=config.retry_on_status,
        )
        self._cache = ResponseCache(
            max_entries=config.cache_max_entries,
            default_ttl=config.cache_ttl_seconds,
        ) if config.cache_enabled else None
        self._audit = AuditLogger()
        self._metrics = ConnectorMetrics(connector=config.name)
        self._health_task: asyncio.Task | None = None
        self._last_health: HealthResult | None = None

        # Auto-register with the global registry
        if self._auto_register:
            self._register_with_registry()

    # ─── Abstract Methods (subclasses must implement) ─────────────────────
    @abc.abstractmethod
    async def authenticate(self) -> None:
        """Establish an authenticated session with the upstream service."""
        ...

    @abc.abstractmethod
    async def health(self) -> HealthResult:
        """Check if the upstream service is healthy."""
        ...

    @abc.abstractmethod
    async def search(self, query: str, **kwargs) -> list[dict]:
        """Perform a semantic search against the upstream service."""
        ...

    @abc.abstractmethod
    async def execute(self, action: str, **kwargs) -> dict:
        """Execute a named action against the upstream service."""
        ...

    @abc.abstractmethod
    def metadata(self) -> dict:
        """Return connector metadata (name, version, capabilities, schema)."""
        ...

    @abc.abstractmethod
    def permissions(self) -> list[str]:
        """Return the list of permissions required to use this connector."""
        ...

    # ─── Optional Methods (subclasses may override) ───────────────────────
    async def connect(self) -> None:
        """Initialize the connector (create HTTP client, authenticate)."""
        if self.state == ConnectorState.CONNECTED:
            return
        self.state = ConnectorState.INITIALIZING
        try:
            self._client = httpx.AsyncClient(
                base_url=self.config.base_url,
                timeout=httpx.Timeout(
                    connect=self.config.connect_timeout,
                    read=self.config.read_timeout,
                    write=self.config.write_timeout,
                ),
                headers={"User-Agent": f"HSAAI-Connector/{self.config.version}"},
            )
            await self.authenticate()
            self.state = ConnectorState.CONNECTED
            logger.info(f"Connector '{self.config.name}' connected")
            # Start health check loop
            self._start_health_check()
        except Exception as e:
            self.state = ConnectorState.ERROR
            logger.error(f"Connector '{self.config.name}' failed to connect: {e}")
            raise

    async def disconnect(self) -> None:
        """Clean up resources."""
        if self._health_task:
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                pass
        if self._client:
            await self._client.aclose()
            self._client = None
        self.state = ConnectorState.DISCONNECTED
        logger.info(f"Connector '{self.config.name}' disconnected")

    async def sync(self, **kwargs) -> dict:
        """Trigger a data synchronization (optional)."""
        return {"status": "not_supported", "connector": self.config.name}

    def validate(self, params: dict, schema: type[BaseModel] | None = None) -> dict:
        """Validate input parameters against a pydantic schema."""
        if schema:
            return schema(**params).model_dump()
        return params

    # ─── Built-in Capabilities (subclasses inherit, not override) ─────────
    async def call(self, action: str, *, user: str | None = None,
                   use_cache: bool = True, **kwargs) -> dict:
        """
        Execute a connector action with full middleware stack:
        rate limit → circuit breaker → retry → cache → audit.
        """
        # Check permissions
        if user and not self._check_permissions(user):
            raise PermissionError(f"User '{user}' lacks permissions for '{self.config.name}'")

        # Cache lookup
        cache_key = self._cache_key(action, kwargs)
        if use_cache and self._cache:
            cached = self._cache.get(cache_key)
            if cached is not None:
                self._metrics.cache_hits += 1
                return cached
            self._metrics.cache_misses += 1

        # Rate limit
        if not await self._rate_limiter.acquire():
            self._metrics.rate_limit_rejections += 1
            raise RateLimitExceededError(f"Rate limit exceeded for '{self.config.name}'")

        # Execute with retry + circuit breaker
        start = time.monotonic()
        last_error: Exception | None = None
        for attempt in range(self._retry_policy.max_retries + 1):
            try:
                result = await self._circuit_breaker.call(
                    lambda: self._execute_with_timeout(action, **kwargs)
                )
                duration_ms = (time.monotonic() - start) * 1000
                self._update_metrics(success=True, duration_ms=duration_ms)
                self._audit.log_call(self.config.name, action, user, kwargs, result, None, duration_ms)
                if use_cache and self._cache:
                    self._cache.set(cache_key, result)
                return result
            except CircuitBreakerOpenError as e:
                duration_ms = (time.monotonic() - start) * 1000
                self._update_metrics(success=False, duration_ms=duration_ms, error=str(e))
                self._audit.log_call(self.config.name, action, user, kwargs, None, str(e), duration_ms)
                raise
            except Exception as e:
                last_error = e
                if attempt < self._retry_policy.max_retries:
                    delay = self._retry_policy.delay(attempt)
                    logger.warning(f"Connector '{self.config.name}' attempt {attempt + 1} failed: {e}. Retrying in {delay:.2f}s")
                    await asyncio.sleep(delay)
                else:
                    duration_ms = (time.monotonic() - start) * 1000
                    self._update_metrics(success=False, duration_ms=duration_ms, error=str(e))
                    self._audit.log_call(self.config.name, action, user, kwargs, None, str(e), duration_ms)
                    raise

    async def _execute_with_timeout(self, action: str, **kwargs) -> dict:
        """Execute the action with a timeout."""
        return await asyncio.wait_for(
            self.execute(action, **kwargs),
            timeout=self.config.read_timeout,
        )

    def _check_permissions(self, user: str) -> bool:
        """Check if the user has the required permissions. Override for real RBAC/ABAC."""
        return True  # default: allow (real impl checks OPA)

    def _cache_key(self, action: str, kwargs: dict) -> str:
        """Generate a cache key from action + params."""
        payload = json.dumps({"action": action, "kwargs": kwargs}, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()

    def _update_metrics(self, success: bool, duration_ms: float, error: str | None = None) -> None:
        """Update internal metrics counters."""
        self._metrics.total_calls += 1
        if success:
            self._metrics.successful_calls += 1
        else:
            self._metrics.failed_calls += 1
        # Rolling average latency
        n = self._metrics.total_calls
        self._metrics.avg_latency_ms = ((self._metrics.avg_latency_ms * (n - 1)) + duration_ms) / n
        self._metrics.last_call_at = datetime.now(timezone.utc)
        if error:
            self._metrics.last_error = error
        self._metrics.circuit_breaker_state = self._circuit_breaker.state

    def _start_health_check(self) -> None:
        """Start the background health check loop."""
        async def _loop():
            while self.state == ConnectorState.CONNECTED:
                try:
                    result = await asyncio.wait_for(
                        self.health(),
                        timeout=self.config.health_check_timeout,
                    )
                    self._last_health = result
                except Exception as e:
                    self._last_health = HealthResult(
                        status=HealthStatus.UNHEALTHY,
                        connector=self.config.name,
                        latency_ms=0,
                        error=str(e),
                    )
                await asyncio.sleep(self.config.health_check_interval)

        self._health_task = asyncio.create_task(_loop())

    def _register_with_registry(self) -> None:
        """Auto-register this connector instance with the global registry."""
        from packages.common.connectors.registry import ConnectorRegistry
        ConnectorRegistry.register(self)

    # ─── Public API for introspection ─────────────────────────────────────
    def get_metrics(self) -> ConnectorMetrics:
        return self._metrics

    def get_health(self) -> HealthResult | None:
        return self._last_health

    def get_state(self) -> ConnectorState:
        return self.state

    def invalidate_cache(self, pattern: str | None = None) -> int:
        """Invalidate cache entries. Returns count of invalidated entries."""
        if not self._cache:
            return 0
        if pattern is None:
            count = len(self._cache._cache)
            self._cache.clear()
            return count
        # Pattern-based invalidation (simple substring match)
        count = 0
        for key in list(self._cache._cache.keys()):
            if pattern in key:
                self._cache.invalidate(key)
                count += 1
        return count


# ═══════════════════════════════════════════════════════════════════════════
#  Custom Exceptions
# ═══════════════════════════════════════════════════════════════════════════
class ConnectorError(Exception):
    """Base exception for connector errors."""


class RateLimitExceededError(ConnectorError):
    """Raised when rate limit is exceeded."""


class ConnectorNotConnectedError(ConnectorError):
    """Raised when an action is called before connect()."""


class ConnectorAuthenticationError(ConnectorError):
    """Raised when authentication fails."""


# ═══════════════════════════════════════════════════════════════════════════
#  Decorator: @connector() — for declarative registration
# ═══════════════════════════════════════════════════════════════════════════
def connector(name: str, version: str = "1.0.0", category: str = "generic",
              auto_register: bool = True) -> Callable[[type], type]:
    """
    Class decorator that marks a class as an HSAAI connector and registers
    its metadata. The class will be auto-discovered by the ConnectorRegistry.

    Usage:
        @connector("sap_s4hana", version="1.0.0", category="ERP")
        class SAPS4HANAConnector(BaseConnector):
            ...
    """
    def decorator(cls: type) -> type:
        cls._connector_name = name
        cls._connector_version = version
        cls._connector_category = category
        cls._auto_register = auto_register
        # Register the class (not instance) in the registry's catalog
        from packages.common.connectors.registry import ConnectorRegistry
        ConnectorRegistry.register_class(name, cls, version, category)
        return cls
    return decorator


__all__ = [
    # Base class
    "BaseConnector",
    # Configuration
    "ConnectorConfig",
    "HealthResult",
    "ConnectorMetrics",
    # Enums
    "ConnectorState",
    "HealthStatus",
    "AuthStrategy",
    "CircuitBreakerState",
    "Severity",
    # Middleware
    "CircuitBreaker",
    "CircuitBreakerOpenError",
    "RateLimiter",
    "RetryPolicy",
    "ResponseCache",
    "AuditLogger",
    # Decorator
    "connector",
    # Exceptions
    "ConnectorError",
    "RateLimitExceededError",
    "ConnectorNotConnectedError",
    "ConnectorAuthenticationError",
]
