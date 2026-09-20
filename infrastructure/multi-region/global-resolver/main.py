"""
HSAAI Global Traffic Resolver (Phase 3 — Scale)
=================================================

FIX v2.3 (Phase 3): Implements global traffic management for multi-region
active-active deployment. Routes each request to the optimal region based on:
  1. Tenant's write-primary region (writes go to the tenant's primary region)
  2. Geographic latency (reads go to the nearest healthy region)
  3. Health checks (unhealthy regions are removed from the pool)
  4. Failover (if a region's write-primary fails, another region takes over)

This service runs in every region and shares state via Redis CRDT.
It exposes a /resolve endpoint that the API Gateway calls before routing
each request to determine the target region.

Usage:
    # Resolve the best region for a request
    GET /resolve?tenant_id=hsa-foods&request_type=write

    # Response:
    {
      "region": "me-west-1",
      "endpoint": "https://me-west-1.hsaai.internal",
      "reason": "write_primary",
      "health": "healthy"
    }

    # Get all region health status
    GET /health/regions
"""
from __future__ import annotations

import os
import sys
import time
import logging
import asyncio
from typing import Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI, HTTPException, Query, Depends, Header
from pydantic import BaseModel

# FIX I-12: Add JWT validation on all non-/health endpoints.
# The global resolver exposes the full multi-region architecture map
# (/resolve returns endpoints, /health/regions returns topology). Without
# auth, any caller inside the cluster could enumerate the topology and
# discover per-tenant write-primary regions. We require a valid HSAAI
# JWT carrying either the hsaai_admin or platform_svc realm role.
_PKG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "packages")
if _PKG_PATH not in sys.path:
    sys.path.insert(0, _PKG_PATH)

try:
    from common.security.jwt_validator import JWTValidator, JWTValidationError  # type: ignore
    _JWT_AVAILABLE = True
    _JWT_LOAD_ERROR: Optional[str] = None
except ImportError as _e:  # pragma: no cover - import guard
    _JWT_AVAILABLE = False
    _JWT_LOAD_ERROR = str(_e)
    JWTValidator = None  # type: ignore
    JWTValidationError = Exception  # type: ignore

logger = logging.getLogger("hsaai.global_resolver")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

app = FastAPI(
    title="HSAAI Global Traffic Resolver",
    description="Multi-region active-active traffic management (Phase 3)",
    version="1.0.0",
)

# ─── Region Configuration ─────────────────────────────────────

@dataclass
class Region:
    name: str
    display_name: str
    endpoint: str
    health_check_path: str = "/health"
    weight: int = 33  # default equal weight
    is_write_primary: bool = False
    failover_priority: int = 99  # lower = higher priority
    health: str = "unknown"  # unknown, healthy, unhealthy
    last_check: float = 0.0
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    avg_latency_ms: float = 0.0


# Load region configuration from environment or use defaults.
# In production, this is loaded from the regions-config ConfigMap.
REGIONS: dict[str, Region] = {}


def _load_regions():
    """Load region configuration from env vars or ConfigMap."""
    global REGIONS
    # Default 3-region setup.
    REGIONS = {
        "me-west-1": Region(
            name="me-west-1",
            display_name="Middle East West (Yemen/Saudi)",
            endpoint=os.getenv("REGION_ME_WEST_1_ENDPOINT", "http://me-west-1.hsaai.internal"),
            weight=40,
            is_write_primary=True,
            failover_priority=1,
        ),
        "me-south-1": Region(
            name="me-south-1",
            display_name="Middle East South (Mumbai)",
            endpoint=os.getenv("REGION_ME_SOUTH_1_ENDPOINT", "http://me-south-1.hsaai.internal"),
            weight=35,
            is_write_primary=True,
            failover_priority=2,
        ),
        "eu-west-1": Region(
            name="eu-west-1",
            display_name="Europe West (Frankfurt)",
            endpoint=os.getenv("REGION_EU_WEST_1_ENDPOINT", "http://eu-west-1.hsaai.internal"),
            weight=25,
            is_write_primary=False,
            failover_priority=3,
        ),
    }


_load_regions()

# ─── FIX I-12: JWT validation dependency ──────────────────────
# Require hsaai_admin or platform_svc role for any endpoint that exposes
# multi-region topology. /health (basic liveness) remains public so that
# Kubernetes probes and the resolver's own health-check loop can reach it
# without a service token. /resolve and /health/regions are protected.

_ALLOWED_RESOLVER_ROLES = {"hsaai_admin", "platform_svc"}

# Singleton validator — created lazily on first request so that a missing
# Keycloak endpoint at startup doesn't crash the service (it will instead
# return 503 on the first authenticated call, which is the safer failure).
_validator_singleton: Any = None


def _get_validator() -> Any:
    global _validator_singleton
    if _validator_singleton is None and _JWT_AVAILABLE:
        _validator_singleton = JWTValidator(
            jwks_url=os.getenv(
                "KEYCLOAK_JWKS_URL",
                "http://keycloak:8080/realms/hsaai/protocol/openid-connect/certs",
            ),
            issuer=os.getenv("KEYCLOAK_ISSUER", "http://keycloak:8080/realms/hsaai"),
            audience=os.getenv("KEYCLOAK_AUDIENCE", "hsaai-api"),
        )
    return _validator_singleton


async def require_admin_or_platform(
    authorization: Optional[str] = Header(None, description="Bearer JWT token"),
) -> dict:
    """FIX I-12: Validate the bearer JWT and require hsaai_admin or platform_svc.

    Returns the validated claims dict on success. Raises 401/403 otherwise.
    """
    if not _JWT_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail=f"JWT validator unavailable on this resolver: {_JWT_LOAD_ERROR}",
        )
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization.split(" ", 1)[1].strip()
    validator = _get_validator()
    try:
        claims = await validator.verify(token)
    except JWTValidationError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")
    # JWTClaims is a dataclass; expose roles as a list for the check below.
    roles = list(getattr(claims, "roles", []) or [])
    if not any(r in _ALLOWED_RESOLVER_ROLES for r in roles):
        raise HTTPException(
            status_code=403,
            detail="Insufficient role: /resolve and /health/regions require hsaai_admin or platform_svc",
        )
    return {
        "sub": claims.sub,
        "tenant_id": claims.tenant_id,
        "roles": roles,
        "email": claims.email,
        "name": claims.name,
    }

# Tenant-to-region routing preferences.
# In production, loaded from the regions-config ConfigMap.
TENANT_ROUTING: dict[str, dict[str, Any]] = {
    "hsa-foods": {"write_primary": "me-west-1", "read_any": True},
    "hsa-retail": {"write_primary": "me-west-1", "read_any": True},
    "hsa-packaging": {"write_primary": "me-west-1", "read_any": True},
    "hsa-realestate": {"write_primary": "me-south-1", "read_any": True},
    "hsa-logging": {"write_primary": "me-south-1", "read_any": True},
    "hsa-corporate": {"write_primary": "me-west-1", "read_any": True},
}

# Health check configuration.
HEALTH_CHECK_INTERVAL = int(os.getenv("HEALTH_CHECK_INTERVAL", "10"))  # seconds
HEALTH_CHECK_TIMEOUT = int(os.getenv("HEALTH_CHECK_TIMEOUT", "5"))  # seconds
UNHEALTHY_THRESHOLD = int(os.getenv("UNHEALTHY_THRESHOLD", "3"))
HEALTHY_THRESHOLD = int(os.getenv("HEALTHY_THRESHOLD", "2"))


# ─── Health Checking ──────────────────────────────────────────

async def _check_region_health(region: Region):
    """Check a single region's health by calling its /health endpoint."""
    url = f"{region.endpoint}{region.health_check_path}"
    started = time.time()
    try:
        async with httpx.AsyncClient(timeout=HEALTH_CHECK_TIMEOUT) as client:
            resp = await client.get(url)
            elapsed = (time.time() - started) * 1000
            if resp.status_code == 200:
                region.consecutive_successes += 1
                region.consecutive_failures = 0
                # Exponential moving average for latency.
                region.avg_latency_ms = region.avg_latency_ms * 0.7 + elapsed * 0.3
                if region.consecutive_successes >= HEALTHY_THRESHOLD:
                    region.health = "healthy"
            else:
                region.consecutive_failures += 1
                region.consecutive_successes = 0
                if region.consecutive_failures >= UNHEALTHY_THRESHOLD:
                    region.health = "unhealthy"
                    logger.warning("Region %s marked unhealthy (HTTP %d)", region.name, resp.status_code)
    except Exception as e:
        region.consecutive_failures += 1
        region.consecutive_successes = 0
        if region.consecutive_failures >= UNHEALTHY_THRESHOLD:
            region.health = "unhealthy"
            logger.warning("Region %s marked unhealthy: %s", region.name, e)
    region.last_check = time.time()


async def _health_check_loop():
    """Background task that periodically checks all regions' health."""
    while True:
        tasks = [_check_region_health(r) for r in REGIONS.values()]
        await asyncio.gather(*tasks, return_exceptions=True)
        await asyncio.sleep(HEALTH_CHECK_INTERVAL)


@app.on_event("startup")
async def _start_health_checks():
    """Start the background health check loop on startup."""
    asyncio.create_task(_health_check_loop())
    logger.info("Started health check loop (interval=%ds)", HEALTH_CHECK_INTERVAL)


# ─── Resolution Logic ─────────────────────────────────────────

class ResolveResponse(BaseModel):
    region: str
    endpoint: str
    reason: str
    health: str
    avg_latency_ms: float
    is_write_primary: bool


@app.get("/resolve", response_model=ResolveResponse)
async def resolve_region(
    tenant_id: str = Query(..., description="Tenant ID for routing"),
    request_type: str = Query("read", description="read or write"),
    claims: dict = Depends(require_admin_or_platform),  # FIX I-12
):
    """Resolve the best region for a request.

    For writes: route to the tenant's write-primary region (if healthy).
    For reads: route to the nearest healthy region with lowest latency.

    If the tenant's write-primary is unhealthy, failover to the next
    priority region that is healthy.
    """
    # Get tenant's routing preferences.
    routing = TENANT_ROUTING.get(tenant_id, {"write_primary": "me-west-1", "read_any": True})

    if request_type == "write":
        # Writes go to the tenant's write-primary region.
        primary_name = routing["write_primary"]
        primary = REGIONS.get(primary_name)
        if primary and primary.health == "healthy":
            return ResolveResponse(
                region=primary.name,
                endpoint=primary.endpoint,
                reason="write_primary",
                health=primary.health,
                avg_latency_ms=primary.avg_latency_ms,
                is_write_primary=primary.is_write_primary,
            )
        # Failover: find the next healthy write-primary region by priority.
        logger.warning("Write-primary %s unhealthy for tenant %s — failing over", primary_name, tenant_id)
        candidates = sorted(
            [r for r in REGIONS.values() if r.health == "healthy" and r.is_write_primary],
            key=lambda r: r.failover_priority,
        )
        if candidates:
            failover = candidates[0]
            return ResolveResponse(
                region=failover.name,
                endpoint=failover.endpoint,
                reason=f"failover_from_{primary_name}",
                health=failover.health,
                avg_latency_ms=failover.avg_latency_ms,
                is_write_primary=failover.is_write_primary,
            )
        # No healthy write-primary — return 503.
        raise HTTPException(503, "No healthy write-primary region available")

    else:  # read
        # Reads go to the nearest healthy region (lowest latency).
        healthy = [r for r in REGIONS.values() if r.health == "healthy"]
        if not healthy:
            raise HTTPException(503, "No healthy region available")
        # Sort by weighted latency (latency / weight — lower weight = higher priority).
        best = min(healthy, key=lambda r: r.avg_latency_ms / r.weight if r.weight > 0 else r.avg_latency_ms)
        return ResolveResponse(
            region=best.name,
            endpoint=best.endpoint,
            reason="lowest_latency",
            health=best.health,
            avg_latency_ms=best.avg_latency_ms,
            is_write_primary=best.is_write_primary,
        )


@app.get("/health/regions")
async def regions_health(claims: dict = Depends(require_admin_or_platform)):  # FIX I-12
    """Get health status of all regions."""
    return {
        "regions": [
            {
                "name": r.name,
                "display_name": r.display_name,
                "endpoint": r.endpoint,
                "health": r.health,
                "avg_latency_ms": round(r.avg_latency_ms, 2),
                "consecutive_failures": r.consecutive_failures,
                "consecutive_successes": r.consecutive_successes,
                "is_write_primary": r.is_write_primary,
                "weight": r.weight,
                "last_check": datetime.fromtimestamp(r.last_check, tz=timezone.utc).isoformat() if r.last_check else None,
            }
            for r in REGIONS.values()
        ],
        "total_regions": len(REGIONS),
        "healthy_regions": sum(1 for r in REGIONS.values() if r.health == "healthy"),
    }


@app.get("/health")
async def health():
    """Service health check."""
    return {
        "status": "ok",
        "service": "global_resolver",
        "version": "1.0.0",
        "regions_monitored": len(REGIONS),
        "healthy_regions": sum(1 for r in REGIONS.values() if r.health == "healthy"),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8060)
