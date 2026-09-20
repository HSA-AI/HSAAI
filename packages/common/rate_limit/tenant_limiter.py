"""
HSAAI Per-Tenant Rate Limiter (v4.0)

Redis-based rate limiting per tenant (not just per-IP).
Supports tiered quotas: free, pro, enterprise.

Usage:
    from packages.common.rate_limit.tenant_limiter import check_rate_limit, RateLimitExceeded

    try:
        check_rate_limit(tenant_id="default", tier="enterprise")
    except RateLimitExceeded:
        raise HTTPException(429, "Rate limit exceeded")
"""
import os
import time
import logging
from typing import Literal
import redis

logger = logging.getLogger("hsaai.rate_limit")

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")

TIER_LIMITS = {
    "free": 100,
    "pro": 1000,
    "enterprise": 10000,
    "internal": 10000,
}


class RateLimitExceeded(Exception):
    """Raised when a tenant exceeds their rate limit."""
    def __init__(self, tenant_id: str, limit: int, retry_after: int):
        self.tenant_id = tenant_id
        self.limit = limit
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded for tenant '{tenant_id}': {limit} req/min")


_redis_client: redis.Redis | None = None


def _get_redis() -> redis.Redis | None:
    global _redis_client
    if _redis_client is None:
        try:
            kwargs = {"decode_responses": True}
            if REDIS_PASSWORD:
                kwargs["password"] = REDIS_PASSWORD
            _redis_client = redis.from_url(REDIS_URL, **kwargs)
            _redis_client.ping()
        except Exception as exc:
            logger.warning("Redis unavailable for rate limiting: %s — failing open", exc)
            return None
    return _redis_client


def check_rate_limit(tenant_id: str, tier: Literal["free", "pro", "enterprise", "internal"] = "enterprise") -> bool:
    """Check if the tenant has exceeded their rate limit.

    Uses Redis sliding window counter for accuracy.
    Returns True if allowed, raises RateLimitExceeded if denied.

    FIX S-15 (cross-cutting): On Redis failure, behavior depends on FAIL_OPEN env var.
    Default is FAIL CLOSED (deny) for production safety. Was always failing open,
    which meant DoS-Redis → DoS-API (anyone could brute-force by killing Redis).
    Set RATE_LIMIT_FAIL_OPEN=true for dev/test environments where you want the
    old behavior.
    """
    client = _get_redis()
    if client is None:
        # FIX S-15: fail CLOSED by default in production
        if os.getenv("RATE_LIMIT_FAIL_OPEN", "false").lower() == "true":
            logger.warning("Redis unavailable — failing OPEN (RATE_LIMIT_FAIL_OPEN=true)")
            return True
        logger.error("Redis unavailable — failing CLOSED (set RATE_LIMIT_FAIL_OPEN=true for dev)")
        raise RateLimitExceeded(tenant_id, 0, 60)

    limit = TIER_LIMITS.get(tier, 10000)
    now = int(time.time())
    window_key = f"rate_limit:{tenant_id}:{now // 60}"

    try:
        pipe = client.pipeline()
        pipe.incr(window_key)
        pipe.expire(window_key, 120)
        results = pipe.execute()
        current_count = results[0]

        if current_count > limit:
            retry_after = 60 - (now % 60)
            logger.warning(
                "Rate limit exceeded for tenant '%s' (tier=%s, count=%d, limit=%d)",
                tenant_id, tier, current_count, limit,
            )
            raise RateLimitExceeded(tenant_id, limit, retry_after)

        return True
    except RateLimitExceeded:
        raise
    except Exception as exc:
        # FIX S-15: fail CLOSED on Redis errors in production
        if os.getenv("RATE_LIMIT_FAIL_OPEN", "false").lower() == "true":
            logger.warning("Rate limit check failed: %s — failing OPEN", exc)
            return True
        logger.error("Rate limit check failed: %s — failing CLOSED", exc)
        raise RateLimitExceeded(tenant_id, 0, 60)


def get_tenant_usage(tenant_id: str) -> dict:
    """Get current rate limit usage for a tenant."""
    client = _get_redis()
    if client is None:
        return {"current": 0, "limit": 0, "redis": "unavailable"}

    now = int(time.time())
    window_key = f"rate_limit:{tenant_id}:{now // 60}"
    current = int(client.get(window_key) or 0)
    return {
        "current": current,
        "limit": TIER_LIMITS.get("enterprise", 10000),
        "window_seconds": 60 - (now % 60),
        "redis": "ok",
    }
