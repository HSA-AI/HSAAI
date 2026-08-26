from __future__ import annotations

from backend_core.knowledge_graph.graph_repository import GraphRepository


def build_graph_context(repo: GraphRepository, query: str, tenant_id: str, workspace_id: str, limit: int = 10) -> dict:
    result = repo.search(query, tenant_id=tenant_id, workspace_id=workspace_id, limit=limit)
    context_lines = []
    for entity in result.get("entities", [])[:limit]:
        context_lines.append(f"[{entity['entity_type']}] {entity['name']}: {entity.get('description') or ''}".strip())
    for rel in result.get("relationships", [])[:limit]:
        context_lines.append(f"({rel['source_key']}) -[{rel['relationship_type']}]-> ({rel['target_key']})")
    return {"query": query, "graph_context": "\n".join(context_lines), "entities": result.get("entities", []), "relationships": result.get("relationships", [])}
