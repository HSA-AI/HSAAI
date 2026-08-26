from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend_core.db.database import get_db, check_db
from backend_core.security.rbac import get_current_claims
from backend_core.knowledge_graph.graph_permissions import graph_scope, require_graph_permission
from backend_core.knowledge_graph.graph_repository import GraphRepository, entity_to_dict, relationship_to_dict
from backend_core.knowledge_graph.graph_service import GraphService
from backend_core.knowledge_graph.graph_rag_bridge import build_graph_context

router = APIRouter(prefix="/api/knowledge-graph", tags=["knowledge-graph"])


class EntityPayload(BaseModel):
    entity_key: str | None = None
    name: str
    entity_type: str = Field(default="Document")
    description: str = ""
    classification: str = "internal"
    visibility: str = "workspace"
    source_ref: str = ""
    source_type: str = "manual"
    confidence: float = 0.85
    metadata: dict[str, Any] = Field(default_factory=dict)
    permissions: list[str] = Field(default_factory=list)


class RelationshipPayload(BaseModel):
    relationship_key: str | None = None
    source_key: str
    relationship_type: str = "RELATED_TO"
    target_key: str
    label: str | None = None
    source_ref: str = ""
    confidence: float = 0.75
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphQueryPayload(BaseModel):
    query: str = ""
    mode: str = "semantic"
    limit: int = 25


@router.get("/entities")
def list_entities(entity_type: str | None = None, q: str | None = None, limit: int = Query(100, le=500), db: Session = Depends(get_db), claims: dict = Depends(get_current_claims)):
    require_graph_permission(claims, "graph:read")
    tenant_id, workspace_id, _ = graph_scope(claims)
    return {"items": GraphRepository(db).list_entities(tenant_id, workspace_id, entity_type=entity_type, q=q, limit=limit)}


@router.post("/entities")
def create_entity(payload: EntityPayload, db: Session = Depends(get_db), claims: dict = Depends(get_current_claims)):
    require_graph_permission(claims, "graph:write")
    tenant_id, workspace_id, actor = graph_scope(claims)
    return entity_to_dict(GraphRepository(db).upsert_entity(payload.model_dump(), actor=actor, tenant_id=tenant_id, workspace_id=workspace_id))


@router.get("/relationships")
def list_relationships(entity_key: str | None = None, limit: int = Query(200, le=500), db: Session = Depends(get_db), claims: dict = Depends(get_current_claims)):
    require_graph_permission(claims, "graph:read")
    tenant_id, workspace_id, _ = graph_scope(claims)
    return {"items": GraphRepository(db).list_relationships(tenant_id, workspace_id, entity_key=entity_key, limit=limit)}


@router.post("/relationships")
def create_relationship(payload: RelationshipPayload, db: Session = Depends(get_db), claims: dict = Depends(get_current_claims)):
    require_graph_permission(claims, "graph:write")
    tenant_id, workspace_id, actor = graph_scope(claims)
    try:
        row = GraphRepository(db).add_relationship(payload.model_dump(), actor=actor, tenant_id=tenant_id, workspace_id=workspace_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return relationship_to_dict(row)


@router.get("/search")
def search(q: str = "", limit: int = Query(25, le=100), db: Session = Depends(get_db), claims: dict = Depends(get_current_claims)):
    require_graph_permission(claims, "graph:read")
    tenant_id, workspace_id, actor = graph_scope(claims)
    repo = GraphRepository(db)
    result = repo.search(q, tenant_id, workspace_id, limit=limit)
    repo.audit("graph.search", actor, "query", q[:120], detail={"limit": limit, "result_count": result.get("result_count")}, tenant_id=tenant_id, workspace_id=workspace_id)
    return result


@router.post("/query")
def query_graph(payload: GraphQueryPayload, db: Session = Depends(get_db), claims: dict = Depends(get_current_claims)):
    require_graph_permission(claims, "graph:read")
    tenant_id, workspace_id, actor = graph_scope(claims)
    repo = GraphRepository(db)
    result = GraphService(db).query(payload.model_dump(), tenant_id, workspace_id)
    repo.audit("graph.query", actor, "query", payload.query[:120], detail={"mode": payload.mode}, tenant_id=tenant_id, workspace_id=workspace_id)
    return result


@router.post("/ingest-document")
def ingest_document(payload: dict[str, Any], db: Session = Depends(get_db), claims: dict = Depends(get_current_claims)):
    require_graph_permission(claims, "graph:write")
    tenant_id, workspace_id, actor = graph_scope(claims)
    return GraphService(db).ingest_document(payload, actor, tenant_id, workspace_id)


@router.get("/document/{document_id}/map")
def document_map(document_id: str, db: Session = Depends(get_db), claims: dict = Depends(get_current_claims)):
    require_graph_permission(claims, "graph:read")
    tenant_id, workspace_id, _ = graph_scope(claims)
    return GraphRepository(db).document_map(document_id, tenant_id, workspace_id)


@router.get("/agent-context/{agent_id}")
def agent_context(agent_id: str, task: str = "", db: Session = Depends(get_db), claims: dict = Depends(get_current_claims)):
    require_graph_permission(claims, "graph:read")
    tenant_id, workspace_id, actor = graph_scope(claims)
    query = task or agent_id
    repo = GraphRepository(db)
    result = build_graph_context(repo, query, tenant_id, workspace_id, limit=12)
    repo.audit("agent.graph_context", actor, "agent", agent_id, detail={"task": task, "entities": len(result.get("entities", []))}, tenant_id=tenant_id, workspace_id=workspace_id)
    return {"agent_id": agent_id, **result}


@router.post("/seed")
def seed_graph(db: Session = Depends(get_db), claims: dict = Depends(get_current_claims)):
    require_graph_permission(claims, "graph:admin")
    tenant_id, workspace_id, actor = graph_scope(claims)
    return GraphService(db).seed_if_empty(tenant_id, workspace_id, actor=actor)


@router.get("/health")
def graph_health(db: Session = Depends(get_db), claims: dict = Depends(get_current_claims)):
    require_graph_permission(claims, "graph:read")
    tenant_id, workspace_id, _ = graph_scope(claims)
    repo = GraphRepository(db)
    stats = repo.stats(tenant_id, workspace_id)
    db_status = check_db()
    neo4j_enabled = bool(os.getenv("NEO4J_URI"))
    return {
        "status": "ok" if db_status.get("status") == "ok" else "degraded",
        "engine": "neo4j-ready" if neo4j_enabled else "postgresql-graph-layer",
        "knowledge_graph_enabled": os.getenv("KNOWLEDGE_GRAPH_ENABLED", "true").lower() == "true",
        "graph_ingestion_enabled": os.getenv("GRAPH_INGESTION_ENABLED", "true").lower() == "true",
        "graph_rag_bridge_enabled": os.getenv("GRAPH_RAG_BRIDGE_ENABLED", "true").lower() == "true",
        "neo4j_configured": neo4j_enabled,
        "database": db_status,
        **stats,
    }
