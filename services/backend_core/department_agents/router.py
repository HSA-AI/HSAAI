from __future__ import annotations

import json
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from backend_core.db.database import SessionLocal
from backend_core.db.models import DepartmentAgent, DepartmentAgentRun
from backend_core.department_agents.schemas import DepartmentAgentCreate, DepartmentAgentUpdate, DepartmentAgentOut, AgentRouteRequest
from backend_core.department_agents.service import list_agents, resolve_department_agent
from backend_core.security.rbac import require_permission, get_current_claims

router = APIRouter(prefix="/department-agents", tags=["Department Agents"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def _out(agent) -> dict:
    if isinstance(agent, DepartmentAgent):
        return {
            "id": agent.id,
            "key": agent.key,
            "name": agent.name,
            "department": agent.department,
            "description": agent.description,
            "system_prompt": agent.system_prompt,
            "allowed_roles": json.loads(agent.allowed_roles_json or "[]"),
            "knowledge_scopes": json.loads(agent.knowledge_scopes_json or "[]"),
            "escalation_target": agent.escalation_target,
            "priority": agent.priority,
            "enabled": agent.enabled,
            "tenant_id": agent.tenant_id,
            "workspace_id": agent.workspace_id,
        }
    return {
        "id": None,
        "key": agent.key,
        "name": agent.name,
        "department": agent.department,
        "description": (agent.metadata or {}).get("description", ""),
        "system_prompt": agent.system_prompt,
        "allowed_roles": agent.allowed_roles,
        "knowledge_scopes": agent.knowledge_scopes,
        "escalation_target": (agent.metadata or {}).get("escalation_target", ""),
        "priority": (agent.metadata or {}).get("priority", 100),
        "enabled": agent.enabled,
        "tenant_id": "default",
        "workspace_id": "default",
    }

@router.get("", dependencies=[Depends(require_permission("agents:read"))])
def get_agents(db: Session = Depends(get_db), claims: dict = Depends(get_current_claims)):
    return [_out(a) for a in list_agents(db, tenant_id=claims.get("tenant_id", "default"), workspace_id=claims.get("workspace_id", "default"))]

@router.post("", dependencies=[Depends(require_permission("agents:admin"))])
def create_agent(payload: DepartmentAgentCreate, db: Session = Depends(get_db), claims: dict = Depends(get_current_claims)):
    existing = db.query(DepartmentAgent).filter(
        DepartmentAgent.key == payload.key,
        DepartmentAgent.tenant_id == claims.get("tenant_id", "default"),
        DepartmentAgent.workspace_id == claims.get("workspace_id", "default"),
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Agent key already exists in this tenant/workspace")
    row = DepartmentAgent(
        key=payload.key,
        name=payload.name,
        department=payload.department,
        description=payload.description,
        system_prompt=payload.system_prompt,
        allowed_roles_json=json.dumps(payload.allowed_roles, ensure_ascii=False),
        knowledge_scopes_json=json.dumps(payload.knowledge_scopes, ensure_ascii=False),
        keywords_json="[]",
        escalation_target=payload.escalation_target,
        priority=payload.priority,
        enabled=payload.enabled,
        tenant_id=claims.get("tenant_id", "default"),
        workspace_id=claims.get("workspace_id", "default"),
        created_by=claims.get("sub", "system"),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _out(row)

@router.patch("/{agent_id}", dependencies=[Depends(require_permission("agents:admin"))])
def update_agent(agent_id: int, payload: DepartmentAgentUpdate, db: Session = Depends(get_db), claims: dict = Depends(get_current_claims)):
    row = db.query(DepartmentAgent).filter(DepartmentAgent.id == agent_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Agent not found")
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        if key == "allowed_roles":
            row.allowed_roles_json = json.dumps(value or [], ensure_ascii=False)
        elif key == "knowledge_scopes":
            row.knowledge_scopes_json = json.dumps(value or [], ensure_ascii=False)
        else:
            setattr(row, key, value)
    row.updated_by = claims.get("sub", "system")
    db.commit()
    db.refresh(row)
    return _out(row)

@router.delete("/{agent_id}", dependencies=[Depends(require_permission("agents:admin"))])
def delete_agent(agent_id: int, db: Session = Depends(get_db)):
    row = db.query(DepartmentAgent).filter(DepartmentAgent.id == agent_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Agent not found")
    db.delete(row)
    db.commit()
    return {"deleted": True, "agent_id": agent_id}

@router.post("/route", dependencies=[Depends(require_permission("agents:read"))])
def route_message(payload: AgentRouteRequest, db: Session = Depends(get_db), claims: dict = Depends(get_current_claims)):
    merged_claims = dict(claims)
    if payload.user_roles:
        merged_claims["roles"] = payload.user_roles
    if payload.department:
        merged_claims["department"] = payload.department
    agent = resolve_department_agent(payload.message, merged_claims, db, tenant_id=payload.tenant_id or claims.get("tenant_id", "default"), workspace_id=payload.workspace_id or claims.get("workspace_id", "default"))
    return {
        "matched": agent.key != "general" and not agent.reason.startswith("blocked"),
        "agent_key": agent.key,
        "agent_name": agent.name,
        "department": agent.department,
        "score": agent.score,
        "reason": agent.reason,
        "allowed": not agent.reason.startswith("blocked"),
        "fallback_agent": "general",
        "metadata": agent.metadata or {},
    }

@router.get("/analytics", dependencies=[Depends(require_permission("analytics:read"))])
def analytics(db: Session = Depends(get_db), claims: dict = Depends(get_current_claims)):
    rows = db.query(DepartmentAgentRun).filter(
        DepartmentAgentRun.tenant_id == claims.get("tenant_id", "default"),
        DepartmentAgentRun.workspace_id == claims.get("workspace_id", "default"),
    ).order_by(DepartmentAgentRun.created_at.desc()).limit(200).all()
    totals: dict[str, int] = {}
    for row in rows:
        totals[row.agent_key] = totals.get(row.agent_key, 0) + 1
    return {"total_runs": len(rows), "by_agent": totals, "recent": [{"agent_key": r.agent_key, "department": r.department, "actor": r.actor, "score": r.score, "success": r.success} for r in rows[:20]]}
