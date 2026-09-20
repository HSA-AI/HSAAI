"""
HSAAI Safety Layer — Runtime Safety Controls (Phase 11)
=========================================================
Operational alignment: runtime controls that prevent harm even when
the alignment layer fails. Implements severity classification, approval
routing, circuit breakers, and kill switches.

Severity classification:
    1 - Catastrophic: irreversible harm → two-person approval
    2 - Serious: reversible harm → one-person approval
    3 - Moderate: side effects → logged, no approval
    4 - Informational: no side effects → unconstrained
"""
import os
import json
import time
import logging
import threading
from typing import Dict, List, Optional, Callable, Awaitable, Any
from enum import IntEnum
from dataclasses import dataclass, field, asdict

import redis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hsaai.safety")


class Severity(IntEnum):
    INFO = 4       # No side effects (read, compute)
    MODERATE = 3   # Side effects (API call, file write)
    SERIOUS = 2    # Reversible harm (email, config change)
    CATASTROPHIC = 1  # Irreversible harm (delete data, large trade)


@dataclass
class ApprovalRequest:
    """Request for human approval of a high-severity action."""
    request_id: str
    agent_id: str
    tenant_id: str
    user_id: str
    tool_name: str
    tool_args: Dict
    severity: Severity
    justification: str
    created_at: float = field(default_factory=time.time)
    approved_by: List[str] = field(default_factory=list)
    required_approvals: int = 1
    status: str = "pending"  # pending, approved, rejected, expired


class DistributedKillSwitch:
    """
    FIX B-13: Distributed kill switch backed by Redis with pub/sub.

    Previously the kill switch was a per-instance boolean (`SafetyLayer.kill_switch_active`),
    which meant that in multi-replica deployments only the replica that received
    the `activate_kill_switch()` call actually halted agents — other replicas
    kept serving requests. This class stores the kill switch state in Redis so
    every replica reads the same value, and uses Redis pub/sub to propagate
    activation/deactivation to all replicas in near-real-time.

    Backward compatibility: if Redis is unavailable, the kill switch falls back
    to in-memory-only operation and logs a warning, because crashing the safety
    layer would be worse than isolated operation. Callers that still read
    `safety_layer.kill_switch_active` continue to work via a property on
    SafetyLayer that delegates to this class.
    """

    CHANNEL = "hsaai:safety:kill_switch"
    KEY = "kill_switch:active"
    REASON_KEY = "kill_switch:reason"
    ACTIVATED_BY_KEY = "kill_switch:activated_by"
    ACTIVATED_AT_KEY = "kill_switch:activated_at"

    def __init__(self, redis_client: Optional[Any] = None):
        self.redis = redis_client
        self._local_active: bool = False  # in-memory fallback / pub/sub cache
        self._local_meta: Dict[str, Any] = {}
        self._lock = threading.Lock()
        self._listener_thread: Optional[threading.Thread] = None
        self._pubsub = None
        if self.redis is not None:
            # Seed local cache from Redis so a freshly-started replica picks
            # up an already-active kill switch immediately.
            try:
                self._local_active = self.redis.get(self.KEY) == "1"
            except Exception as e:
                logger.warning(
                    f"DistributedKillSwitch: initial Redis read failed ({e}); "
                    f"starting with kill_switch=inactive locally."
                )
            self._start_listener()
        else:
            logger.warning(
                "DistributedKillSwitch: Redis unavailable — operating in "
                "in-memory-only mode. Kill switch changes will NOT propagate "
                "to other replicas."
            )

    def _start_listener(self) -> None:
        """Start a background daemon thread that listens for pub/sub updates."""
        def _listen() -> None:
            try:
                self._pubsub = self.redis.pubsub()
                self._pubsub.subscribe(self.CHANNEL)
                for message in self._pubsub.listen():
                    if message.get("type") != "message":
                        continue
                    try:
                        payload = json.loads(message["data"])
                    except Exception:
                        continue
                    with self._lock:
                        self._local_active = bool(payload.get("active", False))
                        self._local_meta = payload
            except Exception as e:
                logger.warning(
                    f"DistributedKillSwitch: pub/sub listener failed: {e}. "
                    f"Falling back to per-call Redis reads."
                )
        try:
            self._listener_thread = threading.Thread(
                target=_listen, name="kill-switch-listener", daemon=True
            )
            self._listener_thread.start()
        except Exception as e:
            logger.warning(
                f"DistributedKillSwitch: could not start listener thread: {e}"
            )

    def _publish(self, payload: Dict[str, Any]) -> None:
        """Publish a state-change notification to all replicas."""
        if self.redis is None:
            return
        try:
            self.redis.publish(self.CHANNEL, json.dumps(payload))
        except Exception as e:
            logger.warning(f"DistributedKillSwitch: publish failed: {e}")

    def is_active(self) -> bool:
        """Return True if the kill switch is currently active."""
        if self.redis is not None:
            # Trust the pub/sub cache, but verify with a Redis read to handle
            # the case where the listener missed a message (e.g., listener
            # thread died or this replica just started before the cache seeded).
            try:
                active = self.redis.get(self.KEY) == "1"
                with self._lock:
                    if active != self._local_active:
                        self._local_active = active
                return active
            except Exception as e:
                logger.warning(
                    f"DistributedKillSwitch: Redis read failed ({e}); "
                    f"using cached in-memory value ({self._local_active})."
                )
        with self._lock:
            return self._local_active

    def get_meta(self) -> Dict[str, Any]:
        """Return metadata about the current kill switch state."""
        with self._lock:
            return dict(self._local_meta)

    def activate(self, reason: str, activated_by: str) -> None:
        """Activate the kill switch and notify all replicas."""
        payload = {
            "active": True,
            "reason": reason,
            "activated_by": activated_by,
            "activated_at": time.time(),
        }
        with self._lock:
            self._local_active = True
            self._local_meta = payload
        if self.redis is not None:
            try:
                pipe = self.redis.pipeline()
                pipe.set(self.KEY, "1")
                pipe.set(self.REASON_KEY, reason)
                pipe.set(self.ACTIVATED_BY_KEY, activated_by)
                pipe.set(self.ACTIVATED_AT_KEY, str(payload["activated_at"]))
                pipe.execute()
                self._publish(payload)
            except Exception as e:
                logger.warning(
                    f"DistributedKillSwitch: Redis write failed ({e}); "
                    f"activated in-memory only — OTHER REPLICAS WILL NOT SEE THIS."
                )
        else:
            logger.warning(
                "DistributedKillSwitch: Redis unavailable — kill switch "
                "activated in-memory only on this replica. Other replicas "
                "will NOT halt agent actions."
            )

    def deactivate(self, deactivated_by: str) -> None:
        """Deactivate the kill switch and notify all replicas."""
        payload = {
            "active": False,
            "deactivated_by": deactivated_by,
            "deactivated_at": time.time(),
        }
        with self._lock:
            self._local_active = False
            self._local_meta = payload
        if self.redis is not None:
            try:
                pipe = self.redis.pipeline()
                pipe.set(self.KEY, "0")
                pipe.delete(self.REASON_KEY, self.ACTIVATED_BY_KEY, self.ACTIVATED_AT_KEY)
                pipe.execute()
                self._publish(payload)
            except Exception as e:
                logger.warning(
                    f"DistributedKillSwitch: Redis write failed ({e}); "
                    f"deactivated in-memory only — OTHER REPLICAS MAY STILL BE HALTED."
                )
        else:
            logger.warning(
                "DistributedKillSwitch: Redis unavailable — kill switch "
                "deactivated in-memory only on this replica. Other replicas "
                "may remain halted."
            )


class SafetyLayer:
    """
    Runtime safety layer. Every agent tool call must pass through this layer.
    """

    def __init__(self, redis_url: str = None):
        redis_url = redis_url or os.getenv("SAFETY_REDIS_URL", "redis://redis:6379/3")
        try:
            self.redis = redis.from_url(redis_url, decode_responses=True)
            self.redis.ping()
            logger.info("Safety layer: Redis connected")
        except Exception as e:
            logger.error(f"Safety layer: Redis unavailable: {e}")
            self.redis = None

        # Tool severity registry
        self.tool_severity: Dict[str, Severity] = {}
        self._register_default_tools()

        # Circuit breaker state
        self.agent_actions: Dict[str, List[float]] = {}  # agent_id → [timestamps]

        # FIX B-13: Kill switch state is now distributed via Redis so that
        # activation/deactivation propagates to every replica. Backward
        # compatibility: the `kill_switch_active` attribute is exposed as a
        # property below that delegates to this distributed switch, so callers
        # that read `safety_layer.kill_switch_active` continue to work.
        self.kill_switch = DistributedKillSwitch(self.redis)

    def _register_default_tools(self):
        """Register default tool severity classifications."""
        # Catastrophic tools (two-person approval)
        for tool in ["delete_production_data", "execute_wire_transfer",
                     "modify_payroll", "approve_large_contract"]:
            self.tool_severity[tool] = Severity.CATASTROPHIC

        # Serious tools (one-person approval)
        for tool in ["send_external_email", "modify_config",
                     "publish_document", "modify_permissions"]:
            self.tool_severity[tool] = Severity.SERIOUS

        # Moderate tools (logged, no approval)
        for tool in ["call_external_api", "write_file", "create_record",
                     "web_search", "rag_query"]:
            self.tool_severity[tool] = Severity.MODERATE

        # Informational tools (unconstrained)
        for tool in ["read_data", "compute", "search_internal",
                     "get_status", "list_records"]:
            self.tool_severity[tool] = Severity.INFO

    def register_tool(self, tool_name: str, severity: Severity):
        """Register a custom tool with its severity."""
        self.tool_severity[tool_name] = severity
        logger.info(f"Registered tool '{tool_name}' → severity {severity.name}")

    @property
    def kill_switch_active(self) -> bool:
        """FIX B-13: Backward-compatible accessor that delegates to the distributed kill switch."""
        return self.kill_switch.is_active()

    async def check_tool(
        self,
        agent_id: str,
        tenant_id: str,
        user_id: str,
        tool_name: str,
        tool_args: Dict,
        justification: str = "",
    ) -> Dict:
        """
        Check whether a tool call is permitted.
        Returns: {allowed, severity, requires_approval, request_id?}
        """
        # 1. Kill switch check (FIX B-13: distributed across replicas via Redis)
        if self.kill_switch.is_active():
            meta = self.kill_switch.get_meta()
            reason = meta.get("reason") or "Kill switch is active — all agent actions halted"
            return {
                "allowed": False,
                "reason": reason,
                "severity": None,
            }

        severity = self.tool_severity.get(tool_name, Severity.MODERATE)

        # 2. Circuit breaker check
        if not self._circuit_breaker_ok(agent_id, severity):
            return {
                "allowed": False,
                "reason": f"Circuit breaker tripped for agent {agent_id}",
                "severity": severity.name,
            }

        # 3. Severity-based routing
        if severity == Severity.INFO:
            # No restrictions
            return {"allowed": True, "severity": severity.name,
                    "requires_approval": False}

        elif severity == Severity.MODERATE:
            # Logged but no approval
            self._log_action(agent_id, tenant_id, user_id, tool_name, tool_args, severity)
            return {"allowed": True, "severity": severity.name,
                    "requires_approval": False}

        elif severity == Severity.SERIOUS:
            # Requires one-person approval
            req = await self._create_approval_request(
                agent_id, tenant_id, user_id, tool_name, tool_args,
                severity, justification, required_approvals=1
            )
            return {"allowed": False, "severity": severity.name,
                    "requires_approval": True, "request_id": req.request_id,
                    "required_approvals": 1}

        elif severity == Severity.CATASTROPHIC:
            # Requires two-person approval
            req = await self._create_approval_request(
                agent_id, tenant_id, user_id, tool_name, tool_args,
                severity, justification, required_approvals=2
            )
            return {"allowed": False, "severity": severity.name,
                    "requires_approval": True, "request_id": req.request_id,
                    "required_approvals": 2}

        return {"allowed": False, "reason": "Unknown severity"}

    def _circuit_breaker_ok(self, agent_id: str, severity: Severity) -> bool:
        """
        Circuit breaker: if agent makes too many high-severity actions
        in a time window, pause it.
        """
        now = time.time()
        window = 3600  # 1 hour
        max_high_severity = 10  # max 10 serious+ actions per hour

        if agent_id not in self.agent_actions:
            self.agent_actions[agent_id] = []

        # Filter to actions in last hour
        recent = [t for t in self.agent_actions[agent_id] if now - t < window]
        self.agent_actions[agent_id] = recent

        if severity <= Severity.SERIOUS:
            if len(recent) >= max_high_severity:
                logger.warning(
                    f"Circuit breaker tripped for agent {agent_id}: "
                    f"{len(recent)} high-severity actions in last hour"
                )
                return False
            recent.append(now)

        return True

    async def _create_approval_request(
        self, agent_id, tenant_id, user_id, tool_name,
        tool_args, severity, justification, required_approvals
    ) -> ApprovalRequest:
        """Create an approval request and store it."""
        import uuid
        req = ApprovalRequest(
            request_id=str(uuid.uuid4()),
            agent_id=agent_id, tenant_id=tenant_id, user_id=user_id,
            tool_name=tool_name, tool_args=tool_args,
            severity=severity, justification=justification,
            required_approvals=required_approvals,
        )
        if self.redis:
            self.redis.setex(
                f"approval:{req.request_id}",
                86400,  # 24-hour TTL
                json.dumps(asdict(req)),
            )
        logger.info(f"Approval request {req.request_id} created "
                    f"(severity={severity.name}, required={required_approvals})")
        return req

    async def approve_request(self, request_id: str, approver_id: str) -> Dict:
        """Approve an approval request. Returns {approved, remaining_approvals}."""
        if not self.redis:
            return {"approved": False, "reason": "Redis unavailable"}

        data = self.redis.get(f"approval:{request_id}")
        if not data:
            return {"approved": False, "reason": "Request not found or expired"}

        req = json.loads(data)
        if req["status"] != "pending":
            return {"approved": False, "reason": f"Request already {req['status']}"}

        if approver_id in req["approved_by"]:
            return {"approved": False, "reason": "Already approved by this user"}

        req["approved_by"].append(approver_id)
        if len(req["approved_by"]) >= req["required_approvals"]:
            req["status"] = "approved"
            self.redis.setex(f"approval:{request_id}", 86400, json.dumps(req))
            logger.info(f"Request {request_id} fully approved by {req['approved_by']}")
            return {"approved": True, "remaining_approvals": 0}
        else:
            self.redis.setex(f"approval:{request_id}", 86400, json.dumps(req))
            remaining = req["required_approvals"] - len(req["approved_by"])
            return {"approved": False, "remaining_approvals": remaining}

    async def reject_request(self, request_id: str, rejecter_id: str, reason: str) -> Dict:
        """Reject an approval request."""
        if not self.redis:
            return {"rejected": False, "reason": "Redis unavailable"}
        data = self.redis.get(f"approval:{request_id}")
        if not data:
            return {"rejected": False, "reason": "Request not found"}
        req = json.loads(data)
        req["status"] = "rejected"
        req["rejection_reason"] = reason
        req["rejected_by"] = rejecter_id
        self.redis.setex(f"approval:{request_id}", 86400, json.dumps(req))
        logger.info(f"Request {request_id} rejected by {rejecter_id}: {reason}")
        return {"rejected": True}

    def _log_action(self, agent_id, tenant_id, user_id, tool_name, tool_args, severity):
        """Log a tool call for audit trail."""
        log_entry = {
            "timestamp": time.time(),
            "agent_id": agent_id, "tenant_id": tenant_id, "user_id": user_id,
            "tool_name": tool_name, "tool_args": tool_args,
            "severity": severity.name,
        }
        if self.redis:
            self.redis.lpush("audit:tool_calls", json.dumps(log_entry))
            self.redis.ltrim("audit:tool_calls", 0, 99999)  # keep last 100k
        logger.info(f"Tool call: {tool_name} by agent {agent_id} (severity={severity.name})")

    def activate_kill_switch(self, reason: str, activated_by: str):
        """Activate the kill switch — halts all agent actions immediately.

        FIX B-13: Delegates to the DistributedKillSwitch so activation
        propagates to every replica via Redis (with pub/sub notification).
        """
        # FIX B-13: Distributed activation across all replicas.
        self.kill_switch.activate(reason, activated_by)
        log_entry = {
            "timestamp": time.time(), "action": "kill_switch_activated",
            "reason": reason, "activated_by": activated_by,
        }
        if self.redis:
            self.redis.lpush("audit:safety", json.dumps(log_entry))
        logger.critical(f"🛑 KILL SWITCH ACTIVATED by {activated_by}: {reason}")

    def deactivate_kill_switch(self, deactivated_by: str):
        """Deactivate the kill switch.

        FIX B-13: Delegates to the DistributedKillSwitch so deactivation
        propagates to every replica via Redis (with pub/sub notification).
        """
        # FIX B-13: Distributed deactivation across all replicas.
        self.kill_switch.deactivate(deactivated_by)
        log_entry = {
            "timestamp": time.time(), "action": "kill_switch_deactivated",
            "deactivated_by": deactivated_by,
        }
        if self.redis:
            self.redis.lpush("audit:safety", json.dumps(log_entry))
        logger.info(f"Kill switch deactivated by {deactivated_by}")

    async def get_pending_approvals(self, tenant_id: str = None) -> List[Dict]:
        """Get pending approval requests, optionally filtered by tenant."""
        if not self.redis:
            return []
        # In production, this would use a Redis index. For now, scan.
        pending = []
        for key in self.redis.scan_iter("approval:*"):
            data = self.redis.get(key)
            if data:
                req = json.loads(data)
                if req["status"] == "pending":
                    if tenant_id is None or req["tenant_id"] == tenant_id:
                        pending.append(req)
        return pending


# Singleton
safety_layer = SafetyLayer()
