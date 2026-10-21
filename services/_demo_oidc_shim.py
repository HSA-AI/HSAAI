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




# HSAAI_LOCAL_LLM_BRIDGE_V1
# Local demo only. Does not modify the production AI pipeline.
async def _local_hsa_llm(message: str, workspace_id: str) -> dict:
    from pathlib import Path
    import httpx

    folder = Path(
        os.environ.get(
            "HSAAI_HSA_CONTEXT_DIR",
            "/data/data/com.termux/files/home/HSAAI_HSA_Demo"
        )
    )
    system_file = folder / "system_prompt.txt"
    context_file = folder / "company_context.txt"

    system = system_file.read_text(encoding="utf-8").strip()
    reference = context_file.read_text(encoding="utf-8").strip()


    # HSAAI_FINANCIAL_FACT_GUARD_V1
    # Demo-only protection against unsupported revenue claims.
    import re

    normalized_question = message.casefold().strip()

    revenue_terms = (
        "revenue",
        "annual income",
        "turnover",
        "الإيرادات",
        "الايرادات",
        "الإيراد",
        "الايراد",
        "الدخل السنوي",
    )

    if (
        "hsaai" in normalized_question
        and any(term in normalized_question for term in revenue_terms)
    ):
        return {
            "response": (
                "No verified annual revenue figures for HSAAI "
                "are available in the provided reference data."
            ),
            "agent": "local_llm",
            "agent_name": "HSAAI Local AI",
            "source": "verified_context",
            "rag_found": 0,
            "sources": [],
            "workspace_id": workspace_id,
            "local_demo": True,
        }


    # HSAAI_VERIFIED_PROJECT_FACTS_V2
    # Demo-only verified reference responses.
    _verified_question = message.strip().casefold().replace("؟", "?")

    _relationship_questions = (
        "relationship between hsaai and hsa",
        "relationship of hsaai to hsa",
        "hsaai and hsa group",
        "علاقة hsaai",
        "علاقة المشروع بمجموعة",
        "هل hsaai تابع",
        "هل المشروع تابع",
    )

    if any(p in _verified_question for p in _relationship_questions):
        return {
            "response": (
                "HSAAI is an independent, sovereign, self-hosted "
                "enterprise AI platform developed by Haithim Nasher. "
                "It was submitted to HSA Group for consideration "
                "as an independent initiative. Submission does not "
                "imply ownership, endorsement, partnership, or "
                "adoption by HSA Group."
            ),
            "agent": "local_llm",
            "source": "verified_context",
            "sources": ["company_context.txt"],
            "workspace_id": workspace_id,
        }

    _technology_questions = (
        "what technologies does hsaai use",
        "technologies used by hsaai",
        "hsaai technology stack",
        "hsaai tech stack",
        "تقنيات hsaai",
        "ما هي تقنيات hsaai",
        "ما التقنيات التي يستخدمها hsaai",
    )

    if any(p in _verified_question for p in _technology_questions):
        from pathlib import Path as _VerifiedPath

        _context_dir = _VerifiedPath(
            os.environ.get(
                "HSAAI_HSA_CONTEXT_DIR",
                str(_VerifiedPath.home() / "HSAAI_HSA_Demo"),
            )
        )
        _technology_file = _context_dir / "technology_context.txt"

        if not _technology_file.is_file():
            return {
                "response": "Verified technology reference is unavailable.",
                "agent": "local_llm",
                "source": "reference_unavailable",
                "sources": [],
                "workspace_id": workspace_id,
            }

        _technology_answer = _technology_file.read_text(
            encoding="utf-8"
        ).strip()

        return {
            "response": _technology_answer,
            "agent": "local_llm",
            "source": "verified_context",
            "sources": ["technology_context.txt"],
            "workspace_id": workspace_id,
        }

    # HSAAI_VERIFIED_FACT_LOOKUP_V1
    # Demo-only deterministic lookup from the local reference file.
    import re

    question = message.strip().lower()

    developer_questions = (
        "who developed hsaai",
        "who created hsaai",
        "who founded hsaai",
        "من طور hsaai",
        "من طور منصة hsaai",
        "من مؤسس hsaai",
        "من أنشأ hsaai",
    )

    if any(q in question for q in developer_questions):
        match = re.search(
            r"^Founder and developer:\s*(.+)$",
            reference,
            flags=re.IGNORECASE | re.MULTILINE,
        )

        if match:
            developer = match.group(1).strip()

            # Use the English name before any Arabic translation.
            developer = developer.split("(")[0].strip()

            if developer:
                return {
                    "response": f"HSAAI was developed by {developer}.",
                    "agent": "local_llm",
                    "agent_name": "HSAAI Local AI",
                    "source": "verified_context",
                    "rag_found": 0,
                    "sources": ["company_context.txt"],
                    "workspace_id": workspace_id,
                    "local_demo": True,
                }

    greetings = {
        "مرحبا", "مرحباً", "السلام عليكم",
        "اهلا", "أهلا", "اهلاً", "hello", "hi"
    }

    if message.strip().lower() in greetings:
        return {
            "response": "مرحباً بك في HSAAI! أنا مساعدك الذكي المحلي. كيف يمكنني مساعدتك اليوم؟",
            "agent": "local_llm",
            "agent_name": "HSAAI Local AI",
            "source": "local_rule",
            "rag_found": 0,
            "sources": [],
            "workspace_id": workspace_id,
            "local_demo": True,
        }

    greetings = {
        "مرحبا", "مرحباً", "السلام عليكم",
        "اهلا", "أهلا", "اهلاً", "hello", "hi"
    }

    if message.strip().lower() in greetings:
        return {
            "response": "مرحباً بك في HSAAI! أنا مساعدك الذكي المحلي. كيف يمكنني مساعدتك اليوم؟",
            "agent": "local_llm",
            "agent_name": "HSAAI Local AI",
            "source": "local_rule",
            "rag_found": 0,
            "sources": [],
            "workspace_id": workspace_id,
            "local_demo": True,
        }

    if not system or not reference:
        raise ValueError("HSA demo customization files are empty")

    endpoint = os.environ.get(
        "HSAAI_LOCAL_LLM_URL",
        "http://127.0.0.1:8081/v1/chat/completions",
    )

    body = {
        "messages": [
            {
                "role": "system",
                "content": system,
            },
            {
                "role": "user",
                "content": (
                    "Reference data:\n"
                    + reference
                    + "\n\nQuestion:\n"
                    + message
                    + "\n\nAnswer briefly in English. "
                    "Use only verified reference facts."
                ),
            },
        ],
        "max_tokens": 48,
        "temperature": 0,
        "repeat_penalty": 1.2,
        "frequency_penalty": 0.5,
        "stream": False,
    }

    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(endpoint, json=body)
        response.raise_for_status()
        data = response.json()

    answer = data["choices"][0]["message"]["content"].strip()

    if not answer:
        raise ValueError("Local LLM returned an empty answer")

    return {
        "response": answer,
        "agent": "local_llm",
        "agent_name": "HSAAI Local AI",
        "source": "local_llm",
        "model": data.get("model", "SmolLM2-135M"),
        "rag_found": 0,
        "sources": [],
        "workspace_id": workspace_id,
        "local_demo": True,
    }

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

    # Local inference is opt-in and follows authorization.
    if os.environ.get("HSAAI_LOCAL_LLM", "").lower() == "true":
        if not isinstance(message, str) or not message.strip():
            return JSONResponse(
                status_code=400,
                content={"detail": "Message must not be empty"},
            )
        try:
            result = await _local_hsa_llm(message, workspace_id)
            return JSONResponse(result)
        except Exception:
            import logging
            logging.getLogger(__name__).exception(
                "HSAAI local inference failed"
            )
            return JSONResponse(
                status_code=503,
                content={"detail": "Local AI temporarily unavailable"},
            )

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
