"""
_demo_oidc_shim.py — DEPLOYMENT SHIM for the local (dockerless) demo environment.

The HSAAI web frontend discovers OIDC endpoints via GET /v1/keycloak/config and
GET /v1/auth/me, normally served by services/auth_service. In this demo runtime
auth_service runs embedded behind backend_core via this shim, backed by the
local mock IdP (scripts/mock-keycloak.js).

This file is demo infrastructure only — NOT part of the product codebase.
It is excluded from packaging (see scripts/package-hsaai.sh) and imports the
real application (backend_core.main) without modifying it.

FIX (demo-runtime D-2): the web chat page calls POST {API_BASE}/v1/chat, but
backend_core serves /chat (the /v1 prefix belongs to the api_gateway in the
compose deployment, which is not running in dockerless mode). This shim now
also bridges /v1/chat -> /chat and /v1/auth/{logout,refresh} so the dockerless
demo matches the gateway contract without touching product code.

Run with:  uvicorn _demo_oidc_shim:app   (PYTHONPATH includes services/ and repo root)
"""
import json
import os
import urllib.parse
import urllib.request

from fastapi import Request
from fastapi.responses import JSONResponse

from backend_core.main import app  # real backend application (unmodified)

ISSUER = os.environ.get("KEYCLOAK_ISSUER", "http://127.0.0.1:9080/realms/hsaai")
AUDIENCE = os.environ.get("KEYCLOAK_AUDIENCE", "hsaai-api")
CLIENT_ID = os.environ.get("KEYCLOAK_CLIENT_ID", "hsaai-frontend")
CLIENT_SECRET = os.environ.get("KEYCLOAK_CLIENT_SECRET", "hsaai-demo-secret")


@app.get("/v1/keycloak/config")
async def demo_keycloak_config():
    """OIDC discovery payload expected by the web frontend (lib/auth-provider)."""
    return {
        "issuer": ISSUER,
        "authorization_endpoint": f"{ISSUER}/protocol/openid-connect/auth",
        "token_endpoint": f"{ISSUER}/protocol/openid-connect/token",
        "userinfo_endpoint": f"{ISSUER}/protocol/openid-connect/userinfo",
        "end_session_endpoint": f"{ISSUER}/protocol/openid-connect/logout",
        "jwks_uri": f"{ISSUER}/protocol/openid-connect/certs",
        "realm": "hsaai",
        "client_id": "hsaai-frontend",
        "audience": "hsaai-frontend",
        "scopes": ["openid", "profile", "email", "roles"],
        "pkce_enabled": True,
        "code_challenge_method": "S256",
    }


@app.get("/v1/auth/me")
async def demo_auth_me(request: Request):
    """Session introspection for the web frontend — validates the httpOnly access
    token cookie against the local demo IdP JWKS."""
    token = request.cookies.get("hsaai_access_token")
    if not token:
        return JSONResponse(status_code=401, content={"detail": "Not authenticated"})
    try:
        import jwt as jose_jwt

        with urllib.request.urlopen(
            f"{ISSUER}/protocol/openid-connect/certs", timeout=5
        ) as resp:
            jwks = json.loads(resp.read().decode("utf-8"))
        header = jose_jwt.get_unverified_header(token)
        kdict = next(k for k in jwks["keys"] if k.get("kid") == header.get("kid"))
        key = jose_jwt.PyJWK.from_dict(kdict).key
        claims = jose_jwt.decode(
            token, key, algorithms=["RS256"], audience=AUDIENCE, issuer=ISSUER
        )
        roles = claims.get("roles") or claims.get("realm_access", {}).get("roles", [])
        return {
            "sub": claims.get("sub"),
            "username": claims.get("preferred_username") or claims.get("email"),
            "email": claims.get("email"),
            "roles": roles,
            "tenant_id": claims.get("tenant_id", "default"),
            "workspace_id": claims.get("workspace_id", "default"),
        }
    except Exception:
        return JSONResponse(status_code=401, content={"detail": "Invalid or expired token"})


# ---------------------------------------------------------------------------
# FIX (demo-runtime D-2): gateway-contract bridges for the dockerless demo.
# The compose deployment puts api_gateway in front of backend_core, exposing
# /v1/chat (backend: /chat). Without these bridges the web chat page 404s in
# dockerless mode. They forward the httpOnly cookie as a Bearer header, exactly
# like api_gateway does in production.
# ---------------------------------------------------------------------------
from backend_core.core.engine import process_message, stream_message  # noqa: E402
from backend_core.smart_responses.service import detect_response  # noqa: E402
from backend_core.db.database import SessionLocal  # noqa: E402
from backend_core.security.rbac import verify_authorization  # noqa: E402


def _bearer_from_cookie(request: Request) -> str | None:
    token = request.cookies.get("hsaai_access_token")
    return f"Bearer {token}" if token else None


@app.post("/v1/chat")
async def demo_v1_chat(request: Request):
    """Gateway-contract bridge: POST /v1/chat -> engine, auth via cookie."""
    authorization = _bearer_from_cookie(request)
    claims = await verify_authorization(authorization)
    payload = await request.json()
    message = payload.get("message", "")
    tenant_id = claims.get("tenant_id", "default")
    workspace_id = claims.get("workspace_id") or payload.get("workspace_id", "default")
    user = claims.get("sub") or payload.get("user", "demo-user")

    db = SessionLocal()
    try:
        smart = detect_response(db, message, tenant_id=tenant_id, workspace_id=workspace_id, user_id=user)
    finally:
        db.close()
    if smart.get("matched"):
        return JSONResponse(smart)

    result = process_message(user, message, workspace_id, tenant_id=tenant_id, claims=claims)
    want_stream = payload.get("stream", False)
    if want_stream:
        return stream_message(user, message, workspace_id, tenant_id=tenant_id, claims=claims)
    return JSONResponse(result)


@app.post("/v1/auth/logout")
async def demo_v1_logout():
    """Clear demo session cookies (mirrors auth_service behaviour)."""
    resp = JSONResponse({"status": "logged_out"})
    for name in ("hsaai_access_token", "hsaai_refresh_token", "hsaai_id_token"):
        resp.delete_cookie(name, path="/")
    return resp


@app.post("/v1/auth/refresh")
async def demo_v1_refresh(request: Request):
    """Exchange the refresh cookie for fresh tokens via the mock IdP."""
    refresh_token = request.cookies.get("hsaai_refresh_token")
    if not refresh_token:
        return JSONResponse(status_code=401, content={"detail": "No refresh token"})
    data = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }).encode()
    req = urllib.request.Request(f"{ISSUER}/protocol/openid-connect/token", data=data)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            tokens = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return JSONResponse(status_code=401, content={"detail": "Refresh failed"})
    out = JSONResponse({"status": "refreshed", "expires_in": tokens.get("expires_in")})
    out.set_cookie("hsaai_access_token", tokens["access_token"], httponly=True, samesite="lax", path="/")
    if tokens.get("refresh_token"):
        out.set_cookie("hsaai_refresh_token", tokens["refresh_token"], httponly=True, samesite="lax", path="/")
    return out
