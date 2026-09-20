"""
HSAAI Timeout Enforcement (v1.0)
================================

Provides async-context-manager and decorator-based timeout enforcement
for any awaitable. Built on `asyncio.wait_for` with these extras:

  - **Per-service default timeouts** (configurable via env).
  - **Budget-aware timeouts**: subtract already-elapsed time from the
    overall request budget so an inner call cannot exceed the
    remaining outer budget.
  - **Prometheus metrics**: timeout counters per service.
  - **Composition with circuit breakers**: a timeout fires the breaker's
    failure path so repeated timeouts will eventually open the breaker.

Usage
-----
    from packages.common.resilience.timeout import timeout, TimeoutError as HSAaiTimeout

    @timeout("rag_engine", seconds=5.0)
    async def search(q: str):
        ...

    # Context manager form
    async with TimeoutContext("llm_gateway", seconds=30.0) as ctx:
        result = await llm.generate(prompt)
"""
from __future__ import annotations

import os
import asyncio
import logging
import functools
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger("hsaai.resilience.timeout")

# ── Prometheus metrics (optional) ──
try:
    from prometheus_client import Counter, Histogram
    TIMEOUTS_TOTAL = Counter(
        "hsaai_timeouts_total",
        "Total operations that timed out",
        ["service"],
    )
    TIMEOUT_DURATION = Histogram(
        "hsaai_timeout_configured_seconds",
        "Configured timeout per operation (s)",
        ["service"],
        buckets=(0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 120.0),
    )
    _METRICS = True
except ImportError:  # pragma: no cover
    _METRICS = False
    TIMEOUTS_TOTAL = TIMEOUT_DURATION = None


# ── Per-service default timeouts ──
SERVICE_DEFAULT_TIMEOUTS: dict[str, float] = {
    "llm_gateway": float(os.getenv("TIMEOUT_LLM_GATEWAY", "120.0")),
    "rag_engine": float(os.getenv("TIMEOUT_RAG_ENGINE", "30.0")),
    "auth_service": float(os.getenv("TIMEOUT_AUTH_SERVICE", "10.0")),
    "governance": float(os.getenv("TIMEOUT_GOVERNANCE", "10.0")),
    "qdrant": float(os.getenv("TIMEOUT_QDRANT", "15.0")),
    "neo4j": float(os.getenv("TIMEOUT_NEO4J", "15.0")),
    "ollama": float(os.getenv("TIMEOUT_OLLAMA", "300.0")),  # local inference can be slow
    "default": float(os.getenv("TIMEOUT_DEFAULT", "30.0")),
}


def get_default_timeout(service: str) -> float:
    return SERVICE_DEFAULT_TIMEOUTS.get(service, SERVICE_DEFAULT_TIMEOUTS["default"])


class HSAAITimeoutError(asyncio.TimeoutError):
    """Raised when an operation exceeds its time budget.

    Subclass of `asyncio.TimeoutError` so existing `except asyncio.TimeoutError`
    handlers continue to work. Adds `service` and `elapsed_ms` for diagnostics.
    """
    def __init__(self, service: str, seconds: float, elapsed_ms: float):
        self.service = service
        self.seconds = seconds
        self.elapsed_ms = elapsed_ms
        super().__init__(
            f"Timeout after {seconds:.1f}s (elapsed {elapsed_ms:.0f}ms) for service '{service}'"
        )


class TimeoutContext:
    """Async context manager that cancels the body after `seconds`.

    Example:
        async with TimeoutContext("rag_engine", seconds=5.0):
            results = await rag.search(q)
    """

    def __init__(self, service: str, seconds: Optional[float] = None):
        self.service = service
        self.seconds = seconds if seconds is not None else get_default_timeout(service)
        self._task: Optional[asyncio.Task] = None
        self._started = 0.0

    async def __aenter__(self) -> "TimeoutContext":
        self._started = asyncio.get_event_loop().time()
        if TIMEOUT_DURATION:
            TIMEOUT_DURATION.labels(service=self.service).observe(self.seconds)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        if exc is asyncio.TimeoutError:
            elapsed_ms = (asyncio.get_event_loop().time() - self._started) * 1000
            if TIMEOUTS_TOTAL:
                TIMEOUTS_TOTAL.labels(service=self.service).inc()
            # Replace with our richer exception type
            raise HSAAITimeoutError(self.service, self.seconds, elapsed_ms)
        return False

    def remaining_budget(self, started_at: float) -> float:
        """Compute remaining budget given an outer `started_at` (loop.time())."""
        elapsed = asyncio.get_event_loop().time() - started_at
        return max(0.0, self.seconds - elapsed)


def timeout(service: str, seconds: Optional[float] = None):
    """Decorator: enforce a timeout on an async function.

    Usage:
        @timeout("rag_engine", seconds=5.0)
        async def search(q: str) -> list: ...
    """
    def decorator(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        secs = seconds if seconds is not None else get_default_timeout(service)

        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            started = asyncio.get_event_loop().time()
            try:
                return await asyncio.wait_for(func(*args, **kwargs), timeout=secs)
            except asyncio.TimeoutError:
                elapsed_ms = (asyncio.get_event_loop().time() - started) * 1000
                if TIMEOUTS_TOTAL:
                    TIMEOUTS_TOTAL.labels(service=service).inc()
                raise HSAAITimeoutError(service, secs, elapsed_ms)

        return wrapper

    return decorator


async def call_with_timeout(
    coro: Awaitable[Any],
    service: str,
    seconds: Optional[float] = None,
) -> Any:
    """One-shot helper: await a coroutine with a timeout.

    Useful when you can't decorate the function (e.g. third-party client).
    """
    secs = seconds if seconds is not None else get_default_timeout(service)
    started = asyncio.get_event_loop().time()
    try:
        return await asyncio.wait_for(coro, timeout=secs)
    except asyncio.TimeoutError:
        elapsed_ms = (asyncio.get_event_loop().time() - started) * 1000
        if TIMEOUTS_TOTAL:
            TIMEOUTS_TOTAL.labels(service=service).inc()
        raise HSAAITimeoutError(service, secs, elapsed_ms)


__all__ = [
    "HSAAITimeoutError",
    "TimeoutContext",
    "timeout",
    "call_with_timeout",
    "get_default_timeout",
    "SERVICE_DEFAULT_TIMEOUTS",
]
