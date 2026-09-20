"""
HSAAI Token Budget Manager (v1.0 — AI-IMPROVEMENTS)
====================================================

Per-tenant + per-user daily token budget enforcement for the HSAAI LLM
gateway. Uses Redis atomic counters for real-time tracking.

Features
--------
1. **Per-tenant daily token budget** (configurable per-tenant via Redis).
2. **Per-user token budget** (default 10K tokens/day, overridable).
3. **Real-time tracking via Redis counters** — atomic INCRBY with a
   daily key that resets at UTC midnight.
4. **Budget exceeded → HTTP 429 with `Retry-After`** (seconds until
   UTC midnight reset).
5. **Budget warning at 80%** — `check()` returns a `warning` flag so
   the caller can notify the user via response headers.
6. **Budget reset at UTC midnight** — TTL-based key expiry.

The module degrades gracefully without Redis (returns `allowed=True`
and logs a warning) so the LLM gateway stays available during Redis
outages. This is the standard "fail open for budget, fail closed for
auth" pattern — being wrong about auth is catastrophic; being wrong
about budget is a billing issue, not a security issue.

Usage
-----
    from packages.common.ai.token_budget import TokenBudgetManager, BudgetCheck

    mgr = TokenBudgetManager(redis_url="redis://redis:6379/2")
    check = mgr.check(tenant_id="acme", user_id="alice", estimated_tokens=500)
    if not check.allowed:
        raise HTTPException(429, check.detail, headers={"Retry-After": str(check.retry_after)})
    if check.warning:
        # notify user they're at 80% of their daily budget
        ...
    # ... after LLM call ...
    mgr.consume(tenant_id="acme", user_id="alice", actual_tokens=480)
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger("hsaai.token_budget")

# Defaults
DEFAULT_TENANT_DAILY_BUDGET = int(os.getenv("DEFAULT_TENANT_DAILY_BUDGET", "1000000"))  # 1M/day
DEFAULT_USER_DAILY_BUDGET = int(os.getenv("DEFAULT_USER_DAILY_BUDGET", "10000"))  # 10K/day
WARNING_THRESHOLD = 0.80  # warn user at 80% of budget


def _utc_today() -> str:
    """Return today's UTC date as YYYY-MM-DD (used for daily key suffix)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _seconds_until_midnight_utc() -> int:
    """Seconds from now until the next UTC midnight."""
    now = datetime.now(timezone.utc)
    tomorrow = (now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return max(1, int((tomorrow - now).total_seconds()))


def _redis_client(url: str):
    """Lazily create a Redis client. Returns None if unavailable."""
    try:
        import redis  # type: ignore
        return redis.from_url(
            url, decode_responses=True,
            socket_timeout=2, socket_connect_timeout=2,
        )
    except ImportError:
        return None
    except Exception as exc:
        logger.debug("Redis connection failed (%s) — budget will fail open", exc)
        return None


# ─────────────────────────────────────────────────────────────────────
# BudgetCheck dataclass
# ─────────────────────────────────────────────────────────────────────


@dataclass
class BudgetCheck:
    """Result of TokenBudgetManager.check()."""
    allowed: bool
    tenant_used: int = 0
    tenant_budget: int = DEFAULT_TENANT_DAILY_BUDGET
    user_used: int = 0
    user_budget: int = DEFAULT_USER_DAILY_BUDGET
    warning: bool = False
    warning_message: str = ""
    retry_after: int = 0
    detail: str = ""
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "tenant_used": self.tenant_used,
            "tenant_budget": self.tenant_budget,
            "user_used": self.user_used,
            "user_budget": self.user_budget,
            "warning": self.warning,
            "warning_message": self.warning_message,
            "retry_after": self.retry_after,
            "detail": self.detail,
            "reason": self.reason,
        }


# ─────────────────────────────────────────────────────────────────────
# TokenBudgetManager
# ─────────────────────────────────────────────────────────────────────


class TokenBudgetManager:
    """Per-tenant + per-user daily token budget enforcement.

    Parameters
    ----------
    redis_url : str
        Redis connection URL.
    tenant_budget : int
        Default daily token budget per tenant.
    user_budget : int
        Default daily token budget per user.
    warning_threshold : float
        Fraction of budget at which to emit a warning (default 0.80).
    """

    def __init__(
        self,
        *,
        redis_url: str = None,
        tenant_budget: int = DEFAULT_TENANT_DAILY_BUDGET,
        user_budget: int = DEFAULT_USER_DAILY_BUDGET,
        warning_threshold: float = WARNING_THRESHOLD,
    ):
        self.redis_url = redis_url or os.getenv(
            "TOKEN_BUDGET_REDIS_URL",
            os.getenv("REDIS_URL", "redis://redis:6379/2"),
        )
        self.default_tenant_budget = int(tenant_budget)
        self.default_user_budget = int(user_budget)
        self.warning_threshold = float(warning_threshold)
        self._redis = None  # lazily initialized

    # ── public API ──────────────────────────────────────────────────

    def check(
        self,
        *,
        tenant_id: str,
        user_id: Optional[str] = None,
        estimated_tokens: int,
    ) -> BudgetCheck:
        """Check whether the request would fit within the budget.

        Does NOT consume the budget — call `consume()` after the LLM
        call to record actual usage.

        Returns BudgetCheck with `allowed=False` if the request would
        exceed either the tenant OR the user budget.

        Fail-open behavior: if Redis is unavailable, `allowed=True` is
        returned with `reason='redis_unavailable_fail_open'` so the
        LLM gateway stays available during Redis outages.
        """
        # Fail-open fast path: if Redis was already determined
        # unavailable on a previous call, skip the lookup entirely.
        if self._redis is None:
            self._redis = _redis_client(self.redis_url)
            if self._redis is None:
                # Redis unavailable — fail open.
                return BudgetCheck(
                    allowed=True,
                    tenant_used=0,
                    tenant_budget=self.default_tenant_budget,
                    user_used=0,
                    user_budget=self.default_user_budget,
                    warning=False,
                    reason="redis_unavailable_fail_open",
                    detail="Token budget tracking unavailable — request allowed (fail-open).",
                )

        tenant_used, tenant_budget = self._get_usage_and_budget(
            f"tenant:{tenant_id}", self.default_tenant_budget,
        )
        # If Redis went down during the lookup, fail open.
        if self._redis is None:
            return BudgetCheck(
                allowed=True,
                tenant_used=0,
                tenant_budget=self.default_tenant_budget,
                user_used=0,
                user_budget=self.default_user_budget,
                warning=False,
                reason="redis_unavailable_fail_open",
                detail="Token budget tracking unavailable — request allowed (fail-open).",
            )
        user_used = 0
        user_budget = self.default_user_budget
        if user_id:
            user_used, user_budget = self._get_usage_and_budget(
                f"user:{tenant_id}:{user_id}", self.default_user_budget,
            )
        if self._redis is None:
            return BudgetCheck(
                allowed=True,
                tenant_used=0,
                tenant_budget=self.default_tenant_budget,
                user_used=0,
                user_budget=self.default_user_budget,
                warning=False,
                reason="redis_unavailable_fail_open",
                detail="Token budget tracking unavailable — request allowed (fail-open).",
            )

        tenant_remaining = tenant_budget - tenant_used
        user_remaining = user_budget - user_used
        tenant_ok = estimated_tokens <= tenant_remaining
        user_ok = (not user_id) or (estimated_tokens <= user_remaining)
        allowed = tenant_ok and user_ok

        # Warning at 80% of either budget.
        warning = False
        warning_msg = ""
        tenant_pct = tenant_used / tenant_budget if tenant_budget > 0 else 1.0
        user_pct = user_used / user_budget if (user_id and user_budget > 0) else 0.0
        if tenant_pct >= self.warning_threshold:
            warning = True
            warning_msg = (
                f"Tenant '{tenant_id}' has used {tenant_used}/{tenant_budget} "
                f"tokens ({tenant_pct:.0%}) of its daily budget."
            )
        if user_id and user_pct >= self.warning_threshold:
            warning = True
            warning_msg = (
                f"User '{user_id}' has used {user_used}/{user_budget} "
                f"tokens ({user_pct:.0%}) of their daily budget."
            )

        retry_after = 0
        detail = ""
        reason = ""
        if not allowed:
            retry_after = _seconds_until_midnight_utc()
            if not tenant_ok:
                reason = "tenant_budget_exceeded"
                detail = (
                    f"Tenant '{tenant_id}' token budget exceeded. "
                    f"Used {tenant_used}/{tenant_budget}, requested {estimated_tokens}. "
                    f"Resets in {retry_after}s (UTC midnight)."
                )
            else:
                reason = "user_budget_exceeded"
                detail = (
                    f"User '{user_id}' token budget exceeded. "
                    f"Used {user_used}/{user_budget}, requested {estimated_tokens}. "
                    f"Resets in {retry_after}s (UTC midnight)."
                )

        return BudgetCheck(
            allowed=allowed,
            tenant_used=tenant_used,
            tenant_budget=tenant_budget,
            user_used=user_used,
            user_budget=user_budget,
            warning=warning,
            warning_message=warning_msg,
            retry_after=retry_after,
            detail=detail,
            reason=reason,
        )

    def consume(
        self,
        *,
        tenant_id: str,
        user_id: Optional[str] = None,
        actual_tokens: int,
    ) -> dict:
        """Record actual token usage. Returns the new usage counters.

        Uses Redis INCRBY (atomic) so concurrent requests from the same
        tenant/user are correctly accounted for.
        """
        if actual_tokens <= 0:
            return {"tenant_used": 0, "user_used": 0}
        today = _utc_today()
        ttl = _seconds_until_midnight_utc() + 3600  # +1h safety buffer

        tenant_used = self._incr_with_ttl(
            f"token_budget:tenant:{tenant_id}:{today}", actual_tokens, ttl,
        )
        user_used = 0
        if user_id:
            user_used = self._incr_with_ttl(
                f"token_budget:user:{tenant_id}:{user_id}:{today}",
                actual_tokens, ttl,
            )
        logger.info(
            "Token budget consumed: tenant=%s user=%s tokens=%d → tenant_total=%d user_total=%d",
            tenant_id, user_id, actual_tokens, tenant_used, user_used,
        )
        return {"tenant_used": tenant_used, "user_used": user_used}

    def set_tenant_budget(self, tenant_id: str, budget: int):
        """Override the daily token budget for a specific tenant."""
        if self._redis is None:
            self._redis = _redis_client(self.redis_url)
        if self._redis is None:
            logger.warning("Cannot set tenant budget — Redis unavailable")
            return
        try:
            self._redis.set(
                f"token_budget_limit:tenant:{tenant_id}", int(budget),
            )
            logger.info("Tenant budget override: %s → %d tokens/day", tenant_id, budget)
        except Exception as exc:
            logger.warning("Set tenant budget failed: %s", exc)

    def set_user_budget(self, tenant_id: str, user_id: str, budget: int):
        """Override the daily token budget for a specific user."""
        if self._redis is None:
            self._redis = _redis_client(self.redis_url)
        if self._redis is None:
            return
        try:
            self._redis.set(
                f"token_budget_limit:user:{tenant_id}:{user_id}", int(budget),
            )
        except Exception as exc:
            logger.warning("Set user budget failed: %s", exc)

    def reset(self, *, tenant_id: Optional[str] = None, user_id: Optional[str] = None):
        """Reset the budget counters for a tenant and/or user.

        Mainly used by tests; in production the counters reset
        automatically at UTC midnight via TTL expiry.
        """
        if self._redis is None:
            self._redis = _redis_client(self.redis_url)
        if self._redis is None:
            return
        today = _utc_today()
        try:
            if tenant_id:
                self._redis.delete(f"token_budget:tenant:{tenant_id}:{today}")
            if tenant_id and user_id:
                self._redis.delete(
                    f"token_budget:user:{tenant_id}:{user_id}:{today}",
                )
        except Exception as exc:
            logger.warning("Reset budget failed: %s", exc)

    def status(self, *, tenant_id: str, user_id: Optional[str] = None) -> dict:
        """Return current usage/budget for the tenant (and user if given)."""
        tenant_used, tenant_budget = self._get_usage_and_budget(
            f"tenant:{tenant_id}", self.default_tenant_budget,
        )
        result = {
            "tenant_id": tenant_id,
            "tenant_used": tenant_used,
            "tenant_budget": tenant_budget,
            "tenant_remaining": max(0, tenant_budget - tenant_used),
            "tenant_pct_used": round(tenant_used / tenant_budget, 4) if tenant_budget > 0 else 1.0,
        }
        if user_id:
            user_used, user_budget = self._get_usage_and_budget(
                f"user:{tenant_id}:{user_id}", self.default_user_budget,
            )
            result.update({
                "user_id": user_id,
                "user_used": user_used,
                "user_budget": user_budget,
                "user_remaining": max(0, user_budget - user_used),
                "user_pct_used": round(user_used / user_budget, 4) if user_budget > 0 else 1.0,
            })
        return result

    # ── Internal helpers ────────────────────────────────────────────

    def _get_usage_and_budget(self, scope: str, default_budget: int) -> tuple[int, int]:
        """Return (used_today, budget) for the given scope.

        `scope` is either `tenant:{id}` or `user:{tenant}:{user}`.
        """
        if self._redis is None:
            self._redis = _redis_client(self.redis_url)
        if self._redis is None:
            # Fail open: no usage tracking, default budget.
            return 0, default_budget
        today = _utc_today()
        try:
            used = int(self._redis.get(f"token_budget:{scope}:{today}") or 0)
            budget_override = self._redis.get(f"token_budget_limit:{scope}")
            budget = int(budget_override) if budget_override else default_budget
            return used, budget
        except Exception as exc:
            logger.debug("Budget lookup failed (%s) — failing open", exc)
            # Mark Redis as unavailable so we don't keep retrying.
            self._redis = None
            return 0, default_budget

    def _incr_with_ttl(self, key: str, amount: int, ttl: int) -> int:
        """Atomically INCRBY a key and set its TTL if it's new."""
        if self._redis is None:
            self._redis = _redis_client(self.redis_url)
        if self._redis is None:
            return 0
        try:
            pipe = self._redis.pipeline()
            pipe.incrby(key, amount)
            pipe.expire(key, ttl)
            results = pipe.execute()
            new_val = int(results[0]) if results else 0
            return new_val
        except Exception as exc:
            logger.debug("Budget consume failed (%s) — failing open", exc)
            self._redis = None
            return 0


# ─────────────────────────────────────────────────────────────────────
# Module-level default manager
# ─────────────────────────────────────────────────────────────────────

_default_manager: Optional[TokenBudgetManager] = None


def get_default_manager() -> TokenBudgetManager:
    global _default_manager
    if _default_manager is None:
        _default_manager = TokenBudgetManager()
    return _default_manager


__all__ = [
    "TokenBudgetManager",
    "BudgetCheck",
    "get_default_manager",
    "DEFAULT_TENANT_DAILY_BUDGET",
    "DEFAULT_USER_DAILY_BUDGET",
    "WARNING_THRESHOLD",
]
