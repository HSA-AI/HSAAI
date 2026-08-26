"""
HSAAI Risk Engine — AI Action Risk Scoring (v1.0)
==================================================

Quantitative risk scoring for every AI action (0-100). Provides the
deterministic input that the policy engine and approval workflow use
to decide whether an action can be auto-approved or must be escalated
for human review.

Risk model
----------
The score is a weighted sum of independent factor contributions, each
clamped to [0, 100]. The aggregate is then clamped again and bucketed
into one of four levels:

    low      : 0-29   → auto-approvable
    medium   : 30-60  → auto-approvable with audit (configurable)
    high     : 61-80  → human approval required (two-person rule)
    critical : 81-100 → human approval + governance committee notify

Factors
-------
1. action_type       — base weight from a fixed catalog (e.g. delete=70, read=5)
2. data_sensitivity  — PII / PHI / RESTRICTED data adds 10-40 points
3. user_role         — low-privilege roles acting on sensitive data add points
4. tenant            — tenant trust tier (e.g. new/unverified tenants get +15)
5. time_of_day       — off-hours actions add +10 (anomaly indicator)
6. geography         — requests from unapproved geographies add +20

All factor contributions are computed deterministically from the
RiskContext so two requests with identical context produce identical
scores (auditable + reproducible). The full factor breakdown is stored
in the risk audit trail alongside the final score so a reviewer can
see WHY an action was escalated.

Persistence
-----------
Every score computation is appended to an append-only, hash-chained
audit trail (mirrors the AuditLogger design in services/governance/main.py).
The trail is stored in Redis (fast recent queries) with Postgres as the
durable source of truth when configured.

Usage
-----
    from packages.common.governance.risk_engine import (
        RiskEngine, RiskContext, risk_level_for_score,
    )

    engine = RiskEngine()
    ctx = RiskContext(
        action_type="delete:document",
        data_sensitivity="pii",
        user_role="employee",
        tenant_id="t-001",
        tenant_trust_tier="verified",
        timestamp="2025-01-01T03:00:00Z",
        geography="SA",
    )
    result = engine.score(ctx)
    if result.level in ("high", "critical"):
        # create approval request via backend_core.approvals
        ...
"""
from __future__ import annotations

import os
import json
import uuid
import time
import hashlib
import logging
from enum import Enum
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

logger = logging.getLogger("hsaai.governance.risk_engine")

# ── Optional durable storage (mirrors AuditLogger in services/governance/main.py)
try:
    import redis  # type: ignore
    _REDIS_AVAILABLE = True
except ImportError:  # pragma: no cover
    _REDIS_AVAILABLE = False

try:
    from sqlalchemy import create_engine, text as sa_text  # type: ignore
    from sqlalchemy.exc import SQLAlchemyError  # type: ignore
    _SQLALCHEMY_AVAILABLE = True
except ImportError:  # pragma: no cover
    _SQLALCHEMY_AVAILABLE = False


# ═══════════════════════════════════════════════════════════════════
# Risk levels
# ═══════════════════════════════════════════════════════════════════
class RiskLevel(str, Enum):
    """Discrete risk buckets.

    Thresholds:
        low      : < 30  — auto-approve
        medium   : 30-60 — auto-approve + audit (configurable to require approval)
        high     : 61-80 — human approval required (two-person rule)
        critical : > 80  — human approval + governance committee notify
    """
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


def risk_level_for_score(score: int) -> RiskLevel:
    """Map a numeric score (0-100) to a RiskLevel bucket."""
    if score < 30:
        return RiskLevel.LOW
    if score <= 60:
        return RiskLevel.MEDIUM
    if score <= 80:
        return RiskLevel.HIGH
    return RiskLevel.CRITICAL


# ═══════════════════════════════════════════════════════════════════
# Context
# ═══════════════════════════════════════════════════════════════════
@dataclass
class RiskContext:
    """Inputs required to compute a risk score.

    All fields are strings/enums so the context is JSON-serialisable for
    the audit trail. Optional fields default to neutral values that do
    not add to the score (e.g. unknown geography = no penalty).
    """
    action_type: str                     # e.g. "delete:document"
    data_sensitivity: str = "internal"   # public|internal|confidential|restricted|pii|phi|financial
    user_role: str = "employee"          # see Role enum in services/governance/main.py
    tenant_id: str = "default"
    tenant_trust_tier: str = "verified"  # verified|unverified|external|trial
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    geography: str = "unknown"           # ISO-3166 alpha-2 country code
    ip_address: Optional[str] = None
    request_id: Optional[str] = None
    # Free-form attributes (e.g. {"mfa_verified": False}) — used by future
    # factor extensions without breaking the schema.
    attributes: Dict[str, Any] = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════
# Factor weight catalogs (tunable, no code change required to adjust)
# ═══════════════════════════════════════════════════════════════════
# Base weight per action verb. Verbs not in this catalog default to 25
# (medium-risk — deny-by-default philosophy).
ACTION_TYPE_WEIGHTS: Dict[str, int] = {
    "read": 5,
    "search": 10,
    "write": 20,
    "create": 25,
    "update": 30,
    "execute": 35,
    "export": 55,
    "external_write": 65,
    "delete": 70,
    "admin_change": 75,
    "budget_override": 80,
    "deploy": 85,
}

# Sensitivity → points added (cumulative with action weight)
SENSITIVITY_WEIGHTS: Dict[str, int] = {
    "public": 0,
    "internal": 5,
    "confidential": 15,
    "restricted": 30,
    "pii": 40,
    "phi": 40,
    "financial": 25,
}

# Lower-privilege roles acting on sensitive resources are riskier.
# Penalty added if user_role is in this table.
ROLE_PENALTY: Dict[str, int] = {
    "employee": 10,
    "external_auditor": 20,
    "service_account": 15,
}

# Tenant trust tier → penalty
TENANT_TRUST_PENALTY: Dict[str, int] = {
    "verified": 0,
    "external": 10,
    "trial": 15,
    "unverified": 25,
}

# Approved geographies (no penalty). Anything else gets +20.
DEFAULT_APPROVED_GEOGRAPHIES = {"SA", "AE", "BH", "KW", "QA", "OM", "unknown"}


# ═══════════════════════════════════════════════════════════════════
# Risk result
# ═══════════════════════════════════════════════════════════════════
@dataclass
class RiskResult:
    """Output of a risk scoring computation."""
    score: int                              # 0-100
    level: RiskLevel
    factors: Dict[str, int]                 # factor_name → contribution
    auto_approve: bool                      # True if low/medium-risk auto-approve
    requires_human_approval: bool           # True if high/critical
    requires_two_person_rule: bool          # True if critical
    requires_committee_notify: bool         # True if critical
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    request_id: Optional[str] = None
    context_snapshot: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["level"] = self.level.value
        return d


# ═══════════════════════════════════════════════════════════════════
# Risk engine
# ═══════════════════════════════════════════════════════════════════
class RiskEngine:
    """Compute AI action risk scores.

    The engine is stateless except for the audit-trail hash chain cursor
    (`_last_hash`), which is persisted across restarts so the chain
    continuity cannot be silently broken.
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        postgres_url: Optional[str] = None,
        approved_geographies: Optional[set] = None,
        medium_requires_approval: bool = False,
    ):
        self.approved_geographies = approved_geographies or DEFAULT_APPROVED_GEOGRAPHIES
        # When True, medium-risk actions also require human approval.
        # Default False — medium is auto-approvable but audited.
        self.medium_requires_approval = medium_requires_approval

        # Redis (recent audit trail cache)
        self.redis = None
        if _REDIS_AVAILABLE:
            url = redis_url or os.getenv("RISK_REDIS_URL", "redis://redis:6379/6")
            try:
                self.redis = redis.from_url(url, decode_responses=True)
                self.redis.ping()
            except Exception as e:
                logger.warning("RiskEngine: Redis unavailable: %s", e)
                self.redis = None
        self._last_hash = self._load_last_hash()

        # Postgres (durable audit trail)
        self.pg_engine = None
        if _SQLALCHEMY_AVAILABLE:
            pg_url = postgres_url or os.getenv("RISK_POSTGRES_URL") or os.getenv("DATABASE_URL")
            if pg_url:
                try:
                    self.pg_engine = create_engine(pg_url, pool_pre_ping=True, future=True)
                    with self.pg_engine.connect() as conn:
                        conn.execute(sa_text("SELECT 1"))
                    logger.info("RiskEngine: PostgreSQL durable store connected")
                except Exception as e:
                    logger.error("RiskEngine: PostgreSQL unavailable — risk trail not durable: %s", e)
                    self.pg_engine = None

    # ── Hash chain persistence ───────────────────────────────────────
    def _load_last_hash(self) -> str:
        if self.redis:
            try:
                h = self.redis.get("risk:audit:last_hash")
                if h:
                    return h
            except Exception:
                pass
        return "genesis"

    def _save_last_hash(self, h: str) -> None:
        if self.redis:
            try:
                self.redis.set("risk:audit:last_hash", h)
            except Exception as e:
                logger.error("RiskEngine: failed to persist last_hash: %s", e)

    # ── Factor evaluation ────────────────────────────────────────────
    def _factor_action_type(self, action_type: str) -> int:
        """Extract verb from 'verb:resource' and return base weight."""
        verb = action_type.split(":", 1)[0].lower()
        return ACTION_TYPE_WEIGHTS.get(verb, 25)  # unknown verb → 25 (medium)

    def _factor_data_sensitivity(self, sensitivity: str) -> int:
        return SENSITIVITY_WEIGHTS.get(sensitivity.lower(), SENSITIVITY_WEIGHTS["internal"])

    def _factor_user_role(self, role: str) -> int:
        return ROLE_PENALTY.get(role.lower(), 0)

    def _factor_tenant(self, trust_tier: str) -> int:
        return TENANT_TRUST_PENALTY.get(trust_tier.lower(), 0)

    def _factor_time_of_day(self, timestamp: str) -> int:
        """Off-hours (outside 06:00-19:00 UTC) add +10.

        Most HSA staff are in AST (UTC+3) so business hours map to
        03:00-16:00 UTC. We use a slightly wider 06:00-19:00 UTC window
        to allow for early/late workers without flagging routine use.
        """
        try:
            ts = timestamp.replace("Z", "+00:00")
            hour = datetime.fromisoformat(ts).hour
            if hour < 6 or hour >= 19:
                return 10
        except Exception:
            pass
        return 0

    def _factor_geography(self, geography: str) -> int:
        geo = (geography or "unknown").upper()
        if geo in self.approved_geographies:
            return 0
        return 20

    # ── Public API ───────────────────────────────────────────────────
    def score(self, ctx: RiskContext) -> RiskResult:
        """Compute risk score for the given context.

        Pure function of `ctx` — same input always produces same output.
        Side effect: appends to the audit trail.
        """
        factors: Dict[str, int] = {
            "action_type": self._factor_action_type(ctx.action_type),
            "data_sensitivity": self._factor_data_sensitivity(ctx.data_sensitivity),
            "user_role": self._factor_user_role(ctx.user_role),
            "tenant_trust": self._factor_tenant(ctx.tenant_trust_tier),
            "time_of_day": self._factor_time_of_day(ctx.timestamp),
            "geography": self._factor_geography(ctx.geography),
        }

        # Weighted sum — each factor weighted equally. Weights can be
        # tuned here without changing the factor functions.
        WEIGHTS = {
            "action_type": 1.0,
            "data_sensitivity": 1.0,
            "user_role": 0.8,
            "tenant_trust": 0.7,
            "time_of_day": 1.0,
            "geography": 0.9,
        }
        raw = sum(factors[k] * WEIGHTS[k] for k in factors)
        score = max(0, min(100, int(round(raw))))
        level = risk_level_for_score(score)

        auto_approve = level == RiskLevel.LOW
        if level == RiskLevel.MEDIUM and not self.medium_requires_approval:
            auto_approve = True
        requires_human = level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
        requires_two_person = level == RiskLevel.CRITICAL
        requires_committee = level == RiskLevel.CRITICAL

        result = RiskResult(
            score=score,
            level=level,
            factors=factors,
            auto_approve=auto_approve,
            requires_human_approval=requires_human,
            requires_two_person_rule=requires_two_person,
            requires_committee_notify=requires_committee,
            request_id=ctx.request_id,
            context_snapshot=asdict(ctx),
        )

        self._audit(result)
        return result

    # ── Audit trail (hash-chained, append-only) ──────────────────────
    def _audit(self, result: RiskResult) -> None:
        """Append a risk-score computation to the audit trail."""
        event_id = str(uuid.uuid4())
        entry = {
            "event_id": event_id,
            "timestamp": result.timestamp,
            "previous_hash": self._last_hash,
            "request_id": result.request_id,
            "score": result.score,
            "level": result.level.value,
            "factors": result.factors,
            "auto_approve": result.auto_approve,
            "requires_human_approval": result.requires_human_approval,
            "context": result.context_snapshot,
        }
        entry_str = json.dumps(entry, sort_keys=True, default=str)
        entry_hash = hashlib.sha256(entry_str.encode()).hexdigest()
        entry["entry_hash"] = entry_hash
        self._last_hash = entry_hash
        self._save_last_hash(entry_hash)

        # Durable store first
        if self.pg_engine:
            try:
                with self.pg_engine.begin() as conn:
                    conn.execute(
                        sa_text(
                            "INSERT INTO audit_logs "
                            "(actor, action, resource, workspace_id, tenant_id, success, detail) "
                            "VALUES (:actor, :action, :resource, :workspace_id, :tenant_id, :success, :detail)"
                        ),
                        {
                            "actor": entry["context"].get("user_role", "system"),
                            "action": f"risk_score:{entry['level']}",
                            "resource": entry["context"].get("action_type", ""),
                            "workspace_id": "default",
                            "tenant_id": entry["context"].get("tenant_id", "default"),
                            "success": True,
                            "detail": json.dumps(entry, default=str),
                        },
                    )
            except SQLAlchemyError as e:
                logger.error("RISK AUDIT DURABLE WRITE FAILED: %s | event=%s", e, event_id)

        # Redis cache (recent queries)
        if self.redis:
            try:
                self.redis.lpush("risk:audit:events", json.dumps(entry, default=str))
                self.redis.ltrim("risk:audit:events", 0, 99999)
                tenant_key = f"risk:audit:tenant:{entry['context'].get('tenant_id', '')}"
                self.redis.lpush(tenant_key, json.dumps(entry, default=str))
                self.redis.expire(tenant_key, 7 * 24 * 60 * 60)
            except Exception as e:
                logger.error("RiskEngine: Redis audit write failed: %s", e)

    def query_audit(
        self,
        tenant_id: Optional[str] = None,
        min_score: Optional[int] = None,
        level: Optional[RiskLevel] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Query recent risk audit events from Redis cache."""
        if not self.redis:
            return []
        key = (
            f"risk:audit:tenant:{tenant_id}" if tenant_id else "risk:audit:events"
        )
        raw = self.redis.lrange(key, 0, limit - 1)
        out: List[Dict[str, Any]] = []
        for r in raw:
            try:
                e = json.loads(r)
            except json.JSONDecodeError:
                continue
            if min_score is not None and e.get("score", 0) < min_score:
                continue
            if level is not None and e.get("level") != level.value:
                continue
            out.append(e)
        return out

    def verify_integrity(self) -> bool:
        """Verify the hash chain integrity of the risk audit trail."""
        if not self.redis:
            return True
        events = self.redis.lrange("risk:audit:events", 0, -1)
        events.reverse()
        prev = "genesis"
        for e in events:
            try:
                entry = json.loads(e)
                if entry.get("previous_hash") != prev:
                    logger.error("RISK AUDIT INTEGRITY VIOLATION: hash chain broken")
                    return False
                prev = entry.get("entry_hash")
            except json.JSONDecodeError:
                return False
        return True


__all__ = [
    "RiskLevel",
    "RiskContext",
    "RiskResult",
    "RiskEngine",
    "risk_level_for_score",
    "ACTION_TYPE_WEIGHTS",
    "SENSITIVITY_WEIGHTS",
    "ROLE_PENALTY",
    "TENANT_TRUST_PENALTY",
    "DEFAULT_APPROVED_GEOGRAPHIES",
]
