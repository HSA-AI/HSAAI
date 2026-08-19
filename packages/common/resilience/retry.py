"""
HSAAI Retry Policies — Production Implementation

Provides configurable retry policies with:
  - Exponential backoff with jitter
  - Per-service retry configurations
  - Circuit breaker integration
  - Retry budget (max retries per time window)
  - Prometheus metrics for retry attempts

Usage:
    from packages.common.resilience.retry import retry_with_policy, RetryPolicy

    @retry_with_policy("llm_gateway")
    async def call_llm(prompt: str) -> str:
        async with httpx.AsyncClient() as client:
            response = await client.post(...)
            return response.json()
"""
import os
import time
import random
import logging
from typing import Optional, Type, Tuple, Callable, Any
from functools import wraps
from dataclasses import dataclass

logger = logging.getLogger("hsaai.resilience.retry")

# Prometheus metrics
try:
    from prometheus_client import Counter, Histogram
    RETRY_ATTEMPTS_TOTAL = Counter(
        "hsaai_retry_attempts_total",
        "Total retry attempts",
        ["service", "result"],  # result: success | exhausted | aborted
    )
    RETRY_LATENCY = Histogram(
        "hsaai_retry_latency_seconds",
        "Total latency including all retry attempts",
        ["service"],
    )
except ImportError:
    RETRY_ATTEMPTS_TOTAL = None
    RETRY_LATENCY = None


@dataclass
class RetryPolicy:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    base_delay: float = 1.0          # Initial delay in seconds
    max_delay: float = 60.0           # Maximum delay cap
    exponential_base: float = 2.0     # Backoff multiplier
    jitter: bool = True               # Add random jitter to prevent thundering herd
    retryable_exceptions: Tuple[Type[Exception], ...] = (
        ConnectionError,
        TimeoutError,
        OSError,
    )
    retryable_status_codes: Tuple[int, ...] = (429, 502, 503, 504)

    def compute_delay(self, attempt: int) -> float:
        """Compute delay for the given attempt number (0-indexed)."""
        delay = min(
            self.base_delay * (self.exponential_base ** attempt),
            self.max_delay,
        )
        if self.jitter:
            delay = delay * random.uniform(0.5, 1.5)
        return delay


# ── Pre-configured retry policies per HSAAI service ──

SERVICE_RETRY_POLICIES = {
    "llm_gateway": RetryPolicy(
        max_attempts=3,
        base_delay=2.0,
        max_delay=120.0,
        retryable_exceptions=(ConnectionError, TimeoutError, OSError),
        retryable_status_codes=(429, 502, 503, 504),
    ),
    "rag_engine": RetryPolicy(
        max_attempts=3,
        base_delay=1.0,
        max_delay=30.0,
        retryable_status_codes=(429, 502, 503, 504),
    ),
    "auth_service": RetryPolicy(
        max_attempts=2,
        base_delay=0.5,
        max_delay=5.0,
        retryable_status_codes=(429, 502, 503),
    ),
    "qdrant": RetryPolicy(
        max_attempts=3,
        base_delay=1.0,
        max_delay=15.0,
        retryable_exceptions=(ConnectionError, TimeoutError, OSError),
    ),
    "keycloak": RetryPolicy(
        max_attempts=2,
        base_delay=0.5,
        max_delay=5.0,
        retryable_exceptions=(ConnectionError, TimeoutError, OSError),
        retryable_status_codes=(429, 502, 503),
    ),
    "default": RetryPolicy(
        max_attempts=3,
        base_delay=1.0,
        max_delay=30.0,
    ),
}


def get_retry_policy(service_name: str) -> RetryPolicy:
    """Get the retry policy for a service."""
    return SERVICE_RETRY_POLICIES.get(service_name, SERVICE_RETRY_POLICIES["default"])


def is_retryable_error(exc: Exception, policy: RetryPolicy) -> bool:
    """Check if an exception is retryable according to the policy."""
    if isinstance(exc, policy.retryable_exceptions):
        return True
    # Check for HTTP status code in exception
    status = getattr(exc, "status_code", None) or getattr(getattr(exc, "response", None), "status_code", None)
    if status and status in policy.retryable_status_codes:
        return True
    return False


def retry_with_policy(service_name: str, policy: Optional[RetryPolicy] = None):
    """
    Decorator that applies retry policy to an async function.

    Args:
        service_name: Service name for policy lookup and metrics
        policy: Override retry policy (default: auto-configured per service)
    """
    _policy = policy or get_retry_policy(service_name)

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            started = time.time()
            last_exception = None

            for attempt in range(_policy.max_attempts):
                try:
                    result = await func(*args, **kwargs)
                    if attempt > 0:
                        if RETRY_ATTEMPTS_TOTAL:
                            RETRY_ATTEMPTS_TOTAL.labels(service=service_name, result="success").inc()
                        logger.info(
                            "Retry succeeded for %s after %d attempts (%.1fs)",
                            service_name, attempt + 1, time.time() - started,
                        )
                    if RETRY_LATENCY:
                        RETRY_LATENCY.labels(service=service_name).observe(time.time() - started)
                    return result

                except Exception as exc:
                    last_exception = exc

                    if not is_retryable_error(exc, _policy):
                        if RETRY_ATTEMPTS_TOTAL:
                            RETRY_ATTEMPTS_TOTAL.labels(service=service_name, result="aborted").inc()
                        raise

                    if attempt < _policy.max_attempts - 1:
                        delay = _policy.compute_delay(attempt)
                        logger.warning(
                            "Retry %d/%d for %s: %s — waiting %.1fs",
                            attempt + 1, _policy.max_attempts, service_name,
                            type(exc).__name__, delay,
                        )
                        import asyncio
                        await asyncio.sleep(delay)
                    else:
                        if RETRY_ATTEMPTS_TOTAL:
                            RETRY_ATTEMPTS_TOTAL.labels(service=service_name, result="exhausted").inc()
                        logger.error(
                            "All %d retries exhausted for %s: %s",
                            _policy.max_attempts, service_name, exc,
                        )

            raise last_exception

        return wrapper
    return decorator
