"""
HSAAI Structured JSON Logging (Fix #6)
========================================
Unified structured logging for ALL services.

Features:
  - JSON format (Loki/ELK compatible)
  - Trace ID, Span ID, Correlation ID, Request ID
  - Tenant ID, User ID (when available)
  - Service name, environment, severity
  - Secret redaction (no passwords/tokens in logs)
  - Log sampling for high-traffic services
  - OpenTelemetry integration (auto-inject trace context)

Usage:
    from packages.common.security.structured_logging import setup_structured_logging
    setup_structured_logging("rag_engine")

    import logging
    logger = logging.getLogger("hsaai.rag_engine")
    logger.info("Document uploaded", extra={"document_id": "123", "tenant_id": "hsa-foods"})
"""
import os
import sys
import json
import logging
import time
import re
from typing import Any, Dict, Optional
from datetime import datetime, timezone

# OpenTelemetry trace context (auto-injected if available)
try:
    from opentelemetry import trace
    _OTEL_AVAILABLE = True
except ImportError:
    _OTEL_AVAILABLE = False


# ─── Secret Redaction ─────────────────────────────────────────────
REDACT_KEYS = {
    "password", "passwd", "pwd", "secret", "token", "api_key", "apikey",
    "authorization", "auth", "cookie", "session", "private_key", "client_secret",
    "access_token", "refresh_token", "bearer", "jwt", "credential",
}

REDACT_PATTERNS = [
    # Bearer tokens
    re.compile(r"(Bearer\s+)[^\s]+", re.IGNORECASE),
    # API keys (sk-..., pk-..., etc.)
    re.compile(r"(sk-|pk-|key-|api-)[A-Za-z0-9]{10,}", re.IGNORECASE),
    # JWT tokens (eyJ...)
    re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    # Email addresses (partial redaction)
    # re.compile(r"([a-zA-Z0-9._%+-]+@)[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),  # Disabled — emails are useful in logs
    # Credit card numbers
    re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"),
    # Saudi national ID
    re.compile(r"\b1\d{9}\b"),
    # IBAN
    re.compile(r"\bSA\d{22}\b"),
]


def redact_value(value: Any) -> Any:
    """Redact sensitive patterns from a value."""
    if isinstance(value, str):
        for pattern in REDACT_PATTERNS:
            value = pattern.sub("[REDACTED]", value)
        return value
    elif isinstance(value, dict):
        return {k: redact_value(v) if k.lower() not in REDACT_KEYS else "[REDACTED]"
                for k, v in value.items()}
    elif isinstance(value, list):
        return [redact_value(item) for item in value]
    return value


# ─── JSON Formatter ───────────────────────────────────────────────
class StructuredJSONFormatter(logging.Formatter):
    """
    JSON log formatter with trace context and secret redaction.
    Output is compatible with Loki, Elasticsearch, and Datadog.
    """

    def __init__(self, service_name: str = "unknown"):
        super().__init__()
        self.service_name = service_name
        self.environment = os.getenv("DEPLOY_ENV", "development")
        self.host = os.uname().nodename

    def format(self, record: logging.LogRecord) -> str:
        # Base log entry
        entry = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "severity": record.levelname,
            "service": self.service_name,
            "environment": self.environment,
            "host": self.host,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add trace context from OpenTelemetry
        if _OTEL_AVAILABLE:
            span = trace.get_current_span()
            if span and span.is_recording():
                ctx = span.get_span_context()
                entry["trace_id"] = f"{ctx.trace_id:032x}"
                entry["span_id"] = f"{ctx.span_id:016x}"

        # Add correlation ID from LogRecord (if set by middleware)
        if hasattr(record, "correlation_id"):
            entry["correlation_id"] = record.correlation_id
        if hasattr(record, "request_id"):
            entry["request_id"] = record.request_id
        if hasattr(record, "tenant_id"):
            entry["tenant_id"] = record.tenant_id
        if hasattr(record, "user_id"):
            # Only log user_id if privacy setting allows
            if os.getenv("LOG_USER_IDS", "true").lower() == "true":
                entry["user_id"] = record.user_id

        # Add error info
        if record.exc_info:
            entry["error"] = self.formatException(record.exc_info)
            entry["error_type"] = record.exc_info[0].__name__

        # Add extra fields (custom attributes)
        for key, value in record.__dict__.items():
            if key not in {
                "args", "msg", "levelname", "levelno", "pathname", "filename",
                "module", "exc_info", "exc_text", "stack_info", "lineno",
                "funcName", "created", "msecs", "relativeCreated", "thread",
                "threadName", "processName", "process", "name", "message",
                "taskName", "correlation_id", "request_id", "tenant_id", "user_id",
            }:
                try:
                    json.dumps(value)
                    entry[key] = value
                except (TypeError, ValueError):
                    entry[key] = str(value)

        # Redact sensitive data
        entry = redact_value(entry)

        return json.dumps(entry, default=str, ensure_ascii=False)


# ─── Setup Function ───────────────────────────────────────────────
def setup_structured_logging(
    service_name: str,
    level: str = None,
    sampling_rate: float = 1.0,
):
    """
    Configure structured JSON logging for a service.

    Args:
        service_name: Name of the service (e.g., "rag_engine")
        level: Log level (default: from LOG_LEVEL env var or INFO)
        sampling_rate: Fraction of DEBUG/INFO logs to emit (1.0 = all, 0.1 = 10%)
    """
    level = level or os.getenv("LOG_LEVEL", "INFO")
    log_format = os.getenv("LOG_FORMAT", "json")  # json or text

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)

    if log_format == "json":
        formatter = StructuredJSONFormatter(service_name=service_name)
    else:
        # Text format for development
        formatter = logging.Formatter(
            f"%(asctime)s [{service_name}] %(levelname)s %(name)s: %(message)s"
        )

    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    # Log sampling for high-traffic services
    if sampling_rate < 1.0:
        class SamplingFilter(logging.Filter):
            def __init__(self, rate):
                self.rate = rate
                self.counter = 0

            def filter(self, record):
                if record.levelno >= logging.WARNING:
                    return True  # Always log warnings+
                self.counter += 1
                return (self.counter % int(1 / self.rate)) == 0

        handler.addFilter(SamplingFilter(sampling_rate))

    logger = logging.getLogger(f"hsaai.{service_name}")
    logger.info(
        "Structured logging configured",
        extra={
            "service": service_name,
            "level": level,
            "format": log_format,
            "sampling_rate": sampling_rate,
        }
    )
    return logger
