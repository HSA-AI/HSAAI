"""
HSAAI SSRF Guard — canonical is_private_url.

FIX FIX-MEDIUM-QUALITY (Issue 4): consolidate the three divergent copies of
`_is_private_url` / `is_private_url` that previously lived in:
  - services/llm_gateway/main.py
  - services/api_gateway/main.py
  - services/backend_core/security/internal_only.py

Those copies each defined a *different* INTERNAL_HOSTS set, which meant the
egress guard behaved differently per service. This module is now the single
source of truth.

Usage:
    from common.security.ssrf_guard import is_private_url, _is_private_url

`_is_private_url` is kept as a backward-compatible alias for existing call sites.
"""
from __future__ import annotations

import ipaddress
import os
import socket
from urllib.parse import urlparse

# ─── Private / internal CIDR ranges (RFC 1918 + loopback + link-local) ─────
PRIVATE_CIDRS = [
    ipaddress.ip_network(os.getenv("PRIVATE_NETWORK_CIDR", "172.28.0.0/16"), strict=False),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),  # link-local
]

# ─── Canonical internal host allowlist (union of all previous copies) ──────
# Any host in this set is treated as private/internal without DNS lookup.
INTERNAL_HOSTS = {
    # infra
    "localhost", "127.0.0.1", "0.0.0.0",
    # datastores
    "postgres", "redis", "qdrant", "elasticsearch", "keycloak",
    # HSAAI services
    "backend", "backend_core", "api_gateway", "auth_service", "ai_orchestrator",
    "rag_engine", "analytics", "llm_gateway", "local_llm", "ollama",
    "multi_agents", "workflow_engine", "governance", "mcp_server",
    "pii_detector", "model_training", "ai_alignment",
}


def is_private_url(url: str) -> bool:
    """Return True if `url` points at a private/internal host.

    A host is considered private if any of:
      1. It is missing (e.g. malformed URL) → conservative True.
      2. It is in INTERNAL_HOSTS (DNS-free short-circuit).
      3. It is a Kubernetes internal DNS suffix (.svc / .svc.cluster.local).
      4. It resolves to an IP inside any PRIVATE_CIDRS network.
    Otherwise returns False (treat as external / potentially public).
    """
    host = urlparse(url).hostname
    if not host:
        return True
    if host in INTERNAL_HOSTS:
        return True
    if host.endswith(".svc") or host.endswith(".svc.cluster.local"):
        return True
    try:
        ip = ipaddress.ip_address(socket.gethostbyname(host))
        return any(ip in net for net in PRIVATE_CIDRS)
    except Exception:
        # DNS failure or invalid host — be conservative and treat as external
        # so the egress guard can reject it, rather than silently allowing.
        return False


# Backward-compatible alias used by llm_gateway and api_gateway call sites.
_is_private_url = is_private_url
