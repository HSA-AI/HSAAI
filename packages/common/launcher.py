"""
HSAAI Service Launcher (Phase 2 — Modernize)
=============================================

A single entry point that all services use to start uvicorn with:
  - mTLS configuration (from MTLS_* env vars)
  - Observability (OTEL exporter endpoint)
  - Graceful shutdown
  - Consistent logging

Usage in Dockerfile CMD:
    CMD ["python", "-m", "packages.common.launcher", "--app", "main:app", "--port", "8060"]

Or when the service has its own __main__ block, import and call:
    from packages.common.launcher import launch
    launch("main:app", port=8060)
"""
from __future__ import annotations

import argparse
import logging
import os
import sys

logger = logging.getLogger("hsaai.launcher")


def launch(app_path: str, host: str = "0.0.0.0", port: int = 8000, workers: int = 1) -> None:
    """Launch a uvicorn server with mTLS + observability configured.

    Args:
        app_path: The uvicorn app import path (e.g. "main:app" or "services.api_gateway.main:app").
        host: Bind address (default 0.0.0.0).
        port: Bind port.
        workers: Number of uvicorn workers.
    """
    # Ensure packages/ is importable.
    packages_dir = os.path.join(os.path.dirname(__file__), "..", "..")
    abs_packages = os.path.abspath(packages_dir)
    if abs_packages not in sys.path:
        sys.path.insert(0, abs_packages)

    try:
        import uvicorn
    except ImportError:
        print("ERROR: uvicorn not installed", file=sys.stderr)
        sys.exit(1)

    # Build mTLS kwargs from env vars.
    ssl_kwargs: dict = {}
    try:
        from common.security.mtls_server import get_ssl_kwargs, is_mtls_enabled
        ssl_kwargs = get_ssl_kwargs()
        if is_mtls_enabled() and ssl_kwargs:
            logger.info("mTLS enabled — server will require client certs")
        elif is_mtls_enabled():
            logger.warning("MTLS_ENABLED=true but certs not configured — starting plaintext")
    except ImportError:
        logger.debug("mTLS helper not available — starting without mTLS")

    # Build uvicorn config.
    config: dict = {
        "app": app_path,
        "host": host,
        "port": port,
        "workers": workers,
        "loop": os.getenv("UVICORN_LOOP", "auto"),
        "http": os.getenv("UVICORN_HTTP", "auto"),
        "log_level": os.getenv("LOG_LEVEL", "info").lower(),
        "access_log": os.getenv("UVICORN_ACCESS_LOG", "true").lower() == "true",
        "proxy_headers": True,
        "forwarded_allow_ips": "*",
        **ssl_kwargs,
    }

    logger.info("Launching %s on %s:%d (workers=%d, mTLS=%s)",
                app_path, host, port, workers, bool(ssl_kwargs))
    uvicorn.run(**config)


def main() -> None:
    parser = argparse.ArgumentParser(description="HSAAI service launcher with mTLS support")
    parser.add_argument("--app", required=True, help="uvicorn app path (e.g. main:app)")
    parser.add_argument("--host", default="0.0.0.0", help="bind host")
    parser.add_argument("--port", type=int, default=8000, help="bind port")
    parser.add_argument("--workers", type=int, default=1, help="uvicorn workers")
    args = parser.parse_args()
    launch(args.app, host=args.host, port=args.port, workers=args.workers)


if __name__ == "__main__":
    main()
