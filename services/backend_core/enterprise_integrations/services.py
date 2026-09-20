from __future__ import annotations
import json
import time
from datetime import datetime
from typing import Any
from sqlalchemy.orm import Session
from .base_connector import ConnectorContext
from .connector_registry import registry, AGENT_DATA_SOURCES, WORKFLOW_CONNECTOR_MAP
from .models import IntegrationDefinition, IntegrationAuditLog, IntegrationSyncRun, ConnectorSecurityPolicy


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _loads(value: str | None, fallback: Any):
    try:
        return json.loads(value or "")
    except Exception:
        return fallback


def _request_id(prefix: str) -> str:
    return f"{prefix}-{int(time.time() * 1000)}"


class EnterpriseIntegrationService:
    def ensure_defaults(self, db: Session, tenant_id: str, workspace_id: str) -> None:
        existing = {x.key for x in db.query(IntegrationDefinition).filter_by(tenant_id=tenant_id, workspace_id=workspace_id).all()}
        for item in registry.supported():
            if item["key"] in existing:
                continue
            db.add(IntegrationDefinition(
                key=item["key"], name=item["name"], system_type=item["system_type"], category=item["category"],
                auth_type=item["auth_type"], read_only=item["read_only"], enabled=False, health_status="not_configured",
                capabilities_json=_json(item["capabilities"]), allowed_roles_json=_json(item["allowed_roles"]),
                metadata_json=_json({"source_visibility": "show_source_in_ai_answers", "default_mode": "read_only"}),
                tenant_id=tenant_id, workspace_id=workspace_id,
            ))
            db.add(ConnectorSecurityPolicy(
                connector_key=item["key"], policy_name=f"{item['key']}_default_policy", read_only=True,
                requires_human_approval=item["key"] in {"sap_s4hana", "successfactors", "active_directory", "jira", "service_desk"},
                tenant_id=tenant_id, workspace_id=workspace_id,
            ))
        db.commit()

    def list_connectors(self, db: Session, tenant_id: str, workspace_id: str) -> list[dict[str, Any]]:
        self.ensure_defaults(db, tenant_id, workspace_id)
        rows = db.query(IntegrationDefinition).filter_by(tenant_id=tenant_id, workspace_id=workspace_id).order_by(IntegrationDefinition.category.asc(), IntegrationDefinition.name.asc()).all()
        return [self._serialize(r) for r in rows]

    def _serialize(self, row: IntegrationDefinition) -> dict[str, Any]:
        return {
            "key": row.key, "name": row.name, "system_type": row.system_type, "category": row.category,
            "base_url_configured": bool(row.base_url), "auth_type": row.auth_type, "credentials_ref_configured": bool(row.credentials_ref),
            "read_only": row.read_only, "enabled": row.enabled, "health_status": row.health_status,
            "last_sync_status": row.last_sync_status, "last_sync_at": row.last_sync_at.isoformat() if row.last_sync_at else None,
            "capabilities": _loads(row.capabilities_json, []), "allowed_roles": _loads(row.allowed_roles_json, []),
            "metadata": _loads(row.metadata_json, {}),
        }

    def configure(self, db: Session, data: dict[str, Any], claims: dict[str, Any], tenant_id: str, workspace_id: str) -> dict[str, Any]:
        self.ensure_defaults(db, tenant_id, workspace_id)
        key = data["key"]
        row = db.query(IntegrationDefinition).filter_by(key=key, tenant_id=tenant_id, workspace_id=workspace_id).first()
        if not row:
            raise ValueError("Unsupported connector key")
        row.base_url = data.get("base_url", row.base_url)
        row.auth_type = data.get("auth_type", row.auth_type)
        row.credentials_ref = data.get("credentials_ref", row.credentials_ref)
        row.enabled = bool(data.get("enabled", row.enabled))
        row.metadata_json = _json(data.get("metadata", _loads(row.metadata_json, {})))
        row.updated_at = datetime.utcnow()
        self._audit(db, key, claims, "configure", True, "connector configuration updated", tenant_id, workspace_id)
        db.commit()
        return self._serialize(row)

    def test_connection(self, db: Session, key: str, claims: dict[str, Any], tenant_id: str, workspace_id: str) -> dict[str, Any]:
        self.ensure_defaults(db, tenant_id, workspace_id)
        row = db.query(IntegrationDefinition).filter_by(key=key, tenant_id=tenant_id, workspace_id=workspace_id).first()
        if not row:
            raise ValueError("Connector not found")
        connector = registry.create(key, {"base_url": row.base_url, "credentials_ref": row.credentials_ref})
        result = connector.test_connection()
        row.health_status = "healthy" if result.success else "configuration_required"
        row.updated_at = datetime.utcnow()
        self._audit(db, key, claims, "test_connection", result.success, result.message, tenant_id, workspace_id, result.latency_ms)
        db.commit()
        return result.__dict__ | {"health_status": row.health_status}

    def fetch(self, db: Session, key: str, query: dict[str, Any], claims: dict[str, Any], tenant_id: str, workspace_id: str) -> dict[str, Any]:
        row = db.query(IntegrationDefinition).filter_by(key=key, tenant_id=tenant_id, workspace_id=workspace_id).first()
        if not row or not row.enabled:
            raise ValueError("Connector is not enabled/configured")
        context = ConnectorContext(tenant_id=tenant_id, workspace_id=workspace_id, actor=claims.get("sub", "system"), roles=claims.get("roles", []), request_id=_request_id("conn"))
        result = registry.create(key, {"base_url": row.base_url, "credentials_ref": row.credentials_ref}).fetch_data(query, context)
        self._audit(db, key, claims, "fetch_data", result.success, result.message, tenant_id, workspace_id, result.latency_ms, data_source=result.source)
        db.commit()
        return result.__dict__ | {"audit_request_id": context.request_id, "show_source_in_answer": True}

    def sync(self, db: Session, key: str, claims: dict[str, Any], tenant_id: str, workspace_id: str) -> dict[str, Any]:
        row = db.query(IntegrationDefinition).filter_by(key=key, tenant_id=tenant_id, workspace_id=workspace_id).first()
        if not row or not row.enabled:
            raise ValueError("Connector is not enabled/configured")
        sync_id = _request_id("sync")
        context = ConnectorContext(tenant_id=tenant_id, workspace_id=workspace_id, actor=claims.get("sub", "system"), roles=claims.get("roles", []), request_id=sync_id)
        result = registry.create(key, {"base_url": row.base_url, "credentials_ref": row.credentials_ref}).sync_data(context)
        run = IntegrationSyncRun(sync_id=sync_id, connector_key=key, status="completed" if result.success else "failed", records_read=int((result.data or {}).get("records", 0) if isinstance(result.data, dict) else 0), started_by=context.actor, error_message="" if result.success else result.message, tenant_id=tenant_id, workspace_id=workspace_id, finished_at=datetime.utcnow())
        row.last_sync_status = run.status
        row.last_sync_at = datetime.utcnow()
        db.add(run)
        self._audit(db, key, claims, "sync_data", result.success, result.message, tenant_id, workspace_id, result.latency_ms)
        db.commit()
        return {"sync_id": sync_id, "status": run.status, "connector_key": key, "result": result.__dict__}

    def agent_sources(self, agent_key: str) -> dict[str, Any]:
        return {"agent": agent_key, "connectors": AGENT_DATA_SOURCES.get(agent_key, []), "source_policy": "only approved connectors and RBAC-allowed data are exposed to the agent"}

    def workflow_sources(self, template_key: str) -> dict[str, Any]:
        return {"workflow": template_key, "connectors": WORKFLOW_CONNECTOR_MAP.get(template_key, []), "human_approval": "required for sensitive or write actions"}

    def audit_logs(self, db: Session, tenant_id: str, workspace_id: str, limit: int = 100) -> list[dict[str, Any]]:
        rows = db.query(IntegrationAuditLog).filter_by(tenant_id=tenant_id, workspace_id=workspace_id).order_by(IntegrationAuditLog.id.desc()).limit(limit).all()
        return [{"request_id": r.request_id, "connector_key": r.connector_key, "actor": r.actor, "action": r.action, "success": r.success, "message": r.message, "data_source": r.data_source, "latency_ms": r.latency_ms, "created_at": r.created_at.isoformat() if r.created_at else None} for r in rows]

    def overview(self, db: Session, tenant_id: str, workspace_id: str) -> dict[str, Any]:
        connectors = self.list_connectors(db, tenant_id, workspace_id)
        return {
            "total": len(connectors),
            "enabled": sum(1 for c in connectors if c["enabled"]),
            "healthy": sum(1 for c in connectors if c["health_status"] == "healthy"),
            "read_only_default": True,
            "systems": connectors,
            "agent_data_sources": AGENT_DATA_SOURCES,
            "workflow_connector_map": WORKFLOW_CONNECTOR_MAP,
        }

    def _audit(self, db: Session, key: str, claims: dict[str, Any], action: str, success: bool, message: str, tenant_id: str, workspace_id: str, latency_ms: int = 0, data_source: str = "") -> None:
        db.add(IntegrationAuditLog(request_id=_request_id("audit"), connector_key=key, actor=claims.get("sub", "system"), action=action, success=success, message=message, data_source=data_source, latency_ms=latency_ms, tenant_id=tenant_id, workspace_id=workspace_id))

integration_service = EnterpriseIntegrationService()
