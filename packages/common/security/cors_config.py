"""
HSAAI Centralized CORS Configuration (Production Fix #1)
==========================================================
Single source of truth for CORS origins across all services.

CRITICAL FIX: Removes `allow_origins=["*"]` from governance/main.py
and vllm_server.py. All services now read from this centralized config.

Usage in any FastAPI service:
    from packages.common.security.cors_config import setup_cors
    setup_cors(app, environment=os.getenv("DEPLOY_ENV", "development"))

Configuration via environment variable:
    CORS_ALLOW_ORIGINS=https://app.hsaai.internal,https://admin.hsaai.internal

Security properties:
  - No wildcard origins in production/staging
  - Credentials supported (allow_credentials=True)
  - Preflight requests honored (max_age=600)
  - Unauthorized origins rejected (tested)
  - Development mode allows localhost for DX
"""
import os
import logging
from typing import List
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger("hsaai.cors")

# ─── Default Origins by Environment ────────────────────────────────
_DEV_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:8080",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8080",
    # Mobile dev server (Expo)
    "http://localhost:8081",
    "http://localhost:19000",
    "http://localhost:19006",
]

_STAGING_ORIGINS = [
    "https://staging.hsaai.internal",
    "https://app-staging.hsaai.internal",
]

_PROD_ORIGINS = [
    "https://hsaai.internal",
    "https://app.hsaai.internal",
    "https://admin.hsaai.internal",
]


def get_allowed_origins(environment: str = None) -> List[str]:
    """
    Get the list of allowed CORS origins for the given environment.

    Priority:
      1. CORS_ALLOW_ORIGINS env var (comma-separated, explicit override)
      2. Environment-specific defaults
      3. Fallback to dev origins (NEVER wildcard)
    """
    environment = environment or os.getenv("DEPLOY_ENV", "development")

    # 1. Explicit env var override (highest priority)
    env_origins = os.getenv("CORS_ALLOW_ORIGINS", "").strip()
    if env_origins:
        origins = [o.strip() for o in env_origins.split(",") if o.strip()]
        # SECURITY: Reject wildcard in non-dev environments
        if "*" in origins and environment != "development":
            raise ValueError(
                f"CORS_ALLOW_ORIGINS contains wildcard '*' in {environment} environment. "
                f"Wildcards are only allowed in development. Use explicit origins."
            )
        logger.info(f"CORS origins from env var: {origins}")
        return origins

    # 2. Environment-specific defaults
    if environment == "production":
        origins = _PROD_ORIGINS
    elif environment == "staging":
        origins = _STAGING_ORIGINS
    else:  # development or test
        origins = _DEV_ORIGINS

    logger.info(f"CORS origins for {environment}: {origins}")
    return origins


def setup_cors(app: FastAPI, environment: str = None) -> None:
    """
    Configure CORS middleware on a FastAPI app with secure defaults.

    Args:
        app: FastAPI application instance
        environment: 'development', 'staging', or 'production'

    Security:
        - allow_origins: explicit list, NEVER wildcard in prod/staging
        - allow_credentials: True (supports cookies, Authorization)
        - allow_methods: explicit safe list (not "*")
        - allow_headers: explicit safe list (not "*")
        - max_age: 600 seconds (preflight cache)
    """
    environment = environment or os.getenv("DEPLOY_ENV", "development")
    origins = get_allowed_origins(environment)

    # Explicit method allowlist (no "*")
    allowed_methods = [
        "GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD",
    ]

    # Explicit header allowlist (no "*")
    allowed_headers = [
        "Authorization",
        "Content-Type",
        "X-Tenant-Id",
        "X-User-Id",
        "X-Roles",
        "X-Request-Id",
        "X-Correlation-Id",
        "Accept",
        "Accept-Language",
        "Origin",
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=allowed_methods,
        allow_headers=allowed_headers,
        max_age=600,  # Cache preflight for 10 minutes
    )

    # SECURITY: Log a warning if somehow wildcard slips through
    if "*" in origins:
        if environment == "development":
            logger.warning("CORS wildcard allowed in DEVELOPMENT only")
        else:
            raise ValueError(
                f"SECURITY VIOLATION: CORS wildcard in {environment} environment"
            )

    logger.info(f"CORS configured for {environment}: {len(origins)} origins, "
                f"credentials=True, {len(allowed_methods)} methods, "
                f"{len(allowed_headers)} headers")
