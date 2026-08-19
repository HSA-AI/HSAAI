"""
HSAAI ABAC Client (v3.0)

Python client for the Open Policy Agent (OPA) sidecar.
Caches decisions locally for performance (5-minute TTL).

Usage:
    from packages.common.abac.client import check_access, check_access_or_raise

    # Simple check
    if check_access(user=claims, action="documents:read", resource=doc):
        # proceed

    # Raise 403 on denial
    check_access_or_raise(
        user=claims,
        action="documents:delete",
        resource={"type": "document", "classification": "confidential", "tenant_id": "default"},
    )
"""
import os
import time
import logging
from typing import Any
import httpx
from fastapi import HTTPException

logger = logging.getLogger("hsaai.abac")

OPA_URL = os.getenv("OPA_URL", "http://opa:8181")
OPA_TIMEOUT = float(os.getenv("OPA_TIMEOUT", "2.0"))  # short timeout for sidecar
ABAC_ENABLED = os.getenv("ABAC_ENABLED", "true").lower() == "true"

# Local cache: (user_id, action, resource_hash) → (decision, expiry)
# In production, use Redis for distributed cache.
_decision_cache: dict[tuple, tuple[bool, float]] = {}
_CACHE_TTL = 300  # 5 minutes


def _cache_key(user: dict, action: str, resource: dict) -> tuple:
    user_id = user.get("sub", "unknown")
    tenant_id = user.get("tenant_id", "default")
    resource_id = resource.get("id", str(sorted(resource.items())))
    return (user_id, tenant_id, action, resource_id)


def _get_cached(key: tuple) -> bool | None:
    if key in _decision_cache:
        decision, expiry = _decision_cache[key]
        if time.time() < expiry:
            return decision
        del _decision_cache[key]
    return None


def _set_cached(key: tuple, decision: bool) -> None:
    _decision_cache[key] = (decision, time.time() + _CACHE_TTL)
    # Evict old entries
    now = time.time()
    expired = [k for k, (_, exp) in _decision_cache.items() if now >= exp]
    for k in expired:
        del _decision_cache[k]


async def check_access(
    user: dict[str, Any],
    action: str,
    resource: dict[str, Any],
    env: dict[str, Any] | None = None,
) -> bool:
    """Check if a user is allowed to perform an action on a resource.

    Args:
        user: User claims dict (sub, roles, tenant_id, department, clearance, mfa_verified).
        action: The action to perform (e.g., "documents:read").
        resource: Resource attributes (type, classification, tenant_id, owner, etc.).
        env: Optional environment attributes (ip, time, device).

    Returns:
        True if access is allowed, False otherwise.
    """
    if not ABAC_ENABLED:
        # ABAC disabled — allow (RBAC handles baseline)
        return True

    # Check cache first
    key = _cache_key(user, action, resource)
    cached = _get_cached(key)
    if cached is not None:
        return cached

    # Build OPA input
    input_data = {
        "input": {
            "user": {
                "sub": user.get("sub", "unknown"),
                "roles": user.get("roles", []),
                "tenant_id": user.get("tenant_id", "default"),
                "workspace_id": user.get("workspace_id", "default"),
                "department": user.get("department", "general"),
                "clearance": user.get("clearance", "internal"),
                "mfa_verified": user.get("mfa_verified", False),
            },
            "action": action,
            "resource": {
                "type": resource.get("type", "unknown"),
                "tenant_id": resource.get("tenant_id", user.get("tenant_id", "default")),
                "classification": resource.get("classification", "internal"),
                "owner": resource.get("owner", ""),
                "id": resource.get("id", ""),
            },
            "env": {
                "ip": (env or {}).get("ip", "127.0.0.1"),
                "time": (env or {}).get("time", ""),
                "device": (env or {}).get("device", "unknown"),
            },
        }
    }

    try:
        async with httpx.AsyncClient(timeout=OPA_TIMEOUT) as client:
            response = await client.post(
                f"{OPA_URL}/v1/data/hsaai/abac/allow",
                json=input_data,
            )
            if response.status_code >= 400:
                # FIX v2.1 (P0): Previously failed open for ALL actions, meaning a network
                # blip to OPA disabled all ABAC enforcement (a critical security regression).
                # Now: fail OPEN for read-only actions (don't break the platform), but
                # fail CLOSED for write/approve/delete/admin actions (security-critical).
                # This aligns with Zero-Trust: prefer availability for reads, security for writes.
                write_actions = {"write", "create", "update", "delete", "approve", "reject", "admin", "deploy", "execute"}
                is_write = action.split(":")[-1].lower() in write_actions if ":" in action else action.lower() in write_actions
                if is_write:
                    logger.error("OPA returned HTTP %d for WRITE action '%s' — failing CLOSED (deny)", response.status_code, action)
                    return False
                logger.warning("OPA returned HTTP %d for read action '%s' — failing OPEN (allow)", response.status_code, action)
                return True
            result = response.json()
            allowed = bool(result.get("result", False))
    except httpx.HTTPError as exc:
        # Same fail-open/closed split for network errors.
        write_actions = {"write", "create", "update", "delete", "approve", "reject", "admin", "deploy", "execute"}
        is_write = action.split(":")[-1].lower() in write_actions if ":" in action else action.lower() in write_actions
        if is_write:
            logger.error("OPA unreachable for WRITE action '%s': %s — failing CLOSED (deny)", action, exc)
            return False
        logger.warning("OPA unreachable for read action '%s': %s — failing OPEN (allow)", action, exc)
        return True
    except Exception as exc:
        # FIX S-13: Was failing OPEN on ANY exception — granted access on every error.
        # Now fails CLOSED for all errors. Set ABAC_FAIL_OPEN=true for dev only.
        if os.getenv("ABAC_FAIL_OPEN", "false").lower() == "true":
            logger.warning("ABAC check failed: %s — failing OPEN (ABAC_FAIL_OPEN=true)", exc)
            return True
        logger.error("ABAC check failed: %s — failing CLOSED (deny)", exc)
        return False

    _set_cached(key, allowed)
    return allowed


async def check_access_or_raise(
    user: dict[str, Any],
    action: str,
    resource: dict[str, Any],
    env: dict[str, Any] | None = None,
) -> None:
    """Check access and raise HTTPException(403) if denied.

    Args:
        user, action, resource, env: Same as check_access.

    Raises:
        HTTPException(403) if access is denied.
    """
    if not await check_access(user, action, resource, env):
        resource_desc = resource.get("type", "resource")
        if resource.get("id"):
            resource_desc = f"{resource_desc} {resource['id']}"
        raise HTTPException(
            status_code=403,
            detail=f"Access denied: cannot '{action}' on {resource_desc}. "
                   "This may be due to tenant isolation, data classification, "
                   "time-of-day restrictions, or MFA requirements.",
        )


async def get_decision_reason(
    user: dict[str, Any],
    action: str,
    resource: dict[str, Any],
    env: dict[str, Any] | None = None,
) -> str:
    """Get the human-readable reason for an ABAC decision (for audit logs).

    Returns:
        The decision reason (e.g., "cross_tenant_access", "insufficient_clearance").
    """
    if not ABAC_ENABLED:
        return "abac_disabled"

    input_data = {
        "input": {
            "user": user,
            "action": action,
            "resource": resource,
            "env": env or {},
        }
    }

    try:
        async with httpx.AsyncClient(timeout=OPA_TIMEOUT) as client:
            response = await client.post(
                f"{OPA_URL}/v1/data/hsaai/abac/decision",
                json=input_data,
            )
            if response.status_code < 400:
                result = response.json()
                return result.get("result", {}).get("reason", "unknown")
    except Exception as exc:
        logger.warning("ABAC reason check failed: %s", exc)

    return "unknown"


__all__ = ["check_access", "check_access_or_raise", "get_decision_reason"]
