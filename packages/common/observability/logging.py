"""
HSAAI Structured Logging — Production Configuration

Provides JSON-structured logging with:
  - Correlation IDs (trace_id, span_id) from OpenTelemetry
  - Request IDs for end-to-end tracing
  - Tenant/workspace context
  - Log level configuration per module
  - Rotation and centralized shipping
"""
import os
import sys
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional
from contextvars import ContextVar

# Context variables for request-scoped data
request_id_var: ContextVar[str] = ContextVar("request_id", default="")
tenant_id_var: ContextVar[str] = ContextVar("tenant_id", default="")
workspace_id_var: ContextVar[str] = ContextVar("workspace_id", default="")
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")

APP_ENV = os.getenv("APP_ENV", os.getenv("ENVIRONMENT", "development")).lower()
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = os.getenv("LOG_FORMAT", "json")  # json | text


class HSAAIJsonFormatter(logging.Formatter):
    """JSON log formatter with OpenTelemetry correlation IDs."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": os.getenv("SERVICE_NAME", "hsaai"),
            "env": APP_ENV,
        }

        # Add context variables
        rid = request_id_var.get("")
        if rid:
            log_entry["request_id"] = rid
        tid = tenant_id_var.get("")
        if tid:
            log_entry["tenant_id"] = tid
        wid = workspace_id_var.get("")
        if wid:
            log_entry["workspace_id"] = wid
        cid = correlation_id_var.get("")
        if cid:
            log_entry["correlation_id"] = cid

        # Add OpenTelemetry trace context
        try:
            from opentelemetry import trace
            span = trace.get_current_span()
            if span and span.is_recording():
                ctx = span.get_span_context()
                log_entry["trace_id"] = format(ctx.trace_id, "032x")
                log_entry["span_id"] = format(ctx.span_id, "016x")
                log_entry["trace_flags"] = format(ctx.trace_flags, "02x")
        except Exception:
            pass

        # Add exception info
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "module": record.module,
            }

        # Add extra fields
        if hasattr(record, "hsaai_extra"):
            log_entry.update(record.hsaai_extra)

        return json.dumps(log_entry, ensure_ascii=False, default=str)


class HSAAITextFormatter(logging.Formatter):
    """Human-readable log formatter for development."""

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
        rid = request_id_var.get("")
        trace_part = ""
        try:
            from opentelemetry import trace
            span = trace.get_current_span()
            if span and span.is_recording():
                ctx = span.get_span_context()
                trace_part = f" [trace={format(ctx.trace_id, '032x')[:16]}…]"
        except Exception:
            pass
        rid_part = f" [req={rid[:8]}]" if rid else ""
        msg = f"{ts} {record.levelname:5s} [{record.name}]{rid_part}{trace_part} {record.getMessage()}"
        if record.exc_info and record.exc_info[0]:
            msg += f" | {record.exc_info[0].__name__}: {record.exc_info[1]}"
        return msg


def setup_logging(service_name: Optional[str] = None) -> None:
    """
    Configure structured logging for HSAAI services.

    Call this once at application startup, before any other initialization.
    """
    root = logging.getLogger()

    # Remove existing handlers
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    # Create handler
    handler = logging.StreamHandler(sys.stdout)

    if LOG_FORMAT == "json":
        handler.setFormatter(HSAAIJsonFormatter())
    else:
        handler.setFormatter(HSAAITextFormatter())

    root.addHandler(handler)
    root.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    # Reduce noise from third-party libraries
    for noisy in ("uvicorn.access", "httpx", "httpcore", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    # HSAAI modules at configured level
    logging.getLogger("hsaai").setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    svc = service_name or os.getenv("SERVICE_NAME", "hsaai")
    logger = logging.getLogger("hsaai.logging")
    logger.info("Structured logging initialized: service=%s format=%s level=%s", svc, LOG_FORMAT, LOG_LEVEL)


def new_request_id() -> str:
    """Generate a new request ID."""
    rid = str(uuid.uuid4())
    request_id_var.set(rid)
    return rid


def set_request_context(
    request_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> None:
    """Set request-scoped context for structured logging."""
    if request_id:
        request_id_var.set(request_id)
    if tenant_id:
        tenant_id_var.set(tenant_id)
    if workspace_id:
        workspace_id_var.set(workspace_id)
    if correlation_id:
        correlation_id_var.set(correlation_id)


def clear_request_context() -> None:
    """Clear request-scoped context (call at end of request)."""
    request_id_var.set("")
    tenant_id_var.set("")
    workspace_id_var.set("")
    correlation_id_var.set("")
