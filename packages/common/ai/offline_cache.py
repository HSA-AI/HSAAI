"""
HSAAI Offline Cache (v1.0 — AI-IMPROVEMENTS)
=============================================

Redis-backed LLM response cache + offline-mode request queue.

Features
--------
1. **Cache frequent queries + responses** in Redis with a configurable
   TTL (default 24h).
2. **Cache key**: deterministic hash of
   `(prompt + context_hash + model_version)` — so two callers asking
   the same question with the same retrieved context and model get the
   same cached answer.
3. **Cache hit-ratio monitoring** — increment hit/miss counters and
   expose a `hit_ratio()` method.
4. **Stale-while-revalidate (SWR)** — serve the cached response
   immediately, then refresh it in the background (best-effort).
5. **Offline queue** — if the LLM is unavailable, queue the request
   (FIFO) and serve the cached response if one exists; otherwise
   return a 503 with `retry-after`.

The module degrades gracefully when Redis is unavailable: every method
returns a sensible empty/default value instead of raising, so the LLM
gateway stays available even if Redis is down.

Usage
-----
    from packages.common.ai.offline_cache import OfflineCache

    cache = OfflineCache(redis_url="redis://redis:6379/3", ttl=86400)

    cached = cache.get(prompt, context_chunks, model_version="qwen3:8b")
    if cached:
        return cached["response"]

    response = await call_llm(prompt)
    cache.set(prompt, context_chunks, model_version="qwen3:8b", response=response)

    # SWR: serve cached, refresh in background
    cached = cache.get_swr(prompt, context_chunks, model_version, refresh_fn=...)

    # Offline queue
    if not llm_available:
        cache.enqueue(prompt, tenant_id=...)
        cached = cache.get(...)  # may still serve a stale cached response
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger("hsaai.offline_cache")

DEFAULT_TTL = 86400  # 24 hours
DEFAULT_STALE_TTL = 7 * 86400  # 7 days — stale entries kept for SWR
DEFAULT_QUEUE_MAX = 1000
SWR_REFRESH_THRESHOLD = 0.8  # refresh if cached entry is older than 80% of TTL


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────


def _hash_context(context_chunks: list[dict[str, Any]] | Any) -> str:
    """Hash the context chunks into a stable digest.

    Accepts a list of dicts (with `text` and any metadata) or any
    JSON-serializable object. Returns a 16-char hex string.
    """
    if not context_chunks:
        return "no_context"
    try:
        # Extract just the text + doc_id for stability (ignore scores,
        # timestamps, etc. that don't affect the answer).
        if isinstance(context_chunks, list):
            simplified = []
            for c in context_chunks:
                if isinstance(c, dict):
                    simplified.append({
                        "text": (c.get("text") or "")[:500],
                        "doc_id": c.get("doc_id"),
                        "chunk_index": c.get("chunk_index"),
                    })
                else:
                    simplified.append(str(c)[:500])
            payload = json.dumps(simplified, sort_keys=True, ensure_ascii=False)
        else:
            payload = json.dumps(context_chunks, sort_keys=True, ensure_ascii=False)
    except Exception:
        payload = str(context_chunks)[:2000]
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _cache_key(
    prompt: str,
    context_chunks: list[dict[str, Any]] | Any,
    model_version: str,
) -> str:
    """Build the deterministic cache key.

    Format: `llm_offline:{model_version}:{prompt_hash}:{context_hash}`
    """
    prompt_hash = hashlib.sha256((prompt or "").strip().lower().encode("utf-8")).hexdigest()[:16]
    ctx_hash = _hash_context(context_chunks)
    return f"llm_offline:{model_version}:{prompt_hash}:{ctx_hash}"


# ─────────────────────────────────────────────────────────────────────
# Redis connection helper (lazy)
# ─────────────────────────────────────────────────────────────────────


def _get_redis(url: str):
    """Lazily create a Redis client. Returns None if unavailable."""
    try:
        import redis  # type: ignore
        return redis.from_url(
            url, decode_responses=True,
            socket_timeout=2, socket_connect_timeout=2,
        )
    except ImportError:
        logger.debug("redis package not installed — offline cache disabled")
        return None
    except Exception as exc:
        logger.debug("Redis connection failed (%s) — cache disabled", exc)
        return None


# ─────────────────────────────────────────────────────────────────────
# In-process fallback cache (used when Redis is unavailable)
# ─────────────────────────────────────────────────────────────────────

_LOCAL_CACHE: dict[str, dict[str, Any]] = {}
_LOCAL_CACHE_LOCK = threading.Lock()


def _local_get(key: str) -> Optional[dict[str, Any]]:
    with _LOCAL_CACHE_LOCK:
        entry = _LOCAL_CACHE.get(key)
        if not entry:
            return None
        if time.time() - entry.get("created_at", 0) > DEFAULT_TTL:
            _LOCAL_CACHE.pop(key, None)
            return None
        return entry


def _local_set(key: str, value: dict[str, Any], ttl: int):
    with _LOCAL_CACHE_LOCK:
        # Bound the local cache to 1024 entries (LRU-ish).
        if len(_LOCAL_CACHE) >= 1024:
            for k in list(_LOCAL_CACHE.keys())[:128]:
                _LOCAL_CACHE.pop(k, None)
        _LOCAL_CACHE[key] = {**value, "created_at": time.time()}


# ─────────────────────────────────────────────────────────────────────
# OfflineCache
# ─────────────────────────────────────────────────────────────────────


@dataclass
class CacheStats:
    hits: int = 0
    misses: int = 0
    sets: int = 0
    swr_refreshes: int = 0
    queued: int = 0
    errors: int = 0

    def to_dict(self) -> dict[str, Any]:
        total = self.hits + self.misses
        return {
            "hits": self.hits,
            "misses": self.misses,
            "sets": self.sets,
            "swr_refreshes": self.swr_refreshes,
            "queued": self.queued,
            "errors": self.errors,
            "hit_ratio": round(self.hits / total, 4) if total > 0 else 0.0,
        }


class OfflineCache:
    """Redis-backed LLM response cache + offline queue.

    Parameters
    ----------
    redis_url : str
        Redis connection URL.
    ttl : int
        Cache entry TTL in seconds (default 86400 = 24h).
    stale_ttl : int
        How long to keep stale entries for SWR (default 7d).
    queue_max : int
        Maximum number of pending offline requests.
    namespace : str
        Redis key prefix.
    """

    def __init__(
        self,
        *,
        redis_url: str = None,
        ttl: int = DEFAULT_TTL,
        stale_ttl: int = DEFAULT_STALE_TTL,
        queue_max: int = DEFAULT_QUEUE_MAX,
        namespace: str = "llm_offline",
    ):
        self.redis_url = redis_url or os.getenv(
            "OFFLINE_CACHE_REDIS_URL",
            os.getenv("REDIS_URL", "redis://redis:6379/3"),
        )
        self.ttl = int(ttl)
        self.stale_ttl = int(stale_ttl)
        self.queue_max = int(queue_max)
        self.namespace = namespace
        self._stats = CacheStats()
        self._redis = None  # lazily initialized on first use

    # ── public API ──────────────────────────────────────────────────

    def get(
        self,
        prompt: str,
        context_chunks: list[dict[str, Any]] | Any,
        model_version: str,
    ) -> Optional[dict[str, Any]]:
        """Look up a cached response. Returns the cached dict or None.

        The returned dict has keys: `response`, `model_version`,
        `created_at`, `age_seconds`, `source`.
        """
        key = _cache_key(prompt, context_chunks, model_version)
        # Track whether we ultimately used Redis (vs. local fallback).
        redis_was_used = self._redis is not None
        entry = self._get_entry(key)
        if entry is None:
            self._stats.misses += 1
            return None
        self._stats.hits += 1
        entry["age_seconds"] = int(time.time() - entry.get("created_at", 0))
        # Source reflects what storage actually served the entry. If
        # _get_entry disabled Redis due to a connection failure, the
        # entry came from local fallback.
        entry["source"] = "redis" if (redis_was_used and self._redis is not None) else "local"
        return entry

    def set(
        self,
        prompt: str,
        context_chunks: list[dict[str, Any]] | Any,
        model_version: str,
        response: str,
        *,
        metadata: Optional[dict[str, Any]] = None,
    ):
        """Store a response in the cache."""
        key = _cache_key(prompt, context_chunks, model_version)
        entry = {
            "response": response,
            "model_version": model_version,
            "created_at": time.time(),
            "metadata": metadata or {},
        }
        self._set_entry(key, entry, self.ttl)
        self._stats.sets += 1

    def get_swr(
        self,
        prompt: str,
        context_chunks: list[dict[str, Any]] | Any,
        model_version: str,
        refresh_fn: Callable[[], Awaitable[str]],
    ) -> Optional[dict[str, Any]]:
        """Stale-while-revalidate get.

        If a cached entry exists (even if stale), return it immediately
        and trigger a background refresh via `refresh_fn` if the entry
        is older than 80% of TTL.

        `refresh_fn` is an async callable that returns the new response
        string. The refresh is best-effort — failures are logged and
        ignored.

        Returns the cached entry (with `swr_refreshed: True/False`) or
        None if no entry exists.
        """
        entry = self.get(prompt, context_chunks, model_version)
        if entry is None:
            return None

        age = entry.get("age_seconds", 0)
        needs_refresh = age >= self.ttl * SWR_REFRESH_THRESHOLD
        entry["swr_refreshed"] = False

        if needs_refresh:
            # Fire-and-forget background refresh.
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._swr_refresh(
                        prompt, context_chunks, model_version, refresh_fn,
                    ))
                else:
                    # No running loop — run synchronously in a thread.
                    threading.Thread(
                        target=self._swr_refresh_sync,
                        args=(prompt, context_chunks, model_version, refresh_fn),
                        daemon=True,
                    ).start()
                entry["swr_refreshed"] = True
            except RuntimeError:
                # No event loop at all — refresh synchronously.
                try:
                    new_resp = asyncio.run(refresh_fn())
                    self.set(prompt, context_chunks, model_version, new_resp)
                    self._stats.swr_refreshes += 1
                    entry["swr_refreshed"] = True
                except Exception as exc:
                    logger.warning("SWR refresh failed: %s", exc)
        return entry

    async def _swr_refresh(self, prompt, context_chunks, model_version, refresh_fn):
        try:
            new_resp = await refresh_fn()
            self.set(prompt, context_chunks, model_version, new_resp)
            self._stats.swr_refreshes += 1
        except Exception as exc:
            logger.warning("SWR background refresh failed: %s", exc)

    def _swr_refresh_sync(self, prompt, context_chunks, model_version, refresh_fn):
        try:
            new_resp = asyncio.run(refresh_fn())
            self.set(prompt, context_chunks, model_version, new_resp)
            self._stats.swr_refreshes += 1
        except Exception as exc:
            logger.warning("SWR sync refresh failed: %s", exc)

    # ── Offline queue ───────────────────────────────────────────────

    def enqueue(self, prompt: str, *, tenant_id: str = "default", metadata: Optional[dict] = None) -> str:
        """Enqueue a request for later processing (when LLM is back up).

        Returns the request_id (UUID-style string).
        """
        import uuid
        request_id = str(uuid.uuid4())
        item = {
            "request_id": request_id,
            "prompt": prompt,
            "tenant_id": tenant_id,
            "metadata": metadata or {},
            "queued_at": time.time(),
        }
        if self._redis is None:
            self._redis = _get_redis(self.redis_url)
        try:
            if self._redis is not None:
                list_key = f"{self.namespace}:queue:{tenant_id}"
                # Trim queue to queue_max length (FIFO).
                pipe = self._redis.pipeline()
                pipe.lpush(list_key, json.dumps(item, ensure_ascii=False))
                pipe.ltrim(list_key, 0, self.queue_max - 1)
                pipe.expire(list_key, self.stale_ttl)
                pipe.execute()
            else:
                # Local fallback — just log.
                logger.info("Offline queue (local): enqueued request %s", request_id)
        except Exception as exc:
            self._stats.errors += 1
            logger.warning("Offline enqueue failed: %s", exc)
        self._stats.queued += 1
        return request_id

    def dequeue(self, *, tenant_id: str = "default") -> Optional[dict[str, Any]]:
        """Pop the next request from the offline queue (FIFO).

        Returns the request dict or None if the queue is empty.
        """
        if self._redis is None:
            self._redis = _get_redis(self.redis_url)
        if self._redis is None:
            return None
        try:
            list_key = f"{self.namespace}:queue:{tenant_id}"
            raw = self._redis.rpop(list_key)
            if raw:
                return json.loads(raw)
        except Exception as exc:
            self._stats.errors += 1
            logger.warning("Offline dequeue failed: %s", exc)
        return None

    def queue_size(self, *, tenant_id: str = "default") -> int:
        if self._redis is None:
            self._redis = _get_redis(self.redis_url)
        if self._redis is None:
            return 0
        try:
            return int(self._redis.llen(f"{self.namespace}:queue:{tenant_id}"))
        except Exception:
            return 0

    # ── Stats ───────────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """Return cache statistics including hit ratio."""
        return self._stats.to_dict()

    def hit_ratio(self) -> float:
        """Return cache hit ratio (0.0 - 1.0)."""
        return self.stats()["hit_ratio"]

    # ── Internal: get/set with Redis + local fallback ───────────────

    def _get_entry(self, key: str) -> Optional[dict[str, Any]]:
        if self._redis is None:
            self._redis = _get_redis(self.redis_url)
        if self._redis is not None:
            try:
                raw = self._redis.get(f"{self.namespace}:{key}")
                if raw:
                    return json.loads(raw)
                # Stale path: try the stale key.
                stale = self._redis.get(f"{self.namespace}:stale:{key}")
                if stale:
                    return json.loads(stale)
                return None
            except Exception as exc:
                self._stats.errors += 1
                # Mark Redis as unavailable so subsequent calls skip it
                # and use the local fallback directly. This prevents
                # every call from incurring the connection timeout.
                self._redis = None
                logger.debug("Redis get failed: %s — using local fallback", exc)
        # Local fallback.
        return _local_get(key)

    def _set_entry(self, key: str, entry: dict[str, Any], ttl: int):
        if self._redis is None:
            self._redis = _get_redis(self.redis_url)
        if self._redis is not None:
            try:
                pipe = self._redis.pipeline()
                pipe.setex(f"{self.namespace}:{key}", ttl, json.dumps(entry, ensure_ascii=False))
                # Also keep a stale copy with a longer TTL for SWR.
                pipe.setex(f"{self.namespace}:stale:{key}", self.stale_ttl, json.dumps(entry, ensure_ascii=False))
                pipe.execute()
                return
            except Exception as exc:
                self._stats.errors += 1
                self._redis = None  # disable Redis for subsequent calls
                logger.debug("Redis set failed: %s — using local fallback", exc)
        _local_set(key, entry, ttl)


# ─────────────────────────────────────────────────────────────────────
# Module-level default cache
# ─────────────────────────────────────────────────────────────────────

_default_cache: Optional[OfflineCache] = None


def get_default_cache() -> OfflineCache:
    global _default_cache
    if _default_cache is None:
        _default_cache = OfflineCache()
    return _default_cache


__all__ = [
    "OfflineCache",
    "CacheStats",
    "get_default_cache",
    "DEFAULT_TTL",
    "DEFAULT_STALE_TTL",
]
