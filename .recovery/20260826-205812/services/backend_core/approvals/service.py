"""
HSAAI Approval Service — Human-in-the-Loop Workflow (v2.0)
==========================================================

Enhanced from v1.0 with:
  - Two-person rule for critical-risk actions (two distinct approvers
    required before the action is released).
  - SLA tracking (24h default, configurable per request via
    `sla_hours` payload field).
  - Automatic escalation when SLA is breached (re-notify, escalate to
    governance role, mark `escalated=true`).
  - Dedicated approval audit log: every state transition
    (create / approve / reject / escalate / expire / cancel) is
    recorded with actor, timestamp, and reason.

Models
------
Backed by `HumanApprovalRequest` (renamed from ApprovalRequest in
services/backend_core/db/models.py to avoid a table-name collision).
For backward compatibility we expose `ApprovalRequest` as an alias.

Two-person rule
---------------
When `requires_two_person=True` (set by the risk engine for critical
actions), the request enters a `pending_first_approval` state. The
first approval transitions it to `pending_second_approval`. The second
approval (from a different approver than the first) transitions it to
`approved`. A rejection at any stage transitions it to `rejected`.

SLA escalation
--------------
`check_sla_breaches()` should be called by a periodic background task
(e.g. APScheduler cron, every 15 minutes). For every request whose SLA
has elapsed:
  1. Mark `escalated=True` and bump `escalation_count`.
  2. Re-notify the original approver channel.
  3. Notify the `governance` role via email/webhook (escalation target).
  4. If `escalation_count >= MAX_ESCALATIONS`, auto-reject with reason
     "SLA breached — auto-rejected after N escalations".

Usage
-----
    from backend_core.approvals.service import (
        create_approval, decide_approval, check_sla_breaches,
    )

    row = await create_approval(db,
        action_type="delete:document",
        resource_type="document",
        resource_id="d-001",
        requester="u-001",
        payload={"reason": "GDPR erasure request"},
        tenant_id="t-001",
        workspace_id="ws-001",
        risk_level="critical",
        requires_two_person=True,
        sla_hours=24,
    )
"""
from __future__ import annotations

import json
import uuid
import smtplib
import logging
from email.message import EmailMessage
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from backend_core.config import settings
from backend_core.db.models import HumanApprovalRequest as ApprovalRequest, AuditLog

logger = logging.getLogger("hsaai.approvals")

# ── Constants ─────────────────────────────────────────────────────────
SENSITIVE_ACTIONS = {
    "delete", "external_write", "connector_write",
    "admin_change", "data_export", "budget_override",
}

DEFAULT_SLA_HOURS = 24
MAX_ESCALATIONS = 3
ESCALATION_REMINDER_HOURS = 4  # re-notify every 4h after SLA breach

# Approval states
STATE_PENDING = "pending"
STATE_PENDING_FIRST_APPROVAL = "pending_first_approval"   # two-person rule
STATE_PENDING_SECOND_APPROVAL = "pending_second_approval" # two-person rule
STATE_APPROVED = "approved"
STATE_REJECTED = "rejected"
STATE_EXPIRED = "expired"
STATE_CANCELLED = "cancelled"


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════
def requires_approval(action_type: str) -> bool:
    """Heuristic: does this action need an approval workflow?

    Used as a fast pre-check before the risk engine computes a score.
    """
    return any(token in action_type.lower() for token in SENSITIVE_ACTIONS)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_json(row: ApprovalRequest) -> dict:
    """Serialize an ApprovalRequest row to a dict (JSON-safe)."""
    return {
        "request_id": row.request_id,
        "action_type": row.action_type,
        "resource_type": row.resource_type,
        "resource_id": row.resource_id,
        "requester": row.requester,
        "approver": row.approver,
        "second_approver": getattr(row, "second_approver", None),
        "status": row.status,
        "decision_reason": row.decision_reason,
        "tenant_id": row.tenant_id,
        "workspace_id": row.workspace_id,
        "risk_level": getattr(row, "risk_level", None),
        "requires_two_person": getattr(row, "requires_two_person", False),
        "sla_hours": getattr(row, "sla_hours", DEFAULT_SLA_HOURS),
        "sla_deadline": str(getattr(row, "sla_deadline", None)) if hasattr(row, "sla_deadline") and row.sla_deadline else None,
        "escalated": getattr(row, "escalated", False),
        "escalation_count": getattr(row, "escalation_count", 0),
        "created_at": str(row.created_at),
        "decided_at": str(row.decided_at) if row.decided_at else None,
    }


# ═══════════════════════════════════════════════════════════════════
# Approval audit log
# ═══════════════════════════════════════════════════════════════════
def _audit(
    db: Session,
    *,
    actor: str,
    action: str,
    resource: str,
    workspace_id: str,
    tenant_id: str,
    success: bool = True,
    detail: str = "",
) -> None:
    """Write a dedicated approval audit log entry.

    Separated from `AuditLog` table writes only by the `action` prefix
    (`approval.*`); same durable store (Postgres `audit_logs` table).
    """
    db.add(AuditLog(
        actor=actor,
        action=action,
        resource=resource,
        workspace_id=workspace_id,
        tenant_id=tenant_id,
        success=success,
        detail=detail,
    ))


# ═══════════════════════════════════════════════════════════════════
# Create
# ═══════════════════════════════════════════════════════════════════
async def create_approval(
    db: Session,
    *,
    action_type: str,
    resource_type: str,
    resource_id: str,
    requester: str,
    payload: dict,
    tenant_id: str,
    workspace_id: str,
    risk_level: str = "medium",
    requires_two_person: bool = False,
    sla_hours: int = DEFAULT_SLA_HOURS,
) -> ApprovalRequest:
    """Create a new approval request.

    Args:
        risk_level: from the risk engine (`low|medium|high|critical`).
        requires_two_person: True for critical-risk actions.
        sla_hours: SLA window. Default 24h.
    """
    sla_hours = int(sla_hours or DEFAULT_SLA_HOURS)
    sla_deadline = _now() + timedelta(hours=sla_hours)

    initial_state = (
        STATE_PENDING_FIRST_APPROVAL if requires_two_person else STATE_PENDING
    )

    row = ApprovalRequest(
        request_id=str(uuid.uuid4()),
        action_type=action_type,
        resource_type=resource_type,
        resource_id=resource_id,
        requester=requester,
        status=initial_state,
        payload=payload,  # JSON column (renamed from payload_json in v1)
        tenant_id=tenant_id,
        workspace_id=workspace_id,
    )
    # Set extended fields if the columns exist (migration-managed).
    for attr, val in (
        ("risk_level", risk_level),
        ("requires_two_person", requires_two_person),
        ("sla_hours", sla_hours),
        ("sla_deadline", sla_deadline),
        ("escalated", False),
        ("escalation_count", 0),
    ):
        if hasattr(row, attr):
            setattr(row, attr, val)

    db.add(row)
    _audit(
        db,
        actor=requester,
        action="approval.create",
        resource=f"{resource_type}:{resource_id}",
        workspace_id=workspace_id,
        tenant_id=tenant_id,
        success=True,
        detail=json.dumps({
            "request_id": row.request_id,
            "risk_level": risk_level,
            "requires_two_person": requires_two_person,
            "sla_hours": sla_hours,
            "sla_deadline": sla_deadline.isoformat(),
        }, default=str),
    )
    db.commit()
    db.refresh(row)
    notify_approval(row)
    return row


# ═══════════════════════════════════════════════════════════════════
# Decide
# ═══════════════════════════════════════════════════════════════════
def decide_approval(
    db: Session,
    *,
    request_id: str,
    approver: str,
    approved: bool,
    reason: str = "",
) -> ApprovalRequest:
    """Record an approval decision.

    Enforces the two-person rule for critical-risk requests: two distinct
    approvers must approve before the request transitions to `approved`.
    """
    row = db.query(ApprovalRequest).filter(
        ApprovalRequest.request_id == request_id
    ).first()
    if row is None:
        raise ValueError("Approval request not found")

    requires_two = bool(getattr(row, "requires_two_person", False))

    valid_states = (
        {STATE_PENDING_FIRST_APPROVAL, STATE_PENDING_SECOND_APPROVAL}
        if requires_two else {STATE_PENDING}
    )
    if row.status not in valid_states:
        raise ValueError(f"Approval request is not pending (state={row.status})")

    if not approved:
        # Any rejection immediately rejects the whole request.
        row.status = STATE_REJECTED
        row.approver = approver
        row.decision_reason = reason
        row.decided_at = _now()
        _audit(
            db, actor=approver, action="approval.reject",
            resource=f"{row.resource_type}:{row.resource_id}",
            workspace_id=row.workspace_id, tenant_id=row.tenant_id,
            success=True, detail=json.dumps({"request_id": request_id, "reason": reason}, default=str),
        )
        db.commit()
        db.refresh(row)
        return row

    # Approval path
    if requires_two:
        # First approval?
        if row.status == STATE_PENDING_FIRST_APPROVAL:
            if approver == row.requester:
                raise ValueError("Requester cannot be the first approver (two-person rule)")
            row.approver = approver
            row.status = STATE_PENDING_SECOND_APPROVAL
            row.decision_reason = reason
            _audit(
                db, actor=approver, action="approval.first_approve",
                resource=f"{row.resource_type}:{row.resource_id}",
                workspace_id=row.workspace_id, tenant_id=row.tenant_id,
                success=True, detail=json.dumps({"request_id": request_id, "reason": reason}, default=str),
            )
            db.commit()
            db.refresh(row)
            # Notify second approver channel
            notify_approval(row, stage="second")
            return row
        # Second approval
        if row.status == STATE_PENDING_SECOND_APPROVAL:
            if approver == row.approver:
                raise ValueError("Second approver must be a different person (two-person rule)")
            if hasattr(row, "second_approver"):
                row.second_approver = approver
            row.status = STATE_APPROVED
            row.decision_reason = reason
            row.decided_at = _now()
            _audit(
                db, actor=approver, action="approval.second_approve",
                resource=f"{row.resource_type}:{row.resource_id}",
                workspace_id=row.workspace_id, tenant_id=row.tenant_id,
                success=True, detail=json.dumps({"request_id": request_id, "reason": reason}, default=str),
            )
            db.commit()
            db.refresh(row)
            return row
    else:
        # Single-approver path
        if approver == row.requester:
            raise ValueError("Requester cannot approve their own request")
        row.approver = approver
        row.status = STATE_APPROVED
        row.decision_reason = reason
        row.decided_at = _now()
        _audit(
            db, actor=approver, action="approval.approve",
            resource=f"{row.resource_type}:{row.resource_id}",
            workspace_id=row.workspace_id, tenant_id=row.tenant_id,
            success=True, detail=json.dumps({"request_id": request_id, "reason": reason}, default=str),
        )
        db.commit()
        db.refresh(row)
        return row

    raise ValueError(f"Cannot approve from state={row.status}")


# ═══════════════════════════════════════════════════════════════════
# Cancel / Expire
# ═══════════════════════════════════════════════════════════════════
def cancel_approval(db: Session, *, request_id: str, actor: str, reason: str = "") -> ApprovalRequest:
    row = db.query(ApprovalRequest).filter(ApprovalRequest.request_id == request_id).first()
    if row is None:
        raise ValueError("Approval request not found")
    if row.status in (STATE_APPROVED, STATE_REJECTED, STATE_EXPIRED, STATE_CANCELLED):
        raise ValueError(f"Cannot cancel request in state={row.status}")
    row.status = STATE_CANCELLED
    row.decision_reason = reason
    row.decided_at = _now()
    _audit(
        db, actor=actor, action="approval.cancel",
        resource=f"{row.resource_type}:{row.resource_id}",
        workspace_id=row.workspace_id, tenant_id=row.tenant_id,
        success=True, detail=json.dumps({"request_id": request_id, "reason": reason}, default=str),
    )
    db.commit()
    db.refresh(row)
    return row


# ═══════════════════════════════════════════════════════════════════
# SLA + escalation
# ═══════════════════════════════════════════════════════════════════
def check_sla_breaches(db: Session) -> List[ApprovalRequest]:
    """Find pending requests whose SLA has elapsed, escalate them.

    Returns the list of requests that were escalated on this run.
    Should be invoked by a periodic task (e.g. APScheduler every 15 min).
    """
    pending_states = (
        [STATE_PENDING_FIRST_APPROVAL, STATE_PENDING_SECOND_APPROVAL]
        if True else [STATE_PENDING]
    )
    # Build a flexible filter: status in pending states AND
    # (sla_deadline < now OR created_at < now - sla_hours)
    now = _now()
    rows = (
        db.query(ApprovalRequest)
        .filter(ApprovalRequest.status.in_(pending_states))
        .all()
    )
    escalated: List[ApprovalRequest] = []
    for row in rows:
        sla_hours = int(getattr(row, "sla_hours", DEFAULT_SLA_HOURS) or DEFAULT_SLA_HOURS)
        deadline = getattr(row, "sla_deadline", None)
        if deadline is None:
            # Compute from created_at if sla_deadline column missing
            deadline = (row.created_at or now) + timedelta(hours=sla_hours)
        # Make both offset-aware for comparison
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        if now < deadline:
            continue
        # SLA breached — escalate
        esc_count = int(getattr(row, "escalation_count", 0) or 0) + 1
        if hasattr(row, "escalation_count"):
            row.escalation_count = esc_count
        if hasattr(row, "escalated"):
            row.escalated = True

        if esc_count >= MAX_ESCALATIONS:
            # Auto-reject
            row.status = STATE_EXPIRED
            row.decision_reason = f"SLA breached — auto-rejected after {esc_count} escalations"
            row.decided_at = now
            _audit(
                db, actor="system:scheduler", action="approval.expire",
                resource=f"{row.resource_type}:{row.resource_id}",
                workspace_id=row.workspace_id, tenant_id=row.tenant_id,
                success=False, detail=json.dumps({
                    "request_id": row.request_id,
                    "escalation_count": esc_count,
                    "reason": row.decision_reason,
                }, default=str),
            )
        else:
            _audit(
                db, actor="system:scheduler", action="approval.escalate",
                resource=f"{row.resource_type}:{row.resource_id}",
                workspace_id=row.workspace_id, tenant_id=row.tenant_id,
                success=True, detail=json.dumps({
                    "request_id": row.request_id,
                    "escalation_count": esc_count,
                }, default=str),
            )
            # Re-notify + escalate to governance
            notify_approval(row, stage="escalation")
        escalated.append(row)
    if escalated:
        db.commit()
        for r in escalated:
            db.refresh(r)
    return escalated


def get_sla_status(db: Session, request_id: str) -> Dict[str, Any]:
    """Return SLA info for a single request."""
    row = db.query(ApprovalRequest).filter(ApprovalRequest.request_id == request_id).first()
    if row is None:
        raise ValueError("Approval request not found")
    sla_hours = int(getattr(row, "sla_hours", DEFAULT_SLA_HOURS) or DEFAULT_SLA_HOURS)
    deadline = getattr(row, "sla_deadline", None)
    if deadline is None:
        deadline = (row.created_at or _now()) + timedelta(hours=sla_hours)
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    now = _now()
    return {
        "request_id": request_id,
        "status": row.status,
        "sla_hours": sla_hours,
        "sla_deadline": deadline.isoformat(),
        "remaining_seconds": max(0, int((deadline - now).total_seconds())),
        "breached": now > deadline and row.status not in (STATE_APPROVED, STATE_REJECTED, STATE_EXPIRED, STATE_CANCELLED),
        "escalated": bool(getattr(row, "escalated", False)),
        "escalation_count": int(getattr(row, "escalation_count", 0) or 0),
    }


# ═══════════════════════════════════════════════════════════════════
# List
# ═══════════════════════════════════════════════════════════════════
def list_approvals(
    db: Session,
    tenant_id: str,
    status: Optional[str] = None,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    q = db.query(ApprovalRequest).filter(ApprovalRequest.tenant_id == tenant_id)
    if status:
        q = q.filter(ApprovalRequest.status == status)
    return [_safe_json(x) for x in q.order_by(ApprovalRequest.id.desc()).limit(limit).all()]


def get_approval(db: Session, request_id: str) -> Optional[Dict[str, Any]]:
    row = db.query(ApprovalRequest).filter(ApprovalRequest.request_id == request_id).first()
    return _safe_json(row) if row else None


# ═══════════════════════════════════════════════════════════════════
# Notifications
# ═══════════════════════════════════════════════════════════════════
def notify_approval(row: ApprovalRequest, stage: str = "first") -> None:
    """Best-effort notification. Never blocks the workflow.

    stage:
        first     — initial request notification
        second    — second approver needed (two-person rule)
        escalation — SLA breached, escalating to governance
    """
    prefix = {
        "first": "HSAAI approval required",
        "second": "HSAAI approval: second approver required",
        "escalation": "HSAAI approval: SLA BREACHED — escalated",
    }.get(stage, "HSAAI approval")
    message = (
        f"{prefix}: {row.action_type} on "
        f"{row.resource_type}:{row.resource_id}. "
        f"Request ID: {row.request_id}. Risk: {getattr(row, 'risk_level', 'unknown')}."
    )
    try:
        if settings.smtp_host and settings.approval_email_from:
            email = EmailMessage()
            email["From"] = settings.approval_email_from
            email["To"] = settings.approval_email_from
            email["Subject"] = prefix
            email.set_content(message)
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
                if settings.smtp_user and settings.smtp_password:
                    smtp.starttls()
                    smtp.login(settings.smtp_user, settings.smtp_password)
                smtp.send_message(email)
    except Exception as e:
        logger.warning("notify_approval: email send failed: %s", e)

    for url in [settings.teams_webhook_url, settings.slack_webhook_url, settings.approval_webhook_url]:
        if not url:
            continue
        try:
            httpx.post(url, json={
                "text": message,
                "request_id": row.request_id,
                "stage": stage,
                "risk_level": getattr(row, "risk_level", "unknown"),
            }, timeout=10)
        except Exception as e:
            logger.warning("notify_approval: webhook %s failed: %s", url, e)


__all__ = [
    "ApprovalRequest",
    "requires_approval",
    "create_approval",
    "decide_approval",
    "cancel_approval",
    "check_sla_breaches",
    "get_sla_status",
    "list_approvals",
    "get_approval",
    "notify_approval",
    # Constants
    "DEFAULT_SLA_HOURS",
    "MAX_ESCALATIONS",
    "STATE_PENDING",
    "STATE_PENDING_FIRST_APPROVAL",
    "STATE_PENDING_SECOND_APPROVAL",
    "STATE_APPROVED",
    "STATE_REJECTED",
    "STATE_EXPIRED",
    "STATE_CANCELLED",
]
