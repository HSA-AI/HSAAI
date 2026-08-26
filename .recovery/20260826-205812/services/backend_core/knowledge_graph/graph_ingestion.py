from __future__ import annotations

import os
import re
import httpx
import logging

logger = logging.getLogger("hsaai.graph_ingestion")

LLM_GATEWAY_URL = os.getenv("LLM_GATEWAY_URL", "http://llm_gateway:8090")
USE_LLM_EXTRACTION = os.getenv("USE_LLM_EXTRACTION", "true").lower() == "true"
from typing import Any

from backend_core.knowledge_graph.graph_repository import GraphRepository, slugify

ENTITY_HINTS = {
    "policy": "Policy", "سياسة": "Policy", "governance": "Policy", "risk": "Risk", "مخاطر": "Risk",
    "workflow": "Workflow", "approval": "Workflow", "sap": "System", "sharepoint": "System", "active directory": "System",
    "agent": "AIAgent", "rag": "System", "qdrant": "System", "neo4j": "System", "department": "Department", "إدارة": "Department",
}


def infer_type(token: str) -> str:
    low = token.lower()
    for hint, entity_type in ENTITY_HINTS.items():
        if hint in low:
            return entity_type
    return "Document"


def extract_candidate_entities(text: str, title: str = "") -> list[dict[str, Any]]:
    candidates: dict[str, dict[str, Any]] = {}
    if title:
        candidates[f"document:{slugify(title)}"] = {"entity_key": f"document:{slugify(title)}", "name": title, "entity_type": "Document", "description": "Document source node extracted during ingestion"}
    patterns = [r"\b[A-Z][A-Za-z0-9_/.-]{2,}\b", r"[\u0600-\u06FF]{3,}(?:\s+[\u0600-\u06FF]{3,}){0,2}"]
    for pattern in patterns:
        for match in re.findall(pattern, text or "")[:80]:
            name = match.strip()[:120]
            if len(name) < 3:
                continue
            entity_type = infer_type(name)
            key = f"{entity_type.lower()}:{slugify(name)}"
            candidates[key] = {"entity_key": key, "name": name, "entity_type": entity_type, "description": "Extracted from document text", "confidence": 0.62, "source_type": "document"}
    return list(candidates.values())[:60]


def ingest_document(repo: GraphRepository, payload: dict[str, Any], actor: str, tenant_id: str, workspace_id: str) -> dict[str, Any]:
    document_id = str(payload.get("document_id") or payload.get("id") or "doc-unknown")
    title = str(payload.get("title") or payload.get("filename") or document_id)
    text = str(payload.get("text") or payload.get("content") or payload.get("summary") or "")
    classification = str(payload.get("classification") or "internal")
    permissions = payload.get("permissions") or []
    entities_payload = payload.get("entities") or extract_candidate_entities(text, title=title)
    saved = []
    for entity in entities_payload:
        entity = dict(entity)
        entity.setdefault("classification", classification)
        entity.setdefault("permissions", permissions)
        entity.setdefault("source_ref", document_id)
        row = repo.upsert_entity(entity, actor=actor, tenant_id=tenant_id, workspace_id=workspace_id)
        saved.append(row.entity_key)
        repo.record_document_map(document_id, title, row.entity_key, entity.get("citation") or title, entity.get("chunk_ref") or document_id, tenant_id, workspace_id)
    rel_count = 0
    doc_key = f"document:{slugify(title)}"
    for key in saved:
        if key != doc_key:
            repo.add_relationship({"source_key": doc_key, "target_key": key, "relationship_type": "MENTIONS", "label": "MENTIONS", "source_ref": document_id, "confidence": 0.66}, actor=actor, tenant_id=tenant_id, workspace_id=workspace_id)
            rel_count += 1
    for rel in payload.get("relationships") or []:
        repo.add_relationship({**rel, "source_ref": rel.get("source_ref") or document_id}, actor=actor, tenant_id=tenant_id, workspace_id=workspace_id)
        rel_count += 1
    run = repo.record_ingestion(document_id, len(saved), rel_count, tenant_id, workspace_id)
    repo.audit("document.ingest", actor, "document", document_id, detail={"entities": len(saved), "relationships": rel_count}, tenant_id=tenant_id, workspace_id=workspace_id)
    return {"status": "completed", "run_key": run.run_key, "document_id": document_id, "entities_count": len(saved), "relationships_count": rel_count, "entity_keys": saved}
