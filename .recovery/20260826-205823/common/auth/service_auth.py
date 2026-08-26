"""
HSAAI Shared Service-to-Service Authentication (v2.0)

All microservices must use this dependency to enforce authentication on every endpoint.
This fixes the Critical v2.0 audit finding: 8 microservices had no auth at all.
"""
import os
import logging
from typing import Optional
import httpx
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from jwt import PyJWKClient

logger = logging.getLogger("hsaai.common.auth")

# Optional: use auth_service /v1/token/verify, OR verify JWT directly with Keycloak JWKS
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth_service:8010")
KEYCLOAK_ISSUER = os.getenv("KEYCLOAK_ISSUER", "http://keycloak:8080/realms/hsaai")
KEYCLOAK_AUDIENCE = os.getenv("KEYCLOAK_AUDIENCE", "hsaai-api")
JWT_ALGORITHMS = ["RS256"]

_bearer = HTTPBearer(auto_error=False)
_jwks_client: Optional[PyJWKClient] = None


def _get_jwks_client() -> Optional[PyJWKClient]:
    global _jwks_client
    if _jwks_client is None:
        try:
            _jwks_client = PyJWKClient(f"{KEYCLOAK_ISSUER}/protocol/openid-connect/certs")
        except Exception as exc:
            logger.warning("Failed to initialize JWKS client: %s", exc)
    return _jwks_client


def verify_jwt(token: str) -> dict:
    """Verify a JWT token against Keycloak JWKS.

    Returns the decoded claims dict on success, raises HTTPException(401) on failure.
    """
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing token")
    client = _get_jwks_client()
    if client is None:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "JWKS client not available")
    try:
        signing_key = client.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=JWT_ALGORITHMS,
            audience=KEYCLOAK_AUDIENCE,
            issuer=KEYCLOAK_ISSUER,
            options={"verify_exp": True},
        )
        return claims
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expired")
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid token: {exc}")


async def verify_service_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> dict:
    """FastAPI dependency: verify Authorization Bearer token.

    Usage in any microservice:

        from packages.common.auth.service_auth import verify_service_auth
        from fastapi import Depends

        @app.get("/v1/search")
        async def search(claims: dict = Depends(verify_service_auth)):
            tenant_id = claims.get("tenant_id", "default")
            ...

    Returns the JWT claims dict on success.
    """
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Missing Authorization header. All endpoints require authentication.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return verify_jwt(credentials.credentials)


def require_permission(required_permission: str):
    """FastAPI dependency factory: require a specific permission.

    Usage:
        @app.delete("/v1/documents/{doc_id}")
        async def delete_doc(doc_id: str, claims: dict = Depends(require_permission("documents:delete"))):
            ...

    FIX S-03: Was a STUB that always returned claims (granting ALL permissions
    to ALL users). Now performs a real check against the role-permission mapping.
    """
    async def _check(claims: dict = Depends(verify_service_auth)) -> dict:
        roles = _extract_roles(claims)
        # hsaai_admin has all permissions
        if "hsaai_admin" in roles:
            return claims
        # Check role-permission mapping
        if _has_permission(roles, required_permission):
            return claims
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"Permission denied: requires '{required_permission}'. Roles: {roles}"
        )
    return _check


# FIX S-03: Real role-permission mapping (mirror of backend_core/security/rbac.py).
# Without this, require_permission was a no-op stub that granted all permissions.
ROLE_PERMISSIONS: dict[str, set[str]] = {
    "hsaai_admin": {"*"},  # all permissions
    "knowledge_admin": {
        "chat:write", "files:write", "knowledge:read", "knowledge:write",
        "knowledge:admin", "knowledge:review", "knowledge:delete",
        "audit:read", "analytics:read", "agents:read", "agents:admin",
        "agents:execute", "workflows:read", "observability:read",
        "approvals:create", "approvals:read", "approvals:decide",
        "graph:read", "graph:write", "graph:admin", "graph:audit",
        "executive:read",
    },
    "document_reviewer": {
        "chat:write", "knowledge:read", "knowledge:review", "audit:read",
        "agents:read", "agents:execute", "approvals:read", "approvals:decide",
        "executive:read",
    },
    "document_uploader": {
        "chat:write", "files:write", "knowledge:read", "knowledge:upload",
        "knowledge:write", "agents:read", "agents:execute", "approvals:create",
    },
    "department_manager": {
        "chat:write", "knowledge:read", "analytics:read", "reports:read",
        "agents:read", "agents:execute", "workflows:read", "workflows:execute",
        "approvals:create", "approvals:read", "approvals:decide",
        "connectors:read", "connectors:sync", "observability:read",
        "graph:read", "executive:read",
    },
    "ai_user": {
        "chat:write", "knowledge:read", "agents:read", "agents:execute",
        "approvals:create", "graph:read",
    },
    "auditor": {
        "knowledge:read", "audit:read", "analytics:read", "reports:read",
        "agents:read", "workflows:read", "connectors:read",
        "observability:read", "approvals:read", "graph:read", "graph:audit",
        "executive:read",
    },
    "executive": {
        "chat:write", "knowledge:read", "analytics:read", "reports:read",
        "executive:read", "executive:write",
    },
    # Service accounts (machine-to-machine)
    "service_account": {
        "chat:write", "knowledge:read", "agents:read", "agents:execute",
        "workflows:read", "workflows:execute", "audit:read", "analytics:read",
    },
    # Platform service — for internal microservice calls (RBAC, governance)
    "platform_svc": {"*"},
    # Safety-specific permissions
    "safety_admin": {
        "safety:kill_switch", "safety:approve", "safety:admin", "safety:check",
        "audit:read", "observability:read",
    },
}


def _extract_roles(claims: dict) -> list[str]:
    """Extract roles from JWT claims (direct, realm_access, or resource_access)."""
    roles: list[str] = []
    # Direct roles claim
    direct = claims.get("roles") or claims.get("role") or []
    if isinstance(direct, str):
        roles.append(direct)
    elif isinstance(direct, list):
        roles.extend([str(r) for r in direct])
    # realm_access.roles
    realm = claims.get("realm_access") or {}
    if isinstance(realm, dict):
        realm_roles = realm.get("roles") or []
        if isinstance(realm_roles, list):
            roles.extend([str(r) for r in realm_roles])
    # resource_access.<client>.roles
    resource_access = claims.get("resource_access") or {}
    if isinstance(resource_access, dict):
        for _, data in resource_access.items():
            if isinstance(data, dict):
                client_roles = data.get("roles") or []
                if isinstance(client_roles, list):
                    roles.extend([str(r) for r in client_roles])
    # Dedupe preserving order
    deduped: list[str] = []
    for r in roles:
        if r and r not in deduped:
            deduped.append(r)
    return deduped


def _has_permission(roles: list[str], permission: str) -> bool:
    """Check if any of the user's roles grant the requested permission."""
    for role in roles:
        perms = ROLE_PERMISSIONS.get(role, set())
        if "*" in perms or permission in perms:
            return True
    return False


def get_tenant_id(claims: dict) -> str:
    """Extract tenant_id from JWT claims. NEVER trust client headers."""
    return claims.get("tenant_id", "default")


def get_workspace_id(claims: dict) -> str:
    """Extract workspace_id from JWT claims."""
    return claims.get("workspace_id", "default")


def get_user_id(claims: dict) -> str:
    """Extract user_id (sub) from JWT claims."""
    return claims.get("sub", "unknown")
