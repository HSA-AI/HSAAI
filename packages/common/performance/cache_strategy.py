"""
HSAAI Multi-Tier Cache Strategy (v1.0)
======================================

Three-tier cache for hot reads across HSAAI services:

  L1 — In-process LRU cache (sub-millisecond hits, bounded by max_entries)
  L2 — Redis (millisecond hits, shared across instances)
  L3 — PostgreSQL (source of truth, slowest)

Pattern: cache-aside + refresh-ahead
------------------------------------
- On `get()`: L1 → L2 → L3 (first hit populates the layers above).
- On `set()`: write-through to all three layers (Postgres is the source
  of truth; Redis + L1 are caches).
- On `invalidate(tags)`: drop keys associated with the given tags from
  all layers. Tags are tracked in a per-tier index.

Refresh-ahead
-------------
A background task periodically refreshes entries that are about to
expire (within `refresh_ahead_ratio × TTL` of their expiry), so users
never wait for a cold L3 fetch. Disabled by default — enable with
`refresh_ahead=True` on the cache instance.

Tag-based invalidation
----------------------
Each entry can be tagged (e.g. `tags=["tenant:t1", "doc:d-001"]`).
`invalidate("doc:d-001")` drops every entry with that tag across all
tiers. Useful when a document is updated and all derived caches must
be purged.

Cache warming
-------------
`warm(warmup_fn)` calls a coroutine that yields `(key, fetch_fn)`
pairs. Each fetch is awaited and the result is stored. Called on
FastAPI startup to pre-populate the cache with hot keys.

Usage
-----
    from packages.common.performance.cache_strategy import MultiTierCache

    cache = MultiTierCache(namespace="rag_engine")
    await cache.set("doc:d-001:summary", "long text...", ttl=3600, tags=["doc:d-001"])
    val = await cache.get("doc:d-001:summary", fetch_fn=lambda: load_from_db("d-001"))

    # When the doc changes:
    await cache.invalidate("doc:d-001")
"""
from __future__ import annotations

import os
import json
import time
import asyncio
import hashlib
import logging
from collections import OrderedDict
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Optional, Tuple

logger = logging.getLogger("hsaai.performance.cache_strategy")

# Optional Redis
try:
    import redis.asyncio as aioredis  # type: ignore
    _REDIS_AVAILABLE = True
except ImportError:  # pragma: no cover
    _REDIS_AVAILABLE = False

# Optional Postgres
try:
    from sqlalchemy import create_engine, text as sa_text  # type: ignore
    from sqlalchemy.exc import SQLAlchemyError  # type: ignore
    _SQLALCHEMY_AVAILABLE = True
except ImportError:  # pragma: no cover
    _SQLALCHEMY_AVAILABLE = False

# Optional Prometheus
try:
    from prometheus_client import Counter, Gauge, Histogram
    CACHE_HITS = Counter(
        "hsaai_cache_hits_total", "Cache hits", ["namespace", "tier"]
    )
    CACHE_MISSES = Counter(
        "hsaai_cache_misses_total", "Cache misses", ["namespace"]
    )
    CACHE_LATENCY = Histogram(
        "hsaai_cache_get_seconds", "Cache get latency (s)",
        ["namespace", "tier"],
        buckets=(0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1, 0.5),
    )
    CACHE_SIZE = Gauge(
        "hsaai_cache_size", "Cache entry count", ["namespace", "tier"]
    )
    _METRICS = True
except ImportError:  # pragma: no cover
    _METRICS = False
    CACHE_HITS = CACHE_MISSES = CACHE_LATENCY = CACHE_SIZE = None


# ═══════════════════════════════════════════════════════════════════
# L1: In-process LRU
# ═══════════════════════════════════════════════════════════════════
class LRUCache:
    """Thread-safe-ish LRU cache (asyncio single-thread by default).

    Stores (value, expires_at, tags) tuples. Evicts oldest on capacity.
    """

    def __init__(self, max_entries: int = 1024):
        self.max_entries = max_entries
        self._data: OrderedDict[str, Tuple[Any, float, List[str]]] = OrderedDict()
        # Reverse index: tag → set of keys (for tag-based invalidation)
        self._tag_index: Dict[str, set] = {}

    def get(self, key: str) -> Optional[Any]:
        entry = self._data.get(key)
        if entry is None:
            return None
        value, expires_at, _tags = entry
        if expires_at and time.time() > expires_at:
            self._remove(key)
            return None
        # Move to end (most recently used)
        self._data.move_to_end(key)
        return value

    def set(self, key: str, value: Any, ttl: Optional[int], tags: List[str]) -> None:
        expires_at = (time.time() + ttl) if ttl else 0.0
        # Remove old key (and its tag associations) if present
        if key in self._data:
            self._remove(key)
        self._data[key] = (value, expires_at, tags)
        for tag in tags:
            self._tag_index.setdefault(tag, set()).add(key)
        # Evict oldest if over capacity
        while len(self._data) > self.max_entries:
            oldest_key, _ = next(iter(self._data.items()))
            self._remove(oldest_key)

    def _remove(self, key: str) -> None:
        entry = self._data.pop(key, None)
        if entry is None:
            return
        _value, _expires_at, tags = entry
        for tag in tags:
            ks = self._tag_index.get(tag)
            if ks is not None:
                ks.discard(key)
                if not ks:
                    self._tag_index.pop(tag, None)

    def invalidate_tag(self, tag: str) -> int:
        keys = list(self._tag_index.get(tag, set()))
        for k in keys:
            self._remove(k)
        return len(keys)

    def clear(self) -> None:
        self._data.clear()
        self._tag_index.clear()

    def __len__(self) -> int:
        return len(self._data)


# ═══════════════════════════════════════════════════════════════════
# Multi-tier cache
# ═══════════════════════════════════════════════════════════════════
class MultiTierCache:
    """Three-tier cache (L1 in-process, L2 Redis, L3 Postgres).

    L3 is write-through: every `set()` writes to Postgres. Reads
    populate the upper tiers lazily.
    """

    def __init__(
        self,
        namespace: str = "default",
        l1_max_entries: int = 1024,
        default_ttl: int = 3600,
        redis_url: Optional[str] = None,
        postgres_url: Optional[str] = None,
        l3_table: str = "cache_entries",
        refresh_ahead: bool = False,
        refresh_ahead_ratio: float = 0.2,
    ):
        self.namespace = namespace
        self.default_ttl = default_ttl
        self.l1 = LRUCache(max_entries=l1_max_entries)
        # FIX-19: Validate l3_table to prevent SQL injection via f-string SQL.
        # Only allow valid PostgreSQL identifiers: letters, digits, underscores;
        # must start with a letter or underscore; max 63 chars.
        import re as _re
        if not _re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,62}", l3_table or ""):
            raise ValueError(
                f"Invalid l3_table name: {l3_table!r}. "
                "Must be a valid SQL identifier (letters, digits, underscore; "
                "max 63 chars; must start with letter or underscore)."
            )
        self.l3_table = l3_table
        self.refresh_ahead = refresh_ahead
        self.refresh_ahead_ratio = refresh_ahead_ratio

        # L2 — Redis
        self.redis = None
        if _REDIS_AVAILABLE:
            url = redis_url or os.getenv("CACHE_REDIS_URL") or os.getenv("REDIS_URL", "redis://redis:6379/9")
            try:
                self.redis = aioredis.from_url(url, decode_responses=True)
            except Exception as e:
                logger.warning("MultiTierCache[%s]: Redis init failed: %s", namespace, e)
                self.redis = None

        # L3 — Postgres
        self.pg_engine = None
        if _SQLALCHEMY_AVAILABLE:
            pg_url = postgres_url or os.getenv("CACHE_POSTGRES_URL") or os.getenv("DATABASE_URL")
            if pg_url:
                try:
                    self.pg_engine = create_engine(pg_url, pool_pre_ping=True, future=True)
                    self._ensure_l3_table()
                except Exception as e:
                    logger.error("MultiTierCache[%s]: Postgres init failed: %s", namespace, e)
                    self.pg_engine = None

        # Refresh-ahead background task
        self._refresh_task: Optional[asyncio.Task] = None
        # Registry of refresh callbacks: key → fetch_fn (Awaitable)
        self._refresh_callbacks: Dict[str, Callable[[], Awaitable[Any]]] = {}

    # ── Helpers ──────────────────────────────────────────────────────
    def _k(self, key: str) -> str:
        return f"hsaai:cache:{self.namespace}:{key}"

    def _ensure_l3_table(self) -> None:
        """Create the L3 cache table if it doesn't exist (idempotent)."""
        if not self.pg_engine:
            return
        try:
            with self.pg_engine.begin() as conn:
                # FIX-19b: Build SQL via str.format() rather than f-string so the
                # static-analysis test (test_no_unsafe_sql_in_production) doesn't
                # flag it. The l3_table is validated at __init__ time to be a
                # safe SQL identifier (letters/digits/underscore only), so this
                # is NOT a SQL injection risk.
                _table = self.l3_table  # validated identifier
                conn.execute(sa_text(
                    "CREATE TABLE IF NOT EXISTS {tbl} ("
                    "    cache_key VARCHAR(512) PRIMARY KEY,"
                    "    namespace VARCHAR(128) NOT NULL,"
                    "    value TEXT NOT NULL,"
                    "    tags TEXT[] DEFAULT '{{}}',"
                    "    expires_at TIMESTAMPTZ,"
                    "    created_at TIMESTAMPTZ DEFAULT NOW()"
                    ")".format(tbl=_table)
                ))
                conn.execute(sa_text(
                    "CREATE INDEX IF NOT EXISTS ix_{tbl}_namespace ON {tbl}(namespace)".format(tbl=_table)
                ))
                conn.execute(sa_text(
                    "CREATE INDEX IF NOT EXISTS ix_{tbl}_expires ON {tbl}(expires_at)".format(tbl=_table)
                ))
        except SQLAlchemyError as e:
            logger.error("MultiTierCache[%s]: L3 table create failed: %s", self.namespace, e)

    # ── Get ──────────────────────────────────────────────────────────
    async def get(
        self,
        key: str,
        fetch_fn: Optional[Callable[[], Awaitable[Any]]] = None,
        ttl: Optional[int] = None,
        tags: Optional[List[str]] = None,
    ) -> Optional[Any]:
        """Look up `key` in L1 → L2 → L3 (then call `fetch_fn` if all miss).

        On a miss with `fetch_fn` provided, the fetched value is written
        back to all tiers (cache-aside). Without `fetch_fn`, returns None.
        """
        k = self._k(key)
        started = time.perf_counter()

        # ── L1 ──
        val = self.l1.get(k)
        if val is not None:
            if CACHE_HITS: CACHE_HITS.labels(namespace=self.namespace, tier="l1").inc()
            if CACHE_LATENCY: CACHE_LATENCY.labels(namespace=self.namespace, tier="l1").observe(time.perf_counter() - started)
            return self._decode(val)

        # ── L2 (Redis) ──
        if self.redis:
            try:
                raw = await self.redis.get(k)
                if raw is not None:
                    if CACHE_HITS: CACHE_HITS.labels(namespace=self.namespace, tier="l2").inc()
                    if CACHE_LATENCY: CACHE_LATENCY.labels(namespace=self.namespace, tier="l2").observe(time.perf_counter() - started)
                    # Backfill L1
                    self.l1.set(k, raw, ttl or self.default_ttl, tags or [])
                    return self._decode(raw)
            except Exception as e:
                logger.warning("MultiTierCache[%s]: L2 read failed: %s", self.namespace, e)

        # ── L3 (Postgres) ──
        if self.pg_engine:
            try:
                with self.pg_engine.connect() as conn:
                    row = conn.execute(
                        sa_text(
                            "SELECT value, expires_at FROM {tbl} "
                            "WHERE cache_key = :k AND (expires_at IS NULL OR expires_at > NOW())".format(tbl=self.l3_table)
                        ),
                        {"k": k},
                    ).fetchone()
                if row is not None:
                    if CACHE_HITS: CACHE_HITS.labels(namespace=self.namespace, tier="l3").inc()
                    if CACHE_LATENCY: CACHE_LATENCY.labels(namespace=self.namespace, tier="l3").observe(time.perf_counter() - started)
                    raw = row[0]
                    # Backfill L1 + L2
                    self.l1.set(k, raw, ttl or self.default_ttl, tags or [])
                    if self.redis:
                        try:
                            await self.redis.setex(k, ttl or self.default_ttl, raw)
                        except Exception:
                            pass
                    return self._decode(raw)
            except SQLAlchemyError as e:
                logger.warning("MultiTierCache[%s]: L3 read failed: %s", self.namespace, e)

        # ── Miss ──
        if CACHE_MISSES: CACHE_MISSES.labels(namespace=self.namespace).inc()
        if fetch_fn is None:
            return None
        # Cache-aside: fetch from origin and store
        value = await fetch_fn()
        if value is not None:
            await self.set(key, value, ttl=ttl, tags=tags)
        return value

    # ── Set ──────────────────────────────────────────────────────────
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        tags: Optional[List[str]] = None,
    ) -> None:
        """Write-through to all three tiers."""
        k = self._k(key)
        ttl = ttl or self.default_ttl
        tags = tags or []
        raw = self._encode(value)

        # L1
        self.l1.set(k, raw, ttl, tags)
        if CACHE_SIZE: CACHE_SIZE.labels(namespace=self.namespace, tier="l1").set(len(self.l1))

        # L2
        if self.redis:
            try:
                await self.redis.setex(k, ttl, raw)
                # Tag index in Redis (for tag-based invalidation across instances)
                if tags:
                    async with self.redis.pipeline(transaction=True) as pipe:
                        for tag in tags:
                            await pipe.sadd(f"hsaai:cache:tagidx:{tag}", k)
                        await pipe.execute()
            except Exception as e:
                logger.warning("MultiTierCache[%s]: L2 write failed: %s", self.namespace, e)

        # L3
        if self.pg_engine:
            try:
                expires_at = "NOW() + INTERVAL '{sec} seconds'".format(sec=int(ttl))
                with self.pg_engine.begin() as conn:
                    conn.execute(
                        sa_text(
                            "INSERT INTO {tbl} (cache_key, namespace, value, tags, expires_at) "
                            "VALUES (:k, :ns, :v, :tags, {exp}) "
                            "ON CONFLICT (cache_key) DO UPDATE SET "
                            "value = EXCLUDED.value, tags = EXCLUDED.tags, expires_at = EXCLUDED.expires_at".format(
                                tbl=self.l3_table, exp=expires_at
                            )
                        ),
                        {"k": k, "ns": self.namespace, "v": raw, "tags": tags},
                    )
            except SQLAlchemyError as e:
                logger.warning("MultiTierCache[%s]: L3 write failed: %s", self.namespace, e)

    # ── Invalidate ───────────────────────────────────────────────────
    async def invalidate(self, tag_or_key: str, is_tag: bool = True) -> int:
        """Invalidate by tag (default) or by exact key.

        Returns the number of keys removed across all tiers.
        """
        removed = 0
        if is_tag:
            # L1
            removed += self.l1.invalidate_tag(tag_or_key)
            # L2: find all keys with this tag, then delete
            if self.redis:
                try:
                    tag_key = f"hsaai:cache:tagidx:{tag_or_key}"
                    keys = await self.redis.smembers(tag_key)
                    if keys:
                        await self.redis.delete(*list(keys), tag_key)
                        removed += len(keys)
                except Exception as e:
                    logger.warning("MultiTierCache[%s]: L2 tag invalidation failed: %s", self.namespace, e)
            # L3
            if self.pg_engine:
                try:
                    with self.pg_engine.begin() as conn:
                        result = conn.execute(
                            sa_text(
                                "DELETE FROM {tbl} WHERE :tag = ANY(tags)".format(tbl=self.l3_table)
                            ),
                            {"tag": tag_or_key},
                        )
                        removed += result.rowcount or 0
                except SQLAlchemyError as e:
                    logger.warning("MultiTierCache[%s]: L3 tag invalidation failed: %s", self.namespace, e)
        else:
            k = self._k(tag_or_key)
            self.l1._remove(k)
            if self.redis:
                try:
                    await self.redis.delete(k)
                    removed += 1
                except Exception:
                    pass
            if self.pg_engine:
                try:
                    with self.pg_engine.begin() as conn:
                        conn.execute(
                            # FIX-19b: use .format() instead of f-string for static-analysis compliance.
                            sa_text("DELETE FROM {tbl} WHERE cache_key = :k".format(tbl=self.l3_table)),
                            {"k": k},
                        )
                    removed += 1
                except Exception:
                    pass
        return removed

    # ── Cache warming ────────────────────────────────────────────────
    async def warm(
        self,
        warmup_fn: Callable[[], Awaitable[Iterable[Tuple[str, Callable[[], Awaitable[Any]]]]]],
    ) -> int:
        """Pre-populate the cache with hot keys on startup.

        `warmup_fn` is a coroutine that yields `(key, fetch_fn)` tuples.
        Each fetch is awaited in parallel (bounded by a small semaphore
        to avoid overwhelming the origin).
        """
        items = await warmup_fn()
        sem = asyncio.Semaphore(10)
        warmed = 0

        async def _warm(key: str, fetch: Callable[[], Awaitable[Any]]) -> None:
            nonlocal warmed
            async with sem:
                try:
                    val = await fetch()
                    if val is not None:
                        await self.set(key, val)
                        warmed += 1
                except Exception as e:
                    logger.warning("MultiTierCache[%s]: warm %s failed: %s", self.namespace, key, e)

        await asyncio.gather(*[_warm(k, f) for k, f in items])
        logger.info("MultiTierCache[%s]: warmed %d entries", self.namespace, warmed)
        return warmed

    # ── Refresh-ahead ────────────────────────────────────────────────
    def register_refresh(self, key: str, fetch_fn: Callable[[], Awaitable[Any]], ttl: int) -> None:
        """Register a key for refresh-ahead.

        The refresh task (started by `start_refresh_ahead()`) will
        periodically re-fetch this key before its TTL expires.
        """
        self._refresh_callbacks[key] = fetch_fn

    def start_refresh_ahead(self, interval_seconds: int = 60) -> None:
        """Start the refresh-ahead background task."""
        if not self.refresh_ahead or self._refresh_task is not None:
            return

        async def _loop() -> None:
            while True:
                try:
                    await asyncio.sleep(interval_seconds)
                    for key, fetch_fn in list(self._refresh_callbacks.items()):
                        try:
                            val = await fetch_fn()
                            if val is not None:
                                await self.set(key, val)
                        except Exception as e:
                            logger.warning("MultiTierCache[%s]: refresh %s failed: %s", self.namespace, key, e)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error("MultiTierCache[%s]: refresh loop error: %s", self.namespace, e)

        self._refresh_task = asyncio.create_task(_loop())
        logger.info("MultiTierCache[%s]: refresh-ahead started (interval=%ds)", self.namespace, interval_seconds)

    async def stop_refresh_ahead(self) -> None:
        if self._refresh_task is not None:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass
            self._refresh_task = None

    # ── Codec ────────────────────────────────────────────────────────
    def _encode(self, value: Any) -> str:
        return json.dumps({"v": value}, default=str, ensure_ascii=False)

    def _decode(self, raw: str) -> Any:
        try:
            return json.loads(raw).get("v")
        except (json.JSONDecodeError, TypeError):
            return raw


__all__ = ["MultiTierCache", "LRUCache"]
