"""
HSAAI OpenTelemetry Tracing — Production Configuration

Provides distributed tracing for all HSAAI services using OpenTelemetry.
Auto-instruments FastAPI, HTTPX, SQLAlchemy, and Redis.

Environment Variables:
  OTEL_ENABLED:            Enable/disable tracing (default: true in production)
  OTEL_EXPORTER_OTLP_ENDPOINT: OTLP collector endpoint (default: http://otel-collector:4317)
  OTEL_SERVICE_NAME:       Service name for spans (default: from SERVICE_NAME env)
  OTEL_EXPORTER_OTLP_PROTOCOL: otlp/grpc or otlp/http (default: grpc)
  OTEL_TRACES_SAMPLER:     Sampling strategy (default: parentbased_traceidratio)
  OTEL_TRACES_SAMPLER_ARG: Sampling rate 0.0-1.0 (default: 0.1 in prod, 1.0 in dev)
"""
import os
import logging
from typing import Optional

logger = logging.getLogger("hsaai.observability")

OTEL_ENABLED = os.getenv("OTEL_ENABLED", "true").lower() == "true"
OTEL_EXPORTER_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317")
OTEL_SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", os.getenv("SERVICE_NAME", "hsaai-service"))
OTEL_PROTOCOL = os.getenv("OTEL_EXPORTER_OTLP_PROTOCOL", "grpc")
APP_ENV = os.getenv("APP_ENV", os.getenv("ENVIRONMENT", "development")).lower()

# Sampling: 100% in dev, 10% in production
DEFAULT_SAMPLE_RATE = "1.0" if APP_ENV not in {"production", "prod"} else "0.1"
OTEL_SAMPLE_RATE = float(os.getenv("OTEL_TRACES_SAMPLER_ARG", DEFAULT_SAMPLE_RATE))


_tracer_provider = None
_meter_provider = None


def setup_tracing(app=None, service_name: Optional[str] = None) -> None:
    """
    Initialize OpenTelemetry tracing and instrument FastAPI app.

    This MUST be called once at application startup, before any
    request handling begins.

    Args:
        app: FastAPI application instance to auto-instrument
        service_name: Override service name (default: OTEL_SERVICE_NAME env)
    """
    global _tracer_provider

    if not OTEL_ENABLED:
        logger.info("OpenTelemetry tracing is DISABLED (OTEL_ENABLED=false)")
        return

    svc = service_name or OTEL_SERVICE_NAME

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.sampling import ParentBasedTraceIdRatio
        from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION, DEPLOYMENT_ENVIRONMENT

        # Create resource with service identity
        resource = Resource.create({
            SERVICE_NAME: svc,
            SERVICE_VERSION: os.getenv("APP_VERSION", "10.0.0"),
            DEPLOYMENT_ENVIRONMENT: APP_ENV,
            "hsaai.tenant": os.getenv("DEFAULT_TENANT_ID", "default"),
        })

        # Configure sampler
        sampler = ParentBasedTraceIdRatio(rate=OTEL_SAMPLE_RATE)

        # Create tracer provider
        _tracer_provider = TracerProvider(resource=resource, sampler=sampler)

        # Configure exporter
        _setup_exporter(_tracer_provider)

        # Set global tracer provider
        trace.set_tracer_provider(_tracer_provider)

        # Auto-instrument FastAPI if app provided
        if app is not None:
            _instrument_fastapi(app)

        # Auto-instrument HTTPX (for inter-service calls)
        _instrument_httpx()

        # Auto-instrument SQLAlchemy
        _instrument_sqlalchemy()

        # Auto-instrument Redis
        _instrument_redis()

        logger.info(
            "OpenTelemetry tracing initialized: service=%s endpoint=%s sample_rate=%.2f",
            svc, OTEL_EXPORTER_ENDPOINT, OTEL_SAMPLE_RATE,
        )

    except ImportError as e:
        logger.warning("OpenTelemetry packages not fully installed: %s", e)
    except Exception as e:
        logger.error("Failed to initialize OpenTelemetry: %s", e)


def _setup_exporter(provider) -> None:
    """Configure the OTLP trace exporter."""
    try:
        if OTEL_PROTOCOL == "grpc":
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        else:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        exporter = OTLPSpanExporter(endpoint=OTEL_EXPORTER_ENDPOINT, insecure=True)
        processor = BatchSpanProcessor(
            exporter,
            max_queue_size=2048,
            max_export_batch_size=512,
            schedule_delay_millis=5000,
            export_timeout_millis=30000,
        )
        provider.add_span_processor(processor)

    except ImportError as e:
        logger.warning("OTLP exporter not available: %s. Traces will not be exported.", e)


def _instrument_fastapi(app) -> None:
    """Auto-instrument FastAPI application."""
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
        logger.info("FastAPI auto-instrumented for tracing")
    except ImportError:
        logger.debug("opentelemetry-instrumentation-fastapi not installed")


def _instrument_httpx() -> None:
    """Auto-instrument HTTPX client for distributed tracing."""
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        HTTPXClientInstrumentor().instrument()
        logger.info("HTTPX auto-instrumented for tracing")
    except ImportError:
        logger.debug("opentelemetry-instrumentation-httpx not installed")


def _instrument_sqlalchemy() -> None:
    """Auto-instrument SQLAlchemy for query tracing."""
    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from backend_core.db.database import engine
        SQLAlchemyInstrumentor().instrument(engine=engine)
        logger.info("SQLAlchemy auto-instrumented for tracing")
    except ImportError:
        logger.debug("opentelemetry-instrumentation-sqlalchemy not installed")
    except Exception:
        logger.debug("SQLAlchemy instrumentation skipped (engine not available yet)")


def _instrument_redis() -> None:
    """Auto-instrument Redis client for tracing."""
    try:
        from opentelemetry.instrumentation.redis import RedisInstrumentor
        RedisInstrumentor().instrument()
        logger.info("Redis auto-instrumented for tracing")
    except ImportError:
        logger.debug("opentelemetry-instrumentation-redis not installed")


def get_tracer(name: str = "hsaai"):
    """Get a tracer for manual span creation."""
    from opentelemetry import trace
    return trace.get_tracer(name)


def shutdown_tracing() -> None:
    """Gracefully shutdown tracer provider (flush pending spans)."""
    global _tracer_provider
    if _tracer_provider:
        _tracer_provider.shutdown()
        logger.info("OpenTelemetry tracer provider shut down")
