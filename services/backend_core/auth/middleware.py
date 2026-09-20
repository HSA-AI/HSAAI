"""
HSAAI Authentication Middleware — Production-Grade

Replaces the insecure static-token auth (HSAAI-INTERNAL) with proper
Keycloak OIDC verification via the central RBAC module.

FIX: Removed hardcoded HSAAI-INTERNAL token. All auth now flows through
verify_authorization() which validates JWT tokens via Keycloak JWKS.

SECURITY FIX v2.1 (P0): auth() is now async and properly awaits
verify_authorization. Previously it returned a coroutine that was
never awaited, silently breaking authentication.
"""

from fastapi import Header, HTTPException
from typing import Any
from backend_core.security.rbac import verify_authorization


async def auth(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    """
    Verify the Authorization header against Keycloak OIDC.

    Previously this function accepted a static token 'HSAAI-INTERNAL'
    which was a critical security vulnerability. Now it delegates to
    the enterprise RBAC module which performs proper JWT verification.
    """
    return await verify_authorization(authorization)
