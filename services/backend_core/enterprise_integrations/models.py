from __future__ import annotations
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Float
from sqlalchemy.sql import func
from backend_core.db.database import Base


class IntegrationDefinition(Base):
    __tablename__ = "enterprise_integration_definitions"
    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, index=True, nullable=False)
    system_type = Column(String, index=True, nullable=False)
    category = Column(String, index=True, default="enterprise")
    base_url = Column(Text, default="")
    auth_type = Column(String, index=True, default="oauth2")
    credentials_ref = Column(String, default="")
    read_only = Column(Boolean, default=True)
    enabled = Column(Boolean, index=True, default=False)
    health_status = Column(String, index=True, default="not_configured")
    last_sync_status = Column(String, index=True, default="never")
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    capabilities_json = Column(Text, default="[]")
    allowed_roles_json = Column(Text, default="[]")
    metadata_json = Column(Text, default="{}")
    tenant_id = Column(String, index=True, default="default")
    workspace_id = Column(String, index=True, default="default")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())


class IntegrationAuditLog(Base):
    __tablename__ = "enterprise_integration_audit_logs"
    id = Column(Integer, primary_key=True)
    request_id = Column(String, index=True, nullable=False)
    connector_key = Column(String, index=True, nullable=False)
    actor = Column(String, index=True, default="system")
    action = Column(String, index=True, nullable=False)
    resource = Column(String, index=True, default="")
    success = Column(Boolean, default=True)
    message = Column(Text, default="")
    data_source = Column(String, index=True, default="")
    latency_ms = Column(Integer, default=0)
    tenant_id = Column(String, index=True, default="default")
    workspace_id = Column(String, index=True, default="default")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class IntegrationSyncRun(Base):
    __tablename__ = "enterprise_integration_sync_runs"
    id = Column(Integer, primary_key=True)
    sync_id = Column(String, unique=True, index=True, nullable=False)
    connector_key = Column(String, index=True, nullable=False)
    status = Column(String, index=True, default="queued")
    records_read = Column(Integer, default=0)
    records_written = Column(Integer, default=0)
    error_message = Column(Text, default="")
    started_by = Column(String, index=True, default="system")
    tenant_id = Column(String, index=True, default="default")
    workspace_id = Column(String, index=True, default="default")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True), nullable=True)


class ConnectorSecurityPolicy(Base):
    __tablename__ = "enterprise_connector_security_policies"
    id = Column(Integer, primary_key=True)
    connector_key = Column(String, index=True, nullable=False)
    policy_name = Column(String, index=True, nullable=False)
    read_only = Column(Boolean, default=True)
    blocked_operations_json = Column(Text, default='["UPDATE","DELETE","DROP","ALTER","TRUNCATE"]')
    field_masking_json = Column(Text, default="{}")
    row_filter_json = Column(Text, default="{}")
    requires_human_approval = Column(Boolean, default=False)
    tenant_id = Column(String, index=True, default="default")
    workspace_id = Column(String, index=True, default="default")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
