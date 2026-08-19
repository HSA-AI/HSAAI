from __future__ import annotations

import json
import re
import uuid
from typing import Any

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from backend_core.knowledge_graph.graph_models import GraphAuditLog, GraphDocumentMap, GraphEntity, GraphIngestionRun, GraphRelationship

ENTITY_TYPES = {"Department", "EmployeeRole", "Policy", "System", "Document", "AIAgent", "Risk", "Workflow", "Permission", "DataSource", "User", "SearchResult", "RAGCitation"}


def safe_json(value: Any, default: Any) -> Any:
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


def slugify(value: str) -> str:
    base = re.sub(r"[^a-zA-Z0-9\u0600-\u06FF]+", "-", (value or "entity").strip()).strip("-")
    return base.lower()[:90] or f"entity-{uuid.uuid4().hex[:8]}"


def entity_to_dict(row: GraphEntity) -> dict[str, Any]:
    return {
        "id": row.id,
        "entity_key": row.entity_key,
        "name": row.name,
        "entity_type": row.entity_type,
        "description": row.description,
        "classification": row.classification,
        "visibility": row.visibility,
        "source_ref": row.source_ref,
        "source_type": row.source_type,
        "confidence": row.confidence,
        "metadata": safe_json(row.metadata_json, {}),
        "permissions": safe_json(row.permissions_json, []),
        "tenant_id": row.tenant_id,
        "workspace_id": row.workspace_id,
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def relationship_to_dict(row: GraphRelationship) -> dict[str, Any]:
    return {
        "id": row.id,
        "relationship_key": row.relationship_key,
        "source_key": row.source_key,
        "relationship_type": row.relationship_type,
        "target_key": row.target_key,
        "label": row.label,
        "source_ref": row.source_ref,
        "confidence": row.confidence,
        "metadata": safe_json(row.metadata_json, {}),
        "tenant_id": row.tenant_id,
        "workspace_id": row.workspace_id,
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


class GraphRepository:
    def __init__(self, db: Session):
        self.db = db

    def audit(self, event_type: str, actor: str, resource_type: str, resource_id: str, status: str = "success", detail: dict[str, Any] | None = None, tenant_id: str = "default", workspace_id: str = "default") -> None:
        self.db.add(GraphAuditLog(event_type=event_type, actor=actor, resource_type=resource_type, resource_id=resource_id, status=status, detail_json=json.dumps(detail or {}, ensure_ascii=False), tenant_id=tenant_id, workspace_id=workspace_id))
        self.db.commit()

    def upsert_entity(self, payload: dict[str, Any], actor: str = "system", tenant_id: str = "default", workspace_id: str = "default") -> GraphEntity:
        name = str(payload.get("name") or payload.get("entity_key") or "Entity").strip()
        entity_type = str(payload.get("entity_type") or payload.get("type") or "Document").strip()
        if entity_type not in ENTITY_TYPES:
            entity_type = entity_type[:80] or "Document"
        key = str(payload.get("entity_key") or f"{entity_type.lower()}:{slugify(name)}")
        row = self.db.query(GraphEntity).filter_by(entity_key=key, tenant_id=tenant_id, workspace_id=workspace_id).first()
        if not row:
            row = GraphEntity(entity_key=key, tenant_id=tenant_id, workspace_id=workspace_id)
            self.db.add(row)
        row.name = name
        row.entity_type = entity_type
        row.description = str(payload.get("description") or "")
        row.classification = str(payload.get("classification") or "internal")
        row.visibility = str(payload.get("visibility") or "workspace")
        row.source_ref = str(payload.get("source_ref") or "")
        row.source_type = str(payload.get("source_type") or "manual")
        row.confidence = float(payload.get("confidence") or 0.85)
        row.metadata_json = json.dumps(payload.get("metadata") or {}, ensure_ascii=False)
        row.permissions_json = json.dumps(payload.get("permissions") or [], ensure_ascii=False)
        row.created_by = actor
        self.db.commit()
        self.db.refresh(row)
        self.audit("entity.upsert", actor, "entity", key, detail={"name": name, "entity_type": entity_type}, tenant_id=tenant_id, workspace_id=workspace_id)
        return row

    def add_relationship(self, payload: dict[str, Any], actor: str = "system", tenant_id: str = "default", workspace_id: str = "default") -> GraphRelationship:
        source = str(payload.get("source_key") or payload.get("source") or "")
        target = str(payload.get("target_key") or payload.get("target") or "")
        rel_type = str(payload.get("relationship_type") or payload.get("type") or "RELATED_TO")
        if not source or not target:
            raise ValueError("source_key and target_key are required")
        key = str(payload.get("relationship_key") or f"rel:{slugify(source)}:{slugify(rel_type)}:{slugify(target)}:{uuid.uuid4().hex[:8]}")
        row = GraphRelationship(relationship_key=key, source_key=source, target_key=target, relationship_type=rel_type, label=str(payload.get("label") or rel_type), source_ref=str(payload.get("source_ref") or ""), confidence=float(payload.get("confidence") or 0.75), metadata_json=json.dumps(payload.get("metadata") or {}, ensure_ascii=False), tenant_id=tenant_id, workspace_id=workspace_id, created_by=actor)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        self.audit("relationship.create", actor, "relationship", key, detail={"source_key": source, "target_key": target, "relationship_type": rel_type}, tenant_id=tenant_id, workspace_id=workspace_id)
        return row

    def list_entities(self, tenant_id: str, workspace_id: str, entity_type: str | None = None, q: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        query = self.db.query(GraphEntity).filter(GraphEntity.tenant_id == tenant_id, GraphEntity.workspace_id == workspace_id)
        if entity_type:
            query = query.filter(GraphEntity.entity_type == entity_type)
        if q:
            like = f"%{q}%"
            query = query.filter(or_(GraphEntity.name.ilike(like), GraphEntity.description.ilike(like), GraphEntity.entity_key.ilike(like)))
        return [entity_to_dict(x) for x in query.order_by(GraphEntity.id.desc()).limit(min(limit, 500)).all()]

    def list_relationships(self, tenant_id: str, workspace_id: str, entity_key: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        query = self.db.query(GraphRelationship).filter(GraphRelationship.tenant_id == tenant_id, GraphRelationship.workspace_id == workspace_id)
        if entity_key:
            query = query.filter(or_(GraphRelationship.source_key == entity_key, GraphRelationship.target_key == entity_key))
        return [relationship_to_dict(x) for x in query.order_by(GraphRelationship.id.desc()).limit(min(limit, 500)).all()]

    def search(self, text: str, tenant_id: str, workspace_id: str, limit: int = 25) -> dict[str, Any]:
        entities = self.list_entities(tenant_id, workspace_id, q=text, limit=limit)
        keys = {e["entity_key"] for e in entities}
        rels = []
        if keys:
            rel_rows = self.db.query(GraphRelationship).filter(and_(GraphRelationship.tenant_id == tenant_id, GraphRelationship.workspace_id == workspace_id), or_(GraphRelationship.source_key.in_(keys), GraphRelationship.target_key.in_(keys))).limit(100).all()
            rels = [relationship_to_dict(r) for r in rel_rows]
        self.audit("graph.search", "system", "query", text[:120], detail={"result_count": len(entities)}, tenant_id=tenant_id, workspace_id=workspace_id)
        return {"query": text, "entities": entities, "relationships": rels, "result_count": len(entities)}

    def document_map(self, document_id: str, tenant_id: str, workspace_id: str) -> dict[str, Any]:
        rows = self.db.query(GraphDocumentMap).filter_by(document_id=document_id, tenant_id=tenant_id, workspace_id=workspace_id).all()
        keys = [r.entity_key for r in rows]
        entities = [entity_to_dict(x) for x in self.db.query(GraphEntity).filter(GraphEntity.entity_key.in_(keys)).all()] if keys else []
        relationships = self.list_relationships(tenant_id, workspace_id, limit=200)
        return {"document_id": document_id, "entities": entities, "relationships": [r for r in relationships if r["source_key"] in keys or r["target_key"] in keys], "citations": [{"entity_key": r.entity_key, "citation": r.citation, "chunk_ref": r.chunk_ref} for r in rows]}

    def record_document_map(self, document_id: str, title: str, entity_key: str, citation: str, chunk_ref: str, tenant_id: str, workspace_id: str) -> None:
        self.db.add(GraphDocumentMap(document_id=document_id, document_title=title, entity_key=entity_key, citation=citation, chunk_ref=chunk_ref, tenant_id=tenant_id, workspace_id=workspace_id))
        self.db.commit()

    def record_ingestion(self, source_ref: str, entities_count: int, relationships_count: int, tenant_id: str, workspace_id: str, status: str = "completed", error: str = "") -> GraphIngestionRun:
        row = GraphIngestionRun(run_key=f"kg-ingest-{uuid.uuid4().hex[:12]}", source_ref=source_ref, status=status, entities_count=entities_count, relationships_count=relationships_count, error=error, tenant_id=tenant_id, workspace_id=workspace_id)
        self.db.add(row)
        self.db.commit()
        return row

    def stats(self, tenant_id: str, workspace_id: str) -> dict[str, Any]:
        last = self.db.query(GraphIngestionRun).filter_by(tenant_id=tenant_id, workspace_id=workspace_id).order_by(GraphIngestionRun.id.desc()).first()
        return {
            "entities": self.db.query(GraphEntity).filter_by(tenant_id=tenant_id, workspace_id=workspace_id).count(),
            "relationships": self.db.query(GraphRelationship).filter_by(tenant_id=tenant_id, workspace_id=workspace_id).count(),
            "documents": self.db.query(GraphDocumentMap.document_id).filter_by(tenant_id=tenant_id, workspace_id=workspace_id).distinct().count(),
            "last_ingestion": {"status": last.status, "source_ref": last.source_ref, "created_at": last.created_at.isoformat() if last and last.created_at else None} if last else None,
        }
