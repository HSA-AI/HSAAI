"""
HSAAI Auth Service
Keycloak OIDC Authorization Code Flow + PKCE

Architecture:
- KEYCLOAK_INTERNAL_URL: server-to-server URL.
- KEYCLOAK_PUBLIC_URL: browser-facing Keycloak URL.
- Frontend never receives the internal Docker hostname.
- PKCE state/verifier are server-side.
- Tokens are stored in httpOnly cookies.
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
from fastapi import FastAPI, HTTPException, Depends, Response, Request
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


# ============================================================
# Logging
# ============================================================

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("hsaai.auth")


# ============================================================
# Environment
# ============================================================

APP_ENV = os.getenv(
    "APP_ENV",
    os.getenv("ENVIRONMENT", "development"),
).lower()

REALM = os.getenv("KEYCLOAK_REALM", "hsaai")

# Internal URL:
# Used ONLY by backend/server-side communication.
KEYCLOAK_INTERNAL_URL = os.getenv(
    "KEYCLOAK_INTERNAL_URL",
    os.getenv("KEYCLOAK_URL", "http://keycloak:8080"),
).rstrip("/")

# Public URL:
# Used by browsers.
#
# Development:
#   http://localhost:8080
#
# Production:
#   https://auth.example.com
#
# IMPORTANT:
# Never expose http://keycloak:8080 to a browser.
KEYCLOAK_PUBLIC_URL = os.getenv(
    "KEYCLOAK_PUBLIC_URL",
    "http://localhost:8080",
).rstrip("/")

KEYCLOAK_ISSUER = os.getenv(
    "KEYCLOAK_ISSUER",
    f"{KEYCLOAK_INTERNAL_URL}/realms/{REALM}",
).rstrip("/")

KEYCLOAK_PUBLIC_ISSUER = os.getenv(
    "KEYCLOAK_PUBLIC_ISSUER",
    f"{KEYCLOAK_PUBLIC_URL}/realms/{REALM}",
).rstrip("/")

KEYCLOAK_AUDIENCE = os.getenv(
    "KEYCLOAK_AUDIENCE",
    "hsaai-api",
)

FRONTEND_CLIENT_ID = os.getenv(
    "KEYCLOAK_FRONTEND_CLIENT_ID",
    "hsaai-frontend",
)

JWT_SECRET = os.getenv("JWT_SECRET", "")

if APP_ENV in {"production", "prod"}:
    if not JWT_SECRET:
        raise RuntimeError(
            "JWT_SECRET must be set in production."
        )

    if len(JWT_SECRET) < 32:
        raise RuntimeError(
            "JWT_SECRET must be at least 32 characters in production."
        )


# ============================================================
# Cookies
# ============================================================

COOKIE_DOMAIN = os.getenv("COOKIE_DOMAIN", "")

COOKIE_SECURE = (
    os.getenv("COOKIE_SECURE", "").lower() == "true"
    if os.getenv("COOKIE_SECURE") is not None
    else APP_ENV in {"production", "prod"}
)

COOKIE_SAMESITE = os.getenv(
    "COOKIE_SAMESITE",
    "lax",
)

ACCESS_TOKEN_MAX_AGE = int(
    os.getenv("ACCESS_TOKEN_MAX_AGE", "900")
)

REFRESH_TOKEN_MAX_AGE = int(
    os.getenv("REFRESH_TOKEN_MAX_AGE", "86400")
)


# ============================================================
# FastAPI
# ============================================================

app = FastAPI(
    title="HSAAI Auth Service",
    version="11.0.0",
)

bearer = HTTPBearer(auto_error=False)


# ============================================================
# Temporary stores
#
# Production recommendation:
# move these to Redis/PostgreSQL.
# ============================================================

_pkce_states: dict[str, dict] = {}
_mfa_secrets: dict[str, str] = {}


# ============================================================
# Models
# ============================================================

class LoginRequest(BaseModel):
    username: str
    password: str
    otp: str | None = None


class MfaEnrollRequest(BaseModel):
    pass


class MfaVerifyRequest(BaseModel):
    otp: str


class TokenExchangeRequest(BaseModel):
    code: str
    state: str
    redirect_uri: str


# ============================================================
# URL helpers
# ============================================================

def internal_issuer() -> str:
    return f"{KEYCLOAK_INTERNAL_URL}/realms/{REALM}"


def public_issuer() -> str:
    return KEYCLOAK_PUBLIC_ISSUER


def internal_endpoint(path: str) -> str:
    return f"{internal_issuer()}/{path.lstrip('/')}"


def public_endpoint(path: str) -> str:
    return f"{public_issuer()}/{path.lstrip('/')}"


# ============================================================
# PKCE
# ============================================================

def generate_code_verifier() -> str:
    return secrets.token_urlsafe(64)


def generate_code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(
        verifier.encode("ascii")
    ).digest()

    return base64.urlsafe_b64encode(
        digest
    ).rstrip(b"=").decode("ascii")


# ============================================================
# JWT / JWKS
# ============================================================

@lru_cache(maxsize=1)
def jwks_client():
    if PyJWKClient is None:
        return None

    return PyJWKClient(
        f"{internal_issuer()}/protocol/openid-connect/certs"
    )


def extract_roles(claims: dict) -> list[str]:
    roles: set[str] = set()

    realm_access = claims.get("realm_access") or {}

    for role in realm_access.get("roles", []) or []:
        roles.add(role)

    resource_access = claims.get("resource_access") or {}

    for resource in resource_access.values():
        if not isinstance(resource, dict):
            continue

        for role in resource.get("roles", []) or []:
            roles.add(role)

    return sorted(roles)


def verify_keycloak_token(token: str) -> dict:
    if jwt is None or jwks_client() is None:
        raise HTTPException(
            status_code=500,
            detail=(
                "PyJWT with crypto support is required "
                "for Keycloak verification"
            ),
        )

    try:
        signing_key = jwks_client().get_signing_key_from_jwt(token)

        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=KEYCLOAK_AUDIENCE,
            issuer=KEYCLOAK_ISSUER,
            options={
                "verify_exp": True,
            },
        )

        claims["roles"] = extract_roles(claims)

        return claims

    except Exception as exc:
        logger.warning(
            "Keycloak token verification failed: %s",
            exc,
        )

        raise HTTPException(
            status_code=401,
            detail="Invalid Keycloak token",
        )


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
):
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Missing bearer token",
        )

    return verify_keycloak_token(
        credentials.credentials
    )


# ============================================================
# Health
# ============================================================

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "auth_service",
        "version": "11.0.0-oidc-pkce-public-url",
        "realm": REALM,
        "internal_issuer": KEYCLOAK_ISSUER,
        "public_issuer": KEYCLOAK_PUBLIC_ISSUER,
        "audience": KEYCLOAK_AUDIENCE,
        "frontend_client_id": FRONTEND_CLIENT_ID,
        "oidc_enabled": True,
        "pkce_enabled": True,
    }


# ============================================================
# Public OIDC configuration
#
# IMPORTANT:
# These URLs are intentionally PUBLIC URLs.
# ============================================================

@app.get("/v1/keycloak/config")
def keycloak_config():
    return {
        "issuer": KEYCLOAK_PUBLIC_ISSUER,

        "authorization_endpoint": public_endpoint(
            "protocol/openid-connect/auth"
        ),

        "token_endpoint": public_endpoint(
            "protocol/openid-connect/token"
        ),

        "userinfo_endpoint": public_endpoint(
            "protocol/openid-connect/userinfo"
        ),

        "end_session_endpoint": public_endpoint(
            "protocol/openid-connect/logout"
        ),

        "jwks_uri": public_endpoint(
            "protocol/openid-connect/certs"
        ),

        "realm": REALM,
        "client_id": FRONTEND_CLIENT_ID,
        "audience": KEYCLOAK_AUDIENCE,
        "scopes": [
            "openid",
            "profile",
            "email",
        ],
        "pkce_enabled": True,
        "code_challenge_method": "S256",
    }


# ============================================================
# Authorization
# ============================================================

@app.post("/v1/auth/authorize")
def authorize(
    response: Response,
    redirect_uri: str = "http://localhost:3000/api/auth/callback",
):
    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(
        code_verifier
    )

    state = secrets.token_urlsafe(32)

    _pkce_states[state] = {
        "code_verifier": code_verifier,
        "redirect_uri": redirect_uri,
        "created_at": time.time(),
    }

    now = time.time()

    expired = [
        key
        for key, value in _pkce_states.items()
        if now - value["created_at"] > 600
    ]

    for key in expired:
        _pkce_states.pop(key, None)

    params = {
        "client_id": FRONTEND_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid profile email",
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": state,
    }

    auth_url = (
        f"{public_endpoint('protocol/openid-connect/auth')}"
        f"?{urlencode(params)}"
    )

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

    return {
        "authorization_url": auth_url,
        "state": state,
    }


# ============================================================
# Authorization Code Callback
# ============================================================

@app.post("/v1/auth/callback")
async def auth_callback(
    request: TokenExchangeRequest,
    http_request: Request,
    response: Response,
):
    stored = _pkce_states.pop(
        request.state,
        None,
    )

    if not stored:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired state parameter",
        )

    if time.time() - stored["created_at"] > 600:
        raise HTTPException(
            status_code=400,
            detail="State parameter expired",
        )

    if request.redirect_uri != stored["redirect_uri"]:
        raise HTTPException(
            status_code=400,
            detail="redirect_uri mismatch",
        )

    code_verifier = stored["code_verifier"]

    async with httpx.AsyncClient(
        timeout=30
    ) as client:

        token_response = await client.post(
            internal_endpoint(
                "protocol/openid-connect/token"
            ),
            data={
                "grant_type": "authorization_code",
                "client_id": FRONTEND_CLIENT_ID,
                "code": request.code,
                "code_verifier": code_verifier,
                "redirect_uri": request.redirect_uri,
            },
            headers={
                "Content-Type":
                    "application/x-www-form-urlencoded"
            },
        )

    if token_response.status_code >= 400:
        logger.error(
            "Keycloak token exchange failed: %s",
            token_response.text[:500],
        )

        raise HTTPException(
            status_code=401,
            detail="Token exchange failed",
        )

    tokens = token_response.json()

    access_token = tokens.get(
        "access_token",
        "",
    )

    refresh_token = tokens.get(
        "refresh_token",
        "",
    )

    id_token = tokens.get(
        "id_token",
        "",
    )

    if not access_token:
        raise HTTPException(
            status_code=401,
            detail="Keycloak did not return an access token",
        )

    claims = verify_keycloak_token(
        access_token
    )

    cookie_kwargs = {
        "httponly": True,
        "secure": COOKIE_SECURE,
        "samesite": COOKIE_SAMESITE,
        "domain": COOKIE_DOMAIN or None,
        "path": "/",
    }

    response.set_cookie(
        "hsaai_access_token",
        access_token,
        max_age=ACCESS_TOKEN_MAX_AGE,
        **cookie_kwargs,
    )

    if refresh_token:
        response.set_cookie(
            "hsaai_refresh_token",
            refresh_token,
            max_age=REFRESH_TOKEN_MAX_AGE,
            **cookie_kwargs,
        )

    if id_token:
        response.set_cookie(
            "hsaai_id_token",
            id_token,
            max_age=ACCESS_TOKEN_MAX_AGE,
            **cookie_kwargs,
        )

    response.delete_cookie(
        "hsaai_pkce_verifier",
        path="/",
    )

    return {
        "user": {
            "sub": claims.get("sub"),
            "username": (
                claims.get("preferred_username")
                or claims.get("email")
            ),
            "email": claims.get("email"),
            "roles": claims.get("roles", []),
            "tenant_id": claims.get(
                "tenant_id",
                "default",
            ),
            "workspace_id": claims.get(
                "workspace_id",
                "default",
            ),
        },
        "expires_in": tokens.get(
            "expires_in",
            ACCESS_TOKEN_MAX_AGE,
        ),
    }


# ============================================================
# Direct login
# ============================================================

@app.post("/v1/auth/login")
async def login_direct(
    request: LoginRequest,
    response: Response,
):
    async with httpx.AsyncClient(
        timeout=30
    ) as client:

        token_response = await client.post(
            internal_endpoint(
                "protocol/openid-connect/token"
            ),
            data={
                "grant_type": "password",
                "client_id": FRONTEND_CLIENT_ID,
                "username": request.username,
                "password": request.password,
                "scope": "openid profile email",
            },
            headers={
                "Content-Type":
                    "application/x-www-form-urlencoded"
            },
        )

    if token_response.status_code >= 400:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
        )

    tokens = token_response.json()

    access_token = tokens.get(
        "access_token",
        "",
    )

    refresh_token = tokens.get(
        "refresh_token",
        "",
    )

    claims = verify_keycloak_token(
        access_token
    )

    if (
        "admin" in claims.get("roles", [])
        or "hsaai_admin" in claims.get("roles", [])
    ):
        if not request.otp:
            raise HTTPException(
                status_code=403,
                detail="MFA OTP is required for admin roles",
            )

    cookie_kwargs = {
        "httponly": True,
        "secure": COOKIE_SECURE,
        "samesite": COOKIE_SAMESITE,
        "domain": COOKIE_DOMAIN or None,
        "path": "/",
    }

    response.set_cookie(
        "hsaai_access_token",
        access_token,
        max_age=ACCESS_TOKEN_MAX_AGE,
        **cookie_kwargs,
    )

    if refresh_token:
        response.set_cookie(
            "hsaai_refresh_token",
            refresh_token,
            max_age=REFRESH_TOKEN_MAX_AGE,
            **cookie_kwargs,
        )

    return {
        "user": {
            "sub": claims.get("sub"),
            "username": (
                claims.get("preferred_username")
                or claims.get("email")
            ),
            "email": claims.get("email"),
            "roles": claims.get("roles", []),
        }
    }


# ============================================================
# Refresh
# ============================================================

@app.post("/v1/auth/refresh")
async def refresh_token(
    request: Request,
    response: Response,
):
    refresh_tok = request.cookies.get(
        "hsaai_refresh_token"
    )

    if not refresh_tok:
        raise HTTPException(
            status_code=401,
            detail="No refresh token",
        )

    async with httpx.AsyncClient(
        timeout=30
    ) as client:

        token_response = await client.post(
            internal_endpoint(
                "protocol/openid-connect/token"
            ),
            data={
                "grant_type": "refresh_token",
                "client_id": FRONTEND_CLIENT_ID,
                "refresh_token": refresh_tok,
            },
            headers={
                "Content-Type":
                    "application/x-www-form-urlencoded"
            },
        )

    if token_response.status_code >= 400:
        raise HTTPException(
            status_code=401,
            detail="Refresh token expired or invalid",
        )

    tokens = token_response.json()

    new_access = tokens.get(
        "access_token",
        "",
    )

    new_refresh = tokens.get(
        "refresh_token",
        "",
    )

    claims = verify_keycloak_token(
        new_access
    )

    cookie_kwargs = {
        "httponly": True,
        "secure": COOKIE_SECURE,
        "samesite": COOKIE_SAMESITE,
        "domain": COOKIE_DOMAIN or None,
        "path": "/",
    }

    response.set_cookie(
        "hsaai_access_token",
        new_access,
        max_age=ACCESS_TOKEN_MAX_AGE,
        **cookie_kwargs,
    )

    if new_refresh:
        response.set_cookie(
            "hsaai_refresh_token",
            new_refresh,
            max_age=REFRESH_TOKEN_MAX_AGE,
            **cookie_kwargs,
        )

    return {
        "user": {
            "sub": claims.get("sub"),
            "username": (
                claims.get("preferred_username")
                or claims.get("email")
            ),
            "email": claims.get("email"),
            "roles": claims.get("roles", []),
        },
        "expires_in": tokens.get(
            "expires_in",
            ACCESS_TOKEN_MAX_AGE,
        ),
    }


# ============================================================
# Logout
# ============================================================

@app.post("/v1/auth/logout")
async def logout(
    request: Request,
    response: Response,
):
    refresh_tok = request.cookies.get(
        "hsaai_refresh_token"
    )

    if refresh_tok:
        try:
            async with httpx.AsyncClient(
                timeout=10
            ) as client:

                await client.post(
                    internal_endpoint(
                        "protocol/openid-connect/logout"
                    ),
                    data={
                        "client_id":
                            FRONTEND_CLIENT_ID,
                        "refresh_token":
                            refresh_tok,
                    },
                    headers={
                        "Content-Type":
                            "application/x-www-form-urlencoded"
                    },
                )

        except Exception as exc:
            logger.warning(
                "Keycloak logout failed: %s",
                exc,
            )

    for name in (
        "hsaai_access_token",
        "hsaai_refresh_token",
        "hsaai_id_token",
        "hsaai_pkce_verifier",
    ):
        response.delete_cookie(
            name,
            path="/",
            domain=COOKIE_DOMAIN or None,
        )

    return {
        "logged_out": True
    }


# ============================================================
# Current user
# ============================================================

@app.get("/v1/auth/me")
def me(request: Request):
    access_token = request.cookies.get(
        "hsaai_access_token"
    )

    if not access_token:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
        )

    claims = verify_keycloak_token(
        access_token
    )

    return {
        "sub": claims.get("sub"),
        "username": (
            claims.get("preferred_username")
            or claims.get("email")
        ),
        "preferred_username":
            claims.get("preferred_username"),
        "email": claims.get("email"),
        "roles": claims.get("roles", []),
        "tenant_id": claims.get(
            "tenant_id",
            "default",
        ),
        "workspace_id": claims.get(
            "workspace_id",
            "default",
        ),
        "issuer": claims.get("iss"),
    }


# ============================================================
# Token verification
# ============================================================

@app.post("/v1/token/verify")
def verify_token(
    user: dict = Depends(current_user),
):
    return {
        "active": True,
        "sub": user.get("sub"),
        "roles": user.get("roles", []),
    }


# ============================================================
# MFA
# ============================================================

@app.post(
    "/v1/mfa/enroll",
    dependencies=[Depends(current_user)],
)
def mfa_enroll(
    req: MfaEnrollRequest,
    user: dict = Depends(current_user),
):
    if not pyotp:
        raise HTTPException(
            status_code=500,
            detail="pyotp dependency is not installed",
        )

    secret = pyotp.random_base32()

    user_id = user.get(
        "sub",
        "unknown",
    )

    _mfa_secrets[user_id] = secret

    username = (
        user.get("preferred_username")
        or user.get("email")
        or user_id
    )

    uri = pyotp.totp.TOTP(
        secret
    ).provisioning_uri(
        name=username,
        issuer_name="HSAAI",
    )

    return {
        "otpauth_uri": uri,
        "enrolled": True,
    }


@app.post(
    "/v1/mfa/verify",
    dependencies=[Depends(current_user)],
)
def mfa_verify(
    req: MfaVerifyRequest,
    user: dict = Depends(current_user),
):
    if not pyotp:
        raise HTTPException(
            status_code=500,
            detail="pyotp dependency is not installed",
        )

    user_id = user.get(
        "sub",
        "unknown",
    )

    secret = _mfa_secrets.get(
        user_id
    )

    if not secret:
        raise HTTPException(
            status_code=400,
            detail="MFA not enrolled for this user",
        )

    valid = pyotp.TOTP(
        secret
    ).verify(
        req.otp,
        valid_window=1,
    )

    return {
        "valid": bool(valid)
    }
