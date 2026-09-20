from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.sql import func
from backend_core.db.database import Base


class GraphEntity(Base):
    __tablename__ = "kg_entities"
    __table_args__ = (UniqueConstraint("entity_key", "tenant_id", "workspace_id", name="uq_kg_entity_scope"),)

    id = Column(Integer, primary_key=True)
    entity_key = Column(String, index=True, nullable=False)
    name = Column(String, index=True, nullable=False)
    entity_type = Column(String, index=True, nullable=False)
    description = Column(Text, default="")
    classification = Column(String, index=True, default="internal")
    visibility = Column(String, index=True, default="workspace")
    source_ref = Column(String, index=True, default="")
    source_type = Column(String, index=True, default="manual")
    confidence = Column(Float, default=0.85)
    metadata_json = Column(Text, default="{}")
    permissions_json = Column(Text, default="[]")
    tenant_id = Column(String, index=True, default="default")
    workspace_id = Column(String, index=True, default="default")
    created_by = Column(String, index=True, default="system")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class GraphRelationship(Base):
    __tablename__ = "kg_relationships"

    id = Column(Integer, primary_key=True)
    relationship_key = Column(String, unique=True, index=True, nullable=False)
    source_key = Column(String, index=True, nullable=False)
    relationship_type = Column(String, index=True, nullable=False)
    target_key = Column(String, index=True, nullable=False)
    label = Column(String, index=True, default="RELATED_TO")
    source_ref = Column(String, index=True, default="")
    confidence = Column(Float, default=0.75)
    metadata_json = Column(Text, default="{}")
    tenant_id = Column(String, index=True, default="default")
    workspace_id = Column(String, index=True, default="default")
    created_by = Column(String, index=True, default="system")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class GraphDocumentMap(Base):
    __tablename__ = "kg_document_maps"

    id = Column(Integer, primary_key=True)
    document_id = Column(String, index=True, nullable=False)
    document_title = Column(String, index=True, default="")
    entity_key = Column(String, index=True, nullable=False)
    citation = Column(Text, default="")
    chunk_ref = Column(String, index=True, default="")
    tenant_id = Column(String, index=True, default="default")
    workspace_id = Column(String, index=True, default="default")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class GraphAuditLog(Base):
    __tablename__ = "kg_audit_logs"

    id = Column(Integer, primary_key=True)
    event_type = Column(String, index=True, nullable=False)
    actor = Column(String, index=True, default="system")
    resource_type = Column(String, index=True, default="graph")
    resource_id = Column(String, index=True, default="")
    status = Column(String, index=True, default="success")
    detail_json = Column(Text, default="{}")
    tenant_id = Column(String, index=True, default="default")
    workspace_id = Column(String, index=True, default="default")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class GraphIngestionRun(Base):
    __tablename__ = "kg_ingestion_runs"

    id = Column(Integer, primary_key=True)
    run_key = Column(String, unique=True, index=True, nullable=False)
    source_type = Column(String, index=True, default="document")
    source_ref = Column(String, index=True, default="")
    status = Column(String, index=True, default="completed")
    entities_count = Column(Integer, default=0)
    relationships_count = Column(Integer, default=0)
    error = Column(Text, default="")
    tenant_id = Column(String, index=True, default="default")
    workspace_id = Column(String, index=True, default="default")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
