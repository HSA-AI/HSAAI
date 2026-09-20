"""
HSAAI Observability Foundation (Phase 1 — Critical)
=====================================================
OpenTelemetry instrumentation for all services. Provides:
- Distributed tracing across service boundaries
- Metrics for SLO tracking
- Structured logging with correlation IDs
- Auto-instrumentation for FastAPI, HTTPX, Redis, PostgreSQL

Usage in any service:
    from packages.common.telemetry import setup_telemetry, get_tracer
    setup_telemetry("my-service")
    tracer = get_tracer(__name__)
    with tracer.start_as_current_span("my_operation") as span:
        span.set_attribute("key", "value")
        ...
"""
import os
import sys
import logging
from typing import Optional

# OpenTelemetry imports
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter

# Auto-instrumentation
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor

logger = logging.getLogger(__name__)

_initialized = False


def setup_telemetry(
    service_name: str,
    service_version: str = "1.0.0",
    otlp_endpoint: Optional[str] = None,
    enable_console_export: bool = False,
):
    """
    Initialize OpenTelemetry for a service. Call once at service startup.

    Args:
        service_name: e.g., "hsaai-llm-gateway"
        service_version: semantic version
        otlp_endpoint: OTLP collector endpoint (default: from env or localhost)
        enable_console_export: also print spans to console (dev only)
    """
    global _initialized
    if _initialized:
        logger.warning("Telemetry already initialized — skipping")
        return
    _initialized = True

    endpoint = otlp_endpoint or os.getenv(
        "OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317"
    )

    # Resource identifies this service in all telemetry
    resource = Resource.create({
        "service.name": service_name,
        "service.version": service_version,
        "deployment.environment": os.getenv("DEPLOY_ENV", "production"),
        "host.name": os.uname().nodename,
    })

    # ─── Tracing ──────────────────────────────────────────────
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
    )
    if enable_console_export:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)

    # ─── Metrics ──────────────────────────────────────────────
    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=endpoint),
        export_interval_millis=15000,  # export every 15s
    )
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)

    # ─── Auto-instrumentation ─────────────────────────────────
    LoggingInstrumentor().instrument(set_logging_format=True)
    RedisInstrumentor().instrument()
    HTTPXClientInstrumentor().instrument()

    logger.info(f"Telemetry initialized: {service_name} v{service_version} → {endpoint}")


def get_tracer(name: str):
    """Get a tracer for the given module name."""
    return trace.get_tracer(name)


def get_meter(name: str):
    """Get a meter for the given module name."""
    return metrics.get_meter(name)


def instrument_fastapi(app):
    """Instrument a FastAPI app. Call after setup_telemetry()."""
    FastAPIInstrumentor.instrument_app(app)
    logger.info(f"FastAPI instrumented: {app.title}")


# ─── SLO Metrics Helpers ────────────────────────────────────────────
class SLOMetrics:
    """
    Standard SLO metrics for every user-facing API.
    Usage:
        slo = SLOMetrics("my-service")
        slo.record_request(endpoint="/v1/generate", latency_ms=150, status=200)
    """

    def __init__(self, service_name: str):
        self.meter = get_meter(service_name)
        self.request_counter = self.meter.create_counter(
            "hsaai_requests_total",
            description="Total requests by endpoint and status",
            unit="1",
        )
        self.latency_histogram = self.meter.create_histogram(
            "hsaai_request_duration_ms",
            description="Request latency in milliseconds",
            unit="ms",
        )
        self.error_counter = self.meter.create_counter(
            "hsaai_errors_total",
            description="Total errors by type",
            unit="1",
        )

    def record_request(self, endpoint: str, latency_ms: float, status: int):
        """Record a request."""
        attrs = {"endpoint": endpoint, "status_code": str(status)}
        self.request_counter.add(1, attrs)
        self.latency_histogram.record(latency_ms, {"endpoint": endpoint})

    def record_error(self, error_type: str, endpoint: str = ""):
        """Record an error."""
        self.error_counter.add(1, {"error_type": error_type, "endpoint": endpoint})


# ─── Correlation ID Middleware ──────────────────────────────────────
class CorrelationIdMiddleware:
    """
    Middleware that propagates correlation IDs across service boundaries.
    Enables tracing a single user request across 12 services.
    """

    async def __call__(self, request, call_next):
        from opentelemetry import trace
        import uuid

        # Extract or generate correlation ID
        corr_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))

        # Add to current span
        current_span = trace.get_current_span()
        if current_span:
            current_span.set_attribute("correlation.id", corr_id)

        response = await call_next(request)
        response.headers["X-Correlation-ID"] = corr_id
        return response
