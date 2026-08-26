"""
HSAAI mTLS Configuration — Mutual TLS Between Services

Provides SSL context configuration for inter-service communication
using client certificates signed by the HSAAI internal CA.

Usage in FastAPI service:
    from common.security.mtls import create_ssl_context, MTLSMiddleware

    ssl_ctx = create_ssl_context()
    app.add_middleware(MTLSMiddleware, ssl_context=ssl_ctx)
"""
import os
import ssl
import logging
from pathlib import Path
from functools import lru_cache
from typing import Optional

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("hsaai.mtls")

# Default certificate paths (mounted from Kubernetes secrets or Docker volumes)
DEFAULT_CERTS_DIR = os.getenv("MTLS_CERTS_DIR", "/certs")
DEFAULT_CA_PATH = os.getenv("MTLS_CA_PATH", f"{DEFAULT_CERTS_DIR}/ca.crt")
DEFAULT_CERT_PATH = os.getenv("MTLS_CERT_PATH", f"{DEFAULT_CERTS_DIR}/tls.crt")
DEFAULT_KEY_PATH = os.getenv("MTLS_KEY_PATH", f"{DEFAULT_CERTS_DIR}/tls.key")
MTLS_ENABLED = os.getenv("MTLS_ENABLED", "true")  # FIX v5.1: default-on (Zero Trust).lower() == "true"
MTLS_STRICT = os.getenv("MTLS_STRICT", "true").lower() == "true"  # Fail on cert errors


@lru_cache(maxsize=1)
def get_service_name() -> str:
    """Get the current service name from environment."""
    return os.getenv("SERVICE_NAME", os.getenv("HOSTNAME", "unknown"))


def create_ssl_context(
    ca_path: Optional[str] = None,
    cert_path: Optional[str] = None,
    key_path: Optional[str] = None,
    verify_mode: int = ssl.CERT_REQUIRED,
) -> ssl.SSLContext:
    """
    Create an SSL context for mTLS (mutual TLS).

    This context:
    1. Verifies the peer certificate against the internal CA
    2. Presents our client certificate to the peer
    3. Enforces TLS 1.2+ with strong cipher suites

    Args:
        ca_path: Path to the CA certificate bundle
        cert_path: Path to our service certificate
        key_path: Path to our service private key
        verify_mode: ssl.CERT_REQUIRED (default) or ssl.CERT_OPTIONAL

    Returns:
        Configured ssl.SSLContext
    """
    ca = ca_path or DEFAULT_CA_PATH
    cert = cert_path or DEFAULT_CERT_PATH
    key = key_path or DEFAULT_KEY_PATH

    # Verify files exist
    for path, name in [(ca, "CA certificate"), (cert, "Service certificate"), (key, "Service private key")]:
        if not Path(path).exists():
            raise FileNotFoundError(f"mTLS {name} not found: {path}")

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.verify_mode = verify_mode
    ctx.check_hostname = True

    # Load CA bundle for verifying peers
    ctx.load_verify_locations(ca)

    # Load our certificate and key for presenting to peers
    ctx.load_cert_chain(cert, key)

    # Strong cipher suites only
    ctx.set_ciphers(
        "ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20"
    )
    ctx.options |= ssl.OP_NO_SSLv2 | ssl.OP_NO_SSLv3 | ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1

    logger.info("mTLS SSL context created for service=%s ca=%s cert=%s", get_service_name(), ca, cert)
    return ctx


def create_httpx_ssl_context() -> ssl.SSLContext:
    """Create SSL context for httpx clients (service-to-service calls)."""
    return create_ssl_context()


def verify_peer_certificate(request: Request) -> Optional[dict]:
    """
    Extract and verify the peer certificate from the request.

    In production behind nginx/envoy, the peer cert info is forwarded
    via HTTP headers (X-Client-Cert-DN, X-Client-Cert-Verify).

    Returns:
        Dict with peer info or None if mTLS is not enabled.
    """
    if not MTLS_ENABLED:
        return None

    # Check for forwarded client cert (nginx/envoy pattern)
    client_cert_dn = request.headers.get("X-Client-Cert-DN")
    client_cert_verify = request.headers.get("X-Client-Cert-Verify")

    if client_cert_dn and client_cert_verify == "SUCCESS":
        return {
            "peer_dn": client_cert_dn,
            "peer_verified": True,
            "peer_service": _extract_service_from_dn(client_cert_dn),
        }

    # Direct TLS connection (development/testing)
    transport = request.scope.get("asgi", {}).get("transport")
    if transport and hasattr(transport, "get_peer_certificate"):
        peercert = transport.get_peer_certificate()
        if peercert:
            return {
                "peer_subject": dict(peercert.get("subject", [])),
                "peer_verified": True,
            }

    if MTLS_STRICT:
        raise HTTPException(403, "mTLS: Client certificate required")

    return None


def _extract_service_from_dn(dn: str) -> str:
    """Extract service name from a DN like CN=backend_core.hsaai.internal."""
    for part in dn.split("/"):
        if part.startswith("CN="):
            return part[3:].split(".")[0]
    return "unknown"


class MTLSMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware that enforces mTLS on incoming requests.

    When MTL_ENABLED=true, all requests must present a valid
    client certificate signed by the HSAAI internal CA.

    Usage:
        app.add_middleware(MTLSMiddleware, ssl_context=ssl_ctx)
    """

    def __init__(self, app, ssl_context: Optional[ssl.SSLContext] = None):
        super().__init__(app)
        self.ssl_context = ssl_context

    async def dispatch(self, request: Request, call_next):
        # Skip mTLS check for health endpoints
        if request.url.path in ("/health", "/ready", "/metrics"):
            return await call_next(request)

        # Skip if mTLS is not enabled
        if not MTLS_ENABLED:
            return await call_next(request)

        # Verify peer certificate
        peer = verify_peer_certificate(request)
        if peer:
            # Add peer info to request state for downstream handlers
            request.state.mtls_peer = peer
            request.state.peer_service = peer.get("peer_service", "unknown")
        elif MTLS_STRICT:
            raise HTTPException(403, "mTLS: Valid client certificate required")

        return await call_next(request)
