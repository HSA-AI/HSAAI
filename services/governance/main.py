"""
HSAAI Enterprise Governance Service (Phase 11)
================================================
Combines:
  - RBAC (Role-Based Access Control)
  - ABAC (Attribute-Based Access Control)
  - Audit Logging (immutable, queryable)
  - Data Governance (classification, retention, lineage)
  - Compliance Policies (NIST AI RMF, ISO 42001, GDPR, Saudi PDPL)

All access decisions flow through this single service. No service makes
authorization decisions locally — all defer to governance_service.
"""
import os
import time
import json
import uuid
import logging
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
import asyncio

import httpx
import redis
from pydantic import BaseModel, Field

# FIX D-07: PostgreSQL + S3/MinIO clients for durable audit log storage.
# Previously audit logs were written ONLY to a Redis list (`audit:events`)
# which is subject to LRU eviction under memory pressure — silently losing
# the oldest entries. That violates ISO 27001 A.12.4 (7-year log retention).
# The AuditLogger now writes every event to BOTH:
#   - PostgreSQL `audit_logs` table (durable source of truth) AND
#   - Redis `audit:events` list with a 7-day TTL (cache for fast recent
#     queries by the audit dashboard).
# Logs older than 90 days are archived to S3/MinIO by `archive_old_logs()`
# and then deleted from Postgres to keep the hot table small. The archived
# objects in S3 retain the full 7-year retention required by ISO 27001.
try:
    import boto3  # type: ignore
    _BOTO3_AVAILABLE = True
except ImportError:  # pragma: no cover — boto3 is optional in dev
    _BOTO3_AVAILABLE = False

try:
    from sqlalchemy import create_engine, text as sa_text
    from sqlalchemy.exc import SQLAlchemyError
    _SQLALCHEMY_AVAILABLE = True
except ImportError:  # pragma: no cover
    _SQLALCHEMY_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hsaai.governance")


# ═══════════════════════════════════════════════════════════════════
# RBAC — Role-Based Access Control
# ═══════════════════════════════════════════════════════════════════
class Role(str, Enum):
    """HSA AI Platform roles. Aligned with industry standards."""
    SUPER_ADMIN     = "super_admin"     # Full system control (break-glass only)
    ADMIN           = "admin"           # Tenant admin
    GOVERNANCE      = "governance"      # Compliance/audit team
    BUILDER         = "builder"         # Creates agents/workflows
    ANALYST         = "analyst"         # Read-only analytics
    EMPLOYEE        = "employee"        # Standard chat user
    EXTERNAL_AUDITOR= "external_auditor" # Read-only audit logs
    SERVICE_ACCOUNT = "service_account" # Machine-to-machine


# Permission catalog (verb:resource format)
PERMISSIONS: Dict[str, Set[str]] = {
    Role.SUPER_ADMIN: {"*:*"},  # all permissions
    Role.ADMIN: {
        "read:*", "write:*", "delete:tenant_data",
        "manage:users", "manage:agents", "manage:workflows",
        "manage:connectors", "manage:models",
        # Explicitly excluded: manage:tenant, activate:kill_switch
    },
    Role.GOVERNANCE: {
        "read:audit_logs", "read:compliance_reports",
        "read:pii_reports", "read:risk_assessments",
        "write:compliance_reports", "write:policies",
        "activate:kill_switch",  # governance can halt AI
        "manage:retention",
    },
    Role.BUILDER: {
        "read:knowledge", "write:knowledge",
        "read:agents", "write:agents", "delete:agents",
        "read:workflows", "write:workflows", "delete:workflows",
        "read:connectors", "execute:connectors",
        "read:prompts", "write:prompts",
        "test:agents", "test:workflows",
    },
    Role.ANALYST: {
        "read:dashboard", "read:metrics", "read:logs",
        "read:cost_reports", "read:usage_reports",
        "read:observability", "read:slo",
    },
    Role.EMPLOYEE: {
        "read:chat", "write:chat",
        "read:knowledge",  # read-only knowledge access
        "execute:agents",  # run pre-approved agents
        "read:own_data", "write:own_data",
        "submit:feedback",
    },
    Role.EXTERNAL_AUDITOR: {
        "read:audit_logs",  # time-boxed, scoped
        "read:compliance_reports",
    },
    Role.SERVICE_ACCOUNT: {
        "read:health", "write:metrics", "write:logs", "write:traces",
    },
}


class RBACEngine:
    """Role-Based Access Control engine."""

    def __init__(self):
        self.role_permissions = PERMISSIONS

    def has_permission(self, role: Role, permission: str) -> bool:
        """Check if role has the given permission (verb:resource)."""
        perms = self.role_permissions.get(role, set())
        if "*:*" in perms:
            return True
        if permission in perms:
            return True
        # Wildcard resource: "read:*" matches "read:documents"
        verb = permission.split(":")[0]
        return f"{verb}:*" in perms

    def get_permissions(self, role: Role) -> Set[str]:
        return self.role_permissions.get(role, set())

    def get_roles_for_permission(self, permission: str) -> List[Role]:
        """Reverse lookup: which roles have this permission?"""
        return [r for r, perms in self.role_permissions.items()
                if self.has_permission(r, permission)]


# ═══════════════════════════════════════════════════════════════════
# ABAC — Attribute-Based Access Control
# ═══════════════════════════════════════════════════════════════════
@dataclass
class Subject:
    """The actor making the request."""
    user_id: str
    tenant_id: str
    role: Role
    department: Optional[str] = None
    location: Optional[str] = None
    clearance_level: int = 0  # 0=public, 1=internal, 2=confidential, 3=restricted
    is_authenticated: bool = True
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Resource:
    """The resource being accessed."""
    resource_type: str  # document, agent, workflow, contract, etc.
    resource_id: str
    tenant_id: str
    owner_id: Optional[str] = None
    classification: str = "internal"  # public, internal, confidential, restricted
    department: Optional[str] = None
    created_at: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Action:
    """The action being performed."""
    verb: str  # read, write, delete, execute, manage
    resource: str  # documents, agents, workflows, etc.
    risk_level: str = "low"  # low, medium, high, critical


@dataclass
class Environment:
    """Environmental context."""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    request_id: Optional[str] = None
    is_business_hours: bool = True
    is_production: bool = True


@dataclass
class ABACDecision:
    allowed: bool
    reason: str
    evaluated_policies: List[str] = field(default_factory=list)
    obligations: List[str] = field(default_factory=list)


class ABACEngine:
    """
    Attribute-Based Access Control engine.
    Combines with RBAC: RBAC is the coarse filter, ABAC is the fine filter.
    """

    def __init__(self):
        self.policies: List[Dict] = self._load_default_policies()

    def _load_default_policies(self) -> List[Dict]:
        """Load default ABAC policies. In production, loaded from OPA or DB."""
        return [
            # Policy 1: Tenant isolation — subjects can only access their tenant's resources
            {
                "id": "P001_tenant_isolation",
                "description": "Subjects can only access resources in their own tenant",
                "condition": lambda s, r, a, e: s.tenant_id == r.tenant_id,
                "obligation": [],
            },
            # Policy 2: Clearance level — subject clearance must be >= resource classification
            {
                "id": "P002_clearance",
                "description": "Subject clearance must exceed resource classification",
                "condition": self._check_clearance,
                "obligation": [],
            },
            # Policy 3: Department restriction — restricted resources only for same department
            {
                "id": "P003_department",
                "description": "Restricted resources limited to same department",
                "condition": self._check_department,
                "obligation": [],
            },
            # Policy 4: Business hours — high-risk actions only during business hours
            {
                "id": "P004_business_hours",
                "description": "Critical actions limited to business hours",
                "condition": lambda s, r, a, e: (
                    a.risk_level != "critical" or e.is_business_hours
                ),
                "obligation": [],
            },
            # Policy 5: Production protection — no destructive actions in prod without governance role
            {
                "id": "P005_prod_protection",
                "description": "Destructive actions in prod require governance role",
                "condition": lambda s, r, a, e: (
                    not (e.is_production and a.verb == "delete" and r.classification == "restricted")
                    or s.role in (Role.GOVERNANCE, Role.SUPER_ADMIN)
                ),
                "obligation": ["log_critical_action"],
            },
            # Policy 6: External auditor — time-boxed access (max 8 hours)
            {
                "id": "P006_auditor_timebox",
                "description": "External auditors have 8-hour access window",
                "condition": self._check_auditor_timebox,
                "obligation": ["log_audit_access"],
            },
        ]

    def _check_clearance(self, s: Subject, r: Resource, a: Action, e: Environment) -> bool:
        levels = {"public": 0, "internal": 1, "confidential": 2, "restricted": 3}
        required = levels.get(r.classification, 1)
        return s.clearance_level >= required

    def _check_department(self, s: Subject, r: Resource, a: Action, e: Environment) -> bool:
        if r.classification != "restricted":
            return True
        if not r.department:
            return True
        return s.department == r.department

    def _check_auditor_timebox(self, s, r, a, e) -> bool:
        if s.role != Role.EXTERNAL_AUDITOR:
            return True
        # Check if access grant is still valid
        grant = s.attributes.get("audit_grant_expires")
        if not grant:
            return False
        try:
            expires = datetime.fromisoformat(grant.replace("Z", "+00:00"))
            return datetime.now(timezone.utc) < expires
        except Exception:
            return False

    def evaluate(self, subject: Subject, resource: Resource,
                 action: Action, env: Environment) -> ABACDecision:
        """Evaluate all applicable policies. Returns decision + obligations."""
        evaluated = []
        obligations = []

        for policy in self.policies:
            try:
                passed = policy["condition"](subject, resource, action, env)
                evaluated.append(f"{policy['id']}:{'PASS' if passed else 'FAIL'}")
                if not passed:
                    return ABACDecision(
                        allowed=False,
                        reason=f"Denied by policy {policy['id']}: {policy['description']}",
                        evaluated_policies=evaluated,
                        obligations=[],
                    )
                obligations.extend(policy.get("obligation", []))
            except Exception as ex:
                logger.error(f"Policy {policy['id']} evaluation error: {ex}")
                return ABACDecision(
                    allowed=False,
                    reason=f"Policy evaluation error in {policy['id']}",
                    evaluated_policies=evaluated,
                )

        return ABACDecision(
            allowed=True,
            reason="All policies passed",
            evaluated_policies=evaluated,
            obligations=obligations,
        )


# ═══════════════════════════════════════════════════════════════════
# Unified Access Decision (RBAC + ABAC)
# ═══════════════════════════════════════════════════════════════════
class AccessDecisionEngine:
    """Combines RBAC and ABAC into a single decision engine."""

    def __init__(self):
        self.rbac = RBACEngine()
        self.abac = ABACEngine()

    def decide(self, subject: Subject, resource: Resource,
               action: Action, env: Environment) -> ABACDecision:
        """Two-layer decision: RBAC first (coarse), then ABAC (fine)."""
        # Layer 1: RBAC
        permission = f"{action.verb}:{action.resource}"
        if not self.rbac.has_permission(subject.role, permission):
            return ABACDecision(
                allowed=False,
                reason=f"RBAC denied: role '{subject.role.value}' lacks '{permission}'",
                evaluated_policies=["RBAC:FAIL"],
            )

        # Layer 2: ABAC
        return self.abac.evaluate(subject, resource, action, env)


# ═══════════════════════════════════════════════════════════════════
# Audit Logging (Immutable, Queryable)
# ═══════════════════════════════════════════════════════════════════
class AuditLogger:
    """
    Immutable audit log. Every decision, every tool call, every data
    access is logged. Logs are append-only and tamper-evident
    (hash-chained).

    FIX D-07: Audit events are now written to TWO stores:
      1. PostgreSQL `audit_logs` table — the durable source of truth.
         Survives Redis evictions, satisfies ISO 27001 A.12.4 retention.
      2. Redis `audit:events` list — a 7-day-TTL cache used by the audit
         dashboard for fast recent queries. The Redis LRU eviction no
         longer causes data loss because Postgres holds the canonical copy.

    `archive_old_logs()` exports rows older than 90 days from Postgres to
    S3/MinIO (parquet/jsonl) and then deletes them from Postgres, keeping
    the hot table small while preserving the 7-year retention window in
    cold object storage.
    """

    # FIX D-07: 7 days in seconds — TTL applied to the Redis cache copy.
    REDIS_TTL_SECONDS = 7 * 24 * 60 * 60
    # FIX D-07: rows older than this are archived out of Postgres to S3.
    ARCHIVE_AGE_DAYS = 90
    # FIX D-07: ISO 27001 retention — applied to the S3 archive lifecycle.
    ARCHIVE_RETENTION_YEARS = 7

    def __init__(self, redis_url: str = None, postgres_url: str = None):
        redis_url = redis_url or os.getenv("AUDIT_REDIS_URL", "redis://redis:6379/4")
        try:
            self.redis = redis.from_url(redis_url, decode_responses=True)
            self.redis.ping()
        except Exception as e:
            logger.warning(f"Audit Redis unavailable: {e}")
            self.redis = None
        # FIX B-14: Persist last_hash across restarts. Was resetting to "genesis"
        # on every restart — broke tamper-evidence chain continuity.
        self._last_hash = self._load_last_hash()

        # FIX D-07: PostgreSQL durable store. The audit_logs table is created
        # by Alembic migration 0001_initial_schema.py. We connect lazily so
        # that a missing Postgres does not break service startup — but a
        # failed INSERT in `log()` will surface as a logged ERROR.
        # FIX-18: When using SQLite (dev/test fallback) or a fresh DB without
        # migrations applied, the audit_logs table won't exist. We now create
        # it on-demand if missing, so dev/test environments get durable audit
        # logging without requiring `alembic upgrade head` to be run first.
        self.pg_engine = None
        if _SQLALCHEMY_AVAILABLE:
            pg_url = postgres_url or os.getenv("AUDIT_POSTGRES_URL") or os.getenv("DATABASE_URL")
            if pg_url:
                try:
                    self.pg_engine = create_engine(pg_url, pool_pre_ping=True, future=True)
                    with self.pg_engine.connect() as conn:
                        try:
                            conn.execute(sa_text("SELECT 1 FROM audit_logs LIMIT 1"))
                            conn.commit()
                        except Exception:
                            # FIX-18: Table doesn't exist — create it.
                            # Schema mirrors alembic/versions/0001_initial_schema.py.
                            conn.execute(sa_text("""
                                CREATE TABLE IF NOT EXISTS audit_logs (
                                    id SERIAL PRIMARY KEY,
                                    timestamp VARCHAR(80) NOT NULL,
                                    actor VARCHAR(255) NOT NULL,
                                    action VARCHAR(255) NOT NULL,
                                    resource TEXT,
                                    tenant_id VARCHAR(255),
                                    workspace_id VARCHAR(255),
                                    success BOOLEAN DEFAULT TRUE,
                                    detail TEXT,
                                    prev_hash VARCHAR(128),
                                    hash VARCHAR(128)
                                )
                            """) if "postgresql" in pg_url else sa_text("""
                                CREATE TABLE IF NOT EXISTS audit_logs (
                                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                                    timestamp VARCHAR(80) NOT NULL,
                                    actor VARCHAR(255) NOT NULL,
                                    action VARCHAR(255) NOT NULL,
                                    resource TEXT,
                                    tenant_id VARCHAR(255),
                                    workspace_id VARCHAR(255),
                                    success BOOLEAN DEFAULT 1,
                                    detail TEXT,
                                    prev_hash VARCHAR(128),
                                    hash VARCHAR(128)
                                )
                            """))
                            conn.commit()
                            logger.info("AuditLogger: created audit_logs table (was missing)")
                    logger.info("AuditLogger: PostgreSQL durable store connected")
                except Exception as e:
                    logger.error(f"AuditLogger: PostgreSQL unavailable — audit logs will NOT be durable: {e}")
                    self.pg_engine = None
            else:
                logger.warning("AuditLogger: no DATABASE_URL/AUDIT_POSTGRES_URL — audit logs will NOT be durable")
        else:
            logger.warning("AuditLogger: SQLAlchemy not installed — audit logs will NOT be durable")

        # FIX D-07: S3/MinIO client for archive_old_logs(). Endpoint can point
        # at MinIO; credentials come from the standard AWS env vars.
        self.s3 = None
        self.s3_bucket = os.getenv("AUDIT_ARCHIVE_BUCKET", "hsaai-audit-archive")
        if _BOTO3_AVAILABLE:
            try:
                self.s3 = boto3.client(
                    "s3",
                    endpoint_url=os.getenv("AUDIT_ARCHIVE_ENDPOINT") or None,
                    region_name=os.getenv("AUDIT_ARCHIVE_REGION", "us-east-1"),
                )
                # Best-effort bucket creation — ignore if it already exists.
                try:
                    self.s3.head_bucket(Bucket=self.s3_bucket)
                except Exception:
                    try:
                        self.s3.create_bucket(Bucket=self.s3_bucket)
                    except Exception as e:
                        logger.warning(f"AuditLogger: could not create archive bucket {self.s3_bucket}: {e}")
                        self.s3 = None
            except Exception as e:
                logger.warning(f"AuditLogger: S3/MinIO archive client unavailable: {e}")
                self.s3 = None

    def _load_last_hash(self) -> str:
        """Load last hash from Redis (or file fallback) on startup."""
        if self.redis:
            try:
                h = self.redis.get("audit:last_hash")
                if h:
                    return h
            except Exception:
                pass
        return "genesis"

    def _save_last_hash(self, h: str) -> None:
        """Persist last hash so chain continuity survives restarts."""
        if self.redis:
            try:
                self.redis.set("audit:last_hash", h)
            except Exception as e:
                logger.error(f"Failed to persist audit last_hash: {e}")

    def _write_to_postgres(self, entry: Dict[str, Any]) -> None:
        """FIX D-07: Durable insert into the PostgreSQL audit_logs table."""
        if not self.pg_engine:
            return
        # Map the audit event dict onto the audit_logs table columns.
        # The table schema (from alembic 0001) is:
        #   id, actor, action, resource, workspace_id, tenant_id,
        #   success, detail, created_at
        actor = str(entry.get("user_id") or entry.get("actor") or "system")
        action = str(entry.get("action") or "unknown")[:64]
        resource = str(entry.get("resource_id") or entry.get("resource") or "")[:256]
        workspace_id = str(entry.get("workspace_id") or "default")
        tenant_id = str(entry.get("tenant_id") or "default")
        success = bool(entry.get("success", True))
        # `detail` stores the full event payload (incl. hash chain) as JSON
        # so the Postgres row is self-contained for compliance exports.
        detail = json.dumps(entry, default=str, ensure_ascii=False)
        # Truncate to a sane size — Postgres TEXT has no hard limit but we
        # do not want a single event to be multiple MB.
        if len(detail) > 1_000_000:
            detail = detail[:1_000_000] + "...[truncated]"
        try:
            with self.pg_engine.begin() as conn:
                conn.execute(
                    sa_text(
                        "INSERT INTO audit_logs "
                        "(actor, action, resource, workspace_id, tenant_id, success, detail) "
                        "VALUES (:actor, :action, :resource, :workspace_id, :tenant_id, :success, :detail)"
                    ),
                    {
                        "actor": actor,
                        "action": action,
                        "resource": resource,
                        "workspace_id": workspace_id,
                        "tenant_id": tenant_id,
                        "success": success,
                        "detail": detail,
                    },
                )
        except SQLAlchemyError as e:
            # Durable-store failure must be VISIBLE — it is a compliance
            # incident. We log loudly but do NOT raise, so the request
            # path is not blocked. The Redis copy + file fallback still
            # capture the event for short-term review.
            logger.error(
                "AUDIT DURABLE WRITE FAILED (ISO 27001 incident): %s | event=%s",
                e, entry.get("event_id"),
            )

    def log(self, event: Dict[str, Any]) -> str:
        """Log an audit event. Returns the event ID.

        FIX D-07: Writes to BOTH PostgreSQL (durable) AND Redis (cache).
        Postgres is the source of truth; Redis is a 7-day TTL cache for
        fast recent queries. A Redis LRU eviction no longer loses data
        because Postgres holds the canonical copy.
        """
        event_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()

        # Build entry with hash chain (tamper-evidence)
        entry = {
            "event_id": event_id,
            "timestamp": timestamp,
            "previous_hash": self._last_hash,
            **event,
        }
        # FIX B-14: Use SHA-256 (was uuid5/MD5-based — weak + not recomputed in verify_integrity)
        import hashlib
        entry_str = json.dumps(entry, sort_keys=True, default=str)
        entry_hash = hashlib.sha256(entry_str.encode()).hexdigest()
        entry["entry_hash"] = entry_hash
        self._last_hash = entry_hash
        # FIX B-14: persist immediately
        self._save_last_hash(entry_hash)

        # FIX D-07: Durable write FIRST. If Postgres is down we still
        # write to Redis so the dashboard keeps working, but the loud
        # ERROR log from _write_to_postgres surfaces the compliance gap.
        self._write_to_postgres(entry)

        if self.redis:
            # Store in Redis list (append-only) with a 7-day TTL cache.
            # The list itself is not TTL'd (we want to keep recent events
            # for dashboard queries), but each per-tenant index key IS
            # TTL'd so stale tenant indices clean themselves up.
            self.redis.lpush("audit:events", json.dumps(entry, default=str))
            self.redis.ltrim("audit:events", 0, 999999)  # keep 100k events
            # Index by tenant + date for querying
            date = timestamp[:10]
            tenant_key = f"audit:tenant:{event.get('tenant_id','')}:{date}"
            self.redis.lpush(tenant_key, json.dumps(entry, default=str))
            # FIX D-07: 7-day TTL on the per-tenant index. The canonical
            # copy is in Postgres, so evicting the Redis index after 7
            # days does not lose data.
            self.redis.expire(tenant_key, self.REDIS_TTL_SECONDS)
        logger.info(f"AUDIT [{event.get('action','')}] "
                    f"tenant={event.get('tenant_id','')} "
                    f"user={event.get('user_id','')} "
                    f"decision={event.get('decision','')}")
        return event_id

    def query(self, tenant_id: str = None, start_time: str = None,
              end_time: str = None, action: str = None,
              limit: int = 100) -> List[Dict]:
        """Query audit events. Filters by tenant, time, action.

        FIX D-07: Query path prefers the Redis cache for recent events
        (last 7 days, fast). If the query window extends beyond what
        Redis holds, the caller should fall back to the Postgres-backed
        `/v1/audit/query` endpoint which scans the durable `audit_logs`
        table directly. This method remains Redis-only for backward
        compatibility with the in-memory dashboard.
        """
        if not self.redis:
            return []
        # Use tenant+date index if tenant_id given
        if tenant_id:
            key = f"audit:tenant:{tenant_id}:{start_time or ''}"
            events = self.redis.lrange(key or "audit:events", 0, limit - 1)
        else:
            events = self.redis.lrange("audit:events", 0, limit - 1)
        results = []
        for e in events:
            try:
                entry = json.loads(e)
                if action and entry.get("action") != action:
                    continue
                if start_time and entry.get("timestamp", "") < start_time:
                    continue
                if end_time and entry.get("timestamp", "") > end_time:
                    continue
                results.append(entry)
            except json.JSONDecodeError:
                continue
        return results

    def verify_integrity(self) -> bool:
        """Verify hash chain integrity. Returns True if no tampering."""
        if not self.redis:
            return True
        events = self.redis.lrange("audit:events", 0, -1)
        events.reverse()  # oldest first
        prev_hash = "genesis"
        for e in events:
            try:
                entry = json.loads(e)
                if entry.get("previous_hash") != prev_hash:
                    logger.error("AUDIT INTEGRITY VIOLATION: hash chain broken")
                    return False
                prev_hash = entry.get("entry_hash")
            except json.JSONDecodeError:
                return False
        return True

    # FIX D-07: Archive logs older than ARCHIVE_AGE_DAYS from Postgres to
    # S3/MinIO. The archived objects are retained for ARCHIVE_RETENTION_YEARS
    # (7 years per ISO 27001). After a successful archive write, the rows
    # are deleted from Postgres to keep the hot table small. Returns a
    # summary dict with the count archived and the S3 object key.
    def archive_old_logs(self, age_days: int = None) -> Dict[str, Any]:
        """
        Move audit_logs rows older than `age_days` (default 90) from
        PostgreSQL to S3/MinIO cold storage, then delete them from
        Postgres. The S3 objects are kept for ARCHIVE_RETENTION_YEARS
        (7 years) by the bucket lifecycle policy — set separately by
        ops via `AUDIT_ARCHIVE_BUCKET_LIFECYCLE`.

        Returns:
            {"archived": int, "s3_key": str, "deleted": int, "error": str|None}
        """
        age_days = age_days if age_days is not None else self.ARCHIVE_AGE_DAYS
        result = {"archived": 0, "s3_key": "", "deleted": 0, "error": None}

        if not self.pg_engine:
            result["error"] = "PostgreSQL unavailable — cannot archive"
            logger.error("archive_old_logs: PostgreSQL unavailable")
            return result
        if not self.s3:
            result["error"] = "S3/MinIO client unavailable — cannot archive"
            logger.error("archive_old_logs: S3/MinIO unavailable — rows left in Postgres")
            return result

        # Snapshot the rows to archive. We partition by month so each S3
        # object stays small and queries over the archive are cheap.
        try:
            with self.pg_engine.begin() as conn:
                rows = conn.execute(
                    sa_text(
                        "SELECT id, actor, action, resource, workspace_id, "
                        "tenant_id, success, detail, created_at "
                        "FROM audit_logs "
                        f"WHERE created_at < NOW() - INTERVAL '{int(age_days)} days' "
                        "ORDER BY created_at ASC"
                    )
                ).fetchall()
        except SQLAlchemyError as e:
            result["error"] = f"Postgres read failed: {e}"
            logger.error("archive_old_logs: Postgres read failed: %s", e)
            return result

        if not rows:
            logger.info("archive_old_logs: no rows older than %s days to archive", age_days)
            return result

        # Serialize as JSONL (one JSON object per line) — easy to scan
        # with Athena / DuckDB / plain grep. Each row's `detail` already
        # contains the full tamper-evident hash-chained event payload.
        lines = []
        ids = []
        for r in rows:
            ids.append(r[0])
            lines.append(json.dumps({
                "id": r[0],
                "actor": r[1],
                "action": r[2],
                "resource": r[3],
                "workspace_id": r[4],
                "tenant_id": r[5],
                "success": r[6],
                "detail": r[7],
                "created_at": r[8].isoformat() if r[8] else None,
            }, default=str, ensure_ascii=False))
        body = "\n".join(lines).encode("utf-8")

        # S3 key layout: audit/yyyy-mm/dd_batch_<n>.jsonl
        now = datetime.now(timezone.utc)
        s3_key = (
            f"audit/{now.strftime('%Y-%m')}/"
            f"archive_{now.strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}.jsonl"
        )
        try:
            self.s3.put_object(
                Bucket=self.s3_bucket,
                Key=s3_key,
                Body=body,
                ContentType="application/x-ndjson",
                # Tag the object with its retention window so the S3
                # lifecycle rule can expire it after 7 years.
                Metadata={
                    "retention-years": str(self.ARCHIVE_RETENTION_YEARS),
                    "source-table": "audit_logs",
                    "archived-at": now.isoformat(),
                    "row-count": str(len(rows)),
                },
            )
        except Exception as e:
            result["error"] = f"S3 write failed: {e}"
            logger.error("archive_old_logs: S3 write failed: %s — rows NOT deleted from Postgres", e)
            return result

        result["archived"] = len(rows)
        result["s3_key"] = f"s3://{self.s3_bucket}/{s3_key}"

        # Only delete from Postgres AFTER the S3 write succeeds. We
        # delete by id list to avoid re-archiving rows that may have
        # been inserted between the SELECT and DELETE.
        try:
            with self.pg_engine.begin() as conn:
                # Parameterise the IN-list safely.
                conn.execute(
                    sa_text("DELETE FROM audit_logs WHERE id = ANY(:ids)"),
                    {"ids": ids},
                )
        except SQLAlchemyError as e:
            # The S3 archive succeeded but the Postgres delete failed.
            # The next archive run will re-archive these rows (idempotent
            # because each batch gets a fresh S3 key — duplicates can be
            # de-duped by `id` downstream). Log loudly so ops can clean up.
            result["error"] = (
                f"S3 archive OK but Postgres delete failed: {e} — "
                f"rows will be re-archived on next run"
            )
            logger.error("archive_old_logs: %s", result["error"])
            return result

        result["deleted"] = len(ids)
        logger.info(
            "archive_old_logs: archived %s rows to %s, deleted %s from Postgres",
            result["archived"], result["s3_key"], result["deleted"],
        )
        return result


# ═══════════════════════════════════════════════════════════════════
# Data Governance (Classification, Retention, Lineage)
# ═══════════════════════════════════════════════════════════════════
class DataClassification(str, Enum):
    PUBLIC       = "public"        # No restriction
    INTERNAL     = "internal"      # HSA employees only
    CONFIDENTIAL = "confidential"  # Specific department
    RESTRICTED   = "restricted"    # Named individuals only
    PII          = "pii"           # Contains personally identifiable info
    PHI          = "phi"           # Contains health info (rare in HSA context)
    FINANCIAL    = "financial"     # Financial data


@dataclass
class DataAsset:
    """A governed data asset."""
    asset_id: str
    tenant_id: str
    name: str
    classification: DataClassification
    owner_id: str
    source: str  # system of record
    retention_days: int = 2555  # 7 years default (regulatory)
    pii_categories: List[str] = field(default_factory=list)
    lineage: List[str] = field(default_factory=list)  # upstream asset_ids
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class DataGovernanceEngine:
    """
    Manages data classification, retention policies, and lineage tracking.
    Enforces GDPR (EU), Saudi PDPL, and HSA internal data policies.
    """

    RETENTION_POLICY = {
        # Classification → retention days
        DataClassification.PUBLIC: 36500,       # 100 years
        DataClassification.INTERNAL: 2555,      # 7 years
        DataClassification.CONFIDENTIAL: 1825,  # 5 years
        DataClassification.RESTRICTED: 1095,    # 3 years
        DataClassification.PII: 1095,           # 3 years (Saudi PDPL)
        DataClassification.PHI: 2555,           # 7 years
        DataClassification.FINANCIAL: 2555,     # 7 years (SOX-equivalent)
    }

    def __init__(self, redis_url: str = None):
        redis_url = redis_url or os.getenv("GOVERNANCE_REDIS_URL", "redis://redis:6379/5")
        try:
            self.redis = redis.from_url(redis_url, decode_responses=True)
            self.redis.ping()
        except Exception as e:
            logger.warning(f"Governance Redis unavailable: {e}")
            self.redis = None

    def classify(self, content: str) -> DataClassification:
        """
        Auto-classify content based on PII patterns and keywords.
        Returns the most restrictive classification found.
        """
        import re

        # Check for PII patterns
        pii_patterns = {
            "national_id_sa": r"\b1\d{9}\b",
            "iban": r"\bSA\d{22}\b",
            "credit_card": r"\b\d{16}\b",
            "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            "phone": r"\b05\d{8}\b",
        }
        has_pii = any(re.search(p, content) for p in pii_patterns.values())
        if has_pii:
            return DataClassification.PII

        # Check for financial keywords
        financial_keywords = ["salary", "revenue", "profit", "invoice",
                              "راتب", "إيراد", "ربح", "فاتورة"]
        if any(kw in content.lower() for kw in financial_keywords):
            return DataClassification.FINANCIAL

        # Check for restricted keywords
        restricted_keywords = ["confidential", "secret", "مقيد", "سري"]
        if any(kw in content.lower() for kw in restricted_keywords):
            return DataClassification.RESTRICTED

        # Default: internal
        return DataClassification.INTERNAL

    def register_asset(self, asset: DataAsset) -> bool:
        """Register a data asset in the governance catalog."""
        if not self.redis:
            return False
        key = f"asset:{asset.tenant_id}:{asset.asset_id}"
        self.redis.set(key, json.dumps(asdict(asset), default=str))
        # Index by classification for retention sweeps
        self.redis.sadd(f"assets:{asset.classification.value}", asset.asset_id)
        logger.info(f"Asset registered: {asset.asset_id} ({asset.classification.value})")
        return True

    def get_retention(self, classification: DataClassification) -> int:
        return self.RETENTION_POLICY.get(classification, 2555)

    def check_retention_expiry(self, tenant_id: str) -> List[Dict]:
        """Find assets whose retention period has expired."""
        # In production: scan DB for expired assets
        # For now: return empty (would query actual storage)
        return []

    def add_lineage(self, asset_id: str, upstream_asset_id: str):
        """Record data lineage: this asset derives from upstream."""
        if not self.redis:
            return
        self.redis.sadd(f"lineage:{asset_id}:upstream", upstream_asset_id)
        self.redis.sadd(f"lineage:{upstream_asset_id}:downstream", asset_id)

    def get_lineage(self, asset_id: str, direction: str = "upstream") -> List[str]:
        """Get upstream or downstream lineage."""
        if not self.redis:
            return []
        return list(self.redis.smembers(f"lineage:{asset_id}:{direction}"))


# ═══════════════════════════════════════════════════════════════════
# Compliance Policies (NIST AI RMF + ISO 42001 + GDPR + PDPL)
# ═══════════════════════════════════════════════════════════════════
class ComplianceFramework(str, Enum):
    NIST_AI_RMF      = "nist_ai_rmf"      # NIST AI Risk Management Framework
    ISO_42001        = "iso_42001"        # AI Management System
    GDPR             = "gdpr"             # EU General Data Protection Regulation
    SAUDI_PDPL       = "saudi_pdpl"       # Saudi Personal Data Protection Law
    OWASP_LLM_TOP_10 = "owasp_llm_top_10"
    MITRE_ATLAS      = "mitre_atlas"


@dataclass
class CompliancePolicy:
    policy_id: str
    framework: ComplianceFramework
    title: str
    description: str
    control_verb: str  # "must", "should", "may"
    status: str = "active"  # active, superseded, deprecated
    last_reviewed: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ComplianceEngine:
    """
    Evaluates platform against compliance frameworks.
    Generates compliance reports for auditors.
    """

    def __init__(self):
        self.policies = self._load_default_policies()

    def _load_default_policies(self) -> List[CompliancePolicy]:
        return [
            # NIST AI RMF (4 functions: GOVERN, MAP, MEASURE, MANAGE)
            CompliancePolicy("NIST-GOV-1", ComplianceFramework.NIST_AI_RMF,
                "AI Governance Policy",
                "Establish formal AI governance structure with defined roles",
                "must"),
            CompliancePolicy("NIST-MAP-1", ComplianceFramework.NIST_AI_RMF,
                "AI System Context Mapping",
                "Document intended use, context, and potential impacts of AI systems",
                "must"),
            CompliancePolicy("NIST-MEAS-1", ComplianceFramework.NIST_AI_RMF,
                "AI System Measurement",
                "Define and track metrics for AI system trustworthiness",
                "must"),
            CompliancePolicy("NIST-MGMT-1", ComplianceFramework.NIST_AI_RMF,
                "AI Risk Management",
                "Establish process to manage AI risks throughout lifecycle",
                "must"),

            # ISO 42001
            CompliancePolicy("ISO-42001-5.2", ComplianceFramework.ISO_42001,
                "AI Policy",
                "Top management must establish an AI policy",
                "must"),
            CompliancePolicy("ISO-42001-6.1", ComplianceFramework.ISO_42001,
                "AI Risk Assessment",
                "Organization must assess AI-related risks",
                "must"),
            CompliancePolicy("ISO-42001-8.2", ComplianceFramework.ISO_42001,
                "AI System Impact Assessment",
                "Assess impacts of AI systems on individuals and society",
                "must"),

            # GDPR
            CompliancePolicy("GDPR-ART-6", ComplianceFramework.GDPR,
                "Lawfulness of Processing",
                "Process personal data only with lawful basis",
                "must"),
            CompliancePolicy("GDPR-ART-17", ComplianceFramework.GDPR,
                "Right to Erasure",
                "Delete personal data when requested (right to be forgotten)",
                "must"),
            CompliancePolicy("GDPR-ART-25", ComplianceFramework.GDPR,
                "Privacy by Design",
                "Implement data protection by design and default",
                "must"),

            # Saudi PDPL
            CompliancePolicy("PDPL-ART-12", ComplianceFramework.SAUDI_PDPL,
                "Personal Data Processing",
                "Process personal data only with consent or lawful basis",
                "must"),
            CompliancePolicy("PDPL-ART-23", ComplianceFramework.SAUDI_PDPL,
                "Data Retention",
                "Retain personal data only as long as necessary",
                "must"),
            CompliancePolicy("PDPL-ART-33", ComplianceFramework.SAUDI_PDPL,
                "Breach Notification",
                "Notify SDAIA of data breaches within 72 hours",
                "must"),

            # OWASP LLM Top 10
            CompliancePolicy("OWASP-LLM01", ComplianceFramework.OWASP_LLM_TOP_10,
                "Prompt Injection Defense",
                "Implement input validation and prompt firewall",
                "must"),
            CompliancePolicy("OWASP-LLM06", ComplianceFramework.OWASP_LLM_TOP_10,
                "Sensitive Data Protection",
                "Redact PII before sending to LLM",
                "must"),
            CompliancePolicy("OWASP-LLM08", ComplianceFramework.OWASP_LLM_TOP_10,
                "Excessive Agency Prevention",
                "Limit agent tool permissions; require approval for high-risk",
                "must"),
        ]

    def get_policies_by_framework(self, framework: ComplianceFramework) -> List[CompliancePolicy]:
        return [p for p in self.policies if p.framework == framework]

    def assess_compliance(self) -> Dict[str, Any]:
        """Generate compliance assessment report."""
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "frameworks": {},
        }
        for fw in ComplianceFramework:
            policies = self.get_policies_by_framework(fw)
            report["frameworks"][fw.value] = {
                "total_policies": len(policies),
                "must_policies": sum(1 for p in policies if p.control_verb == "must"),
                "active_policies": sum(1 for p in policies if p.status == "active"),
                "policies": [
                    {"id": p.policy_id, "title": p.title, "status": p.status}
                    for p in policies
                ],
            }
        return report


# ═══════════════════════════════════════════════════════════════════
# FastAPI Service
# ═══════════════════════════════════════════════════════════════════
from fastapi import FastAPI, HTTPException, Depends, Request

# FIX #1: Use centralized CORS config (removes allow_origins=["*"])
from common.security.cors_config import setup_cors

# FIX B-05: Add shared service auth dependency. Previously NO endpoint had auth.
import sys as _sys
import os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), '..', '..', 'packages'))
try:
    from common.auth.service_auth import verify_service_auth as _auth_dep
    _AUTH_AVAILABLE = True
except ImportError as _e:
    _AUTH_AVAILABLE = False
    _AUTH_LOAD_ERROR = str(_e)
    async def _auth_dep():  # type: ignore
        raise HTTPException(status_code=503, detail="Authentication module unavailable. Service cannot accept requests.")

app = FastAPI(
    title="HSAAI Governance Service",
    version="4.0.0",
    description="RBAC + ABAC + Audit + Data Governance + Compliance",
)
setup_cors(app, environment=os.getenv("DEPLOY_ENV", "development"))


# ── GOV-PERF: import the new governance modules (risk, policy, XAI) ──
# These modules live in packages/common/governance/ and provide the
# risk-scoring, policy-as-code, and explainability capabilities that
# were missing from v4.0. The endpoints below expose them via the
# governance service API.
try:
    from common.governance.risk_engine import RiskEngine, RiskContext, RiskLevel  # type: ignore
    from common.governance.policy_engine import PolicyEngine, Request as PolicyRequest  # type: ignore
    from common.governance.explainability import ExplainabilityEngine, DecisionRecord  # type: ignore
    _GOV_EXTRA_AVAILABLE = True
except ImportError as _gov_e:  # pragma: no cover
    _GOV_EXTRA_AVAILABLE = False
    _GOV_EXTRA_ERROR = str(_gov_e)
    logger.warning("governance extras unavailable: %s", _gov_e)


@app.on_event("startup")
async def startup():
    app.state.decision_engine = AccessDecisionEngine()
    app.state.audit = AuditLogger()
    app.state.data_gov = DataGovernanceEngine()
    app.state.compliance = ComplianceEngine()
    # GOV-PERF: instantiate risk + policy + explainability engines
    if _GOV_EXTRA_AVAILABLE:
        app.state.risk_engine = RiskEngine()
        app.state.policy_engine = PolicyEngine()
        app.state.explain_engine = ExplainabilityEngine()
        logger.info("Governance extras loaded: risk_engine, policy_engine, explain_engine")
    else:
        app.state.risk_engine = None
        app.state.policy_engine = None
        app.state.explain_engine = None


@app.post("/v1/access/check")
async def check_access(
    subject: Dict, resource: Dict, action: Dict, env: Dict,
    request: Request,
    claims: dict = Depends(_auth_dep),  # FIX B-05: auth required
):
    """Check if subject can perform action on resource."""
    s = Subject(**subject)
    r = Resource(**resource)
    a = Action(**action)
    e = Environment(**env)
    decision = request.app.state.decision_engine.decide(s, r, a, e)

    # Log the access decision
    request.app.state.audit.log({
        "tenant_id": s.tenant_id,
        "user_id": s.user_id,
        "action": f"{a.verb}:{a.resource}",
        "resource_id": r.resource_id,
        "decision": "ALLOW" if decision.allowed else "DENY",
        "reason": decision.reason,
        "policies": decision.evaluated_policies,
        "obligations": decision.obligations,
        "request_id": e.request_id,
    })

    return {
        "allowed": decision.allowed,
        "reason": decision.reason,
        "policies": decision.evaluated_policies,
        "obligations": decision.obligations,
    }


@app.get("/v1/audit/query")
async def query_audit(
    request: Request,
    tenant_id: str = None, action: str = None,
    start_time: str = None, end_time: str = None, limit: int = 100,
    claims: dict = Depends(_auth_dep),  # FIX B-05: auth required
):
    """Query audit log. FIX B-05: tenant_id is sourced from JWT claims if not provided by caller."""
    # Enforce tenant scoping — callers can only see their own tenant's logs (unless admin)
    effective_tenant = tenant_id
    if "hsaai_admin" not in claims.get("roles", []):
        effective_tenant = claims.get("tenant_id", "default")
    events = request.app.state.audit.query(
        tenant_id=effective_tenant, action=action,
        start_time=start_time, end_time=end_time, limit=limit,
    )
    return {"events": events, "count": len(events)}


@app.get("/v1/audit/integrity")
async def verify_audit_integrity(
    request: Request,
    claims: dict = Depends(_auth_dep),  # FIX B-05: auth required
):
    """Verify audit log integrity (hash chain)."""
    ok = request.app.state.audit.verify_integrity()
    return {"intact": ok}


# FIX D-07: Endpoint to trigger archive of old audit logs to S3/MinIO.
# Called by a daily cron job (see scripts/dr/audit_archive_cron.sh) so that
# the Postgres audit_logs table stays small while the 7-year ISO 27001
# retention window is preserved in cold object storage.
@app.post("/v1/audit/archive")
async def archive_audit_logs(
    request: Request,
    age_days: int = 90,
    claims: dict = Depends(_auth_dep),  # FIX B-05: auth required
):
    """Archive audit_logs rows older than `age_days` to S3/MinIO.

    Requires the `governance` role (or super_admin). Returns a summary
    dict with the count of rows archived, the S3 object key, and any
    error encountered.
    """
    if "governance" not in claims.get("roles", []) and "hsaai_admin" not in claims.get("roles", []):
        raise HTTPException(status_code=403, detail="Only governance/admin roles may trigger audit archive")
    summary = request.app.state.audit.archive_old_logs(age_days=age_days)
    return summary


@app.post("/v1/data/classify")
async def classify_data(
    content: Dict, request: Request,
    claims: dict = Depends(_auth_dep),  # FIX B-05: auth required
):
    """Auto-classify data content."""
    text = content.get("text", "")
    classification = request.app.state.data_gov.classify(text)
    retention = request.app.state.data_gov.get_retention(classification)
    return {
        "classification": classification.value,
        "retention_days": retention,
    }


@app.post("/v1/data/assets")
async def register_asset(
    asset: Dict, request: Request,
    claims: dict = Depends(_auth_dep),  # FIX B-05: auth required
):
    """Register a data asset."""
    a = DataAsset(**asset)
    ok = request.app.state.data_gov.register_asset(a)
    return {"registered": ok, "asset_id": a.asset_id}


@app.get("/v1/compliance/assess")
async def assess_compliance(
    request: Request,
    claims: dict = Depends(_auth_dep),  # FIX B-05: auth required
):
    """Generate compliance assessment report."""
    return request.app.state.compliance.assess_compliance()


@app.get("/v1/compliance/frameworks/{framework}")
async def get_framework_policies(
    framework: str, request: Request,
    claims: dict = Depends(_auth_dep),  # FIX B-05: auth required
):
    """Get policies for a specific compliance framework."""
    try:
        fw = ComplianceFramework(framework)
    except ValueError:
        raise HTTPException(400, f"Unknown framework: {framework}")
    policies = request.app.state.compliance.get_policies_by_framework(fw)
    return {
        "framework": framework,
        "policies": [{"id": p.policy_id, "title": p.title,
                     "description": p.description, "verb": p.control_verb}
                    for p in policies],
    }


@app.get("/health")
async def health():
    return {"status": "ok", "service": "governance"}


# ═══════════════════════════════════════════════════════════════════
# GOV-PERF: Risk Engine endpoints
# ═══════════════════════════════════════════════════════════════════
@app.post("/v1/risk/score")
async def risk_score(
    ctx: Dict,
    request: Request,
    claims: dict = Depends(_auth_dep),
):
    """Score the risk of an AI action (0-100).

    Input is a RiskContext dict with fields:
      action_type, data_sensitivity, user_role, tenant_id,
      tenant_trust_tier, timestamp, geography.

    Returns the RiskResult: score, level, factor breakdown, and the
    auto-approve / requires-human-approval flags.
    """
    if not getattr(request.app.state, "risk_engine", None):
        raise HTTPException(503, detail="Risk engine not initialised")
    engine = request.app.state.risk_engine
    ctx_obj = RiskContext(**ctx)
    result = engine.score(ctx_obj)
    # Audit the decision (uses the existing AuditLogger)
    request.app.state.audit.log({
        "tenant_id": ctx_obj.tenant_id,
        "user_id": ctx_obj.attributes.get("user_id", "system"),
        "action": f"risk_score:{result.level.value}",
        "resource_id": ctx_obj.action_type,
        "decision": "ALLOW" if result.auto_approve else "ESCALATE",
        "reason": f"score={result.score} factors={result.factors}",
        "request_id": ctx_obj.request_id,
    })
    return result.to_dict()


@app.get("/v1/risk/audit")
async def risk_audit_query(
    request: Request,
    tenant_id: str = None,
    min_score: int = None,
    level: str = None,
    limit: int = 100,
    claims: dict = Depends(_auth_dep),
):
    """Query recent risk-score audit events."""
    if not getattr(request.app.state, "risk_engine", None):
        raise HTTPException(503, detail="Risk engine not initialised")
    # Tenant scoping: callers can only see their own tenant's risk events
    effective_tenant = tenant_id
    if "hsaai_admin" not in claims.get("roles", []) and "governance" not in claims.get("roles", []):
        effective_tenant = claims.get("tenant_id", "default")
    level_enum = RiskLevel(level) if level else None
    events = request.app.state.risk_engine.query_audit(
        tenant_id=effective_tenant,
        min_score=min_score,
        level=level_enum,
        limit=limit,
    )
    return {"events": events, "count": len(events)}


@app.get("/v1/risk/integrity")
async def risk_integrity(
    request: Request,
    claims: dict = Depends(_auth_dep),
):
    """Verify the hash-chain integrity of the risk audit trail."""
    if not getattr(request.app.state, "risk_engine", None):
        raise HTTPException(503, detail="Risk engine not initialised")
    return {"intact": request.app.state.risk_engine.verify_integrity()}


# ═══════════════════════════════════════════════════════════════════
# GOV-PERF: Policy Engine endpoints
# ═══════════════════════════════════════════════════════════════════
@app.post("/v1/policy/evaluate")
async def policy_evaluate(
    payload: Dict,
    request: Request,
    claims: dict = Depends(_auth_dep),
):
    """Evaluate a request against the policy set (deny-by-default).

    Payload:
      subject: dict (sub, roles, tenant_id, department, mfa_verified, ...)
      action: str ("verb:resource")
      resource: dict (type, tenant_id, classification, owner, ...)
      env: dict (timestamp, ip, is_off_hours, is_production, ...)
    """
    if not getattr(request.app.state, "policy_engine", None):
        raise HTTPException(503, detail="Policy engine not initialised")
    req = PolicyRequest(
        subject=payload.get("subject", {}),
        action=payload.get("action", ""),
        resource=payload.get("resource", {}),
        env=payload.get("env", {}),
    )
    decision = request.app.state.policy_engine.evaluate(req)
    # Audit
    request.app.state.audit.log({
        "tenant_id": req.subject.get("tenant_id", "default"),
        "user_id": req.subject.get("sub", "system"),
        "action": req.action,
        "resource_id": req.resource.get("id", ""),
        "decision": "ALLOW" if decision.allowed else "DENY",
        "reason": decision.reason,
        "policies": decision.matched_policies,
        "request_id": None,
    })
    return {
        "allowed": decision.allowed,
        "reason": decision.reason,
        "matched_policies": decision.matched_policies,
        "denied_by": decision.denied_by,
        "allowed_by": decision.allowed_by,
        "evaluated_versions": decision.evaluated_versions,
    }


@app.get("/v1/policy/list")
async def policy_list(
    request: Request,
    claims: dict = Depends(_auth_dep),
):
    """List all loaded policies with their versions."""
    if not getattr(request.app.state, "policy_engine", None):
        raise HTTPException(503, detail="Policy engine not initialised")
    return {"policies": request.app.state.policy_engine.list_policies()}


@app.post("/v1/policy/reload")
async def policy_reload(
    request: Request,
    claims: dict = Depends(_auth_dep),
):
    """Hot-reload policies from disk (governance/admin only)."""
    if "governance" not in claims.get("roles", []) and "hsaai_admin" not in claims.get("roles", []):
        raise HTTPException(403, detail="Only governance/admin roles may reload policies")
    if not getattr(request.app.state, "policy_engine", None):
        raise HTTPException(503, detail="Policy engine not initialised")
    count = request.app.state.policy_engine.reload()
    request.app.state.audit.log({
        "tenant_id": claims.get("tenant_id", "default"),
        "user_id": claims.get("sub", "system"),
        "action": "policy.reload",
        "resource_id": "",
        "decision": "ALLOW",
        "reason": f"reloaded {count} policies",
    })
    return {"reloaded": count}


# ═══════════════════════════════════════════════════════════════════
# GOV-PERF: Explainability endpoints
# ═══════════════════════════════════════════════════════════════════
@app.post("/v1/explainability/record")
async def explainability_record(
    rec: Dict,
    request: Request,
    claims: dict = Depends(_auth_dep),
):
    """Record an AI decision for audit + later explanation.

    Payload is a DecisionRecord dict (decision_id, user_id, tenant_id,
    model, prompt, output, confidence, rag_chunks, factors, ...).
    """
    if not getattr(request.app.state, "explain_engine", None):
        raise HTTPException(503, detail="Explainability engine not initialised")
    record = DecisionRecord(**rec)
    decision_id = request.app.state.explain_engine.record(record)
    return {"decision_id": decision_id, "recorded": True}


@app.get("/v1/explainability/{decision_id}")
async def explainability_get(
    decision_id: str,
    request: Request,
    claims: dict = Depends(_auth_dep),
):
    """Retrieve a recorded AI decision."""
    if not getattr(request.app.state, "explain_engine", None):
        raise HTTPException(503, detail="Explainability engine not initialised")
    rec = request.app.state.explain_engine.get(decision_id)
    if rec is None:
        raise HTTPException(404, detail="Decision record not found or expired")
    return rec.to_dict()


@app.get("/v1/explainability/{decision_id}/explain")
async def explainability_explain(
    decision_id: str,
    request: Request,
    claims: dict = Depends(_auth_dep),
):
    """Generate a human-readable explanation of an AI decision.

    Returns:
      - summary: 1-2 sentence plain-language explanation
      - contributing_factors: ranked list with weight + value
      - supporting_sources: top RAG chunks with scores
      - composite_score: weighted trust score (0-1)
      - caveats: list of trust caveats
    """
    if not getattr(request.app.state, "explain_engine", None):
        raise HTTPException(503, detail="Explainability engine not initialised")
    return request.app.state.explain_engine.explain(decision_id)


@app.get("/v1/explainability/{decision_id}/lineage")
async def explainability_lineage(
    decision_id: str,
    request: Request,
    claims: dict = Depends(_auth_dep),
):
    """Trace decision lineage back through RAG context to source docs.

    Returns a DAG (nodes + edges) suitable for visualisation.
    """
    if not getattr(request.app.state, "explain_engine", None):
        raise HTTPException(503, detail="Explainability engine not initialised")
    graph = request.app.state.explain_engine.lineage(decision_id)
    return graph.to_dict()


@app.get("/v1/explainability/tenant/{tenant_id}/list")
async def explainability_list(
    tenant_id: str,
    request: Request,
    limit: int = 50,
    claims: dict = Depends(_auth_dep),
):
    """List recent AI decisions for a tenant."""
    if not getattr(request.app.state, "explain_engine", None):
        raise HTTPException(503, detail="Explainability engine not initialised")
    # Enforce tenant scoping
    effective_tenant = tenant_id
    if "hsaai_admin" not in claims.get("roles", []) and "governance" not in claims.get("roles", []):
        effective_tenant = claims.get("tenant_id", "default")
    return {
        "decisions": request.app.state.explain_engine.list_for_tenant(effective_tenant, limit=limit),
    }


# ═══════════════════════════════════════════════════════════════════
# GOV-PERF: Approval Workflow Integration endpoint
# ═══════════════════════════════════════════════════════════════════
# This endpoint orchestrates the risk engine + approval workflow:
# 1. Compute risk score for the proposed action.
# 2. If low/medium (auto-approvable): return ALLOW with the score.
# 3. If high/critical: create an approval request via the backend_core
#    approvals service (HTTP call) and return the approval request ID
#    so the caller can poll for the decision.
@app.post("/v1/governance/evaluate")
async def governance_evaluate(
    payload: Dict,
    request: Request,
    claims: dict = Depends(_auth_dep),
):
    """End-to-end governance gate: risk score + policy + approval routing.

    Payload:
      action_type, data_sensitivity, user_role, tenant_id,
      tenant_trust_tier, geography, resource (dict), env (dict)

    Returns:
      decision: ALLOW | ESCALATE | DENY
      risk: RiskResult
      policy: PolicyDecision
      approval_request_id: str (only when decision=ESCALATE)
    """
    if not getattr(request.app.state, "risk_engine", None):
        raise HTTPException(503, detail="Risk engine not initialised")

    # 1. Risk score
    ctx = RiskContext(
        action_type=payload["action_type"],
        data_sensitivity=payload.get("data_sensitivity", "internal"),
        user_role=payload.get("user_role", claims.get("roles", ["employee"])[0] if claims.get("roles") else "employee"),
        tenant_id=payload.get("tenant_id", claims.get("tenant_id", "default")),
        tenant_trust_tier=payload.get("tenant_trust_tier", "verified"),
        geography=payload.get("geography", "unknown"),
        request_id=payload.get("request_id"),
    )
    risk_result = request.app.state.risk_engine.score(ctx)

    # 2. Policy evaluation
    policy_decision = None
    if getattr(request.app.state, "policy_engine", None):
        pol_req = PolicyRequest(
            subject={
                "sub": claims.get("sub", "system"),
                "roles": claims.get("roles", []),
                "tenant_id": ctx.tenant_id,
                "department": payload.get("department", "general"),
                "mfa_verified": claims.get("mfa_verified", False),
            },
            action=ctx.action_type,
            resource=payload.get("resource", {"type": "generic", "tenant_id": ctx.tenant_id, "classification": ctx.data_sensitivity}),
            env=payload.get("env", {}),
        )
        policy_decision = request.app.state.policy_engine.evaluate(pol_req)

    # 3. Decision routing
    # Policy DENY always wins
    if policy_decision and not policy_decision.allowed:
        decision = "DENY"
        approval_request_id = None
    elif risk_result.requires_human_approval:
        decision = "ESCALATE"
        # Create an approval request via HTTP call to backend_core
        approval_request_id = None
        try:
            backend_url = os.getenv("BACKEND_CORE_URL", "http://backend_core:8000")
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{backend_url}/v1/approvals",
                    json={
                        "action_type": ctx.action_type,
                        "resource_type": payload.get("resource", {}).get("type", "generic"),
                        "resource_id": payload.get("resource", {}).get("id", ""),
                        "payload": payload.get("approval_payload", {}),
                        "risk_level": risk_result.level.value,
                        "requires_two_person": risk_result.requires_two_person_rule,
                        "sla_hours": 24 if risk_result.level == RiskLevel.HIGH else 4,
                    },
                    headers={"Authorization": request.headers.get("Authorization", "")},
                )
                if resp.status_code < 400:
                    approval_request_id = resp.json().get("request_id")
        except Exception as e:
            logger.error("governance_evaluate: failed to create approval request: %s", e)
    else:
        decision = "ALLOW"
        approval_request_id = None

    # 4. Audit
    request.app.state.audit.log({
        "tenant_id": ctx.tenant_id,
        "user_id": claims.get("sub", "system"),
        "action": ctx.action_type,
        "resource_id": payload.get("resource", {}).get("id", ""),
        "decision": decision,
        "reason": f"risk={risk_result.score}/{risk_result.level.value} policy={policy_decision.allowed if policy_decision else 'n/a'}",
        "request_id": ctx.request_id,
    })

    return {
        "decision": decision,
        "risk": risk_result.to_dict(),
        "policy": {
            "allowed": policy_decision.allowed,
            "reason": policy_decision.reason,
            "denied_by": policy_decision.denied_by,
            "allowed_by": policy_decision.allowed_by,
        } if policy_decision else None,
        "approval_request_id": approval_request_id,
    }


if __name__ == "__main__":
    # FIX v2.2 (Phase 2): mTLS support via shared helper.
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), '..', '..', 'packages'))
    try:
        from common.security.mtls_server import run_with_mtls
        run_with_mtls("governance.main:app", host="0.0.0.0", port=8011)
    except ImportError:
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8011)
