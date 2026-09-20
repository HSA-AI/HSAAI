from typing import Literal
from common.security.request_policy import verified_scope
from common.auth.service_auth import _extract_roles
"""
HSAAI Approval Workflow Router (v2.0)
=====================================

Endpoints for human-in-the-loop approvals. Adds SLA + escalation +
two-person-rule endpoints on top of v1's basic create/decide/list.
"""
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException
from backend_core.db.database import get_db
from backend_core.security.rbac import require_permission, get_current_claims
from .service import (
    create_approval, decide_approval, cancel_approval,
    check_sla_breaches, get_sla_status, list_approvals, get_approval,
    DEFAULT_SLA_HOURS,
)

router = APIRouter(prefix="/v1/approvals", tags=["Human-in-the-Loop"])


def _scope(claims):
    try:
        tenant, workspace = verified_scope(claims)
        user = claims.get("sub")
        if not isinstance(user, str) or not user.strip():
            raise ValueError("Verified subject required")
        return tenant, workspace, user
    except (ValueError, TypeError):
        raise HTTPException(status_code=403, detail="Verified scope required")


def _scoped_request(db, request_id, claims):
    tenant, workspace, _ = _scope(claims)
    row = get_approval(db, request_id)
    if row is None or (row["tenant_id"], row["workspace_id"]) != (tenant, workspace):
        raise HTTPException(status_code=404, detail="Approval request not found")
    return row


# ═══════════════════════════════════════════════════════════════════
# Schemas
# ═══════════════════════════════════════════════════════════════════
class ApprovalCreateIn(BaseModel):
    action_type: str
    resource_type: str = "generic"
    resource_id: str = ""
    payload: dict = {}
    risk_level: Literal["low", "medium", "high", "critical"] = "medium"           # low|medium|high|critical
    requires_two_person: bool = False    # True for critical-risk actions
    sla_hours: int = Field(default=DEFAULT_SLA_HOURS, ge=1, le=168)


class ApprovalDecisionIn(BaseModel):
    approved: bool
    reason: str = ""


class ApprovalCancelIn(BaseModel):
    reason: str = ""


# ═══════════════════════════════════════════════════════════════════
# Endpoints
# ═══════════════════════════════════════════════════════════════════
@router.post("", dependencies=[Depends(require_permission("approvals:create"))])
async def request_approval(
    payload: ApprovalCreateIn,
    claims: dict = Depends(get_current_claims),
    db=Depends(get_db),
):
    """Create a new approval request.

    For critical-risk actions, set `requires_two_person=True` to enforce
    the two-person rule: two distinct approvers (neither of whom is the
    requester) must approve before the action is released.
    """
    tenant, workspace, user = _scope(claims)
    row = await create_approval(
        db,
        action_type=payload.action_type,
        resource_type=payload.resource_type,
        resource_id=payload.resource_id,
        requester=user,
        payload=payload.payload,
        tenant_id=tenant,
        workspace_id=workspace,
        risk_level=payload.risk_level,
        requires_two_person=payload.requires_two_person,
        sla_hours=payload.sla_hours,
    )
    return {
        "request_id": row.request_id,
        "status": row.status,
        "sla_hours": payload.sla_hours,
        "requires_two_person": row.requires_two_person,
    }


@router.get("", dependencies=[Depends(require_permission("approvals:read"))])
def approvals(
    status: str | None = None,
    limit: int = 200,
    claims: dict = Depends(get_current_claims),
    db=Depends(get_db),
):
    """List approval requests for the caller's tenant."""
    tenant, workspace, _ = _scope(claims)
    return {"items": list_approvals(db, tenant, status=status, limit=max(1, min(limit, 200)), workspace_id=workspace)}


@router.get("/{request_id}", dependencies=[Depends(require_permission("approvals:read"))])
def approval_detail(request_id: str, claims: dict = Depends(get_current_claims), db=Depends(get_db)):
    """Get a single approval request."""
    return _scoped_request(db, request_id, claims)


@router.post("/{request_id}/decision", dependencies=[Depends(require_permission("approvals:decide"))])
def decide(
    request_id: str,
    payload: ApprovalDecisionIn,
    claims: dict = Depends(get_current_claims),
    db=Depends(get_db),
):
    """Approve or reject a request.

    For two-person-rule requests:
      - First approval transitions `pending_first_approval` → `pending_second_approval`.
      - Second approval (from a different user) transitions → `approved`.
    Any rejection immediately transitions to `rejected`.
    """
    _scoped_request(db, request_id, claims)
    try:
        row = decide_approval(
            db,
            request_id=request_id,
            approver=claims.get("sub", "system"),
            approved=payload.approved,
            reason=payload.reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "request_id": row.request_id,
        "status": row.status,
        "decided_at": row.decided_at,
    }


@router.post("/{request_id}/cancel", dependencies=[Depends(require_permission("approvals:create"))])
def cancel(
    request_id: str,
    payload: ApprovalCancelIn,
    claims: dict = Depends(get_current_claims),
    db=Depends(get_db),
):
    """Cancel a pending approval request (requester or admin only)."""
    _scoped_request(db, request_id, claims)
    try:
        row = cancel_approval(
            db,
            request_id=request_id,
            actor=claims["sub"],
            allow_admin="hsaai_admin" in _extract_roles(claims),
            reason=payload.reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"request_id": row.request_id, "status": row.status}


@router.get("/{request_id}/sla", dependencies=[Depends(require_permission("approvals:read"))])
def sla_status(request_id: str, claims: dict = Depends(get_current_claims), db=Depends(get_db)):
    """Get SLA status for an approval request."""
    _scoped_request(db, request_id, claims)
    try:
        return get_sla_status(db, request_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/sla/check", dependencies=[Depends(require_permission("approvals:decide"))])
def trigger_sla_check(claims: dict = Depends(get_current_claims), db=Depends(get_db)):
    """Manually trigger an SLA breach check.

    Normally invoked by a periodic scheduler, but exposed here for
    ops/admins to force an escalation sweep on demand.
    """
    tenant, workspace, _ = _scope(claims)
    escalated = check_sla_breaches(db, tenant_id=tenant, workspace_id=workspace)
    return {
        "checked": True,
        "escalated_count": len(escalated),
        "escalated_ids": [r.request_id for r in escalated],
    }
