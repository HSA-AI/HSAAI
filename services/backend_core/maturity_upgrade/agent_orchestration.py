from __future__ import annotations
import json, time
from dataclasses import dataclass
from typing import Any
from sqlalchemy.orm import Session
from .models import AgentInvocationLog, AgentMemoryRecord
from .schemas import AgentRouteRequest

@dataclass(frozen=True)
class AgentProfile:
    key: str
    name: str
    department: str
    roles_required: list[str]
    connectors: list[str]
    capabilities: list[str]
    keywords: list[str]

AGENTS: dict[str, AgentProfile] = {
    "hr": AgentProfile("hr", "HR Agent", "Human Resources", ["hsaai_admin", "department_manager", "ai_user"], ["successfactors", "sharepoint", "dms"], ["leave", "policies", "employees", "organization"], ["موظف", "إجازة", "دوام", "موارد", "راتب موظف", "هيكل"]),
    "finance": AgentProfile("finance", "Finance Agent", "Finance", ["hsaai_admin", "department_manager"], ["sap_s4hana", "powerbi", "data_warehouse"], ["budget", "procurement", "expenses", "sales"], ["مشتريات", "ميزانية", "مصروف", "فاتورة", "مبيعات", "مخزون", "مالي"]),
    "it": AgentProfile("it", "IT Agent", "Information Technology", ["hsaai_admin", "department_manager", "ai_user"], ["active_directory", "jira", "service_desk", "outlook_exchange"], ["support", "incidents", "access", "infrastructure"], ["دعم", "تذكرة", "سيرفر", "صلاحية", "vpn", "بريد", "جهاز"]),
    "legal": AgentProfile("legal", "Legal Agent", "Legal", ["hsaai_admin", "document_reviewer", "department_manager"], ["dms", "sharepoint"], ["contracts", "compliance", "governance"], ["عقد", "قانون", "امتثال", "حوكمة", "مخالفة"]),
    "executive": AgentProfile("executive", "Executive Agent", "Executive", ["hsaai_admin", "department_manager", "auditor"], ["sap_s4hana", "powerbi", "data_warehouse"], ["executive summaries", "kpis", "performance"], ["تقرير تنفيذي", "مؤشرات", "أداء", "إيرادات", "ملخص"]),
}

SUPERVISOR_POLICY = {
    "name": "Supervisor Agent",
    "routing_strategy": "keyword_score + department_hint + role_guard",
    "fallback_agent": "it",
    "human_review_triggers": ["financial_decision", "legal_recommendation", "access_change", "knowledge_publication"],
}

class AdvancedAgentOrchestrator:
    def route(self, db: Session, payload: AgentRouteRequest) -> dict[str, Any]:
        start = time.time(); msg = payload.message.lower(); scores: dict[str, int] = {}
        for key, profile in AGENTS.items():
            score = sum(3 for kw in profile.keywords if kw.lower() in msg)
            score += sum(1 for cap in profile.capabilities if cap.lower() in msg)
            if payload.department and payload.department.lower() in profile.department.lower(): score += 2
            scores[key] = score
        selected = max(scores, key=lambda k: scores[k]) if max(scores.values() or [0]) > 0 else "it"
        profile = AGENTS[selected]
        allowed = "hsaai_admin" in payload.roles or bool(set(payload.roles).intersection(profile.roles_required)) or not payload.roles
        decision = f"Supervisor selected {profile.name} using scores={scores}."
        plan = [
            "تحليل نية المستخدم وسياق القسم",
            f"توجيه الطلب إلى {profile.name}",
            "التحقق من صلاحيات المستخدم قبل استخدام مصادر البيانات",
            "جلب المعرفة المعتمدة فقط من RAG أو التكاملات المصرح بها",
            "تسجيل الأداء والقرار في Agent Audit Logs",
        ]
        request_id = f"agent-{int(time.time()*1000)}"
        log = AgentInvocationLog(
            request_id=request_id, user_id=payload.user_id, tenant_id=payload.tenant_id, workspace_id=payload.workspace_id,
            message=payload.message, selected_agent=selected, supervisor_decision=decision,
            confidence=min(0.99, 0.55 + scores[selected] * 0.08), required_connectors_json=json.dumps(profile.connectors),
            permission_status="allowed" if allowed else "denied", latency_ms=int((time.time()-start)*1000), success=allowed,
        )
        db.add(log)
        db.add(AgentMemoryRecord(agent_key="supervisor", memory_scope="routing", subject=request_id, content=decision, tenant_id=payload.tenant_id, workspace_id=payload.workspace_id))
        db.commit()
        return {
            "request_id": request_id,
            "supervisor_decision": decision,
            "selected_agent": selected,
            "confidence": log.confidence,
            "plan": plan,
            "required_connectors": profile.connectors,
            "permission_status": log.permission_status,
            "audit_event_id": str(log.id),
            "latency_ms": log.latency_ms,
        }

    def registry(self) -> dict[str, Any]:
        return {"supervisor": SUPERVISOR_POLICY, "agents": [profile.__dict__ for profile in AGENTS.values()]}

    def performance(self, db: Session, tenant_id: str, workspace_id: str) -> dict[str, Any]:
        rows = db.query(AgentInvocationLog).filter_by(tenant_id=tenant_id, workspace_id=workspace_id).order_by(AgentInvocationLog.id.desc()).limit(250).all()
        by_agent: dict[str, dict[str, Any]] = {}
        for r in rows:
            item = by_agent.setdefault(r.selected_agent, {"requests": 0, "success": 0, "denied": 0, "avg_latency_ms": 0})
            item["requests"] += 1; item["success"] += int(bool(r.success)); item["denied"] += int(r.permission_status == "denied"); item["avg_latency_ms"] += r.latency_ms
        for item in by_agent.values():
            item["avg_latency_ms"] = round(item["avg_latency_ms"] / max(1, item["requests"]), 2)
            item["success_rate"] = round(item["success"] / max(1, item["requests"]), 3)
        return {"agent_performance": by_agent, "recent_invocations": [{"request_id": r.request_id, "agent": r.selected_agent, "decision": r.supervisor_decision, "permission": r.permission_status, "latency_ms": r.latency_ms} for r in rows[:20]]}

agent_orchestrator = AdvancedAgentOrchestrator()
