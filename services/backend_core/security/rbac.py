import os
import asyncio
import logging
from typing import Any

import httpx
from fastapi import Header, HTTPException, Request
from jose import jwt
from jose.exceptions import JWTError

logger = logging.getLogger("hsaai.rbac")

# HSAAI Enterprise RBAC matrix. Keycloak role names are the source of truth.
# SECURITY FIX v2.0: Removed legacy "admin" and "member" demo roles.
# SECURITY FIX v2.0: Added executive:read and executive:write permissions.
# SECURITY FIX v2.1 (P0): All FastAPI dependency callables are now async and
#   properly await verify_authorization. Previously verify_authorization was
#   async but every caller invoked it without await, returning a coroutine
#   instead of claims — this silently broke authentication on every protected
#   endpoint. See Discovery Report C-1.
ROLE_PERMISSIONS = {
    "hsaai_admin": {"*"},
    "knowledge_admin": {"chat:write", "files:write", "knowledge:read", "knowledge:write", "knowledge:admin", "knowledge:review", "knowledge:delete", "audit:read", "analytics:read", "agents:read", "agents:admin", "agents:execute", "workflows:read", "observability:read", "approvals:create", "approvals:read", "graph:read", "graph:write", "graph:admin", "graph:audit", "executive:read"},
    "document_reviewer": {"chat:write", "knowledge:read", "knowledge:review", "audit:read", "agents:read", "agents:execute", "approvals:read", "approvals:decide", "executive:read"},
    "document_uploader": {"chat:write", "files:write", "knowledge:read", "knowledge:upload", "knowledge:write", "agents:read", "agents:execute", "approvals:create"},
    "department_manager": {"chat:write", "knowledge:read", "analytics:read", "reports:read", "agents:read", "agents:execute", "workflows:read", "workflows:execute", "approvals:create", "approvals:read", "approvals:decide", "connectors:read", "connectors:sync", "observability:read", "graph:read", "executive:read"},
    "ai_user": {"chat:write", "knowledge:read", "agents:read", "agents:execute", "approvals:create", "graph:read"},
    "auditor": {"knowledge:read", "audit:read", "analytics:read", "reports:read", "agents:read", "workflows:read", "connectors:read", "observability:read", "approvals:read", "graph:read", "graph:audit", "executive:read"},
    "executive": {"chat:write", "knowledge:read", "analytics:read", "reports:read", "executive:read", "executive:write"},
}

AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth_service:8010")
from backend_core.config import settings
KEYCLOAK_ISSUER = settings.effective_keycloak_issuer
KEYCLOAK_AUDIENCE = settings.keycloak_audience
KEYCLOAK_CLIENT_ID = settings.keycloak_client_id
VERIFY_KEYCLOAK_AUDIENCE = settings.verify_keycloak_audience

# FIX: Removed ALLOW_DEV_RBAC bypass. This was a critical security flaw
# that allowed any request to pass as admin without authentication.
# All requests must now go through proper Keycloak JWT verification.

# FIX B-08: JWKS fetching must be synchronous (called from sync _verify_with_keycloak_jwks).
# Was async + called without await → TypeError on every authenticated request.
_jwks_cache: dict[str, Any] | None = None
_jwks_cache_lock = asyncio.Lock()


async def _fetch_jwks_async() -> dict[str, Any]:
    """Fetch and cache JWKS from Keycloak. Async — called once then cached."""
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache
    async with _jwks_cache_lock:
        if _jwks_cache is not None:
            return _jwks_cache
        url = f"{KEYCLOAK_ISSUER.rstrip('/')}/protocol/openid-connect/certs"
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url)
            r.raise_for_status()
            _jwks_cache = r.json()
            return _jwks_cache


async def _verify_with_keycloak_jwks_async(token: str) -> dict[str, Any]:
    """Async JWT verification using cached JWKS."""
    options = {"verify_aud": VERIFY_KEYCLOAK_AUDIENCE}
    kwargs: dict[str, Any] = {"issuer": KEYCLOAK_ISSUER, "options": options}
    if VERIFY_KEYCLOAK_AUDIENCE:
        kwargs["audience"] = KEYCLOAK_AUDIENCE
    jwks = await _fetch_jwks_async()
    unverified_header = jwt.get_unverified_header(token)
    kid = unverified_header.get("kid")
    if not kid:
        raise JWTError("No kid in token header")
    key = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
    if not key:
        # Invalidate cache and retry once in case Keycloak rotated keys
        global _jwks_cache
        _jwks_cache = None
        jwks = await _fetch_jwks_async()
        key = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
        if not key:
            raise JWTError(f"No matching key for kid={kid}")
    return jwt.decode(token, key=key, algorithms=["RS256"], **kwargs)


def _roles_from_resource_access(resource_access: dict[str, Any]) -> list[str]:
    roles: list[str] = []
    if not isinstance(resource_access, dict):
        return roles
    for _, data in resource_access.items():
        if isinstance(data, dict):
            item_roles = data.get("roles") or []
            if isinstance(item_roles, list):
                roles.extend([str(x) for x in item_roles])
    return roles

def _roles_from_claims(claims: dict[str, Any]) -> list[str]:
    roles: list[str] = []
    direct = claims.get("roles") or claims.get("role") or []
    if isinstance(direct, str):
        roles.append(direct)
    elif isinstance(direct, list):
        roles.extend([str(x) for x in direct])
    realm = claims.get("realm_access") or {}
    if isinstance(realm, dict):
        realm_roles = realm.get("roles") or []
        if isinstance(realm_roles, list):
            roles.extend([str(x) for x in realm_roles])
    roles.extend(_roles_from_resource_access(claims.get("resource_access") or {}))
    # remove duplicates while preserving order
    deduped = []
    for role in roles:
        if role and role not in deduped:
            deduped.append(role)
    return deduped  # SECURITY FIX v2.0: Return empty list if no roles — was ["ai_user"]
               # which granted unintended privileges to misconfigured tokens.

def _normalize_claims(claims: dict[str, Any]) -> dict[str, Any]:
    claims = dict(claims)
    claims["roles"] = _roles_from_claims(claims)
    claims.setdefault("tenant_id", claims.get("tenant_id") or claims.get("tenant") or claims.get("organization") or "default")
    claims.setdefault("workspace_id", claims.get("workspace_id") or claims.get("workspace") or claims.get("department") or "default")
    claims.setdefault("department", claims.get("department") or claims.get("workspace_id") or "default")
    return claims

async def _verify_with_auth_service(authorization: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(f"{AUTH_SERVICE_URL}/v1/token/verify", headers={"Authorization": authorization})
    if response.status_code >= 400:
        raise HTTPException(status_code=401, detail="Invalid or expired bearer token")
    return response.json()

async def verify_authorization(authorization: str | None) -> dict[str, Any]:
    """
    Verify the bearer token against Keycloak OIDC.

    FIX: Removed the ALLOW_DEV_RBAC bypass that previously allowed
    unauthenticated access with admin privileges. Every request must
    now present a valid JWT token signed by Keycloak.

    SECURITY FIX v2.1 (P0): This function is async. All FastAPI dependency
    wrappers (require_permission, require_any_role, get_current_claims) are
    now also async and properly await this function.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing bearer token. Authentication is required.")
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header format. Expected: Bearer <token>")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Empty bearer token")

    # FIX: No more bypass. Always verify the token.
    # FIX B-08: Use the async JWKS verification — was calling sync function that internally called async without await.
    try:
        claims = await _verify_with_keycloak_jwks_async(token)
    except (JWTError, httpx.HTTPError, TypeError, ValueError) as exc:
        # Keep compatibility with the existing auth_service verifier.
        try:
            claims = await _verify_with_auth_service(authorization)
        except (httpx.HTTPError, HTTPException) as http_exc:
            logger.warning("Token verification failed: JWKS error=%s, auth_service error=%s", exc, http_exc)
            raise HTTPException(status_code=401, detail="Invalid or expired bearer token")
    return _normalize_claims(claims)

def permissions_for_roles(roles: list[str]) -> set[str]:
    allowed: set[str] = set()
    for role in roles:
        allowed |= ROLE_PERMISSIONS.get(role, set())
    return allowed

def has_permission(claims: dict[str, Any], permission: str) -> bool:
    allowed = permissions_for_roles(_roles_from_claims(claims))
    return "*" in allowed or permission in allowed

def require_permission(permission: str):
    # FIX v2.1 (P0): async + await. Previously this returned a coroutine
    # that was never awaited, breaking auth on every protected endpoint.
    async def dependency(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        claims = await verify_authorization(authorization)
        if not has_permission(claims, permission):
            raise HTTPException(status_code=403, detail=f"Permission denied: {permission}")
        return claims
    return dependency

def require_any_role(*roles: str):
    # FIX v2.1 (P0): async + await.
    async def dependency(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        claims = await verify_authorization(authorization)
        user_roles = set(_roles_from_claims(claims))
        if "hsaai_admin" not in user_roles and user_roles.isdisjoint(set(roles)):
            raise HTTPException(status_code=403, detail="Role is not allowed for this operation")
        return claims
    return dependency

async def get_current_claims(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    # FIX v2.1 (P0): async + await.
    return await verify_authorization(authorization)

async def rbac_request_middleware(request: Request, call_next):
    response = await call_next(request)
    return response
