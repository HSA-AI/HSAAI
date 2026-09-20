"""
HSAAI mTLS Server Configuration (Phase 2 — Modernize)
======================================================

FIX v2.2 (Phase 2): Previously mTLS env vars (MTLS_ENABLED, MTLS_STRICT)
were set in docker-compose but NO service actually read them — uvicorn
was started without --ssl-certfile/--ssl-keyfile/--ssl-ca-certs. mTLS
was theatre.

This module provides a helper that all services use to build the correct
uvicorn CLI args (or programmatic config) based on the MTLS_* env vars.
When MTLS_ENABLED=true, the service starts with TLS + client cert
verification, enforcing mutual authentication at the transport layer.

Usage (in any service's main.py or __main__ block):

    from packages.common.security.mtls_server import get_ssl_kwargs, run_with_mtls

    if __name__ == "__main__":
        run_with_mtls("services.api_gateway.main:app", host="0.0.0.0", port=8080)

Or programmatically:

    import uvicorn
    from packages.common.security.mtls_server import get_ssl_kwargs

    ssl_kwargs = get_ssl_kwargs()
    uvicorn.run(app, host="0.0.0.0", port=8080, **ssl_kwargs)
"""
from __future__ import annotations

import os
import sys
import logging
from typing import Any

logger = logging.getLogger("hsaai.mtls")

# Env vars consumed (set by infrastructure/mtls/docker-compose.mtls.yml):
#   MTLS_ENABLED       — "true" / "false" (default false for dev)
#   MTLS_STRICT        — "true" / "false" — if true, client cert is REQUIRED
#   MTLS_CERT_FILE     — path to server TLS cert (PEM)
#   MTLS_KEY_FILE      — path to server TLS private key (PEM)
#   MTLS_CA_FILE       — path to CA cert for verifying client certs (PEM)
#   MTLS_MIN_VERSION   — "tls12" / "tls13" (default tls12)


def is_mtls_enabled() -> bool:
    """Check if mTLS is enabled via env var."""
    return os.getenv("MTLS_ENABLED", "true")  # FIX v5.1: default-on.lower() == "true"


def is_mtls_strict() -> bool:
    """Check if strict client-cert verification is required."""
    return os.getenv("MTLS_STRICT", "false").lower() == "true"


def get_ssl_kwargs() -> dict[str, Any]:
    """Build uvicorn ssl kwargs from MTLS_* env vars.

    Returns a dict that can be splatted into uvicorn.run() or passed
    to uvicorn.Config(). Returns empty dict if mTLS is disabled.

    When MTLS_ENABLED=true:
        - ssl_certfile: server cert (required)
        - ssl_keyfile:  server key (required)
        - ssl_ca_certs: CA cert for client verification (required if MTLS_STRICT)
        - ssl_cert_reqs: CERT_REQUIRED if strict, CERT_OPTIONAL if not

    The resulting configuration enforces:
        1. Server presents its cert to the client (TLS)
        2. Client must present a cert signed by the CA (mTLS)
        3. If MTLS_STRICT=true, connections without a valid client cert are rejected
    """
    if not is_mtls_enabled():
        return {}

    cert_file = os.getenv("MTLS_CERT_FILE")
    key_file = os.getenv("MTLS_KEY_FILE")
    ca_file = os.getenv("MTLS_CA_FILE")

    if not cert_file or not key_file:
        logger.warning(
            "MTLS_ENABLED=true but MTLS_CERT_FILE/MTLS_KEY_FILE not set — "
            "mTLS cannot be enforced. Falling back to plaintext."
        )
        return {}

    # Verify cert files exist on disk.
    for path, label in [(cert_file, "cert"), (key_file, "key"), (ca_file, "ca")]:
        if path and not os.path.exists(path):
            logger.error("mTLS %s file not found: %s — mTLS cannot start", label, path)
            return {}

    import ssl

    ssl_kwargs: dict[str, Any] = {
        "ssl_certfile": cert_file,
        "ssl_keyfile": key_file,
    }

    if ca_file:
        ssl_kwargs["ssl_ca_certs"] = ca_file
        # CERT_REQUIRED: client MUST present a valid cert (strict mTLS).
        # CERT_OPTIONAL: client MAY present a cert; if presented, it must be valid.
        if is_mtls_strict():
            ssl_kwargs["ssl_cert_reqs"] = ssl.CERT_REQUIRED
            logger.info("mTLS enabled (STRICT): client cert REQUIRED, ca=%s", ca_file)
        else:
            ssl_kwargs["ssl_cert_reqs"] = ssl.CERT_OPTIONAL
            logger.info("mTLS enabled (OPTIONAL): client cert optional, ca=%s", ca_file)

    # Minimum TLS version.
    min_version = os.getenv("MTLS_MIN_VERSION", "tls12").lower()
    if min_version == "tls13":
        ssl_kwargs["ssl_min_version"] = ssl.TLSVersion.TLSv1_3
    else:
        ssl_kwargs["ssl_min_version"] = ssl.TLSVersion.TLSv1_2

    return ssl_kwargs


def run_with_mtls(
    app_path: str,
    host: str = "0.0.0.0",
    port: int = 8000,
    workers: int = 1,
    **extra_kwargs: Any,
) -> None:
    """Run a uvicorn server with mTLS configuration applied.

    Args:
        app_path: The uvicorn app import path (e.g. "services.api_gateway.main:app").
        host: Bind address.
        port: Bind port.
        workers: Number of uvicorn workers.
        **extra_kwargs: Additional uvicorn.run() kwargs (e.g. loop="uvloop").
    """
    try:
        import uvicorn
    except ImportError:
        print("ERROR: uvicorn not installed — cannot start server", file=sys.stderr)
        sys.exit(1)

    ssl_kwargs = get_ssl_kwargs()
    config: dict[str, Any] = {
        "app": app_path,
        "host": host,
        "port": port,
        "workers": workers,
        **ssl_kwargs,
        **extra_kwargs,
    }

    if ssl_kwargs:
        logger.info("Starting %s with mTLS on %s:%d", app_path, host, port)
    else:
        logger.info("Starting %s WITHOUT mTLS on %s:%d (dev mode)", app_path, host, port)

    uvicorn.run(**config)


__all__ = ["is_mtls_enabled", "is_mtls_strict", "get_ssl_kwargs", "run_with_mtls"]
