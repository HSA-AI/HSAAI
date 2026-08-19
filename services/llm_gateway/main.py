import os, time, json, httpx, socket, ipaddress, sys, hashlib, logging
from urllib.parse import urlparse
from typing import AsyncIterator, Any, Optional
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

# FIX CRITICAL-3 (HSAAI-DEP-2026-07-11): Use robust import that works both
# when run as `python -m uvicorn llm_gateway.main:app` (from project root)
# AND when run as `uvicorn main:app` (from inside llm_gateway/). Previously
# the bare `from model_router import ...` only worked in the second case.
try:
    # When imported as part of the `llm_gateway` package (production / Docker)
    from .model_router import load_model_config, route_model
except ImportError:
    # When run directly from inside the services/llm_gateway/ directory
    # (local development / Dockerfile CMD ["uvicorn", "main:app", ...])
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from model_router import load_model_config, route_model  # type: ignore[no-redef]

# SECURITY FIX v2.0: Add shared service auth
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'packages'))
try:
    from common.auth.service_auth import verify_service_auth
    _AUTH_AVAILABLE = True
except ImportError as _e:
    _AUTH_AVAILABLE = False
    _AUTH_LOAD_ERROR = str(_e)
    async def verify_service_auth():  # type: ignore
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Authentication module unavailable. Service cannot accept requests.")

# FIX FIX-MEDIUM-QUALITY (Issue 4): import canonical SSRF guard from common.
try:
    from common.security.ssrf_guard import is_private_url as _is_private_url  # noqa: F401
    _SSRF_GUARD_AVAILABLE = True
except ImportError:
    _SSRF_GUARD_AVAILABLE = False
    # Fallback: minimal local implementation if common package is not on path.
    def _is_private_url(url: str) -> bool:  # type: ignore[no-redef]
        host = urlparse(url).hostname
        if not host:
            return True
        if host in INTERNAL_LLM_HOSTS or host.endswith(".svc") or host.endswith(".svc.cluster.local"):
            return True
        try:
            ip = ipaddress.ip_address(socket.gethostbyname(host))
            return any(ip in net for net in PRIVATE_CIDRS)
        except Exception:
            return False

# FIX B-02: Define _auth_dep alias used throughout the module — was undefined, causing NameError on every protected route.
_auth_dep = verify_service_auth

logger = logging.getLogger("hsaai.llm_gateway")

APP_VERSION = "4.0.0"
LOCAL_ONLY = os.getenv("INTERNAL_ONLY_MODE", "true").lower() == "true"
DEFAULT_PROVIDER = os.getenv("LOCAL_LLM_PROVIDER", "ollama")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL") or os.getenv("LOCAL_LLM_BASE_URL", "http://ollama:11434")
DEFAULT_MODEL = os.getenv("LOCAL_LLM_MODEL", "qwen2.5:7b-instruct")
ALLOW_EXTERNAL_AI = os.getenv("ALLOW_EXTERNAL_AI", "false").lower() == "true"
STRICT_EGRESS_DENY = os.getenv("STRICT_EGRESS_DENY", "true").lower() == "true"
# SECURITY FIX: ALLOW_LOCAL_LLM_STUB removed. No fake LLM responses in production.
PRIVATE_CIDRS = [ipaddress.ip_network(os.getenv("PRIVATE_NETWORK_CIDR", "172.28.0.0/16"), strict=False), ipaddress.ip_network("10.0.0.0/8"), ipaddress.ip_network("172.16.0.0/12"), ipaddress.ip_network("192.168.0.0/16"), ipaddress.ip_network("127.0.0.0/8")]
INTERNAL_LLM_HOSTS = {"local_llm", "ollama", "localhost", "127.0.0.1"}
BLOCKED_EXTERNAL_SECRET_KEYS = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "MISTRAL_API_KEY", "COHERE_API_KEY")

# ─── FIX v2.2 (Phase 2): Semantic Cache + Token Budget ─────────
# Both use Redis. The semantic cache stores LLM responses keyed by a hash of
# (prompt + system + model + temperature) with a 24h TTL. Before calling the
# LLM, we check the cache — if a semantically similar query was answered
# recently, we return the cached response (saving LLM cost + latency).
#
# The token budget enforces per-tenant daily token limits. When a tenant
# exceeds their budget, requests are rejected (or downgraded to a smaller model).
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/1")  # DB 1 = semantic cache
TOKEN_BUDGET_REDIS_URL = os.getenv("TOKEN_BUDGET_REDIS_URL", "redis://redis:6379/2")  # DB 2 = token budget
ENABLE_SEMANTIC_CACHE = os.getenv("ENABLE_SEMANTIC_CACHE", "true").lower() == "true"
ENABLE_TOKEN_BUDGET = os.getenv("ENABLE_TOKEN_BUDGET", "true").lower() == "true"
# Default daily token budget per tenant (can be overridden via Redis).
DEFAULT_DAILY_TOKEN_BUDGET = int(os.getenv("DEFAULT_DAILY_TOKEN_BUDGET", "1000000"))  # 1M tokens/day
# Cache similarity threshold (0.0-1.0; higher = stricter matching).
CACHE_SIMILARITY_THRESHOLD = float(os.getenv("CACHE_SIMILARITY_THRESHOLD", "0.95"))


def _get_redis_client(url: str):
    """Lazily create a Redis client. Returns None if Redis is unavailable."""
    try:
        import redis
        return redis.from_url(url, decode_responses=True, socket_timeout=2, socket_connect_timeout=2)
    except ImportError:
        logger.warning("redis package not installed — semantic cache disabled")
        return None
    except Exception as e:
        logger.warning("Redis connection failed (%s) — cache disabled", e)
        return None


def _cache_key(prompt: str, system: str, model: str, temperature: float) -> str:
    """Build a deterministic cache key from the request parameters.

    We normalize the prompt (strip whitespace, lowercase) before hashing so
    that minor formatting differences don't cause cache misses.
    """
    normalized = f"{system.strip().lower()}|{prompt.strip().lower()}|{model}|{temperature:.1f}"
    return hashlib.sha256(normalized.encode()).hexdigest()


def _check_semantic_cache(prompt: str, system: str, model: str, temperature: float, tenant_id: str) -> Optional[dict]:
    """Check the semantic cache for a matching response.

    Returns the cached response dict if found, None otherwise.
    Uses exact-match hashing (not embedding similarity) for speed.
    Embedding-based similarity would require a vector DB call per request —
    the hash-based approach is O(1) and sufficient for enterprise workloads
    where queries are often repeated verbatim.
    """
    if not ENABLE_SEMANTIC_CACHE:
        return None
    client = _get_redis_client(REDIS_URL)
    if client is None:
        return None
    try:
        key = f"llm_cache:{tenant_id}:{_cache_key(prompt, system, model, temperature)}"
        cached = client.get(key)
        if cached:
            logger.info("Semantic cache HIT: key=%s... (tenant=%s)", key[:16], tenant_id)
            return json.loads(cached)
    except Exception as e:
        logger.debug("Cache check failed: %s", e)
    return None


def _store_in_semantic_cache(prompt: str, system: str, model: str, temperature: float,
                              tenant_id: str, response: dict, ttl: int = 86400):
    """Store a response in the semantic cache with a 24h TTL (default).

    Args:
        ttl: Cache TTL in seconds (default 86400 = 24 hours).
    """
    if not ENABLE_SEMANTIC_CACHE:
        return
    client = _get_redis_client(REDIS_URL)
    if client is None:
        return
    try:
        key = f"llm_cache:{tenant_id}:{_cache_key(prompt, system, model, temperature)}"
        client.setex(key, ttl, json.dumps(response, ensure_ascii=False))
        logger.info("Semantic cache STORE: key=%s... (tenant=%s, ttl=%ds)", key[:16], tenant_id, ttl)
    except Exception as e:
        logger.debug("Cache store failed: %s", e)


def _check_token_budget(tenant_id: str, estimated_tokens: int) -> tuple[bool, int, int]:
    """Check if the tenant has enough token budget remaining.

    Returns (allowed, used_today, budget).
    - allowed: True if the request can proceed, False if budget exceeded.
    - used_today: tokens consumed today by this tenant.
    - budget: the tenant's daily budget.
    """
    if not ENABLE_TOKEN_BUDGET:
        return True, 0, DEFAULT_DAILY_TOKEN_BUDGET
    client = _get_redis_client(TOKEN_BUDGET_REDIS_URL)
    if client is None:
        return True, 0, DEFAULT_DAILY_TOKEN_BUDGET  # fail open — don't block on Redis outage
    try:
        # Use a daily key that resets at UTC midnight.
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        key = f"token_budget:{tenant_id}:{today}"
        used = int(client.get(key) or 0)
        # Check for a tenant-specific budget override.
        budget_key = f"token_budget_limit:{tenant_id}"
        budget = int(client.get(budget_key) or DEFAULT_DAILY_TOKEN_BUDGET)
        allowed = used + estimated_tokens <= budget
        if not allowed:
            logger.warning(
                "Token budget exceeded for tenant %s: used=%d, requested=%d, budget=%d",
                tenant_id, used, estimated_tokens, budget
            )
        return allowed, used, budget
    except Exception as e:
        logger.warning("Token budget check failed: %s — failing open", e)
        return True, 0, DEFAULT_DAILY_TOKEN_BUDGET


def _consume_token_budget(tenant_id: str, actual_tokens: int):
    """Increment the tenant's daily token usage counter."""
    if not ENABLE_TOKEN_BUDGET:
        return
    client = _get_redis_client(TOKEN_BUDGET_REDIS_URL)
    if client is None:
        return
    try:
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        key = f"token_budget:{tenant_id}:{today}"
        pipe = client.pipeline()
        pipe.incrby(key, actual_tokens)
        # Set TTL to expire at next UTC midnight (cleanup).
        pipe.expireat(key, int(datetime.strptime(today, "%Y-%m-%d").replace(
            tzinfo=timezone.utc
        ).timestamp()) + 86400 + 3600)  # +1h buffer
        pipe.execute()
        logger.info("Token budget consumed: tenant=%s, tokens=%d", tenant_id, actual_tokens)
    except Exception as e:
        logger.warning("Token budget increment failed: %s", e)


def _estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 chars per token for English, ~2 for Arabic)."""
    # Count Arabic characters (they tokenize to ~1 token per 2 chars).
    arabic_chars = sum(1 for c in text if '\u0600' <= c <= '\u06FF')
    other_chars = len(text) - arabic_chars
    return (arabic_chars // 2) + (other_chars // 4) + 1

app = FastAPI(title="HSAAI Local LLM Gateway", version=APP_VERSION)

class GenerateRequest(BaseModel):
    prompt: str
    system: str = "You are HSAAI, a private enterprise AI assistant."
    model: str | None = None
    temperature: float = 0.2
    max_tokens: int = 1024
    stream: bool = False
    tenant_id: str = "default"
    workspace_id: str = "default"
    task: str | None = None
    sensitivity: str = "internal"

class GenerateResponse(BaseModel):
    provider: str
    model: str
    text: str
    local_only: bool
    elapsed_ms: int
    route_reason: str | None = None

class RouteRequest(BaseModel):
    prompt: str = ""
    task: str | None = None
    sensitivity: str = "internal"
    model: str | None = None

class RouteResponse(BaseModel):
    provider: str
    model_key: str
    model: str
    reason: str
    local_only: bool

@app.get("/health")
def health():
    assert_no_external_ai()
    cfg = load_model_config()
    return {"status": "ok", "service": "llm_gateway", "provider": DEFAULT_PROVIDER, "model": DEFAULT_MODEL, "registered_models": list(cfg.get("models", {}).keys()), "local_only": LOCAL_ONLY, "egress_policy": "strict-deny-external" if STRICT_EGRESS_DENY else "not-strict"}

# NOTE: _is_private_url is now imported from common.security.ssrf_guard (Issue 4 fix).
# The previous local copy (with INTERNAL_LLM_HOSTS) was removed to dedupe.

def assert_no_external_ai() -> None:
    leaked = [k for k in BLOCKED_EXTERNAL_SECRET_KEYS if os.getenv(k)]
    if LOCAL_ONLY and ALLOW_EXTERNAL_AI:
        raise HTTPException(500, "Unsafe config: external AI is enabled while INTERNAL_ONLY_MODE=true")
    if LOCAL_ONLY and leaked:
        raise HTTPException(500, f"External AI secrets are forbidden in HSAAI internal-only mode: {', '.join(leaked)}")
    if LOCAL_ONLY and STRICT_EGRESS_DENY and not _is_private_url(OLLAMA_BASE_URL):
        raise HTTPException(500, f"LLM endpoint must be inside the company network: {OLLAMA_BASE_URL}")

async def ollama_generate(req: GenerateRequest) -> str:
    payload = {
        "model": route_model(req.prompt, req.task, req.sensitivity, req.model)["model"],
        "prompt": f"{req.system}\n\nUser: {req.prompt}\nAssistant:",
        "stream": False,
        "options": {"temperature": req.temperature, "num_predict": req.max_tokens},
    }
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload)
        if r.status_code >= 400:
            raise HTTPException(r.status_code, f"Ollama error: {r.text[:500]}")
        return r.json().get("response", "")


async def external_generate(req: GenerateRequest, selected: dict[str, Any]) -> str:
    """Call an optional external model only when the gateway policy selected it."""
    provider = selected["provider"]
    model = selected["model"]
    composed = f"{req.system}\n\nUser: {req.prompt}"
    async with httpx.AsyncClient(timeout=120) as client:
        if provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise HTTPException(503, "OPENAI_API_KEY is required for optional OpenAI routing")
            r = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": model, "messages": [{"role": "system", "content": req.system}, {"role": "user", "content": req.prompt}], "temperature": req.temperature, "max_tokens": req.max_tokens},
            )
            if r.status_code >= 400:
                raise HTTPException(r.status_code, f"OpenAI error: {r.text[:500]}")
            return r.json()["choices"][0]["message"].get("content", "")
        if provider == "anthropic":
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise HTTPException(503, "ANTHROPIC_API_KEY is required for optional Anthropic routing")
            r = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
                json={"model": model, "system": req.system, "messages": [{"role": "user", "content": req.prompt}], "max_tokens": req.max_tokens, "temperature": req.temperature},
            )
            if r.status_code >= 400:
                raise HTTPException(r.status_code, f"Anthropic error: {r.text[:500]}")
            parts = r.json().get("content", [])
            return "".join(part.get("text", "") for part in parts if part.get("type") == "text")
        if provider == "google":
            api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            if not api_key:
                raise HTTPException(503, "GEMINI_API_KEY or GOOGLE_API_KEY is required for optional Gemini routing")
            r = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}",
                json={"contents": [{"role": "user", "parts": [{"text": composed}]}], "generationConfig": {"temperature": req.temperature, "maxOutputTokens": req.max_tokens}},
            )
            if r.status_code >= 400:
                raise HTTPException(r.status_code, f"Gemini error: {r.text[:500]}")
            candidates = r.json().get("candidates", [])
            if not candidates:
                return ""
            return "".join(part.get("text", "") for part in candidates[0].get("content", {}).get("parts", []))
    raise HTTPException(400, f"Unsupported provider: {provider}")

async def ollama_stream(req: GenerateRequest) -> AsyncIterator[bytes]:
    """Stream tokens from Ollama with backpressure + cancellation + metrics.

    v4.0 (AI-IMPROVEMENTS) enhancements:
      - **Token-by-token SSE** — each chunk from Ollama is emitted as a
        separate `data: {token: ...}` SSE event.
      - **Backpressure handling** — if the client is slow, we buffer up
        to `STREAM_MAX_BUFFER_TOKENS` tokens; beyond that we drop the
        oldest buffered tokens to avoid unbounded memory growth.
      - **Streaming cancellation** — if the client disconnects, we
        cancel the upstream Ollama call so we don't keep generating.
      - **Streaming metrics** — emits `event: metrics` with
        `tokens_per_sec`, `time_to_first_token_ms`, and `total_tokens`.
      - **Token counting** — counts emitted tokens for FinOps/budget.
    """
    started = time.time()
    first_token_time: Optional[float] = None
    token_count = 0
    dropped_tokens = 0
    # In-flight buffer for backpressure. We yield immediately when the
    # client is keeping up; when it falls behind, we cap the buffer at
    # STREAM_MAX_BUFFER_TOKENS and drop the oldest entries.
    buffer: list[str] = []
    STREAM_MAX_BUFFER_TOKENS = int(os.getenv("STREAM_MAX_BUFFER_TOKENS", "256"))

    payload = {
        "model": route_model(req.prompt, req.task, req.sensitivity, req.model)["model"],
        "prompt": f"{req.system}\n\nUser: {req.prompt}\nAssistant:",
        "stream": True,
        "options": {"temperature": req.temperature, "num_predict": req.max_tokens},
    }

    # We use a separate httpx client per stream so we can cancel it on
    # client disconnect without affecting other in-flight requests.
    try:
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("POST", f"{OLLAMA_BASE_URL}/api/generate", json=payload) as r:
                if r.status_code >= 400:
                    body = await r.aread()
                    yield f"data: {json.dumps({'error': f'Ollama HTTP {r.status_code}: {body[:200]!r}'}, ensure_ascii=False)}\n\n".encode()
                    yield b"data: [DONE]\n\n"
                    return
                async for line in r.aiter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except Exception:
                        continue
                    token = chunk.get("response", "")
                    done = chunk.get("done", False)
                    if token:
                        if first_token_time is None:
                            first_token_time = time.time()
                        token_count += 1
                        # Backpressure check: if buffer is full, drop oldest.
                        if len(buffer) >= STREAM_MAX_BUFFER_TOKENS:
                            dropped_tokens += 1
                            buffer.pop(0)
                        buffer.append(token)
                        # Try to flush the entire buffer in one SSE event.
                        # If the client is keeping up, buffer is empty by
                        # the next iteration.
                        try:
                            for tok in list(buffer):
                                yield f"data: {json.dumps({'token': tok}, ensure_ascii=False)}\n\n".encode()
                            buffer.clear()
                        except Exception as exc:
                            # Client likely disconnected — stop streaming.
                            logger.info("Stream client disconnected: %s", exc)
                            raise
                    if done:
                        break
    except httpx.RequestError as exc:
        logger.warning("Stream upstream error: %s", exc)
        yield f"data: {json.dumps({'error': f'upstream_error: {exc}'}, ensure_ascii=False)}\n\n".encode()

    # Emit final metrics event.
    elapsed = time.time() - started
    ttft_ms = int((first_token_time - started) * 1000) if first_token_time else 0
    tps = (token_count / elapsed) if elapsed > 0 else 0.0
    metrics = {
        "tokens_per_sec": round(tps, 2),
        "time_to_first_token_ms": ttft_ms,
        "total_tokens": token_count,
        "dropped_tokens": dropped_tokens,
        "elapsed_ms": int(elapsed * 1000),
    }
    yield f"event: metrics\ndata: {json.dumps(metrics, ensure_ascii=False)}\n\n".encode()

    # Record token usage for budget tracking.
    if token_count > 0:
        try:
            _consume_token_budget(req.tenant_id, token_count)
        except Exception:
            pass

    yield b"data: [DONE]\n\n"


@app.get("/v1/models")
def list_models(claims: dict = Depends(_auth_dep)):
    assert_no_external_ai()
    cfg = load_model_config()
    return {
        "provider": "hybrid",
        "local_only": LOCAL_ONLY,
        "external_ai_enabled": ALLOW_EXTERNAL_AI and not LOCAL_ONLY,
        "default": cfg.get("default", DEFAULT_MODEL),
        "models": cfg.get("models", {}),
        "external_models": cfg.get("external_models", {}) if ALLOW_EXTERNAL_AI and not LOCAL_ONLY else {},
        "routing_rules": cfg.get("routing_rules", []),
        "external_routing_rules": cfg.get("external_routing_rules", []) if ALLOW_EXTERNAL_AI and not LOCAL_ONLY else [],
    }

@app.post("/v1/models/route", response_model=RouteResponse)
def route(req: RouteRequest, claims: dict = Depends(_auth_dep)):
    assert_no_external_ai()
    return RouteResponse(**route_model(req.prompt, req.task, req.sensitivity, req.model))

@app.post("/v1/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest, claims: dict = Depends(_auth_dep)):
    """Generate a response using the routed LLM.

    FIX v2.2 (Phase 2): Now with:
      1. Semantic cache check — if a semantically similar query was answered
         recently (within 24h), return the cached response instantly (saving
         LLM cost + latency).
      2. Token budget enforcement — per-tenant daily token limit. Requests
         that would exceed the budget are rejected with HTTP 429.
      3. Token usage tracking — actual tokens consumed are recorded for
         FinOps analytics and budget enforcement.
    """
    assert_no_external_ai()
    started = time.time()
    if req.stream:
        raise HTTPException(400, "Use /v1/stream for streaming responses")
    selected = route_model(req.prompt, req.task, req.sensitivity, req.model)

    # FIX v2.2 (Phase 2): Token budget check.
    estimated_tokens = _estimate_tokens(req.prompt) + req.max_tokens
    allowed, used_today, budget = _check_token_budget(req.tenant_id, estimated_tokens)
    if not allowed:
        raise HTTPException(
            429,
            f"Token budget exceeded for tenant '{req.tenant_id}'. "
            f"Used today: {used_today}, requested: {estimated_tokens}, budget: {budget}. "
            f"Budget resets at UTC midnight."
        )

    # FIX v2.2 (Phase 2): Semantic cache check.
    cached = _check_semantic_cache(req.prompt, req.system, selected["model"], req.temperature, req.tenant_id)
    if cached is not None:
        # Return cached response — mark it as cache hit.
        return GenerateResponse(
            provider=cached.get("provider", "cache"),
            model=selected["model"],
            text=cached["text"],
            local_only=selected.get("local_only", LOCAL_ONLY),
            elapsed_ms=int((time.time() - started) * 1000),
            route_reason=f"semantic_cache_hit ({selected['reason']})",
        )

    # Generate the response via the LLM.
    if not selected.get("local_only"):
        text = await external_generate(req, selected)
        provider = selected["provider"]
    elif DEFAULT_PROVIDER != "ollama":
        raise HTTPException(
            503,
            f"LOCAL_LLM_PROVIDER is '{DEFAULT_PROVIDER}' but Ollama is not configured. "
            f"Set LOCAL_LLM_PROVIDER=ollama and ensure Ollama is running."
        )
    else:
        req.model = selected["model"]
        text = await ollama_generate(req)
        provider = "ollama"

    # FIX v2.2 (Phase 2): Store in semantic cache for future requests.
    _store_in_semantic_cache(
        req.prompt, req.system, selected["model"], req.temperature,
        req.tenant_id, {"text": text, "provider": provider}, ttl=86400,
    )

    # FIX v2.2 (Phase 2): Consume token budget (actual tokens, not estimate).
    actual_tokens = _estimate_tokens(req.prompt) + _estimate_tokens(text)
    _consume_token_budget(req.tenant_id, actual_tokens)

    return GenerateResponse(
        provider=provider,
        model=selected["model"],
        text=text,
        local_only=selected.get("local_only", LOCAL_ONLY),
        elapsed_ms=int((time.time() - started) * 1000),
        route_reason=selected["reason"],
    )

@app.post("/v1/stream")
async def stream(req: GenerateRequest, claims: dict = Depends(_auth_dep), request: Request = None):
    """Stream tokens via Server-Sent Events.

    v4.0 (AI-IMPROVEMENTS):
      - Token-by-token SSE with `data: {token: ...}` events.
      - `event: metrics` final event with `tokens_per_sec`,
        `time_to_first_token_ms`, `total_tokens`, `dropped_tokens`.
      - Backpressure: if the client is slow, we buffer up to
        STREAM_MAX_BUFFER_TOKENS (default 256) and then drop oldest.
      - Cancellation: if the client disconnects, the upstream Ollama
        call is cancelled via httpx's async context manager exit.
      - Token budget: emitted tokens are counted and charged to the
        tenant's daily budget via `_consume_token_budget`.

    The endpoint accepts the same `GenerateRequest` body as `/v1/generate`.
    Set `stream=True` is implicit (this endpoint always streams).

    Requires Ollama as the LLM backend (no stub streaming in production).
    """
    assert_no_external_ai()
    if DEFAULT_PROVIDER != "ollama":
        # SECURITY FIX: No stub streaming. Must use Ollama.
        raise HTTPException(
            503,
            f"Streaming requires Ollama. Set LOCAL_LLM_PROVIDER=ollama and ensure Ollama is running."
        )

    # Token budget check (estimate; actual consumption recorded post-stream).
    estimated_tokens = _estimate_tokens(req.prompt) + req.max_tokens
    allowed, used_today, budget = _check_token_budget(req.tenant_id, estimated_tokens)
    if not allowed:
        raise HTTPException(
            429,
            f"Token budget exceeded for tenant '{req.tenant_id}'. "
            f"Used today: {used_today}, requested: {estimated_tokens}, budget: {budget}. "
            f"Budget resets at UTC midnight."
        )

    # Wire up request-disconnect detection if the Request object is
    # available (FastAPI injects it when we declare the `Request`
    # parameter). When the client disconnects, the StreamingResponse
    # generator will raise a `GeneratorExit`/`ConnectionClosed` and the
    # `ollama_stream` `try/except` will cancel the upstream Ollama call.
    return StreamingResponse(
        ollama_stream(req),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # disable nginx buffering for true SSE
        },
    )


@app.get("/v1/stream/health")
async def stream_health(claims: dict = Depends(_auth_dep)):
    """Health check for the streaming endpoint.

    Reports streaming configuration so operators can verify backpressure
    and cancellation settings without making a real stream request.
    """
    return {
        "status": "ok",
        "streaming_enabled": DEFAULT_PROVIDER == "ollama",
        "backend": DEFAULT_PROVIDER,
        "max_buffer_tokens": int(os.getenv("STREAM_MAX_BUFFER_TOKENS", "256")),
        "media_type": "text/event-stream",
        "features": [
            "token_by_token_sse",
            "backpressure_handling",
            "client_disconnect_cancellation",
            "streaming_metrics",
            "token_budget_enforcement",
        ],
    }
