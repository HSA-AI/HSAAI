from __future__ import annotations

from backend_core.knowledge_graph.graph_rag_bridge import build_graph_context
from backend_core.knowledge_graph.graph_repository import GraphRepository


def execute_graph_query(repo: GraphRepository, payload: dict, tenant_id: str, workspace_id: str) -> dict:
    query = str(payload.get("query") or payload.get("q") or "")
    mode = str(payload.get("mode") or "semantic")
    if mode == "context":
        return build_graph_context(repo, query, tenant_id, workspace_id, limit=int(payload.get("limit") or 10))
    return repo.search(query, tenant_id, workspace_id, limit=int(payload.get("limit") or 25))
