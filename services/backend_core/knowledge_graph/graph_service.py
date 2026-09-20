from __future__ import annotations

from sqlalchemy.orm import Session

from backend_core.knowledge_graph.graph_ingestion import ingest_document
from backend_core.knowledge_graph.graph_query_engine import execute_graph_query
from backend_core.knowledge_graph.graph_repository import GraphRepository

SEED_ENTITIES = [
    {"entity_key": "department:ai-coe", "name": "AI Center of Excellence", "entity_type": "Department", "description": "Enterprise AI enablement, governance and adoption unit"},
    {"entity_key": "role:knowledge-admin", "name": "Knowledge Admin", "entity_type": "EmployeeRole", "description": "Manages graph, RAG sources and knowledge governance"},
    {"entity_key": "policy:internal-ai-only", "name": "Internal AI Only Policy", "entity_type": "Policy", "description": "Requires local/private AI processing for sensitive enterprise data"},
    {"entity_key": "system:sap-s4hana", "name": "SAP S/4HANA", "entity_type": "System", "description": "Enterprise ERP system integration target"},
    {"entity_key": "document:hsaai-charter", "name": "HSAAI Platform Charter", "entity_type": "Document", "description": "Operating charter for the internal enterprise AI platform"},
    {"entity_key": "agent:supervisor", "name": "Supervisor Agent", "entity_type": "AIAgent", "description": "Coordinates enterprise agents and requests graph context before action"},
    {"entity_key": "risk:data-leakage", "name": "AI Data Leakage Risk", "entity_type": "Risk", "description": "Risk of exposing confidential data through AI workflows"},
    {"entity_key": "workflow:hitl-approval", "name": "Human-in-the-Loop Approval", "entity_type": "Workflow", "description": "Approval workflow for high-risk AI actions"},
    {"entity_key": "permission:graph-read", "name": "Graph Read Permission", "entity_type": "Permission", "description": "Allows scoped reading of knowledge graph entities"},
    {"entity_key": "datasource:sharepoint", "name": "SharePoint Knowledge Source", "entity_type": "DataSource", "description": "Document management source for RAG and graph ingestion"},
]
SEED_RELS = [
    {"source_key": "department:ai-coe", "relationship_type": "OWNS", "target_key": "policy:internal-ai-only"},
    {"source_key": "agent:supervisor", "relationship_type": "USES_CONTEXT_FROM", "target_key": "document:hsaai-charter"},
    {"source_key": "workflow:hitl-approval", "relationship_type": "MITIGATES", "target_key": "risk:data-leakage"},
    {"source_key": "datasource:sharepoint", "relationship_type": "FEEDS", "target_key": "document:hsaai-charter"},
    {"source_key": "role:knowledge-admin", "relationship_type": "HAS_PERMISSION", "target_key": "permission:graph-read"},
    {"source_key": "system:sap-s4hana", "relationship_type": "PROTECTED_BY", "target_key": "policy:internal-ai-only"},
]


class GraphService:
    def __init__(self, db: Session):
        self.repo = GraphRepository(db)

    def seed_if_empty(self, tenant_id: str, workspace_id: str, actor: str = "system") -> dict:
        if self.repo.stats(tenant_id, workspace_id)["entities"] > 0:
            return {"status": "skipped", "reason": "graph already contains data"}
        for entity in SEED_ENTITIES:
            self.repo.upsert_entity(entity, actor=actor, tenant_id=tenant_id, workspace_id=workspace_id)
        for rel in SEED_RELS:
            self.repo.add_relationship(rel, actor=actor, tenant_id=tenant_id, workspace_id=workspace_id)
        return {"status": "seeded", "entities": len(SEED_ENTITIES), "relationships": len(SEED_RELS)}

    def query(self, payload: dict, tenant_id: str, workspace_id: str) -> dict:
        return execute_graph_query(self.repo, payload, tenant_id, workspace_id)

    def ingest_document(self, payload: dict, actor: str, tenant_id: str, workspace_id: str) -> dict:
        return ingest_document(self.repo, payload, actor, tenant_id, workspace_id)
