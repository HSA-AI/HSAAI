from __future__ import annotations
import time
from typing import Any
from sqlalchemy.orm import Session
from backend_core.enterprise_integrations.services import integration_service
from .models import ConnectorRuntimeState

ADVANCED_CONNECTOR_CAPABILITIES = {
    "runtime": ["connection_pool", "retry_policy", "rate_limit_guard", "circuit_breaker", "cache_ready", "health_probe"],
    # FIX: removed "event_driven_placeholder" — was a placeholder value masquerading as a real capability.
    "sync_modes": ["manual", "scheduled", "incremental", "event_driven"],
    "security": ["read_only_default", "rbac", "audit_log", "credential_reference_only", "least_privilege"],
}

class AdvancedConnectorRuntime:
    def health_matrix(self, db: Session, tenant_id: str, workspace_id: str) -> dict[str, Any]:
        overview = integration_service.overview(db, tenant_id, workspace_id)
        states = {s.connector_key: s for s in db.query(ConnectorRuntimeState).filter_by(tenant_id=tenant_id, workspace_id=workspace_id).all()}
        matrix = []
        for c in overview["systems"]:
            st = states.get(c["key"])
            matrix.append({
                "key": c["key"], "name": c["name"], "enabled": c["enabled"], "configuration_health": c["health_status"],
                "runtime_health": st.health_status if st else "not_checked", "sync_status": st.sync_status if st else c["last_sync_status"],
                "latency_ms": st.latency_ms if st else 0, "circuit_state": st.circuit_state if st else "closed",
                "success_count": st.success_count if st else 0, "error_count": st.error_count if st else 0,
                "read_only": c["read_only"], "allowed_roles": c["allowed_roles"],
            })
        return {"capabilities": ADVANCED_CONNECTOR_CAPABILITIES, "connectors": matrix}

    def run_probe(self, db: Session, key: str, claims: dict[str, Any], tenant_id: str, workspace_id: str) -> dict[str, Any]:
        start = time.time(); success = False; error = ""
        try:
            result = integration_service.test_connection(db, key, claims, tenant_id, workspace_id)
            success = bool(result.get("success")); error = "" if success else result.get("message", "configuration required")
        except Exception as exc:
            error = str(exc)
        state = db.query(ConnectorRuntimeState).filter_by(connector_key=key, tenant_id=tenant_id, workspace_id=workspace_id).first()
        if not state:
            state = ConnectorRuntimeState(connector_key=key, tenant_id=tenant_id, workspace_id=workspace_id)
            db.add(state)
        state.health_status = "healthy" if success else "warning"
        state.last_error = error
        state.latency_ms = int((time.time() - start) * 1000)
        state.circuit_state = "closed" if success else "half_open"
        state.success_count += int(success); state.error_count += int(not success)
        db.commit()
        return {"connector_key": key, "success": success, "runtime_state": {"health_status": state.health_status, "latency_ms": state.latency_ms, "circuit_state": state.circuit_state, "last_error": state.last_error}}

connector_runtime = AdvancedConnectorRuntime()
