"""
HSAAI Performance common package.

Public API:
    - connection_pool: Centralised httpx AsyncClient pool with circuit
                       breaker integration and connection reuse metrics.
    - cache_strategy:  Multi-tier cache (L1 LRU / L2 Redis / L3 Postgres)
                       with tag-based invalidation + refresh-ahead.
    - metrics:         Standardised Prometheus metrics for the platform.
"""
from packages.common.performance.connection_pool import (
    get_client, request, get_pool_stats, get_all_pool_stats, close_pool, close_all,
)
from packages.common.performance.cache_strategy import MultiTierCache, LRUCache
from packages.common.performance.metrics import (
    record_request, record_db_query, record_token_usage,
    record_cache_hit, record_cache_miss, record_error, record_llm_call,
    metrics_endpoint, metrics_registry,
    BUCKETS_HTTP_LATENCY, BUCKETS_LLM_LATENCY, BUCKETS_DB_QUERY,
)

__all__ = [
    # connection_pool
    "get_client", "request", "get_pool_stats", "get_all_pool_stats",
    "close_pool", "close_all",
    # cache_strategy
    "MultiTierCache", "LRUCache",
    # metrics
    "record_request", "record_db_query", "record_token_usage",
    "record_cache_hit", "record_cache_miss", "record_error", "record_llm_call",
    "metrics_endpoint", "metrics_registry",
    "BUCKETS_HTTP_LATENCY", "BUCKETS_LLM_LATENCY", "BUCKETS_DB_QUERY",
]
