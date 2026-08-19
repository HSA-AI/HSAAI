"""
HSAAI Fallback Strategies (v1.0)
================================

Composable fallbacks for when a primary operation fails. Provides:

  - **Cached value fallback**: return the last good cached value if the
    primary call fails. Useful for read-heavy endpoints that can tolerate
    slightly-stale data during outages.
  - **Default value fallback**: return a static default if the primary
    fails. Useful for non-critical metadata (e.g. user display name).
  - **Alternative service fallback**: try a secondary service (e.g.
    a read-replica or a degraded LLM) if the primary is unavailable.
  - **Empty result fallback**: return `[]` / `{}` / `None` so callers
    do not crash on transient failures.

Each fallback records Prometheus metrics so operators can see how often
the degraded path is exercised.

Usage
-----
    from packages.common.resilience.fallback import (
        cached_fallback, default_fallback, alternative_fallback,
    )

    @cached_fallback("rag_engine", cache=last_good_cache)
    async def search(q: str):
        return await rag.search(q)

    @default_fallback("llm_gateway", default="Service temporarily unavailable.")
    async def generate(prompt: str):
        return await llm.generate(prompt)

    @alternative_fallback("primary", fallback_fn=lambda q: secondary.search(q))
    async def search(q: str):
        return await primary.search(q)
"""
from __future__ import annotations

import logging
import functools
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger("hsaai.resilience.fallback")

# ── Prometheus metrics (optional) ──
try:
    from prometheus_client import Counter
    FALLBACK_TOTAL = Counter(
        "hsaai_fallback_total",
        "Total times a fallback path was exercised",
        ["strategy", "service"],
    )
    _METRICS = True
except ImportError:  # pragma: no cover
    _METRICS = False
    FALLBACK_TOTAL = None


# ── A minimal cache interface (duck-typed) ──
class _LastGoodCache:
    """Tiny in-memory last-good-value cache."""
    def __init__(self):
        self._store: dict[str, Any] = {}

    def get(self, key: str) -> Optional[Any]:
        return self._store.get(key)

    def set(self, key: str, value: Any) -> None:
        self._store[key] = value

    def clear(self) -> None:
        self._store.clear()


def last_good_cache() -> _LastGoodCache:
    """Return a fresh in-memory last-good-value cache."""
    return _LastGoodCache()


# ═══════════════════════════════════════════════════════════════════
# Decorators
# ═══════════════════════════════════════════════════════════════════
def cached_fallback(service: str, cache: Optional[_LastGoodCache] = None):
    """Return the last successful value if the primary call fails.

    The cache key is derived from the call's repr of (args, kwargs).
    On success, the result is stored. On failure, the cached value is
    returned (or the exception re-raised if no cache exists).

    Args:
        service: service name for metrics.
        cache: a `_LastGoodCache` instance. If None, a fresh per-decorator
               cache is created.
    """
    cache = cache or _LastGoodCache()

    def decorator(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            key = repr((args, sorted(kwargs.items())))
            try:
                result = await func(*args, **kwargs)
                cache.set(key, result)
                return result
            except Exception as exc:
                cached = cache.get(key)
                if cached is not None:
                    if FALLBACK_TOTAL:
                        FALLBACK_TOTAL.labels(strategy="cached", service=service).inc()
                    logger.warning(
                        "cached_fallback[%s]: primary failed (%s) — returning last good value",
                        service, type(exc).__name__,
                    )
                    return cached
                raise
        return wrapper
    return decorator


def default_fallback(service: str, default: Any):
    """Return a static default value if the primary call fails.

    Args:
        service: service name for metrics.
        default: the value to return on failure.
    """

    def decorator(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            try:
                return await func(*args, **kwargs)
            except Exception as exc:
                if FALLBACK_TOTAL:
                    FALLBACK_TOTAL.labels(strategy="default", service=service).inc()
                logger.warning(
                    "default_fallback[%s]: primary failed (%s) — returning default",
                    service, type(exc).__name__,
                )
                return default
        return wrapper
    return decorator


def alternative_fallback(service: str, fallback_fn: Callable[..., Awaitable[Any]]):
    """Try a secondary function if the primary fails.

    Args:
        service: service name for metrics.
        fallback_fn: async callable with the same signature as the primary.
    """

    def decorator(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            try:
                return await func(*args, **kwargs)
            except Exception as exc:
                if FALLBACK_TOTAL:
                    FALLBACK_TOTAL.labels(strategy="alternative", service=service).inc()
                logger.warning(
                    "alternative_fallback[%s]: primary failed (%s) — trying secondary",
                    service, type(exc).__name__,
                )
                return await fallback_fn(*args, **kwargs)
        return wrapper
    return decorator


def empty_result_fallback(service: str, empty_value: Any = None):
    """Return an empty value (None, [], {}) if the primary fails.

    Args:
        service: service name for metrics.
        empty_value: the value to return on failure (default None).
    """

    def decorator(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            try:
                return await func(*args, **kwargs)
            except Exception as exc:
                if FALLBACK_TOTAL:
                    FALLBACK_TOTAL.labels(strategy="empty", service=service).inc()
                logger.warning(
                    "empty_result_fallback[%s]: primary failed (%s) — returning empty",
                    service, type(exc).__name__,
                )
                return empty_value
        return wrapper
    return decorator


__all__ = [
    "last_good_cache",
    "cached_fallback",
    "default_fallback",
    "alternative_fallback",
    "empty_result_fallback",
]
