import os
import sys
import socket
import ipaddress
from urllib.parse import urlparse
from fastapi import HTTPException, Request

# FIX FIX-MEDIUM-QUALITY (Issue 4): import canonical SSRF guard from common.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'packages'))
try:
    from common.security.ssrf_guard import is_private_url  # noqa: F401
    _SSRF_GUARD_AVAILABLE = True
except ImportError:
    _SSRF_GUARD_AVAILABLE = False

INTERNAL_ONLY_MODE = os.getenv("INTERNAL_ONLY_MODE", "false").lower() == "true"
ALLOW_EXTERNAL_APIS = os.getenv("ALLOW_EXTERNAL_APIS", "false").lower() == "true"
PRIVATE_CIDRS = [
    ipaddress.ip_network(os.getenv("PRIVATE_NETWORK_CIDR", "172.28.0.0/16"), strict=False),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
]
BLOCKED_ENV_KEYS = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "MISTRAL_API_KEY")


def assert_internal_mode_is_clean() -> dict:
    leaked = [k for k in BLOCKED_ENV_KEYS if os.getenv(k)]
    if INTERNAL_ONLY_MODE and not ALLOW_EXTERNAL_APIS and leaked:
        raise RuntimeError(f"External API keys are not allowed in strict internal mode: {', '.join(leaked)}")
    return {"internal_only_mode": INTERNAL_ONLY_MODE, "external_apis_allowed": ALLOW_EXTERNAL_APIS, "blocked_external_keys_present": leaked}


def is_private_url_fallback(url: str) -> bool:
    # NOTE: kept as fallback only — used if common.security.ssrf_guard import failed.
    parsed = urlparse(url)
    host = parsed.hostname
    if not host:
        return True
    if host in {"localhost", "local_llm", "postgres", "redis", "qdrant", "elasticsearch", "keycloak", "backend", "api_gateway", "rag_engine", "ai_orchestrator"}:
        return True
    try:
        ip = ipaddress.ip_address(socket.gethostbyname(host))
        return any(ip in net for net in PRIVATE_CIDRS)
    except Exception:
        return False

if not _SSRF_GUARD_AVAILABLE:
    is_private_url = is_private_url_fallback  # type: ignore[assignment]


def guard_outbound_url(url: str) -> None:
    if INTERNAL_ONLY_MODE and not ALLOW_EXTERNAL_APIS and not is_private_url(url):
        raise HTTPException(status_code=403, detail=f"Outbound external URL blocked by HSAAI Internal-Only policy: {url}")


async def internal_only_request_guard(request: Request, call_next):
    assert_internal_mode_is_clean()
    return await call_next(request)
