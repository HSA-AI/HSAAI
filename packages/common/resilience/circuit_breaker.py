"""
HSAAI Circuit Breaker (v4.0)

Wraps httpx calls between services with circuit breaker pattern.
Prevents cascade failures when a downstream service is degraded.

States:
  - CLOSED: normal operation, requests flow through
  - OPEN: circuit tripped, requests fail fast (no call to downstream)
  - HALF_OPEN: testing if downstream recovered (allows 1 probe request)

Usage:
    from packages.common.resilience.circuit_breaker import circuit_breaker

    @circuit_breaker(failure_threshold=5, recovery_timeout=30)
    async def call_rag_engine(query: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{RAG_URL}/v1/search", json={"query": query})
            return resp.json()
"""
import os
import time
import logging
import functools
from typing import Callable, Any
from enum import Enum
import asyncio

logger = logging.getLogger("hsaai.circuit_breaker")


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""
    def __init__(self, service: str, recovery_in: float):
        self.service = service
        self.recovery_in = recovery_in
        super().__init__(f"Circuit breaker OPEN for '{service}' — retry in {recovery_in:.0f}s")


class CircuitBreaker:
    """Circuit breaker for a single service."""

    def __init__(self, name: str, failure_threshold: int = 5,
                 recovery_timeout: float = 30.0,
                 half_open_max_calls: int = 1):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = 0.0
        self._half_open_calls = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if time.time() - self._last_failure_time > self.recovery_timeout:
                return CircuitState.HALF_OPEN
            return CircuitState.OPEN
        return self._state

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute func through the circuit breaker."""
        async with self._lock:
            current_state = self.state

            if current_state == CircuitState.OPEN:
                recovery_in = self.recovery_timeout - (time.time() - self._last_failure_time)
                logger.warning("Circuit OPEN for '%s' — failing fast", self.name)
                raise CircuitBreakerOpenError(self.name, max(recovery_in, 0))

            if current_state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.half_open_max_calls:
                    raise CircuitBreakerOpenError(self.name, self.recovery_timeout)
                self._half_open_calls += 1

        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except Exception as exc:
            await self._on_failure()
            raise

    async def _on_success(self):
        async with self._lock:
            self._success_count += 1
            if self.state == CircuitState.HALF_OPEN:
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                self._half_open_calls = 0
                logger.info("Circuit CLOSED for '%s' — recovered", self.name)

    async def _on_failure(self):
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            self._half_open_calls = 0

            if self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning(
                    "Circuit OPENED for '%s' — %d failures (threshold=%d)",
                    self.name, self._failure_count, self.failure_threshold,
                )

    def reset(self):
        """Reset the circuit breaker (for testing)."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0


# ─── Registry (one breaker per service) ───

_breakers: dict[str, CircuitBreaker] = {}


def get_breaker(service: str, **kwargs) -> CircuitBreaker:
    """Get or create a circuit breaker for a service."""
    if service not in _breakers:
        _breakers[service] = CircuitBreaker(service, **kwargs)
    return _breakers[service]


def circuit_breaker(service: str | None = None,
                    failure_threshold: int = 5,
                    recovery_timeout: float = 30.0):
    """Decorator: wrap an async function with a circuit breaker.

    Usage:
        @circuit_breaker("rag_engine", failure_threshold=5, recovery_timeout=30)
        async def call_rag(query: str):
            ...
    """
    def decorator(func: Callable) -> Callable:
        breaker_name = service or func.__name__

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            breaker = get_breaker(breaker_name,
                                  failure_threshold=failure_threshold,
                                  recovery_timeout=recovery_timeout)
            return await breaker.call(func, *args, **kwargs)

        wrapper._circuit_breaker = get_breaker(breaker_name)  # type: ignore
        return wrapper

    return decorator


def get_all_breaker_stats() -> list[dict]:
    """Get stats for all circuit breakers (for monitoring)."""
    return [
        {
            "service": name,
            "state": b.state.value,
            "failures": b._failure_count,
            "successes": b._success_count,
            "last_failure": b._last_failure_time,
        }
        for name, b in _breakers.items()
    ]
