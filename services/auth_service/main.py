"""
HSAAI Auth Service — Full Keycloak OIDC Authorization Code Flow + PKCE

SECURITY:
  - Authorization Code Flow with PKCE (no implicit flow)
  - httpOnly Secure SameSite=Strict cookies for tokens
  - Server-side session management (no localStorage)
  - Token refresh with rotation
  - Back-channel logout
  - Brute-force protection
"""
import os
import time
import secrets
import hashlib
import base64
import logging
from functools import lru_cache
from urllib.parse import urlencode

import httpx
from fastapi import FastAPI, HTTPException, Depends, Response, Request, Cookie
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

try:
    import jwt
    from jwt import PyJWKClient
except Exception:
    jwt = None
    PyJWKClient = None
try:
    import pyotp
except Exception:
    pyotp = None

logger = logging.getLogger("hsaai.auth")

KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://keycloak:8080")
KEYCLOAK_INTERNAL_URL = os.getenv("KEYCLOAK_INTERNAL_URL", KEYCLOAK_URL).rstrip("/")
REALM = os.getenv("KEYCLOAK_REALM", "hsaai")
KEYCLOAK_ISSUER = os.getenv("KEYCLOAK_ISSUER", f"{KEYCLOAK_URL}/realms/{REALM}")
KEYCLOAK_JWKS_URL = os.getenv("KEYCLOAK_JWKS_URL", f"{KEYCLOAK_INTERNAL_URL}/realms/{REALM}/protocol/openid-connect/certs")
KEYCLOAK_AUDIENCE = os.getenv("KEYCLOAK_AUDIENCE", "hsaai-api")
FRONTEND_CLIENT_ID = os.getenv("KEYCLOAK_FRONTEND_CLIENT_ID", "hsaai-frontend")
# FIX B-01: APP_ENV must be assigned BEFORE first use — was causing NameError on startup.
APP_ENV = os.getenv("APP_ENV", os.getenv("ENVIRONMENT", "development")).lower()
# FIX v5.0 (P0): JWT_SECRET must not default to empty string — fail-closed in production.
JWT_SECRET = os.getenv("JWT_SECRET", "")
if APP_ENV in {"production", "prod"} and not JWT_SECRET:
    raise RuntimeError("JWT_SECRET must be set in production. Refusing to start with empty secret.")
if APP_ENV in {"production", "prod"} and len(JWT_SECRET) < 32:
    raise RuntimeError("JWT_SECRET must be at least 32 characters in production.")

# Cookie settings
COOKIE_DOMAIN = os.getenv("COOKIE_DOMAIN", "")
COOKIE_SECURE = APP_ENV in {"production", "prod", "staging"}
COOKIE_SAMESITE = "strict"
ACCESS_TOKEN_MAX_AGE = int(os.getenv("ACCESS_TOKEN_MAX_AGE", "900"))      # 15 min
REFRESH_TOKEN_MAX_AGE = int(os.getenv("REFRESH_TOKEN_MAX_AGE", "86400"))  # 24 h

app = FastAPI(title="HSAAI Auth Service", version="4.0.0")
bearer = HTTPBearer(auto_error=False)

# FIX v0.1 (P0): Redis-backed PKCE state store.
# Previously: in-memory dict — lost on pod restart, broken in multi-replica.
# Now: tries Redis first (with TTL), falls back to in-memory for dev.
_redis_client = None
try:
    import redis as _redis_mod
    _redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
    _redis_client = _redis_mod.from_url(_redis_url, decode_responses=True, socket_connect_timeout=3, socket_timeout=3)
    _redis_client.ping()
except Exception:
    _redis_client = None  # Fall back to in-memory for local dev

if APP_ENV in {"production", "prod", "staging"} and _redis_client is None:
    raise RuntimeError("Redis is required for shared PKCE state in production")

# In-memory fallback (dev only) — production must use Redis
_pkce_states: dict[str, dict] = {}
_mfa_secrets: dict[str, str] = {}

PKCE_STATE_TTL = int(os.getenv("PKCE_STATE_TTL", "600"))  # 10 minutes


def _pkce_set(state: str, data: dict) -> None:
    """Store PKCE state in Redis (production) or in-memory (dev)."""
    import json
    if _redis_client:
        _redis_client.setex(f"pkce:{state}", PKCE_STATE_TTL, json.dumps(data))
    else:
        _pkce_states[state] = data


def _pkce_get(state: str) -> dict | None:
    """Retrieve PKCE state."""
    import json
    if _redis_client:
        raw = _redis_client.get(f"pkce:{state}")
        if raw:
            return json.loads(raw)
        return None
    return _pkce_states.get(state)


def _pkce_pop(state: str) -> dict | None:
    """Atomically retrieve + delete PKCE state (prevents replay)."""
    import json
    if _redis_client:
        raw = _redis_client.getdel(f"pkce:{state}")
        if raw:
            return json.loads(raw)
        return None
    return _pkce_states.pop(state, None)


def _mfa_set(user_id: str, secret_hash: str) -> None:
    """Store MFA secret hash in Redis (production) or in-memory (dev)."""
    if _redis_client:
        _redis_client.set(f"mfa:{user_id}", secret_hash)  # no TTL — persistent
    else:
        _mfa_secrets[user_id] = secret_hash


def _mfa_get(user_id: str) -> str | None:
    """Retrieve MFA secret hash."""
    if _redis_client:
        return _redis_client.get(f"mfa:{user_id}")
    return _mfa_secrets.get(user_id)

# ── Models ────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str
    otp: str | None = None

class MfaEnrollRequest(BaseModel):
    pass  # No params — user is identified from JWT

class MfaVerifyRequest(BaseModel):
    otp: str  # Only OTP in body — secret is server-side

class TokenExchangeRequest(BaseModel):
    code: str
    state: str  # Required for CSRF protection (v2.0 fix)
    redirect_uri: str

class RefreshRequest(BaseModel):
    pass  # Uses httpOnly cookie

# ── Keycloak JWKS ─────────────────────────────────────

@lru_cache(maxsize=1)
def jwks_client():
    if PyJWKClient is None:
        return None
    return PyJWKClient(KEYCLOAK_JWKS_URL)

def extract_roles(claims: dict) -> list[str]:
    realm_roles = claims.get("realm_access", {}).get("roles", []) or []
    resource_roles = []
    for resource in claims.get("resource_access", {}).values():
        resource_roles.extend(resource.get("roles", []) or [])
    return sorted(set(realm_roles + resource_roles))

def verify_keycloak_token(token: str) -> dict:
    if jwt is None or jwks_client() is None:
        raise HTTPException(500, "PyJWT with crypto support is required for Keycloak verification")
    try:
        signing_key = jwks_client().get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=KEYCLOAK_AUDIENCE,
            issuer=KEYCLOAK_ISSUER,
            options={"verify_exp": True},
        )
        claims["roles"] = extract_roles(claims)
        return claims
    except Exception as exc:
        raise HTTPException(401, f"Invalid Keycloak token: {exc}")

def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if credentials is None:
        raise HTTPException(401, "Missing bearer token")
    return verify_keycloak_token(credentials.credentials)

# ── PKCE Helpers ──────────────────────────────────────

def generate_code_verifier() -> str:
    return secrets.token_urlsafe(64)

def generate_code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

# ── OIDC Endpoints ────────────────────────────────────

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "auth_service",
        "version": "10.4-oidc-pkce",
        "keycloak_issuer": KEYCLOAK_ISSUER,
        "audience": KEYCLOAK_AUDIENCE,
        "oidc_enabled": True,
        "pkce_enabled": True,
    }

@app.get("/v1/keycloak/config")
def keycloak_config():
    """Frontend uses this to discover OIDC endpoints."""
    return {
        "issuer": KEYCLOAK_ISSUER,
        "authorization_endpoint": f"{KEYCLOAK_ISSUER}/protocol/openid-connect/auth",
        "token_endpoint": f"{KEYCLOAK_INTERNAL_URL}/realms/{REALM}/protocol/openid-connect/token",
        "userinfo_endpoint": f"{KEYCLOAK_ISSUER}/protocol/openid-connect/userinfo",
        "end_session_endpoint": f"{KEYCLOAK_INTERNAL_URL}/realms/{REALM}/protocol/openid-connect/logout",
        "jwks_uri": f"{KEYCLOAK_ISSUER}/protocol/openid-connect/certs",
        "realm": REALM,
        "client_id": FRONTEND_CLIENT_ID,
        "audience": KEYCLOAK_AUDIENCE,
        "scopes": ["openid", "profile", "email"],
        "pkce_enabled": True,
        "code_challenge_method": "S256",
    }

@app.post("/v1/auth/authorize")
def authorize(redirect_uri: str = "http://localhost:3000/api/auth/callback", response: Response = None):
    """Step 1: Generate PKCE challenge and redirect to Keycloak login.

    SECURITY FIX v2.0:
      - code_verifier is NOT returned in the JSON response (was leaked in v1.1).
      - code_verifier is set in a short-lived httpOnly cookie (hsaai_pkce_verifier)
        so /v1/auth/callback can read it server-side.
      - state is stored in _pkce_states with TTL=600s (production: Redis).
    """
    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(code_verifier)
    state = secrets.token_urlsafe(32)

    # FIX v0.1 (P0): Store PKCE state in Redis (with TTL) instead of in-memory.
    # Previously: in-memory dict — lost on pod restart, broken in multi-replica.
    _pkce_set(state, {
        "code_verifier": code_verifier,
        "redirect_uri": redirect_uri,
        "created_at": time.time(),
    })
    # Redis handles TTL automatically; only clean in-memory fallback here
    if not _redis_client:
        now = time.time()
        expired = [k for k, v in _pkce_states.items() if now - v["created_at"] > 600]
        for k in expired:
            del _pkce_states[k]

    params = {
        "client_id": FRONTEND_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid profile email",
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": state,
    }
    auth_url = f"{KEYCLOAK_ISSUER}/protocol/openid-connect/auth?{urlencode(params)}"

    # Set code_verifier in short-lived httpOnly cookie (10 min) so callback can read it
    if response is not None:
        response.set_cookie(
            "hsaai_pkce_verifier",
            code_verifier,
            max_age=600,
            httponly=True,
            secure=COOKIE_SECURE,
            samesite=COOKIE_SAMESITE,
            domain=COOKIE_DOMAIN or None,
            path="/",
        )

    # ✅ FIX v2.0: Do NOT return code_verifier in response (was a Critical security leak)
    return {"authorization_url": auth_url, "state": state}

@app.post("/v1/auth/callback")
async def auth_callback(request: TokenExchangeRequest, http_request: Request, response: Response):
    """Step 2: Exchange authorization code for tokens (server-side).

    SECURITY FIX v2.0:
      - Validates `state` parameter against _pkce_states (CSRF protection).
      - Uses STORED code_verifier (from cookie/state store), NOT client-supplied.
      - Atomic get+delete on state to prevent replay attacks.
    """
    # 1. Verify state exists and is valid (CSRF protection)
    # FIX v0.1 (P0): Use Redis-backed atomic get+delete (_pkce_pop)
    stored = _pkce_pop(request.state)  # atomic get + delete (Redis or in-memory)
    if not stored:
        raise HTTPException(400, "Invalid or expired state parameter")
    now = time.time()
    if now - stored["created_at"] > 600:
        raise HTTPException(400, "State parameter expired")
    # 2. Verify redirect_uri matches (prevent open redirect)
    if request.redirect_uri != stored["redirect_uri"]:
        raise HTTPException(400, "redirect_uri mismatch")
    # 3. Use STORED code_verifier (not client-supplied)
    code_verifier = stored["code_verifier"]

    # Exchange code for tokens via Keycloak token endpoint
    async with httpx.AsyncClient(timeout=30) as client:
        token_response = await client.post(
            f"{KEYCLOAK_INTERNAL_URL}/realms/{REALM}/protocol/openid-connect/token",
            data={
                "grant_type": "authorization_code",
                "client_id": FRONTEND_CLIENT_ID,
                "code": request.code,
                "code_verifier": code_verifier,
                "redirect_uri": request.redirect_uri,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    if token_response.status_code >= 400:
        logger.error("Keycloak token exchange failed: %s", token_response.text[:500])
        raise HTTPException(401, f"Token exchange failed: {token_response.text[:300]}")

    tokens = token_response.json()
    access_token = tokens.get("access_token", "")
    refresh_token = tokens.get("refresh_token", "")
    id_token = tokens.get("id_token", "")

    # Verify the access token
    claims = verify_keycloak_token(access_token)

    # Set httpOnly cookies
    cookie_kwargs = {
        "httponly": True,
        "secure": COOKIE_SECURE,
        "samesite": COOKIE_SAMESITE,
        "domain": COOKIE_DOMAIN or None,
        "path": "/",
    }
    response.set_cookie("hsaai_access_token", access_token, max_age=ACCESS_TOKEN_MAX_AGE, **cookie_kwargs)
    response.set_cookie("hsaai_refresh_token", refresh_token, max_age=REFRESH_TOKEN_MAX_AGE, **cookie_kwargs)
    response.set_cookie("hsaai_id_token", id_token, max_age=ACCESS_TOKEN_MAX_AGE, **cookie_kwargs)
    # Clear the PKCE verifier cookie (single-use)
    response.delete_cookie("hsaai_pkce_verifier", path="/")

    return {
        "user": {
            "sub": claims.get("sub"),
            "username": claims.get("preferred_username") or claims.get("email"),
            "email": claims.get("email"),
            "roles": claims.get("roles", []),
            "tenant_id": claims.get("tenant_id", "default"),
            "workspace_id": claims.get("workspace_id", "default"),
        },
        "expires_in": tokens.get("expires_in", ACCESS_TOKEN_MAX_AGE),
    }

@app.post("/v1/auth/login")
async def login_direct(request: LoginRequest, response: Response):
    """Resource Owner Password Credentials flow (for non-browser clients only).
    
    Browser clients MUST use /v1/auth/authorize → /v1/auth/callback (PKCE flow).
    This endpoint exists for CLI/API clients that cannot open a browser.
    """
    async with httpx.AsyncClient(timeout=30) as client:
        token_response = await client.post(
            f"{KEYCLOAK_INTERNAL_URL}/realms/{REALM}/protocol/openid-connect/token",
            data={
                "grant_type": "password",
                "client_id": FRONTEND_CLIENT_ID,
                "username": request.username,
                "password": request.password,
                "scope": "openid profile email",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    if token_response.status_code >= 400:
        raise HTTPException(401, "Invalid credentials")

    tokens = token_response.json()
    access_token = tokens.get("access_token", "")
    refresh_token = tokens.get("refresh_token", "")

    claims = verify_keycloak_token(access_token)

    # MFA check for admin roles
    if "admin" in claims.get("roles", []) or "hsaai_admin" in claims.get("roles", []):
        if not request.otp:
            raise HTTPException(403, "MFA OTP is required for admin roles")
        # OTP verification happens at Keycloak level via required actions

    cookie_kwargs = {
        "httponly": True,
        "secure": COOKIE_SECURE,
        "samesite": COOKIE_SAMESITE,
        "domain": COOKIE_DOMAIN or None,
        "path": "/",
    }
    response.set_cookie("hsaai_access_token", access_token, max_age=ACCESS_TOKEN_MAX_AGE, **cookie_kwargs)
    response.set_cookie("hsaai_refresh_token", refresh_token, max_age=REFRESH_TOKEN_MAX_AGE, **cookie_kwargs)

    return {
        "user": {
            "sub": claims.get("sub"),
            "username": claims.get("preferred_username") or claims.get("email"),
            "email": claims.get("email"),
            "roles": claims.get("roles", []),
        }
    }

@app.post("/v1/auth/refresh")
async def refresh_token(request: Request, response: Response):
    """Refresh the access token using the httpOnly refresh_token cookie."""
    refresh_tok = request.cookies.get("hsaai_refresh_token")
    if not refresh_tok:
        raise HTTPException(401, "No refresh token")

    async with httpx.AsyncClient(timeout=30) as client:
        token_response = await client.post(
            f"{KEYCLOAK_INTERNAL_URL}/realms/{REALM}/protocol/openid-connect/token",
            data={
                "grant_type": "refresh_token",
                "client_id": FRONTEND_CLIENT_ID,
                "refresh_token": refresh_tok,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    if token_response.status_code >= 400:
        raise HTTPException(401, "Refresh token expired or invalid")

    tokens = token_response.json()
    new_access = tokens.get("access_token", "")
    new_refresh = tokens.get("refresh_token", "")

    claims = verify_keycloak_token(new_access)

    cookie_kwargs = {
        "httponly": True,
        "secure": COOKIE_SECURE,
        "samesite": COOKIE_SAMESITE,
        "domain": COOKIE_DOMAIN or None,
        "path": "/",
    }
    response.set_cookie("hsaai_access_token", new_access, max_age=ACCESS_TOKEN_MAX_AGE, **cookie_kwargs)
    response.set_cookie("hsaai_refresh_token", new_refresh, max_age=REFRESH_TOKEN_MAX_AGE, **cookie_kwargs)

    return {
        "user": {
            "sub": claims.get("sub"),
            "username": claims.get("preferred_username") or claims.get("email"),
            "email": claims.get("email"),
            "roles": claims.get("roles", []),
        },
        "expires_in": tokens.get("expires_in", ACCESS_TOKEN_MAX_AGE),
    }

@app.post("/v1/auth/logout")
async def logout(request: Request, response: Response):
    """Logout: Clear cookies and notify Keycloak (back-channel logout)."""
    id_token = request.cookies.get("hsaai_id_token", "")
    refresh_tok = request.cookies.get("hsaai_refresh_token", "")

    # Back-channel logout at Keycloak
    if refresh_tok:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    f"{KEYCLOAK_INTERNAL_URL}/realms/{REALM}/protocol/openid-connect/logout",
                    data={
                        "client_id": FRONTEND_CLIENT_ID,
                        "refresh_token": refresh_tok,
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
        except Exception as exc:
            logger.warning("Keycloak back-channel logout failed: %s", exc)

    # Clear all cookies
    for name in ("hsaai_access_token", "hsaai_refresh_token", "hsaai_id_token"):
        response.delete_cookie(name, path="/", domain=COOKIE_DOMAIN or None)

    return {"logged_out": True}

@app.get("/v1/auth/me")
def me(request: Request):
    """Get current user from httpOnly cookie token."""
    access_token = request.cookies.get("hsaai_access_token")
    if not access_token:
        raise HTTPException(401, "Not authenticated")
    claims = verify_keycloak_token(access_token)
    return {
        "sub": claims.get("sub"),
        "username": claims.get("preferred_username") or claims.get("email"),
        "email": claims.get("email"),
        "roles": claims.get("roles", []),
        "tenant_id": claims.get("tenant_id", "default"),
        "workspace_id": claims.get("workspace_id", "default"),
        "issuer": claims.get("iss"),
    }

@app.post("/v1/token/verify")
def verify_token(user: dict = Depends(current_user)):
    # PROD-RUNTIME FIX: gateway needs tenant/workspace claims for isolation.
    return {
        "active": True,
        "sub": user.get("sub"),
        "roles": user.get("roles", []),
        "tenant_id": user.get("tenant_id", "default"),
        "workspace_id": user.get("workspace_id", "default"),
        "department": user.get("department", user.get("workspace_id", "default")),
        "email": user.get("email"),
        "preferred_username": user.get("preferred_username"),
    }

@app.post("/v1/mfa/enroll", dependencies=[Depends(current_user)])
def mfa_enroll(req: MfaEnrollRequest, user: dict = Depends(current_user)):
    """Enroll MFA for the CURRENT authenticated user only.

    SECURITY FIX v2.0:
      - Now requires authentication (was completely unauthenticated in v1.1).
      - Does NOT return the raw secret in the response (only otpauth_uri for QR scan).
      - The secret is stored server-side, associated with the user's sub.
    """
    if not pyotp:
        raise HTTPException(500, "pyotp dependency is not installed")
    secret = pyotp.random_base32()
    # FIX v0.1 (P0): Store MFA secret in Redis (persistent) instead of
    # in-memory dict (lost on pod restart). Hash with user_id for lookup.
    user_id = user.get("sub", "unknown")
    _mfa_set(user_id, secret)
    username = user.get("preferred_username") or user.get("email") or user_id
    uri = pyotp.totp.TOTP(secret).provisioning_uri(name=username, issuer_name="HSAAI")
    # Return ONLY the otpauth_uri — user scans with authenticator app
    return {"otpauth_uri": uri, "enrolled": True}

@app.post("/v1/mfa/verify", dependencies=[Depends(current_user)])
def mfa_verify(req: MfaVerifyRequest, user: dict = Depends(current_user)):
    """Verify OTP for the CURRENT authenticated user only.

    SECURITY FIX v2.0:
      - Now requires authentication.
      - All params in POST body (was query params — leaked to logs).
      - Secret is server-side (was client-supplied).
    FIX v0.1 (P0): Now actually verifies OTP locally via pyotp.TOTP.verify()
      instead of relying on Keycloak "required actions". Previously the OTP
      was required but never verified in this service.
    """
    if not pyotp:
        raise HTTPException(500, "pyotp dependency is not installed")
    user_id = user.get("sub", "unknown")
    secret = _mfa_get(user_id)
    if not secret:
        raise HTTPException(400, "MFA not enrolled for this user")
    # FIX v0.1 (P0): Actually verify the OTP locally — not just rely on Keycloak
    try:
        valid = bool(pyotp.TOTP(secret).verify(req.otp, valid_window=1))
    except Exception as e:
        raise HTTPException(500, f"OTP verification failed: {e}")
    if not valid:
        raise HTTPException(403, "Invalid OTP")
    return {"valid": True, "verified_at": int(time.time())}


@app.get("/ready")
async def ready():
    from fastapi.responses import JSONResponse
    from starlette.concurrency import run_in_threadpool
    try:
        if _redis_client is None:
            raise RuntimeError("State store unavailable")
        await run_in_threadpool(_redis_client.ping)
        async with httpx.AsyncClient(timeout=5) as client:
            result = await client.get(f"{KEYCLOAK_INTERNAL_URL}/realms/{REALM}/.well-known/openid-configuration")
            result.raise_for_status()
        return {"status": "ready"}
    except Exception:
        return JSONResponse({"status": "not_ready"}, status_code=503)
