from __future__ import annotations
from typing import Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from .models import ObservabilityMetric, AgentInvocationLog, WorkflowExecution, ConnectorRuntimeState
from .schemas import ObservabilityEventIn

class MatureObservabilityService:
    def record(self, db: Session, event: ObservabilityEventIn) -> dict[str, Any]:
        row = ObservabilityMetric(**event.dict())
        db.add(row); db.commit()
        return {"recorded": True, "id": row.id}

    def dashboard(self, db: Session, tenant_id: str, workspace_id: str) -> dict[str, Any]:
        metrics = db.query(ObservabilityMetric).filter_by(tenant_id=tenant_id, workspace_id=workspace_id).all()
        agents = db.query(AgentInvocationLog).filter_by(tenant_id=tenant_id, workspace_id=workspace_id).all()
        workflows = db.query(WorkflowExecution).filter_by(tenant_id=tenant_id, workspace_id=workspace_id).all()
        connectors = db.query(ConnectorRuntimeState).filter_by(tenant_id=tenant_id, workspace_id=workspace_id).all()
        avg_latency = round(sum(m.latency_ms for m in metrics) / max(1, len(metrics)), 2)
        error_count = sum(1 for m in metrics if m.status not in {"ok", "success", "healthy"} or m.error_message)
        return {
            "executive_summary": {
                "ai_requests": len([m for m in metrics if m.event_type in {"model", "chat", "rag"}]),
                "agent_invocations": len(agents),
                "workflow_executions": len(workflows),
                "connectors_monitored": len(connectors),
                "avg_latency_ms": avg_latency,
                "error_rate": round(error_count / max(1, len(metrics)), 3),
                "tokens": sum(m.tokens for m in metrics),
            },
            "agent_dashboard": self._group(agents, "selected_agent"),
            "workflow_dashboard": self._group(workflows, "status"),
            "connector_dashboard": [{"connector_key": c.connector_key, "health": c.health_status, "sync": c.sync_status, "latency_ms": c.latency_ms, "errors": c.error_count} for c in connectors],
            "model_usage": self._metric_group(metrics, "model"),
            "component_health": self._metric_group(metrics, "component"),
            "signals": ["Model Usage", "Token Usage", "Agent Performance", "Workflow Performance", "Connector Errors", "Latency", "Service Health"],
        }

    def _group(self, rows, attr: str) -> dict[str, int]:
        data: dict[str, int] = {}
        for r in rows:
            key = str(getattr(r, attr, "unknown") or "unknown")
            data[key] = data.get(key, 0) + 1
        return data

    def _metric_group(self, rows, attr: str) -> dict[str, dict[str, Any]]:
        data: dict[str, dict[str, Any]] = {}
        for r in rows:
            key = str(getattr(r, attr, "unknown") or "unknown")
            item = data.setdefault(key, {"events": 0, "tokens": 0, "avg_latency_ms": 0, "errors": 0})
            item["events"] += 1; item["tokens"] += r.tokens; item["avg_latency_ms"] += r.latency_ms; item["errors"] += int(bool(r.error_message))
        for item in data.values():
            item["avg_latency_ms"] = round(item["avg_latency_ms"] / max(1, item["events"]), 2)
        return data

observability_service = MatureObservabilityService()
