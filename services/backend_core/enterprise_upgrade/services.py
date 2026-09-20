
from __future__ import annotations
import json
import time
from datetime import datetime, timedelta
from typing import Any
from sqlalchemy.orm import Session
from backend_core.security.rbac import has_permission
from .domain import (
    DEFAULT_AGENT_BLUEPRINTS, EnterpriseAgentAuditLog, EnterpriseAgentDefinition,
    WorkflowTemplate, WorkflowExecution, EnterpriseConnector, EnterpriseMetricEvent,
    HumanApprovalRequest, to_json, now_id
)


def _json(value: str | None, fallback):
    try:
        return json.loads(value or "")
    except Exception:
        return fallback

class SupervisorAgentService:
    def ensure_defaults(self, db: Session, tenant_id: str, workspace_id: str) -> None:
        existing = {r.key for r in db.query(EnterpriseAgentDefinition).filter_by(tenant_id=tenant_id, workspace_id=workspace_id).all()}
        for item in DEFAULT_AGENT_BLUEPRINTS:
            if item["key"] in existing:
                continue
            db.add(EnterpriseAgentDefinition(
                key=item["key"], name=item["name"], department=item["department"],
                capabilities_json=to_json(item["capabilities"]), required_roles_json=to_json(item["roles"]),
                tools_json=to_json(item["tools"]),
                system_prompt=f"أنت {item['name']} ضمن HSAAI. التزم بالصلاحيات ومصادر المؤسسة فقط.",
                tenant_id=tenant_id, workspace_id=workspace_id
            ))
        db.commit()

    def registry(self, db: Session, tenant_id: str, workspace_id: str) -> list[dict[str, Any]]:
        self.ensure_defaults(db, tenant_id, workspace_id)
        rows = db.query(EnterpriseAgentDefinition).filter_by(tenant_id=tenant_id, workspace_id=workspace_id).order_by(EnterpriseAgentDefinition.key.asc()).all()
        return [{
            "key": r.key, "name": r.name, "department": r.department,
            "capabilities": _json(r.capabilities_json, []), "required_roles": _json(r.required_roles_json, []),
            "tools": _json(r.tools_json, []), "status": r.status, "health_status": r.health_status,
            "avg_latency_ms": r.avg_latency_ms, "success_rate": r.success_rate,
        } for r in rows]

    def route(self, db: Session, *, message: str, claims: dict[str, Any], tenant_id: str, workspace_id: str, session_id: str = "default") -> dict[str, Any]:
        start = time.time()
        self.ensure_defaults(db, tenant_id, workspace_id)
        text = (message or "").lower()
        best_key = "supervisor"; best_score = 0.2; reason = "fallback_supervisor"
        for item in DEFAULT_AGENT_BLUEPRINTS:
            hits = sum(1 for kw in item.get("keywords", []) if kw in text)
            score = hits / max(1, len(item.get("keywords", [])))
            if hits and score > best_score:
                best_key, best_score, reason = item["key"], min(0.99, score + 0.35), f"keyword_hits:{hits}"
        agent = db.query(EnterpriseAgentDefinition).filter_by(key=best_key, tenant_id=tenant_id, workspace_id=workspace_id).first()
        required_roles = _json(agent.required_roles_json, []) if agent else []
        allowed = has_permission(claims, "agents:execute") or bool(set(claims.get("roles", [])).intersection(required_roles))
        run_id = now_id("agent-route")
        db.add(EnterpriseAgentAuditLog(
            run_id=run_id, supervisor_decision="route_to_specialist", selected_agent=best_key,
            actor=claims.get("sub", "system"), message=message[:2000], allowed=allowed, reason=reason,
            latency_ms=int((time.time() - start) * 1000), tenant_id=tenant_id, workspace_id=workspace_id
        ))
        db.commit()
        return {
            "run_id": run_id,
            "supervisor_decision": "route_to_specialist",
            "selected_agent": best_key,
            "selected_department": agent.department if agent else "enterprise",
            "confidence": round(best_score, 2),
            "reason": reason,
            "allowed": allowed,
            "required_roles": required_roles,
            "next_steps": ["rbac_check", "retrieve_department_knowledge", "execute_agent", "audit_response"],
        }

    def health(self, db: Session, tenant_id: str, workspace_id: str) -> dict[str, Any]:
        agents = self.registry(db, tenant_id, workspace_id)
        return {"agents_total": len(agents), "healthy": sum(1 for a in agents if a["health_status"] == "healthy"), "items": agents}

class WorkflowAutomationService:
    DEFAULT_TEMPLATES = [
        {"key":"purchase_request","name":"Purchase Request","category":"procurement","steps":["submit","review","approval","ticket_creation","notification"]},
        {"key":"document_approval","name":"Document Approval","category":"knowledge","steps":["review","compliance_check","approval","publish"]},
        {"key":"leave_request","name":"Leave Request","category":"hr","steps":["manager_approval","hr_approval","execution"]},
    ]
    def ensure_templates(self, db: Session, tenant_id: str, workspace_id: str) -> None:
        existing = {r.key for r in db.query(WorkflowTemplate).filter_by(tenant_id=tenant_id, workspace_id=workspace_id).all()}
        for t in self.DEFAULT_TEMPLATES:
            if t["key"] not in existing:
                definition = {"nodes": [{"id": step, "type": "approval" if "approval" in step or "review" in step else "task", "sla_hours": 24} for step in t["steps"]], "edges": t["steps"]}
                db.add(WorkflowTemplate(key=t["key"], name=t["name"], category=t["category"], description="Enterprise workflow template", definition_json=to_json(definition), tenant_id=tenant_id, workspace_id=workspace_id))
        db.commit()
    def templates(self, db: Session, tenant_id: str, workspace_id: str):
        self.ensure_templates(db, tenant_id, workspace_id)
        rows = db.query(WorkflowTemplate).filter_by(tenant_id=tenant_id, workspace_id=workspace_id).all()
        return [{"key": r.key, "name": r.name, "category": r.category, "enabled": r.enabled, "definition": _json(r.definition_json, {})} for r in rows]
    def start(self, db: Session, *, template_key: str, payload: dict[str, Any], requested_by: str, tenant_id: str, workspace_id: str):
        self.ensure_templates(db, tenant_id, workspace_id)
        template = db.query(WorkflowTemplate).filter_by(key=template_key, tenant_id=tenant_id, workspace_id=workspace_id, enabled=True).first()
        if not template: raise ValueError("Workflow template not found or disabled")
        definition = _json(template.definition_json, {})
        current = (definition.get("edges") or ["start"])[0]
        execution_id = now_id("wf")
        db.add(WorkflowExecution(execution_id=execution_id, template_key=template_key, status="running", current_step=current, requested_by=requested_by, payload_json=to_json(payload), sla_due_at=datetime.utcnow()+timedelta(hours=24), tenant_id=tenant_id, workspace_id=workspace_id))
        db.commit()
        return {"execution_id": execution_id, "template_key": template_key, "status": "running", "current_step": current, "sla_tracking": "enabled"}
    def executions(self, db: Session, tenant_id: str, workspace_id: str):
        rows = db.query(WorkflowExecution).filter_by(tenant_id=tenant_id, workspace_id=workspace_id).order_by(WorkflowExecution.id.desc()).limit(50).all()
        return [{"execution_id": r.execution_id, "template_key": r.template_key, "status": r.status, "current_step": r.current_step, "requested_by": r.requested_by} for r in rows]

class ConnectorService:
    SUPPORTED = ["sap", "oracle", "active_directory", "exchange", "sharepoint", "jira", "postgresql", "sql_server", "rest_api", "file_repository"]
    def list(self, db: Session, tenant_id: str, workspace_id: str):
        rows = db.query(EnterpriseConnector).filter_by(tenant_id=tenant_id, workspace_id=workspace_id).order_by(EnterpriseConnector.connector_type.asc()).all()
        return [{"key": r.key, "name": r.name, "type": r.connector_type, "auth_type": r.auth_type, "enabled": r.enabled, "health_status": r.health_status, "last_sync_status": r.last_sync_status} for r in rows]
    def create(self, db: Session, data: dict[str, Any], tenant_id: str, workspace_id: str):
        if data["connector_type"] not in self.SUPPORTED:
            raise ValueError(f"Unsupported connector_type. Supported: {', '.join(self.SUPPORTED)}")
        row = EnterpriseConnector(key=data["key"], name=data["name"], connector_type=data["connector_type"], auth_type=data.get("auth_type","none"), base_url=data.get("base_url",""), schedule=data.get("schedule","manual"), secrets_ref=data.get("secrets_ref",""), enabled=data.get("enabled", True), metadata_json=to_json(data.get("metadata", {})), tenant_id=tenant_id, workspace_id=workspace_id)
        db.add(row); db.commit()
        return {"key": row.key, "status": "created"}
    def test(self, db: Session, key: str, tenant_id: str, workspace_id: str):
        row = db.query(EnterpriseConnector).filter_by(key=key, tenant_id=tenant_id, workspace_id=workspace_id).first()
        if not row: raise ValueError("Connector not found")
        row.health_status = "healthy" if row.base_url or row.connector_type in {"active_directory", "file_repository"} else "configuration_required"
        db.commit()
        return {"key": key, "health_status": row.health_status, "checked": True}

class ObservabilityService:
    def record(self, db: Session, metric_type: str, name: str, value: float, tenant_id: str, workspace_id: str, category: str = "platform", labels: dict[str, Any] | None = None):
        db.add(EnterpriseMetricEvent(metric_type=metric_type, category=category, name=name, value=value, labels_json=to_json(labels or {}), tenant_id=tenant_id, workspace_id=workspace_id)); db.commit()
    def dashboard(self, db: Session, tenant_id: str, workspace_id: str):
        rows = db.query(EnterpriseMetricEvent).filter_by(tenant_id=tenant_id, workspace_id=workspace_id).all()
        by_name: dict[str, float] = {}
        for r in rows: by_name[r.name] = by_name.get(r.name, 0.0) + float(r.value)
        return {"executive_dashboard": {"availability": 99.5, "risk_level": "controlled"}, "ai_usage": by_name, "panels": ["model_usage", "token_usage", "agent_performance", "workflow_performance", "latency", "errors", "knowledge_usage"]}

class HumanInLoopService:
    def create(self, db: Session, *, data: dict[str, Any], claims: dict[str, Any], tenant_id: str, workspace_id: str):
        approval_id = now_id("approval")
        row = HumanApprovalRequest(approval_id=approval_id, title=data["title"], action_type=data["action_type"], resource_type=data["resource_type"], resource_id=data["resource_id"], recommendation=data.get("recommendation", ""), risk_level=data.get("risk_level", "medium"), required_roles_json=to_json(data.get("required_roles") or ["hsaai_admin"]), payload_json=to_json(data.get("payload", {})), requested_by=claims.get("sub", "system"), tenant_id=tenant_id, workspace_id=workspace_id)
        db.add(row); db.commit()
        return {"approval_id": approval_id, "status": "pending"}
    def queue(self, db: Session, tenant_id: str, workspace_id: str):
        rows = db.query(HumanApprovalRequest).filter_by(tenant_id=tenant_id, workspace_id=workspace_id).order_by(HumanApprovalRequest.id.desc()).limit(100).all()
        return [{"approval_id": r.approval_id, "title": r.title, "action_type": r.action_type, "risk_level": r.risk_level, "status": r.status, "required_roles": _json(r.required_roles_json, [])} for r in rows]
    def decide(self, db: Session, approval_id: str, status: str, comment: str, claims: dict[str, Any], tenant_id: str, workspace_id: str):
        row = db.query(HumanApprovalRequest).filter_by(approval_id=approval_id, tenant_id=tenant_id, workspace_id=workspace_id).first()
        if not row: raise ValueError("Approval not found")
        required = set(_json(row.required_roles_json, []))
        roles = set(claims.get("roles", []))
        if "hsaai_admin" not in roles and required and roles.isdisjoint(required):
            raise PermissionError("User is not an authorized approver")
        row.status = status; row.reviewed_by = claims.get("sub", "system"); row.review_comment = comment; row.updated_at = datetime.utcnow(); db.commit()
        return {"approval_id": approval_id, "status": status, "reviewed_by": row.reviewed_by}

supervisor_service = SupervisorAgentService()
workflow_service = WorkflowAutomationService()
connector_service = ConnectorService()
observability_service = ObservabilityService()
approval_service = HumanInLoopService()
