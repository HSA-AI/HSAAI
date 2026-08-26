from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any
from sqlalchemy.orm import Session

from backend_core.department_agents.catalog import DEFAULT_DEPARTMENT_AGENTS
from backend_core.db.models import DepartmentAgent, DepartmentAgentRun
from backend_core.security.rbac import has_permission

ARABIC_DIACRITICS = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]")
PUNCT = re.compile(r"[^\w\s\u0600-\u06FF]")

@dataclass
class ResolvedAgent:
    key: str
    name: str
    department: str
    system_prompt: str
    knowledge_scopes: list[str]
    allowed_roles: list[str]
    score: float
    reason: str
    enabled: bool = True
    metadata: dict[str, Any] | None = None

def normalize_arabic(text: str) -> str:
    text = (text or "").strip().lower()
    text = ARABIC_DIACRITICS.sub("", text)
    text = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    text = text.replace("ى", "ي").replace("ة", "ه")
    text = PUNCT.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()

def _json_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        loaded = json.loads(value)
        return [str(x) for x in loaded] if isinstance(loaded, list) else []
    except Exception:
        return []

def _agent_from_default(item: dict[str, Any]) -> ResolvedAgent:
    return ResolvedAgent(
        key=item["key"],
        name=item["name"],
        department=item["department"],
        system_prompt=item["system_prompt"],
        knowledge_scopes=item.get("knowledge_scopes", []),
        allowed_roles=item.get("allowed_roles", []),
        score=0.0,
        reason="default_catalog",
        metadata={"keywords": item.get("keywords", []), "priority": item.get("priority", 100), "description": item.get("description", ""), "escalation_target": item.get("escalation_target", "")},
    )

def _agent_from_model(model: DepartmentAgent) -> ResolvedAgent:
    return ResolvedAgent(
        key=model.key,
        name=model.name,
        department=model.department,
        system_prompt=model.system_prompt,
        knowledge_scopes=_json_list(model.knowledge_scopes_json),
        allowed_roles=_json_list(model.allowed_roles_json),
        score=0.0,
        reason="db_agent",
        enabled=bool(model.enabled),
        metadata={"keywords": _json_list(model.keywords_json), "priority": model.priority, "description": model.description, "escalation_target": model.escalation_target},
    )

def list_agents(db: Session | None = None, tenant_id: str = "default", workspace_id: str = "default") -> list[ResolvedAgent]:
    agents: list[ResolvedAgent] = []
    if db is not None:
        rows = db.query(DepartmentAgent).filter(
            DepartmentAgent.tenant_id == tenant_id,
            DepartmentAgent.workspace_id == workspace_id,
        ).order_by(DepartmentAgent.priority.asc()).all()
        agents.extend([_agent_from_model(row) for row in rows if row.enabled])
    existing = {a.key for a in agents}
    for item in DEFAULT_DEPARTMENT_AGENTS:
        if item["key"] not in existing:
            agents.append(_agent_from_default(item))
    return agents

def score_agent(message: str, agent: ResolvedAgent) -> tuple[float, str]:
    text = normalize_arabic(message)
    if not text:
        return 0.0, "empty"
    keywords = [normalize_arabic(x) for x in (agent.metadata or {}).get("keywords", [])]
    score = 0.0
    hits: list[str] = []
    for kw in keywords:
        if not kw:
            continue
        if text == kw:
            score += 1.0
            hits.append(f"exact:{kw}")
        elif kw in text:
            score += 0.65
            hits.append(f"contains:{kw}")
        else:
            terms = [t for t in kw.split() if len(t) > 2]
            matched = sum(1 for t in terms if t in text.split())
            if terms and matched:
                score += 0.2 * matched / len(terms)
                hits.append(f"term:{kw}")
    priority = float((agent.metadata or {}).get("priority", 100))
    score += max(0.0, (100.0 - priority) / 1000.0)
    return round(score, 4), ",".join(hits) or "no_keyword_match"

def user_can_use_agent(claims: dict[str, Any], agent: ResolvedAgent) -> bool:
    if has_permission(claims, "agents:admin") or "hsaai_admin" in claims.get("roles", []):
        return True
    allowed_roles = set(agent.allowed_roles or [])
    user_roles = set(claims.get("roles", []))
    if allowed_roles and user_roles.isdisjoint(allowed_roles):
        return False
    # Department managers should not be routed into a different restricted department unless explicitly allowed.
    if "department_manager" in user_roles:
        user_department = str(claims.get("department") or claims.get("workspace_id") or "").lower()
        if agent.department not in {"general", "knowledge_management"} and user_department and user_department not in {agent.department.lower(), "default"}:
            return False
    return True

def resolve_department_agent(
    message: str,
    claims: dict[str, Any],
    db: Session | None = None,
    tenant_id: str = "default",
    workspace_id: str = "default",
) -> ResolvedAgent:
    candidates = list_agents(db, tenant_id=tenant_id, workspace_id=workspace_id)
    best: ResolvedAgent | None = None
    for agent in candidates:
        score, reason = score_agent(message, agent)
        candidate = ResolvedAgent(**{**agent.__dict__, "score": score, "reason": reason})
        if best is None or candidate.score > best.score:
            best = candidate
    if best is None or best.score <= 0.05:
        best = ResolvedAgent(
            key="general",
            name="HSAAI Enterprise Assistant",
            department="general",
            system_prompt="أنت HSAAI Enterprise Assistant. أجب باحترافية ووضوح واعتمد على مصادر المؤسسة عند توفرها.",
            knowledge_scopes=["general"],
            allowed_roles=["hsaai_admin", "department_manager", "ai_user", "auditor"],
            score=0.0,
            reason="fallback_general",
            metadata={"keywords": [], "priority": 100},
        )
    if not user_can_use_agent(claims, best):
        return ResolvedAgent(
            key="general",
            name="HSAAI Enterprise Assistant",
            department="general",
            system_prompt="أنت HSAAI Enterprise Assistant. لا تعرض معلومات غير مصرح بها. اطلب من المستخدم التواصل مع المسؤول إذا احتاج صلاحية إضافية.",
            knowledge_scopes=["general"],
            allowed_roles=["hsaai_admin", "department_manager", "ai_user", "auditor"],
            score=best.score,
            reason=f"blocked_by_role:{best.key}",
            metadata={"blocked_agent": best.key, "blocked_department": best.department},
        )
    return best

def record_agent_run(db: Session, *, agent: ResolvedAgent, actor: str, message: str, tenant_id: str, workspace_id: str, success: bool = True, latency_ms: int = 0) -> None:
    db.add(DepartmentAgentRun(
        agent_key=agent.key,
        department=agent.department,
        actor=actor,
        message=message[:2000],
        score=float(agent.score),
        success=success,
        latency_ms=latency_ms,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
    ))
    db.commit()
