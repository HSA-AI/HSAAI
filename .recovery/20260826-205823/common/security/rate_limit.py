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
"""
import os
import time
import logging
import asyncio
from typing import Optional, Dict, Tuple
from collections import defaultdict, deque
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
        self._memory: Dict[str, deque] = defaultdict(lambda: deque())
        self._lock = asyncio.Lock()

        # Limits (requests per minute)
        self.per_user = int(os.getenv("RATE_LIMIT_PER_USER", "100"))
        self.per_tenant = int(os.getenv("RATE_LIMIT_PER_TENANT", "1000"))
        self.per_api_key = int(os.getenv("RATE_LIMIT_PER_API_KEY", "200"))
        self.per_ip = int(os.getenv("RATE_LIMIT_PER_IP", "60"))
        self.burst = int(os.getenv("RATE_LIMIT_BURST", "20"))

        # Health check paths exempt from rate limiting
        self.exempt_paths = {"/health", "/health/auth", "/metrics", "/ready", "/live"}

        # Try Redis connection
        if self.redis_url:
            try:
                import redis
                self._redis = redis.from_url(self.redis_url, decode_responses=True)
                self._redis.ping()
                logger.info(f"Rate limiter: Redis connected → {self.redis_url}")
            except Exception as e:
                logger.warning(f"Rate limiter: Redis unavailable ({e}), using in-memory")
                self._redis = None
        else:
            logger.info("Rate limiter: in-memory mode (set RATE_LIMIT_REDIS_URL for distributed)")

    def _is_exempt(self, path: str) -> bool:
        """Check if path is exempt from rate limiting."""
        for exempt in self.exempt_paths:
            if path == exempt or path.startswith(exempt + "/"):
                return True
        return False

    def _get_identifiers(self, request: Request) -> Dict[str, str]:
        """Extract identifiers from request (from auth claims + IP)."""
        # In production, these come from auth middleware headers
        user_id = request.headers.get("X-User-Id", "")
        tenant_id = request.headers.get("X-Tenant-Id", "")
        api_key = request.headers.get("X-API-Key", "")

        # Get client IP (respect X-Forwarded-For)
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        else:
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

        for limit_type, key, max_requests in limits:
            redis_key = f"rate_limit:{limit_type}:{key}"

            if self._redis:
                # Redis sliding window
                try:
                    pipe = self._redis.pipeline()
                    pipe.zremrangebyscore(redis_key, 0, now - window)
                    pipe.zadd(redis_key, {f"{now}": now})
                    pipe.zcard(redis_key)
                    pipe.expire(redis_key, int(window) + 1)
                    results = pipe.execute()
                    count = results[2]

                    if count > max_requests:
                        retry_after = int(window - (now - (now - window)))
                        logger.warning(
                            f"Rate limit exceeded: {limit_type}={key} "
                            f"({count}/{max_requests} in 60s)"
                        )
                        return False, f"rate_limit_{limit_type}", max(retry_after, 1)
                except Exception as e:
                    logger.error(f"Redis rate limit error: {e}")
                    # Fail open on Redis error (don't block legitimate traffic)
                    return True, None, None
            else:
                # In-memory sliding window
                async with self._lock:
                    dq = self._memory[redis_key]
                    # Remove old entries
                    while dq and dq[0] < now - window:
                        dq.popleft()
                    dq.append(now)
                    count = len(dq)

                    if count > max_requests:
                        retry_after = int(window - (now - dq[0]))
                        logger.warning(
                            f"Rate limit exceeded: {limit_type}={key} "
                            f"({count}/{max_requests} in 60s)"
                        )
                        return False, f"rate_limit_{limit_type}", max(retry_after, 1)

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
            response = JSONResponse(
                status_code=429,
                content={
                    "error": "RATE_LIMITED",
                    "message": f"Rate limit exceeded. Retry after {retry_after}s.",
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
