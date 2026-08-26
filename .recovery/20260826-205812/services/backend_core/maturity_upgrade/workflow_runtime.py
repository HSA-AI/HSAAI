from __future__ import annotations
import json, time
from typing import Any
from sqlalchemy.orm import Session
from .models import WorkflowExecution, WorkflowAuditEvent
from .schemas import WorkflowStartRequest, WorkflowActionRequest

WORKFLOW_TEMPLATES: dict[str, dict[str, Any]] = {
    "purchase_request": {"name": "Purchase Request", "sla_hours": 48, "connectors": ["sap_s4hana", "service_desk"], "steps": ["submit", "sap_check", "manager_approval", "finance_review", "execute", "audit_log"]},
    "document_review": {"name": "Sensitive Document Review", "sla_hours": 24, "connectors": ["sharepoint", "dms"], "steps": ["upload", "classify", "review", "approve_or_reject", "index_to_rag", "publish"]},
    "leave_request": {"name": "Leave Request", "sla_hours": 24, "connectors": ["successfactors", "outlook_exchange"], "steps": ["submit", "successfactors_check", "manager_approval", "hr_approval", "notify_employee"]},
    "support_ticket": {"name": "IT Support Ticket", "sla_hours": 8, "connectors": ["service_desk", "jira", "active_directory"], "steps": ["submit", "classify", "create_ticket", "sla_monitor", "resolve", "close"]},
}

class AdvancedWorkflowEngine:
    def templates(self) -> dict[str, Any]:
        return {"templates": WORKFLOW_TEMPLATES, "supports": ["approvals", "conditional_steps", "sla_tracking", "escalation", "audit_trail"]}

    def start(self, db: Session, payload: WorkflowStartRequest) -> dict[str, Any]:
        if payload.template_key not in WORKFLOW_TEMPLATES:
            raise ValueError("Unsupported workflow template")
        template = WORKFLOW_TEMPLATES[payload.template_key]
        execution_id = f"wf-{payload.template_key}-{int(time.time()*1000)}"
        row = WorkflowExecution(execution_id=execution_id, template_key=payload.template_key, title=payload.title, requested_by=payload.requested_by, payload_json=json.dumps(payload.payload, ensure_ascii=False), steps_json=json.dumps(template["steps"], ensure_ascii=False), current_step=template["steps"][0], tenant_id=payload.tenant_id, workspace_id=payload.workspace_id)
        db.add(row); db.flush()
        db.add(WorkflowAuditEvent(execution_id=execution_id, actor=payload.requested_by, action="start", comment=f"Started {template['name']}", status_after="running"))
        db.commit()
        return self.serialize(row) | {"template": template}

    def action(self, db: Session, payload: WorkflowActionRequest) -> dict[str, Any]:
        row = db.query(WorkflowExecution).filter_by(execution_id=payload.execution_id).first()
        if not row: raise ValueError("Workflow execution not found")
        steps = json.loads(row.steps_json or "[]"); idx = steps.index(row.current_step) if row.current_step in steps else 0
        if payload.action == "reject": row.status = "rejected"
        elif payload.action == "escalate": row.status = "escalated"; row.sla_status = "at_risk"
        elif idx >= len(steps) - 1: row.status = "completed"; row.current_step = steps[-1]
        else: row.current_step = steps[idx + 1]; row.status = "running"
        db.add(WorkflowAuditEvent(execution_id=row.execution_id, actor=payload.actor, action=payload.action, comment=payload.comment, status_after=row.status))
        db.commit(); return self.serialize(row)

    def list(self, db: Session, tenant_id: str, workspace_id: str) -> dict[str, Any]:
        rows = db.query(WorkflowExecution).filter_by(tenant_id=tenant_id, workspace_id=workspace_id).order_by(WorkflowExecution.id.desc()).limit(100).all()
        return {"executions": [self.serialize(r) for r in rows], "summary": {"running": sum(1 for r in rows if r.status == "running"), "completed": sum(1 for r in rows if r.status == "completed"), "escalated": sum(1 for r in rows if r.status == "escalated")}}

    def serialize(self, row: WorkflowExecution) -> dict[str, Any]:
        return {"execution_id": row.execution_id, "template_key": row.template_key, "title": row.title, "status": row.status, "current_step": row.current_step, "sla_status": row.sla_status, "requested_by": row.requested_by, "steps": json.loads(row.steps_json or "[]")}

workflow_engine = AdvancedWorkflowEngine()
