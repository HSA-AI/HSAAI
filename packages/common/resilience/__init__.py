"""
HSAAI Resilience Engineering
============================

Production-grade resilience patterns for the HSAAI platform:

  - **Circuit breaker** (`circuit_breaker.py`) — fail-fast when a
    downstream service is degraded; auto-recover after a cooldown.
  - **Retry with exponential backoff + jitter** (`retry.py`) — tuned
    per-service retry policies; integrates with circuit breaker.
  - **Bulkhead** (`bulkhead.py`) — limit concurrent calls per service
    to prevent cascade failures.
  - **Timeout enforcement** (`timeout.py`) — per-service default
    timeouts; budget-aware so inner calls cannot exceed outer budgets.
  - **Fallback strategies** (`fallback.py`) — cached value, default,
    alternative, and empty-result fallbacks.

All patterns expose Prometheus metrics when `prometheus_client` is
installed (no-op otherwise).

Quick start
-----------
    from packages.common.resilience import (
        circuit_breaker, retry_with_policy, get_bulkhead, timeout,
    )

    @circuit_breaker("rag_engine", failure_threshold=5, recovery_timeout=30)
    @retry_with_policy("rag_engine")
    @timeout("rag_engine", seconds=5.0)
    async def search(q: str):
        async with get_bulkhead("rag_engine"):
            return await rag.search(q)
"""
from packages.common.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    CircuitBreakerOpenError,
    get_breaker,
    circuit_breaker,
    get_all_breaker_stats,
)
from packages.common.resilience.retry import (
    retry_with_policy,
    RetryPolicy,
    get_retry_policy,
    is_retryable_error,
    SERVICE_RETRY_POLICIES,
)
from packages.common.resilience.bulkhead import (
    SemaphoreBulkhead,
    BulkheadFullError,
    get_bulkhead,
    BULKHEAD_CONFIGS,
)
from packages.common.resilience.timeout import (
    HSAAITimeoutError,
    TimeoutContext,
    timeout,
    call_with_timeout,
    get_default_timeout,
    SERVICE_DEFAULT_TIMEOUTS,
)
from packages.common.resilience.fallback import (
    cached_fallback,
    default_fallback,
    alternative_fallback,
    empty_result_fallback,
    last_good_cache,
)

# Back-compat aliases used by older code that imports `Bulkhead` or
# `CircuitOpenError` (previously broken names — fixed in v4.1).
Bulkhead = SemaphoreBulkhead
CircuitOpenError = CircuitBreakerOpenError

__all__ = [
    # Circuit breaker
    "CircuitBreaker", "CircuitState", "CircuitBreakerOpenError",
    "CircuitOpenError",  # alias
    "get_breaker", "circuit_breaker", "get_all_breaker_stats",
    # Retry
    "retry_with_policy", "RetryPolicy", "get_retry_policy",
    "is_retryable_error", "SERVICE_RETRY_POLICIES",
    # Bulkhead
    "SemaphoreBulkhead", "Bulkhead",  # alias
    "BulkheadFullError", "get_bulkhead", "BULKHEAD_CONFIGS",
    # Timeout
    "HSAAITimeoutError", "TimeoutContext", "timeout", "call_with_timeout",
    "get_default_timeout", "SERVICE_DEFAULT_TIMEOUTS",
    # Fallback
    "cached_fallback", "default_fallback", "alternative_fallback",
    "empty_result_fallback", "last_good_cache",
]
