"""
HSAAI Observability Middleware — FastAPI Integration

Adds per-request:
  - Request ID generation/propagation
  - OpenTelemetry span enrichment (tenant, workspace, user)
  - Structured logging context
  - Latency tracking
  - Error tracking with Sentry
"""
import os
import time
import logging
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("hsaai.observability.middleware")

APP_ENV = os.getenv("APP_ENV", os.getenv("ENVIRONMENT", "development")).lower()

# Initialize Sentry if DSN is provided
_sentry_initialized = False

def init_sentry() -> None:
    """Initialize Sentry error tracking."""
    global _sentry_initialized
    dsn = os.getenv("SENTRY_DSN", "")
    if not dsn:
        return
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.redis import RedisIntegration

        sentry_sdk.init(
            dsn=dsn,
            environment=APP_ENV,
            traces_sample_rate=0.1,
            profiles_sample_rate=0.1,
            integrations=[
                FastApiIntegration(),
                RedisIntegration(),
            ],
            send_default_pii=False,  # Never send PII
            max_request_body_size="always",  # For debugging API errors
        )
        _sentry_initialized = True
        logger.info("Sentry error tracking initialized (env=%s)", APP_ENV)
    except ImportError:
        logger.warning("sentry-sdk not installed — error tracking disabled")
    except Exception as e:
        logger.error("Sentry initialization failed: %s", e)


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware that adds observability to every request.

    Features:
    - Generates or propagates X-Request-ID header
    - Sets structured logging context (request_id, tenant, workspace)
    - Enriches OpenTelemetry spans with business context
    - Records request latency histogram
    - Captures unhandled exceptions in Sentry
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        from packages.common.observability.logging import (
            new_request_id, set_request_context, clear_request_context
        )

        # Generate or propagate request ID
        request_id = request.headers.get("X-Request-ID") or new_request_id()
        tenant_id = request.headers.get("X-Tenant-ID", "default")
        workspace_id = request.headers.get("X-Workspace-ID", "default")
        correlation_id = request.headers.get("X-Correlation-ID", "")

        # Set logging context
        set_request_context(
            request_id=request_id,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            correlation_id=correlation_id,
        )

        # Enrich OpenTelemetry span
        try:
            from opentelemetry import trace
            span = trace.get_current_span()
            if span and span.is_recording():
                span.set_attribute("hsaai.request_id", request_id)
                span.set_attribute("hsaai.tenant_id", tenant_id)
                span.set_attribute("hsaai.workspace_id", workspace_id)
                if correlation_id:
                    span.set_attribute("hsaai.correlation_id", correlation_id)
                span.set_attribute("http.request.method", request.method)
                span.set_attribute("url.path", request.url.path)
        except Exception:
            pass

        # Track latency
        started = time.time()

        # FIX B-11: Initialize `response` to None before the try block so the
        # finally block can reliably detect whether call_next returned a
        # response or raised. The previous code used `if "response" in dir()`
        # which is unreliable (dir() inside a function returns local names,
        # but the result depends on Python's compile-time analysis) and line
        # 143 referenced `response` unconditionally, causing a NameError that
        # masked the original exception raised by call_next.
        response = None

        try:
            response = await call_next(request)
        except Exception as exc:
            # Capture in Sentry
            if _sentry_initialized:
                try:
                    import sentry_sdk
                    sentry_sdk.capture_exception(exc)
                except Exception:
                    pass
            logger.exception("Unhandled exception in request %s %s", request.method, request.url.path)
            raise
        finally:
            elapsed_ms = (time.time() - started) * 1000
            status_code = response.status_code if response is not None else 500

            # Log request completion
            logger.info(
                "%s %s → %d (%.1fms)",
                request.method,
                request.url.path,
                status_code,
                elapsed_ms,
                extra={
                    "hsaai_extra": {
                        "method": request.method,
                        "path": request.url.path,
                        "status": status_code,
                        "latency_ms": round(elapsed_ms, 1),
                    }
                },
            )

            # Enrich span with response info
            try:
                from opentelemetry import trace
                span = trace.get_current_span()
                if span and span.is_recording():
                    span.set_attribute("http.response.status_code", status_code)
                    span.set_attribute("hsaai.latency_ms", round(elapsed_ms, 1))
            except Exception:
                pass

            # Clear context
            clear_request_context()

        # Propagate request ID in response
        # (only reached when call_next succeeded; otherwise the exception
        # raised above propagates after the finally block completes.)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time-Ms"] = f"{elapsed_ms:.1f}"

        return response
