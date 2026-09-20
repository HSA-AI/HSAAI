"""
HSAAI FastAPI Documentation Hardening (Phase 29)
===================================================
Production environments MUST NOT expose:
  - /docs (Swagger UI)
  - /redoc (ReDoc)
  - /openapi.json (OpenAPI schema)

This module provides environment-aware configuration for FastAPI apps.

Usage:
    from packages.common.security.fastapi_hardening import create_hardened_app

    app = create_hardened_app(
        title="HSAAI LLM Gateway",
        version="1.0.0",
        environment=os.getenv("DEPLOY_ENV", "development"),
    )
"""
import os
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse


def create_hardened_app(
    title: str,
    version: str = "1.0.0",
    description: str = "",
    environment: str = None,
    docs_token: Optional[str] = None,
) -> FastAPI:
    """
    Create a FastAPI app with environment-aware documentation exposure.

    Args:
        title: App title
        version: App version
        description: App description
        environment: 'development', 'staging', or 'production'
        docs_token: Optional bearer token required to access docs in production

    Production behavior:
        - /docs disabled
        - /redoc disabled
        - /openapi.json requires bearer token (if docs_token set)
          or fully disabled (if docs_token None)
    """
    environment = environment or os.getenv("DEPLOY_ENV", "development")
    is_production = environment == "production"
    is_staging = environment == "staging"

    # In production: disable all docs endpoints
    # In staging: disable docs (consistent with production)
    # In development: enable everything
    app = FastAPI(
        title=title,
        version=version,
        description=description,
        docs_url=None if (is_production or is_staging) else "/docs",
        redoc_url=None if (is_production or is_staging) else "/redoc",
        openapi_url=None if (is_production and not docs_token) else "/openapi.json",
    )

    # Add environment info to app state
    app.state.environment = environment
    app.state.is_production = is_production
    app.state.docs_token = docs_token

    # If production but docs_token provided, add protected openapi endpoint
    if is_production and docs_token:
        security = HTTPBearer()

        @app.get("/openapi.json", include_in_schema=False)
        async def protected_openapi(credentials: HTTPAuthorizationCredentials = Depends(security)):
            if credentials.credentials != docs_token:
                raise HTTPException(403, "Documentation access denied")
            from fastapi.openapi.utils import get_openapi
            return JSONResponse(get_openapi(title=title, version=version, routes=app.routes))

    # Add security headers middleware
    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        if is_production:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            response.headers["Content-Security-Policy"] = "default-src 'self'"
        return response

    return app


def verify_docs_access(token: str) -> bool:
    """Verify token for accessing protected documentation endpoints."""
    expected = os.getenv("HSAAI_DOCS_TOKEN")
    if not expected:
        return False
    return token == expected
