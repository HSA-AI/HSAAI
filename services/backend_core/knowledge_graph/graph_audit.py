from backend_core.knowledge_graph.graph_repository import GraphRepository


def record_graph_event(repo: GraphRepository, event_type: str, actor: str, resource_type: str, resource_id: str, tenant_id: str, workspace_id: str, detail: dict | None = None) -> None:
    repo.audit(event_type, actor, resource_type, resource_id, detail=detail or {}, tenant_id=tenant_id, workspace_id=workspace_id)
