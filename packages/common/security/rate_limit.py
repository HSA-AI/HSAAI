"""
HSAAI Unified Rate Limiting Middleware (Fix #4)
=================================================
Production rate limiting for ALL services.

Features:
  - Per-user, per-tenant, per-API-key, per-IP limits
  - Sliding window algorithm (via Redis)
  - Burst protection
  - Configurable via environment variables
  - Health checks exempt
  - Metrics + logging on limit exceeded
  - Redis-backed for distributed deployments
  - In-memory fallback for development

Usage in any FastAPI service:
    from packages.common.security.rate_limit import RateLimitMiddleware
    app.add_middleware(RateLimitMiddleware)

Configuration:
    RATE_LIMIT_REDIS_URL=redis://redis:6379/6
    RATE_LIMIT_PER_USER=100      # requests per minute
    RATE_LIMIT_PER_TENANT=1000   # requests per minute
    RATE_LIMIT_PER_IP=60         # requests per minute
    RATE_LIMIT_BURST=20          # burst allowance
    RATE_LIMIT_MAX_IDENTITIES=10000
    RATE_LIMIT_FAILURE_MODE=closed  # memory allowed only outside production
"""
import os
import time
import uuid
import logging
import asyncio
from typing import Optional, Dict, Tuple
from collections import OrderedDict, deque
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

logger = logging.getLogger("hsaai.rate_limit")


class SlidingWindowRateLimiter:
    """
    Sliding window rate limiter.
    Uses Redis in production (distributed), in-memory in development.
    """

    def __init__(self):
        self.redis_url = os.getenv("RATE_LIMIT_REDIS_URL", "")
        self._redis = None
        self._memory: Dict[str, deque] = OrderedDict()
        self.max_identities = int(os.getenv("RATE_LIMIT_MAX_IDENTITIES", "10000"))
        self.failure_mode = os.getenv("RATE_LIMIT_FAILURE_MODE", "closed").lower()
        self.production = os.getenv("APP_ENV", "development").lower() in {"prod", "production", "staging"}
        if self.max_identities <= 0 or self.failure_mode not in {"closed", "memory"}:
            raise ValueError("Invalid rate limiter capacity or failure mode")
        if self.production and self.failure_mode != "closed":
            raise ValueError("Production rate limiting must fail closed")
        self._lock = asyncio.Lock()

        # Limits (requests per minute)
        self.per_user = int(os.getenv("RATE_LIMIT_PER_USER", "100"))
        self.per_tenant = int(os.getenv("RATE_LIMIT_PER_TENANT", "1000"))
        self.per_api_key = int(os.getenv("RATE_LIMIT_PER_API_KEY", "200"))
        self.per_ip = int(os.getenv("RATE_LIMIT_PER_IP", "60"))
        self.burst = int(os.getenv("RATE_LIMIT_BURST", "20"))

        # Health check paths exempt from rate limiting
        self.exempt_paths = {"/health", "/health/auth", "/metrics", "/ready", "/live"}

        if min(self.per_user, self.per_tenant, self.per_api_key, self.per_ip) <= 0 or self.burst < 0:
            raise ValueError("Rate limits must be positive and burst must be non-negative")
        if self.redis_url:
            import redis
            self._redis = redis.from_url(self.redis_url, decode_responses=True, socket_timeout=2, socket_connect_timeout=2)
        else:
            logger.info("Rate limiter: %s", "Redis required; requests denied" if self.production else "bounded development memory")

    # Atomic Redis check; blocked requests never grow the sorted set.
    _REDIS_CHECK = """
        local now = tonumber(ARGV[1])
        local window = tonumber(ARGV[2])
        local limit = tonumber(ARGV[3])
        redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now - window)
        if redis.call('ZCARD', KEYS[1]) >= limit then
            return 0
        end
        redis.call('ZADD', KEYS[1], now, ARGV[4])
        redis.call('EXPIRE', KEYS[1], math.ceil(window) + 1)
        return 1
    """

    async def _check_memory(self, limits):
        """Bound identities and per-client events; do not evict active quotas."""
        now, window = time.monotonic(), 60.0
        async with self._lock:
            while self._memory:
                first = next(iter(self._memory))
                if now - self._memory[first][-1] < window:
                    break
                self._memory.popitem(last=False)
            for limit_type, key, maximum in limits:
                memory_key = f"rate_limit:{limit_type}:{key}"
                dq = self._memory.get(memory_key)
                if dq is None:
                    if len(self._memory) >= self.max_identities:
                        return False, "rate_limit_capacity", 60
                    dq = self._memory[memory_key] = deque()
                while dq and dq[0] <= now - window:
                    dq.popleft()
                if len(dq) >= maximum:
                    return False, f"rate_limit_{limit_type}", max(1, int(window - (now - dq[0])))
                dq.append(now)
                self._memory.move_to_end(memory_key)
        return True, None, None

    def _is_exempt(self, path: str) -> bool:
        """Check if path is exempt from rate limiting."""
        for exempt in self.exempt_paths:
            if path == exempt or path.startswith(exempt + "/"):
                return True
        return False

    def _get_identifiers(self, request: Request) -> Dict[str, str]:
        """Extract identifiers from request (from auth claims + IP)."""
        # Accept identities only from verified authentication middleware state.
        claims = getattr(request.state, "claims", None) or {}
        if not isinstance(claims, dict):
            claims = {}
        user_id = claims.get("sub", "")
        tenant_id = claims.get("tenant_id", "")
        api_key = getattr(request.state, "verified_api_key_id", "")
        client_ip = request.client.host if request.client else "unknown"

        return {
            "user": user_id or f"ip:{client_ip}",
            "tenant": tenant_id or "anonymous",
            "api_key": api_key or "none",
            "ip": client_ip,
        }

    async def check(self, request: Request) -> Tuple[bool, Optional[str], Optional[int]]:
        """
        Check if request should be allowed.
        Returns: (allowed, reason_if_blocked, retry_after_seconds)
        """
        if self._is_exempt(request.url.path):
            return True, None, None

        identifiers = self._get_identifiers(request)
        now = time.time()
        window = 60.0  # 1 minute window

        limits = [
            ("user", identifiers["user"], self.per_user + self.burst),
            ("tenant", identifiers["tenant"], self.per_tenant + self.burst),
            ("ip", identifiers["ip"], self.per_ip + self.burst),
        ]

        if identifiers["api_key"] != "none":
            limits.append(("api_key", identifiers["api_key"], self.per_api_key + self.burst))

        if self._redis is None:
            if self.production or (self.redis_url and self.failure_mode == "closed"):
                return False, "rate_limit_unavailable", 1
            return await self._check_memory(limits)
        try:
            for limit_type, key, max_requests in limits:
                accepted = await asyncio.to_thread(
                    self._redis.eval, self._REDIS_CHECK, 1,
                    f"rate_limit:{limit_type}:{key}", now, window, max_requests,
                    f"{now}:{uuid.uuid4().hex}",
                )
                if not accepted:
                    return False, f"rate_limit_{limit_type}", 60
        except Exception as exc:
            logger.error("Redis rate control unavailable (%s)", type(exc).__name__)
            if self.failure_mode == "memory" and not self.production:
                return await self._check_memory(limits)
            return False, "rate_limit_unavailable", 1
        return True, None, None


# Singleton limiter
_limiter: Optional[SlidingWindowRateLimiter] = None


def get_limiter() -> SlidingWindowRateLimiter:
    global _limiter
    if _limiter is None:
        _limiter = SlidingWindowRateLimiter()
    return _limiter


class RateLimitMiddleware:
    """
    ASGI middleware for rate limiting.
    Add to any FastAPI app: app.add_middleware(RateLimitMiddleware)
    """

    def __init__(self, app):
        self.app = app
        self.limiter = get_limiter()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        request = Request(scope, receive)

        allowed, reason, retry_after = await self.limiter.check(request)

        if not allowed:
            unavailable = reason == "rate_limit_unavailable"
            response = JSONResponse(
                status_code=503 if unavailable else 429,
                content={
                    "error": "RATE_LIMIT_UNAVAILABLE" if unavailable else "RATE_LIMITED",
                    "message": "Rate control temporarily unavailable." if unavailable else f"Rate limit exceeded. Retry after {retry_after}s.",
                    "retry_after": retry_after,
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(self.limiter.per_user),
                },
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)


def setup_rate_limiting(app: FastAPI):
    """
    Convenience: add rate limiting to a FastAPI app.
    Usage: setup_rate_limiting(app)
    """
    app.add_middleware(RateLimitMiddleware)
    logger.info("Rate limiting middleware configured")
