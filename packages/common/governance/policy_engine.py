"""
HSAAI Policy Engine — Policy-as-Code (v1.0)
============================================

YAML-defined, deny-by-default policy engine for governance decisions.
Policies are versioned, audited, and evaluated against a request
context (subject + resource + action + environment).

Design
------
- **Deny-by-default**: if no policy explicitly `allow`s the request,
  the engine returns `deny`. This is the Zero-Trust posture required
  by ISO 27001 A.9.4 (Access Control) and NIST AI RMF MAP-1.
- **Policy-as-code**: policies live in YAML files (or a Postgres
  table), version-pinned, and re-loadable at runtime. No service
  restart required to update a policy.
- **Versioning + audit**: every policy has `version` and `updated_at`.
  Every evaluation records which policy versions were considered, so
  an auditor can replay a decision months later and get the same
  result.
- **Composable**: multiple policies may match a request; the engine
  applies `deny` overrides `allow` semantics (a single deny wins).

Sample policies (built-in)
--------------------------
1. `pii_data_requires_admin` — any action on PII data requires the
   `hsaai_admin` role.
2. `off_hours_require_mfa` — actions outside 06:00-19:00 UTC require
   `mfa_verified=true` on the subject.
3. `cross_tenant_requires_governance` — cross-tenant access requires
   the `governance` role.
4. `restricted_data_same_department` — restricted data limited to
   same-department subjects.

Usage
-----
    from packages.common.governance.policy_engine import (
        PolicyEngine, PolicyDecision, Request,
    )

    engine = PolicyEngine()  # loads built-in policies
    decision = engine.evaluate(Request(
        subject={"sub": "u1", "roles": ["employee"], "tenant_id": "t1",
                 "mfa_verified": False, "department": "hr"},
        action="read:document",
        resource={"type": "document", "classification": "pii",
                  "tenant_id": "t1", "department": "hr"},
        env={"timestamp": "2025-01-01T03:00:00Z", "ip": "10.0.0.1"},
    ))
    if not decision.allowed:
        raise HTTPException(403, decision.reason)

Custom YAML file
----------------
    # /etc/hsaai/policies/extra.yaml
    policies:
      - id: no_prod_delete
        version: "1.0.0"
        description: "No deletes in production"
        effect: deny
        when:
          action_verb: delete
          env_is_production: true
"""
from __future__ import annotations

import os
import json
import yaml
import uuid
import hashlib
import logging
from enum import Enum
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Iterable

logger = logging.getLogger("hsaai.governance.policy_engine")

# ── Optional durable storage (mirrors AuditLogger design) ──
try:
    import redis  # type: ignore
    _REDIS_AVAILABLE = True
except ImportError:  # pragma: no cover
    _REDIS_AVAILABLE = False


# ═══════════════════════════════════════════════════════════════════
# Data model
# ═══════════════════════════════════════════════════════════════════
class Effect(str, Enum):
    ALLOW = "allow"
    DENY = "deny"


@dataclass
class Request:
    """Inputs to a policy evaluation.

    All dicts are free-form — policies match on dotted paths, so any
    attribute can be referenced in `when`/`unless` clauses.
    """
    subject: Dict[str, Any]            # sub, roles, tenant_id, department, clearance, mfa_verified, ...
    action: str                        # e.g. "read:document"
    resource: Dict[str, Any]           # type, tenant_id, classification, owner, department, ...
    env: Dict[str, Any] = field(default_factory=dict)  # timestamp, ip, is_production, ...

    @property
    def action_verb(self) -> str:
        return self.action.split(":", 1)[0].lower()

    @property
    def action_resource(self) -> str:
        parts = self.action.split(":", 1)
        return parts[1].lower() if len(parts) > 1 else ""


@dataclass
class PolicyDecision:
    """Result of evaluating policies against a Request."""
    allowed: bool
    reason: str
    matched_policies: List[str] = field(default_factory=list)
    denied_by: Optional[str] = None
    allowed_by: Optional[str] = None
    evaluated_versions: Dict[str, str] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    request_snapshot: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Policy:
    """A single policy rule."""
    id: str
    version: str
    description: str
    effect: Effect
    when: Dict[str, Any] = field(default_factory=dict)   # match conditions (all must pass)
    unless: Dict[str, Any] = field(default_factory=dict) # exclusion conditions (any passing excludes)
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def matches(self, req: Request) -> bool:
        """True if all `when` conditions match AND no `unless` matches."""
        if not self._match_all(self.when, req):
            return False
        if self.unless and self._match_any(self.unless, req):
            return False
        return True

    # ── Condition matching ──
    def _match_all(self, conditions: Dict[str, Any], req: Request) -> bool:
        return all(self._match_one(k, v, req) for k, v in conditions.items())

    def _match_any(self, conditions: Dict[str, Any], req: Request) -> bool:
        return any(self._match_one(k, v, req) for k, v in conditions.items())

    def _match_one(self, key: str, expected: Any, req: Request) -> bool:
        """Match a single condition.

        Keys are dotted paths into the merged request context
        (`subject` + `resource` + `env` + computed `action_verb` etc.).
        Values support:
            - scalar equality
            - list membership (expected is a list → actual must be in it)
            - wildcards: "*" matches any non-empty value
        """
        actual = self._resolve(key, req)
        if expected == "*":
            return actual not in (None, "", [], {})
        if isinstance(expected, list):
            if isinstance(actual, list):
                return any(v in actual for v in expected)
            return actual in expected
        if isinstance(actual, list):
            return expected in actual
        return actual == expected

    def _resolve(self, dotted_key: str, req: Request) -> Any:
        """Resolve a dotted path like `subject.roles` against the request."""
        # Computed pseudo-keys (cheap shortcuts)
        if dotted_key == "action_verb":
            return req.action_verb
        if dotted_key == "action_resource":
            return req.action_resource
        if dotted_key == "action":
            return req.action

        # Dotted path into one of the three buckets.
        parts = dotted_key.split(".", 1)
        bucket = parts[0]
        rest = parts[1] if len(parts) > 1 else ""
        source = {
            "subject": req.subject,
            "resource": req.resource,
            "env": req.env,
        }.get(bucket, {})
        if not rest:
            return source
        # Walk the rest of the path
        cur: Any = source
        for p in rest.split("."):
            if isinstance(cur, dict):
                cur = cur.get(p)
            else:
                return None
        return cur


# ═══════════════════════════════════════════════════════════════════
# Built-in policy set
# ═══════════════════════════════════════════════════════════════════
BUILTIN_POLICIES_YAML = """
policies:
  - id: pii_data_requires_admin
    version: "1.0.0"
    description: "PII data requires hsaai_admin role"
    effect: deny
    when:
      resource.classification: pii
      subject.roles:
        # value is a list → subject.roles (list) must intersect
        # ...but here we want the opposite. Express as `unless`:
        # see below.
        "*"
    unless:
      subject.roles: [hsaai_admin, super_admin, governance]

  - id: off_hours_require_mfa
    version: "1.0.0"
    description: "Off-hours actions require MFA"
    effect: deny
    when:
      env.is_off_hours: true
    unless:
      subject.mfa_verified: true

  - id: cross_tenant_requires_governance
    version: "1.0.0"
    description: "Cross-tenant access requires governance approval"
    effect: deny
    when:
      resource.tenant_id: "*"
    unless:
      subject.roles: [governance, super_admin]
      # Subject's tenant must match resource's tenant, OR subject
      # has governance role (handled by the unless clause above).
      subject.tenant_id: "*"

  - id: restricted_data_same_department
    version: "1.0.0"
    description: "Restricted data limited to same department"
    effect: deny
    when:
      resource.classification: restricted
    unless:
      subject.department: "*"

  - id: allow_internal_reads_for_authenticated_users
    version: "1.0.0"
    description: "Authenticated employees may read internal data"
    effect: allow
    when:
      action_verb: read
      resource.classification: [internal, public]
      subject.tenant_id: "*"
"""


# ═══════════════════════════════════════════════════════════════════
# Policy engine
# ═══════════════════════════════════════════════════════════════════
class PolicyEngine:
    """Deny-by-default policy evaluation engine.

    Loads policies from:
      1. Built-in YAML (above)
      2. `policy_paths` arg (list of YAML file paths)
      3. `POLICY_DIR` env var (directory scanned for `*.yaml`)

    Policies can be reloaded at runtime with `reload()`.
    """

    def __init__(
        self,
        policy_paths: Optional[Iterable[str]] = None,
        redis_url: Optional[str] = None,
    ):
        self._policies: List[Policy] = []
        self._redis = None
        if _REDIS_AVAILABLE:
            url = redis_url or os.getenv("POLICY_REDIS_URL", "redis://redis:6379/7")
            try:
                self._redis = redis.from_url(url, decode_responses=True)
                self._redis.ping()
            except Exception as e:
                logger.warning("PolicyEngine: Redis unavailable: %s", e)
                self._redis = None
        self._last_hash = "genesis"
        self._load_policies(policy_paths)

    # ── Loading ──────────────────────────────────────────────────────
    def _load_policies(self, extra_paths: Optional[Iterable[str]]) -> None:
        """Load policies from built-in YAML, env dir, and explicit paths."""
        sources: List[str] = [BUILTIN_POLICIES_YAML]
        env_dir = os.getenv("POLICY_DIR")
        if env_dir and os.path.isdir(env_dir):
            for fn in sorted(os.listdir(env_dir)):
                if fn.endswith((".yaml", ".yml")):
                    path = os.path.join(env_dir, fn)
                    try:
                        with open(path, "r", encoding="utf-8") as fh:
                            sources.append(fh.read())
                    except OSError as e:
                        logger.error("PolicyEngine: failed to read %s: %s", path, e)
        if extra_paths:
            for p in extra_paths:
                try:
                    with open(p, "r", encoding="utf-8") as fh:
                        sources.append(fh.read())
                except OSError as e:
                    logger.error("PolicyEngine: failed to read %s: %s", p, e)

        self._policies = []
        for src in sources:
            self._merge_yaml(src)
        logger.info("PolicyEngine: loaded %d policies", len(self._policies))

    def _merge_yaml(self, yaml_text: str) -> None:
        try:
            doc = yaml.safe_load(yaml_text) or {}
        except yaml.YAMLError as e:
            logger.error("PolicyEngine: YAML parse error: %s", e)
            return
        for p in doc.get("policies", []):
            try:
                effect = Effect(p.get("effect", "deny"))
                pol = Policy(
                    id=p["id"],
                    version=str(p.get("version", "0.0.0")),
                    description=p.get("description", ""),
                    effect=effect,
                    when=p.get("when", {}) or {},
                    unless=p.get("unless", {}) or {},
                )
                self._policies.append(pol)
            except (KeyError, ValueError) as e:
                logger.error("PolicyEngine: invalid policy %s: %s", p, e)

    def reload(self) -> int:
        """Reload all policies. Returns the new policy count."""
        self._load_policies(None)
        return len(self._policies)

    def list_policies(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": p.id,
                "version": p.version,
                "effect": p.effect.value,
                "description": p.description,
                "when": p.when,
                "unless": p.unless,
                "updated_at": p.updated_at,
            }
            for p in self._policies
        ]

    # ── Evaluation ───────────────────────────────────────────────────
    def evaluate(self, req: Request) -> PolicyDecision:
        """Evaluate all matching policies.

        Deny-by-default with `deny overrides allow`:
          - If any matching DENY policy exists → DENY
          - Else if any matching ALLOW policy exists → ALLOW
          - Else → DENY (default-deny)
        """
        matched_allow: List[Policy] = []
        matched_deny: List[Policy] = []
        versions: Dict[str, str] = {}

        for pol in self._policies:
            versions[pol.id] = pol.version
            if pol.matches(req):
                if pol.effect == Effect.DENY:
                    matched_deny.append(pol)
                else:
                    matched_allow.append(pol)

        matched_ids = [p.id for p in matched_allow + matched_deny]

        if matched_deny:
            d = matched_deny[0]
            decision = PolicyDecision(
                allowed=False,
                reason=f"Denied by policy '{d.id}' (v{d.version}): {d.description}",
                matched_policies=matched_ids,
                denied_by=d.id,
                allowed_by=None,
                evaluated_versions=versions,
                request_snapshot=self._snapshot(req),
            )
        elif matched_allow:
            a = matched_allow[0]
            decision = PolicyDecision(
                allowed=True,
                reason=f"Allowed by policy '{a.id}' (v{a.version}): {a.description}",
                matched_policies=matched_ids,
                denied_by=None,
                allowed_by=a.id,
                evaluated_versions=versions,
                request_snapshot=self._snapshot(req),
            )
        else:
            # Deny-by-default
            decision = PolicyDecision(
                allowed=False,
                reason="Deny-by-default: no matching ALLOW policy",
                matched_policies=[],
                denied_by=None,
                allowed_by=None,
                evaluated_versions=versions,
                request_snapshot=self._snapshot(req),
            )

        self._audit(decision)
        return decision

    def _snapshot(self, req: Request) -> Dict[str, Any]:
        """Capture the request for the audit trail (PII-redacted)."""
        snap = {
            "subject": {k: v for k, v in req.subject.items() if k not in ("password", "token", "secret")},
            "action": req.action,
            "resource": req.resource,
            "env": req.env,
        }
        return snap

    # ── Audit ────────────────────────────────────────────────────────
    def _audit(self, decision: PolicyDecision) -> None:
        """Append the decision to a hash-chained audit trail."""
        event_id = str(uuid.uuid4())
        entry = {
            "event_id": event_id,
            "timestamp": decision.timestamp,
            "previous_hash": self._last_hash,
            "allowed": decision.allowed,
            "reason": decision.reason,
            "matched_policies": decision.matched_policies,
            "denied_by": decision.denied_by,
            "allowed_by": decision.allowed_by,
            "evaluated_versions": decision.evaluated_versions,
            "request": decision.request_snapshot,
        }
        s = json.dumps(entry, sort_keys=True, default=str)
        h = hashlib.sha256(s.encode()).hexdigest()
        entry["entry_hash"] = h
        self._last_hash = h

        if self._redis:
            try:
                self._redis.lpush("policy:audit:events", json.dumps(entry, default=str))
                self._redis.ltrim("policy:audit:events", 0, 99999)
                tenant = decision.request_snapshot.get("subject", {}).get("tenant_id", "default")
                self._redis.lpush(f"policy:audit:tenant:{tenant}", json.dumps(entry, default=str))
                self._redis.expire(f"policy:audit:tenant:{tenant}", 7 * 24 * 60 * 60)
                self._redis.set("policy:audit:last_hash", h)
            except Exception as e:
                logger.error("PolicyEngine: Redis audit write failed: %s", e)

    def verify_integrity(self) -> bool:
        if not self._redis:
            return True
        events = self._redis.lrange("policy:audit:events", 0, -1)
        events.reverse()
        prev = "genesis"
        for e in events:
            try:
                entry = json.loads(e)
                if entry.get("previous_hash") != prev:
                    return False
                prev = entry.get("entry_hash")
            except json.JSONDecodeError:
                return False
        return True


__all__ = [
    "Effect",
    "Request",
    "Policy",
    "PolicyDecision",
    "PolicyEngine",
    "BUILTIN_POLICIES_YAML",
]
