"""
HSAAI Standardized Performance Metrics (v1.0)
=============================================

Centralised Prometheus metrics for the HSAAI platform. All services
import these so dashboards and alerting rules have consistent labels
and buckets.

Metric catalogue
----------------
  - `hsaai_request_latency_seconds`    — HTTP request latency (Histogram)
  - `hsaai_token_usage_total`          — LLM token consumption (Counter)
  - `hsaai_cache_hits_total`           — cache hits (Counter)
  - `hsaai_cache_misses_total`         — cache misses (Counter)
  - `hsaai_db_query_duration_seconds`  — DB query latency (Histogram)
  - `hsaai_in_flight_requests`         — concurrent in-flight requests (Gauge)
  - `hsaai_errors_total`               — application errors (Counter)

Label conventions
-----------------
Standard labels on every metric:
  - `service`     — e.g. "rag_engine", "llm_gateway"
  - `tenant_id`   — multi-tenant scoping
  - `endpoint`    — FastAPI route path (for HTTP metrics)
  - `method`      — HTTP method (for HTTP metrics)

Histogram buckets
-----------------
Tuned for AI workloads:
  - HTTP latency: 5ms, 10ms, 25ms, 50ms, 100ms, 250ms, 500ms, 1s, 2.5s, 5s, 10s
  - DB query:     1ms, 5ms, 10ms, 25ms, 50ms, 100ms, 250ms, 500ms, 1s, 5s
  - LLM latency:  50ms, 100ms, 500ms, 1s, 5s, 30s, 60s, 120s

Usage
-----
    from packages.common.performance.metrics import (
        record_request, record_token_usage, record_cache_hit, record_db_query,
        metrics_registry,
    )

    # In FastAPI middleware
    @app.middleware("http")
    async def metrics_middleware(request, call_next):
        with record_request(service="rag_engine", endpoint=request.url.path,
                            method=request.method, tenant_id=request.state.tenant_id):
            return await call_next(request)

    # After LLM call
    record_token_usage(service="llm_gateway", tenant_id="t1",
                       model="qwen2.5-14b", input_tokens=120, output_tokens=80)
"""
from __future__ import annotations

import os
import time
import logging
from contextlib import contextmanager
from typing import Iterator, Optional

logger = logging.getLogger("hsaai.performance.metrics")

# ── Prometheus (optional) ──
try:
    from prometheus_client import (
        Counter, Gauge, Histogram, Registry, REGISTRY,
        generate_latest, CONTENT_TYPE_LATEST,
    )
    _PROMETHEUS_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PROMETHEUS_AVAILABLE = False
    REGISTRY = None  # type: ignore

    def generate_latest(*args, **kwargs):  # type: ignore
        return b""

    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"


# ═══════════════════════════════════════════════════════════════════
# Histogram buckets tuned for AI workloads
# ═══════════════════════════════════════════════════════════════════
# Per task spec: 50ms, 100ms, 500ms, 1s, 5s, 30s (plus surrounding
# boundary buckets to avoid spillover at the edges).
BUCKETS_HTTP_LATENCY = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
BUCKETS_LLM_LATENCY = (0.05, 0.1, 0.5, 1.0, 5.0, 30.0, 60.0, 120.0)
BUCKETS_DB_QUERY = (0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 5.0)


# ═══════════════════════════════════════════════════════════════════
# Metric definitions (lazy-initialised on first use)
# ═══════════════════════════════════════════════════════════════════
_metrics: dict[str, object] = {}


def _init_metrics() -> None:
    """Initialise all metrics once. Idempotent."""
    if not _PROMETHEUS_AVAILABLE:
        return
    if _metrics:
        return

    _metrics["request_latency"] = Histogram(
        "hsaai_request_latency_seconds",
        "HTTP request latency in seconds",
        labelnames=["service", "endpoint", "method", "tenant_id", "status"],
        buckets=BUCKETS_HTTP_LATENCY,
    )
    _metrics["llm_latency"] = Histogram(
        "hsaai_llm_latency_seconds",
        "LLM inference latency in seconds",
        labelnames=["service", "model", "tenant_id", "operation"],
        buckets=BUCKETS_LLM_LATENCY,
    )
    _metrics["token_usage"] = Counter(
        "hsaai_token_usage_total",
        "Total LLM tokens consumed",
        labelnames=["service", "tenant_id", "model", "direction"],  # direction: input|output
    )
    _metrics["cache_hits"] = Counter(
        "hsaai_cache_hits_total",
        "Total cache hits",
        labelnames=["service", "tier", "tenant_id"],
    )
    _metrics["cache_misses"] = Counter(
        "hsaai_cache_misses_total",
        "Total cache misses",
        labelnames=["service", "tenant_id"],
    )
    _metrics["db_query_duration"] = Histogram(
        "hsaai_db_query_duration_seconds",
        "Database query latency in seconds",
        labelnames=["service", "table", "operation"],
        buckets=BUCKETS_DB_QUERY,
    )
    _metrics["in_flight_requests"] = Gauge(
        "hsaai_in_flight_requests",
        "Currently in-flight HTTP requests",
        labelnames=["service", "tenant_id"],
    )
    _metrics["errors"] = Counter(
        "hsaai_errors_total",
        "Total application errors",
        labelnames=["service", "type", "tenant_id"],
    )


# ═══════════════════════════════════════════════════════════════════
# Recording helpers
# ═══════════════════════════════════════════════════════════════════
@contextmanager
def record_request(
    *,
    service: str,
    endpoint: str,
    method: str,
    tenant_id: str = "default",
) -> Iterator[None]:
    """Context manager: record HTTP request latency + in-flight gauge.

    Usage:
        with record_request(service="rag_engine", endpoint="/v1/search",
                            method="POST", tenant_id=tid):
            response = await call_next(request)
    """
    started = time.perf_counter()
    if _PROMETHEUS_AVAILABLE:
        _init_metrics()
        _metrics["in_flight_requests"].labels(service=service, tenant_id=tenant_id).inc()
    try:
        yield
    finally:
        if _PROMETHEUS_AVAILABLE:
            elapsed = time.perf_counter() - started
            _metrics["request_latency"].labels(
                service=service, endpoint=endpoint, method=method,
                tenant_id=tenant_id, status="200",
            ).observe(elapsed)
            _metrics["in_flight_requests"].labels(service=service, tenant_id=tenant_id).dec()


@contextmanager
def record_db_query(
    *,
    service: str,
    table: str,
    operation: str = "select",
) -> Iterator[None]:
    """Context manager: record DB query latency.

    Usage:
        with record_db_query(service="backend_core", table="messages", operation="insert"):
            db.add(msg); db.commit()
    """
    if not _PROMETHEUS_AVAILABLE:
        yield
        return
    _init_metrics()
    started = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - started
        _metrics["db_query_duration"].labels(
            service=service, table=table, operation=operation,
        ).observe(elapsed)


def record_token_usage(
    *,
    service: str,
    tenant_id: str,
    model: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> None:
    """Record LLM token usage.

    Usage:
        record_token_usage(service="llm_gateway", tenant_id="t1",
                           model="qwen2.5-14b",
                           input_tokens=120, output_tokens=80)
    """
    if not _PROMETHEUS_AVAILABLE:
        return
    _init_metrics()
    if input_tokens:
        _metrics["token_usage"].labels(
            service=service, tenant_id=tenant_id, model=model, direction="input",
        ).inc(input_tokens)
    if output_tokens:
        _metrics["token_usage"].labels(
            service=service, tenant_id=tenant_id, model=model, direction="output",
        ).inc(output_tokens)


def record_cache_hit(*, service: str, tier: str, tenant_id: str = "default") -> None:
    if not _PROMETHEUS_AVAILABLE:
        return
    _init_metrics()
    _metrics["cache_hits"].labels(service=service, tier=tier, tenant_id=tenant_id).inc()


def record_cache_miss(*, service: str, tenant_id: str = "default") -> None:
    if not _PROMETHEUS_AVAILABLE:
        return
    _init_metrics()
    _metrics["cache_misses"].labels(service=service, tenant_id=tenant_id).inc()


def record_error(*, service: str, error_type: str, tenant_id: str = "default") -> None:
    if not _PROMETHEUS_AVAILABLE:
        return
    _init_metrics()
    _metrics["errors"].labels(
        service=service, type=error_type, tenant_id=tenant_id,
    ).inc()


@contextmanager
def record_llm_call(
    *,
    service: str,
    model: str,
    tenant_id: str = "default",
    operation: str = "generate",
) -> Iterator[None]:
    """Context manager: record LLM call latency.

    Usage:
        with record_llm_call(service="llm_gateway", model="qwen2.5-14b",
                             tenant_id=tid, operation="generate"):
            result = await llm.generate(prompt)
    """
    if not _PROMETHEUS_AVAILABLE:
        yield
        return
    _init_metrics()
    started = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - started
        _metrics["llm_latency"].labels(
            service=service, model=model, tenant_id=tenant_id, operation=operation,
        ).observe(elapsed)


# ═══════════════════════════════════════════════════════════════════
# FastAPI integration
# ═══════════════════════════════════════════════════════════════════
def metrics_endpoint():
    """Return a FastAPI route handler that exposes /metrics.

    Usage:
        from fastapi import FastAPI
        from packages.common.performance.metrics import metrics_endpoint

        app = FastAPI()
        app.add_route("/metrics", metrics_endpoint())
    """
    from fastapi import Response

    async def _handler():
        if not _PROMETHEUS_AVAILABLE:
            return Response(
                content="prometheus_client not installed",
                media_type="text/plain",
                status_code=503,
            )
        _init_metrics()
        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST,
        )

    return _handler


def metrics_registry():
    """Return the global Prometheus registry (or None if unavailable)."""
    return REGISTRY if _PROMETHEUS_AVAILABLE else None


__all__ = [
    # Buckets
    "BUCKETS_HTTP_LATENCY",
    "BUCKETS_LLM_LATENCY",
    "BUCKETS_DB_QUERY",
    # Recording helpers
    "record_request",
    "record_db_query",
    "record_token_usage",
    "record_cache_hit",
    "record_cache_miss",
    "record_error",
    "record_llm_call",
    # FastAPI integration
    "metrics_endpoint",
    "metrics_registry",
]
