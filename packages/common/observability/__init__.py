"""
HSAAI Observability Stack (Phase 12)
======================================
Unified observability for all services:
  - Structured logging (JSON, correlation IDs)
  - Metrics (Prometheus-compatible)
  - Distributed tracing (OpenTelemetry → Tempo)
  - Dashboards (Grafana provisioning)
  - Alerting (Prometheus alerting rules + Alertmanager)

Single import gives any service full observability:
    from packages.common.observability import setup_observability
    setup_observability("my-service")
"""
import os
import sys
import json
import time
import logging
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from contextlib import asynccontextmanager

# OpenTelemetry
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor

logger = logging.getLogger(__name__)
_initialized = False


# ═══════════════════════════════════════════════════════════════════
# STRUCTURED LOGGING (JSON with correlation IDs)
# ═══════════════════════════════════════════════════════════════════
class JSONFormatter(logging.Formatter):
    """JSON log formatter for Loki/Elasticsearch ingestion."""

    def format(self, record: logging.LogRecord) -> str:
        # Extract trace context if available
        span = trace.get_current_span()
        trace_id = ""
        span_id = ""
        if span and span.is_recording():
            ctx = span.get_span_context()
            trace_id = f"{ctx.trace_id:032x}"
            span_id = f"{ctx.span_id:016x}"

        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": os.getenv("OTEL_SERVICE_NAME", "unknown"),
            "environment": os.getenv("DEPLOY_ENV", "production"),
            "host": os.uname().nodename,
            "trace_id": trace_id,
            "span_id": span_id,
        }
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in {"args", "msg", "levelname", "levelno", "pathname",
                          "filename", "module", "exc_info", "exc_text", "stack_info",
                          "lineno", "funcName", "created", "msecs", "relativeCreated",
                          "thread", "threadName", "processName", "process", "name",
                          "taskName", "message"}:
                try:
                    json.dumps(value)  # verify serializable
                    log_entry[key] = value
                except (TypeError, ValueError):
                    log_entry[key] = str(value)
        return json.dumps(log_entry, default=str, ensure_ascii=False)


def setup_logging(service_name: str, level: str = "INFO"):
    """Configure structured JSON logging."""
    logging.basicConfig(
        level=level,
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    # Replace formatter on root logger
    for handler in logging.getLogger().handlers:
        handler.setFormatter(JSONFormatter())
    # Set service name for log entries
    os.environ["OTEL_SERVICE_NAME"] = service_name
    logger.info(f"Logging configured for {service_name}")


# ═══════════════════════════════════════════════════════════════════
# METRICS (Prometheus-compatible via OTLP)
# ═══════════════════════════════════════════════════════════════════
class HSAAIMetrics:
    """Standard metrics for every HSAAI service."""

    def __init__(self, service_name: str):
        self.meter = metrics.get_meter(service_name)

        # Request metrics
        self.request_counter = self.meter.create_counter(
            "hsaai_requests_total",
            description="Total requests by endpoint and status",
            unit="1",
        )
        self.request_duration = self.meter.create_histogram(
            "hsaai_request_duration_seconds",
            description="Request duration in seconds",
            unit="s",
        )

        # Error metrics
        self.error_counter = self.meter.create_counter(
            "hsaai_errors_total",
            description="Total errors by type",
            unit="1",
        )

        # LLM-specific metrics
        self.llm_tokens_counter = self.meter.create_counter(
            "hsaai_llm_tokens_total",
            description="Total LLM tokens consumed",
            unit="1",
        )
        self.llm_duration = self.meter.create_histogram(
            "hsaai_llm_duration_seconds",
            description="LLM inference duration",
            unit="s",
        )

        # Agent metrics
        self.agent_actions_counter = self.meter.create_counter(
            "hsaai_agent_actions_total",
            description="Total agent actions by type",
            unit="1",
        )

        # Cache metrics
        self.cache_hits = self.meter.create_counter(
            "hsaai_cache_hits_total", "Cache hits", "1",
        )
        self.cache_misses = self.meter.create_counter(
            "hsaai_cache_misses_total", "Cache misses", "1",
        )

        # DB metrics
        self.db_query_duration = self.meter.create_histogram(
            "hsaai_db_query_seconds", "DB query duration", "s",
        )

    def record_request(self, endpoint: str, duration_s: float, status: int,
                       method: str = "GET"):
        self.request_counter.add(1, {
            "endpoint": endpoint, "status": str(status), "method": method,
        })
        self.request_duration.record(duration_s, {"endpoint": endpoint})

    def record_error(self, error_type: str, endpoint: str = ""):
        self.error_counter.add(1, {"error_type": error_type, "endpoint": endpoint})

    def record_llm_call(self, model: str, tokens: int, duration_s: float,
                        cache_hit: bool = False):
        self.llm_tokens_counter.add(tokens, {"model": model})
        self.llm_duration.record(duration_s, {"model": model})
        if cache_hit:
            self.cache_hits.add(1, {"model": model})
        else:
            self.cache_misses.add(1, {"model": model})

    def record_agent_action(self, agent_id: str, action: str, success: bool):
        self.agent_actions_counter.add(1, {
            "agent_id": agent_id, "action": action,
            "success": str(success),
        })


# ═══════════════════════════════════════════════════════════════════
# DISTRIBUTED TRACING
# ═══════════════════════════════════════════════════════════════════
def setup_tracing(service_name: str, otlp_endpoint: str = None):
    """Initialize OpenTelemetry tracing."""
    global _initialized
    if _initialized:
        return
    _initialized = True

    endpoint = otlp_endpoint or os.getenv(
        "OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317"
    )
    resource = Resource.create({
        "service.name": service_name,
        "service.version": os.getenv("SERVICE_VERSION", "1.0.0"),
        "deployment.environment": os.getenv("DEPLOY_ENV", "production"),
    })
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
    )
    trace.set_tracer_provider(provider)
    # Auto-instrumentation
    LoggingInstrumentor().instrument(set_logging_format=False)
    RedisInstrumentor().instrument()
    HTTPXClientInstrumentor().instrument()
    logger.info(f"Tracing configured: {service_name} → {endpoint}")


def setup_metrics_provider(service_name: str, otlp_endpoint: str = None):
    """Initialize OpenTelemetry metrics."""
    endpoint = otlp_endpoint or os.getenv(
        "OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317"
    )
    resource = Resource.create({"service.name": service_name})
    reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=endpoint),
        export_interval_millis=15000,
    )
    meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
    metrics.set_meter_provider(meter_provider)


# ═══════════════════════════════════════════════════════════════════
# UNIFIED SETUP
# ═══════════════════════════════════════════════════════════════════
def setup_observability(service_name: str):
    """One-call setup: logging + tracing + metrics."""
    setup_logging(service_name)
    setup_tracing(service_name)
    setup_metrics_provider(service_name)
    logger.info(f"✓ Observability configured for {service_name}")


def get_metrics(service_name: str) -> HSAAIMetrics:
    """Get metrics instance for a service."""
    return HSAAIMetrics(service_name)


def get_tracer(name: str):
    return trace.get_tracer(name)


# ═══════════════════════════════════════════════════════════════════
# SLO DEFINITIONS
# ═══════════════════════════════════════════════════════════════════
SLO_DEFINITIONS = {
    "api_gateway": {
        "availability": {"target": 0.999, "window": "30d"},
        "latency_p99": {"target_ms": 500, "window": "5m"},
        "error_rate": {"target": 0.001, "window": "5m"},
    },
    "llm_gateway": {
        "availability": {"target": 0.999, "window": "30d"},
        "latency_p99": {"target_ms": 5000, "window": "5m"},  # LLM is slower
        "error_rate": {"target": 0.01, "window": "5m"},
        "cache_hit_rate": {"target": 0.30, "window": "1h"},
    },
    "rag_engine": {
        "availability": {"target": 0.999, "window": "30d"},
        "latency_p99": {"target_ms": 1000, "window": "5m"},
        "error_rate": {"target": 0.005, "window": "5m"},
    },
    "agent_runtime": {
        "availability": {"target": 0.995, "window": "30d"},
        "latency_p99": {"target_ms": 10000, "window": "5m"},
        "error_rate": {"target": 0.02, "window": "5m"},
    },
}


# ═══════════════════════════════════════════════════════════════════
# HEALTH CHECK UTILITY
# ═══════════════════════════════════════════════════════════════════
async def health_check(deps: Dict[str, str]) -> Dict[str, Any]:
    """
    Standard health check that probes dependencies.
    Usage:
        @app.get("/health")
        async def health():
            return await health_check({"postgres": PG_URL, "redis": REDIS_URL})
    """
    import httpx
    results = {}
    overall = True
    for name, url in deps.items():
        try:
            if url.startswith("http"):
                async with httpx.AsyncClient(timeout=2) as c:
                    r = await c.get(url)
                    results[name] = "ok" if r.status_code < 500 else "degraded"
                    if r.status_code >= 500:
                        overall = False
            elif url.startswith("redis"):
                import redis
                r = redis.from_url(url)
                r.ping()
                results[name] = "ok"
            elif url.startswith("postgres"):
                import psycopg2
                conn = psycopg2.connect(url, connect_timeout=2)
                conn.close()
                results[name] = "ok"
        except Exception as e:
            results[name] = f"error: {str(e)[:50]}"
            overall = False
    return {
        "status": "ok" if overall else "degraded",
        "dependencies": results,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
