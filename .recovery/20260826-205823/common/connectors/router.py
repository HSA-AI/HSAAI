"""
HSAAI Enterprise Connector Router
===================================
FastAPI router that exposes ALL connectors via a unified REST API.
Supports:
  - Dependency Injection (per-request connector resolution)
  - Authentication layer (pluggable)
  - Permission system (RBAC/ABAC via OPA)
  - Health aggregation endpoint
  - Metrics aggregation endpoint (Prometheus format)
  - Admin endpoints (enable/disable/test/list)
  - OpenAPI auto-documentation per connector
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

from .base import (
    BaseConnector, ConnectorConfig, ConnectorState,
    HealthResult, HealthStatus, ConnectorError,
    RateLimitExceededError, CircuitBreakerOpenError,
)
from .registry import ConnectorRegistry as registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/connectors", tags=["Enterprise Connectors"])


# ═══════════════════════════════════════════════════════════════════════════
#  Request/Response Models
# ═══════════════════════════════════════════════════════════════════════════
class ConnectorActionRequest(BaseModel):
    """Request to execute an action on a connector."""
    action: str = Field(..., description="Action name (e.g. 'get_sales_orders')")
    params: dict[str, Any] = Field(default_factory=dict, description="Action parameters")
    use_cache: bool = Field(True, description="Use cached response if available")
    user: Optional[str] = Field(None, description="User ID for audit log")


class ConnectorSearchRequest(BaseModel):
    """Request to search a connector."""
    query: str = Field(..., description="Search query")
    limit: int = Field(10, ge=1, le=100)
    filters: dict[str, Any] = Field(default_factory=dict)


class ConnectorCreateRequest(BaseModel):
    """Request to create/instantiate a connector from config."""
    connector_type: str = Field(..., description="Registered connector class name (e.g. 'sap_s4hana')")
    config: dict[str, Any] = Field(..., description="ConnectorConfig fields")


class ConnectorTestRequest(BaseModel):
    """Request to test a connector connection."""
    config: dict[str, Any]


# ═══════════════════════════════════════════════════════════════════════════
#  Dependency Injection
# ═══════════════════════════════════════════════════════════════════════════
def get_connector(connector_name: str) -> BaseConnector:
    """FastAPI dependency: resolve a connector by name."""
    instance = registry.get_instance(connector_name)
    if instance is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connector '{connector_name}' not found. Available: {[c['name'] for c in registry.list_instances()]}",
        )
    if instance.state != ConnectorState.CONNECTED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Connector '{connector_name}' is not connected (state: {instance.state.value})",
        )
    return instance


# Optional: real auth dependency (plug in Keycloak JWT verification here)
async def verify_auth(request: Request) -> dict:
    """
    Verify the caller is authenticated. In production, this verifies a
    Keycloak JWT. For now, it returns a mock user context.
    """
    # TODO: Replace with real JWT verification against Keycloak JWKS
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        # In dev mode, allow unauthenticated access
        return {"user": "anonymous", "roles": ["ai_user"], "tenant": "default"}
    return {"user": "authenticated_user", "roles": ["ai_user"], "tenant": "default"}


async def verify_admin_auth(auth: dict = Depends(verify_auth)) -> dict:
    """Verify the caller has admin role."""
    if "ai_admin" not in auth.get("roles", []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return auth


# ═══════════════════════════════════════════════════════════════════════════
#  Catalog Endpoints
# ═══════════════════════════════════════════════════════════════════════════
@router.get("/", summary="List all connector instances")
async def list_connectors(auth: dict = Depends(verify_auth)) -> dict:
    """List all registered connector instances with their current state."""
    return {
        "total": len(registry.list_instances()),
        "connectors": registry.list_instances(),
    }


@router.get("/catalog", summary="List all available connector classes")
async def list_catalog(auth: dict = Depends(verify_auth)) -> dict:
    """List all connector CLASSES that can be instantiated (the catalog)."""
    return {
        "total": len(registry.list_classes()),
        "classes": registry.list_classes(),
    }


@router.get("/{connector_name}/metadata", summary="Get connector metadata")
async def get_metadata(
    connector: BaseConnector = Depends(get_connector),
    auth: dict = Depends(verify_auth),
) -> dict:
    """Get metadata for a specific connector (capabilities, schema, permissions)."""
    return connector.metadata()


# ═══════════════════════════════════════════════════════════════════════════
#  Action & Search Endpoints
# ═══════════════════════════════════════════════════════════════════════════
@router.post("/{connector_name}/execute", summary="Execute a connector action")
async def execute_action(
    request: ConnectorActionRequest,
    connector: BaseConnector = Depends(get_connector),
    auth: dict = Depends(verify_auth),
) -> dict:
    """Execute a named action on a connector (with retry, circuit breaker, caching)."""
    try:
        return await connector.call(
            request.action,
            user=auth.get("user"),
            use_cache=request.use_cache,
            **request.params,
        )
    except RateLimitExceededError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except CircuitBreakerOpenError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ConnectorError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.exception(f"Connector action failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{connector_name}/search", summary="Search a connector")
async def search_connector(
    request: ConnectorSearchRequest,
    connector: BaseConnector = Depends(get_connector),
    auth: dict = Depends(verify_auth),
) -> dict:
    """Perform a semantic search against a connector."""
    try:
        results = await connector.search(request.query, limit=request.limit, **request.filters)
        return {"query": request.query, "count": len(results), "results": results}
    except Exception as e:
        logger.exception(f"Connector search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════
#  Health & Metrics Endpoints
# ═══════════════════════════════════════════════════════════════════════════
@router.get("/health/all", summary="Aggregate health of all connectors")
async def health_all(auth: dict = Depends(verify_auth)) -> dict:
    """Get aggregated health status of all connectors."""
    return registry.health_all()


@router.get("/{connector_name}/health", summary="Health of a specific connector")
async def health_one(
    connector: BaseConnector = Depends(get_connector),
    auth: dict = Depends(verify_auth),
) -> dict:
    """Get the latest health status of a specific connector."""
    h = connector.get_health()
    if h is None:
        return {"status": "unknown", "connector": connector.config.name}
    return h.model_dump()


@router.get("/metrics/all", summary="Metrics of all connectors (JSON)")
async def metrics_all(auth: dict = Depends(verify_auth)) -> dict:
    """Get metrics for all connectors (JSON format)."""
    return {name: m.model_dump() for name, m in registry.metrics_all().items()}


@router.get("/metrics/prometheus", summary="Prometheus metrics", response_class=PlainTextResponse)
async def metrics_prometheus() -> str:
    """Export all connector metrics in Prometheus exposition format."""
    lines = [
        "# HELP hsaai_connector_calls_total Total calls per connector",
        "# TYPE hsaai_connector_calls_total counter",
        "# HELP hsaai_connector_latency_ms Average latency in ms",
        "# TYPE hsaai_connector_latency_ms gauge",
        "# HELP hsaai_connector_state Connector state (1=connected)",
        "# TYPE hsaai_connector_state gauge",
    ]
    for name, m in registry.metrics_all().items():
        labels = f'connector="{name}"'
        lines.append(f'hsaai_connector_calls_total{{{labels},result="success"}} {m.successful_calls}')
        lines.append(f'hsaai_connector_calls_total{{{labels},result="failure"}} {m.failed_calls}')
        lines.append(f'hsaai_connector_latency_ms{{{labels}}} {m.avg_latency_ms}')
        lines.append(f'hsaai_connector_cache_hits{{{labels}}} {m.cache_hits}')
        lines.append(f'hsaai_connector_cache_misses{{{labels}}} {m.cache_misses}')
        lines.append(f'hsaai_connector_rate_limit_rejections{{{labels}}} {m.rate_limit_rejections}')
        state_val = 1 if m.circuit_breaker_state == "closed" else 0
        lines.append(f'hsaai_connector_state{{{labels}}} {state_val}')
    return "\n".join(lines) + "\n"


# ═══════════════════════════════════════════════════════════════════════════
#  Admin Endpoints (require admin role)
# ═══════════════════════════════════════════════════════════════════════════
@router.post("/admin/create", summary="Create a connector instance (admin)")
async def create_connector(
    request: ConnectorCreateRequest,
    auth: dict = Depends(verify_admin_auth),
) -> dict:
    """Create and connect a new connector instance from config (no code change needed)."""
    try:
        config = ConnectorConfig(
            name=request.config.get("name", request.connector_type),
            display_name=request.config.get("display_name", request.connector_type),
            category=request.config.get("category", "custom"),
            base_url=request.config["base_url"],
            **{k: v for k, v in request.config.items() if k not in ("name", "display_name", "category", "base_url")},
        )
        instance = registry.create(request.connector_type, config)
        await instance.connect()
        return {"status": "created", "name": instance.config.name, "state": instance.state.value}
    except KeyError as e:
        raise HTTPException(status_code=400, detail=f"Missing config field: {e}")
    except Exception as e:
        logger.exception(f"Failed to create connector: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/admin/{connector_name}", summary="Delete a connector instance (admin)")
async def delete_connector(
    connector_name: str,
    auth: dict = Depends(verify_admin_auth),
) -> dict:
    """Disconnect and unregister a connector."""
    instance = registry.get_instance(connector_name)
    if instance is None:
        raise HTTPException(status_code=404, detail=f"Connector '{connector_name}' not found")
    await instance.disconnect()
    registry.unregister(connector_name)
    return {"status": "deleted", "name": connector_name}


@router.post("/admin/{connector_name}/test", summary="Test a connector connection (admin)")
async def test_connector(
    connector_name: str,
    auth: dict = Depends(verify_admin_auth),
) -> dict:
    """Run a health check against a connector and return the result."""
    instance = registry.get_instance(connector_name)
    if instance is None:
        raise HTTPException(status_code=404, detail=f"Connector '{connector_name}' not found")
    try:
        result = await instance.health()
        return result.model_dump()
    except Exception as e:
        return {"status": "unhealthy", "connector": connector_name, "error": str(e)}


@router.post("/admin/{connector_name}/cache/invalidate", summary="Invalidate connector cache (admin)")
async def invalidate_cache(
    connector_name: str,
    pattern: Optional[str] = Query(None, description="Pattern to match (substring)"),
    auth: dict = Depends(verify_admin_auth),
) -> dict:
    """Invalidate the cache for a connector."""
    instance = registry.get_instance(connector_name)
    if instance is None:
        raise HTTPException(status_code=404, detail=f"Connector '{connector_name}' not found")
    count = instance.invalidate_cache(pattern)
    return {"status": "invalidated", "count": count}


@router.post("/admin/discover", summary="Re-discover all connectors (admin)")
async def discover_connectors(auth: dict = Depends(verify_admin_auth)) -> dict:
    """Re-run auto-discovery to load any newly added connector classes."""
    count = registry.discover()
    return {"status": "discovered", "modules_loaded": count, "total_classes": len(registry.list_classes())}


# ═══════════════════════════════════════════════════════════════════════════
#  Convenience: include this router in any FastAPI app
# ═══════════════════════════════════════════════════════════════════════════
def include_connector_router(app) -> None:
    """Include the connector router in a FastAPI app and run auto-discovery."""
    from .registry import ConnectorRegistry
    ConnectorRegistry.discover()
    app.include_router(router)
    logger.info(f"Connector router included. {len(ConnectorRegistry.list_classes())} classes available.")
