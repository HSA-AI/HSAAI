"""
HSAAI Database Models — Production Grade

DATABASE FIX:
- Added Foreign Keys for referential integrity
- Replaced Text JSON columns with SQLAlchemy JSON type
- Added composite indexes for common query patterns
- Fixed table name collision (approval_requests → human_approval_requests)
- Removed problematic defaults (default="default" → nullable)
- Added string length constraints
"""
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, Float,
    JSON, ForeignKey, ForeignKeyConstraint, Index, UniqueConstraint
)
from sqlalchemy.sql import func
from backend_core.db.database import Base


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_workspace_user", "workspace_id", "user"),
    )
    id = Column(Integer, primary_key=True)
    workspace_id = Column(String(64), index=True, nullable=False)
    user = Column(String(128), index=True, nullable=False)
    role = Column(String(32), nullable=False)
    agent = Column(String(64), default="general")
    message = Column(Text, nullable=False)
    tenant_id = Column(String(64), index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_actor_action", "actor", "action"),
        Index("ix_audit_workspace_created", "workspace_id", "created_at"),
    )
    id = Column(Integer, primary_key=True)
    actor = Column(String(128), index=True, nullable=False)
    action = Column(String(64), index=True, nullable=False)
    resource = Column(String(256))
    workspace_id = Column(String(64), index=True, nullable=False)
    tenant_id = Column(String(64), index=True, nullable=False)
    success = Column(Boolean, default=False)  # FIX: default False to surface failures
    detail = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class KnowledgeSpace(Base):
    __tablename__ = "knowledge_spaces"
    __table_args__ = (
        Index("ix_kspaces_tenant_workspace", "tenant_id", "workspace_id"),
    )
    id = Column(Integer, primary_key=True)
    key = Column(String(128), unique=True, index=True, nullable=False)
    name = Column(String(256), index=True, nullable=False)
    description = Column(Text, default="")
    owner = Column(String(128), index=True, nullable=False)
    classification = Column(String(32), index=True, default="internal")
    tenant_id = Column(String(64), index=True, nullable=False)
    workspace_id = Column(String(64), index=True, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class KnowledgeCollection(Base):
    __tablename__ = "knowledge_collections"
    __table_args__ = (
        Index("ix_kcoll_space_key", "space_key", "key"),
        ForeignKeyConstraint(["space_key"], ["knowledge_spaces.key"]),
        Index("ix_kcoll_tenant_workspace", "tenant_id", "workspace_id"),
    )
    id = Column(Integer, primary_key=True)
    space_key = Column(String(128), ForeignKey("knowledge_spaces.key"), index=True, nullable=False)
    key = Column(String(128), index=True, nullable=False)
    name = Column(String(256), index=True, nullable=False)
    description = Column(Text, default="")
    document_count = Column(Integer, default=0)
    tenant_id = Column(String(64), index=True, nullable=False)
    workspace_id = Column(String(64), index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"
    __table_args__ = (
        Index("ix_kdoc_space_coll_status", "space_key", "collection_key", "status"),
        Index("ix_kdoc_tenant_workspace", "tenant_id", "workspace_id"),
    )
    id = Column(Integer, primary_key=True)
    document_id = Column(String(128), unique=True, index=True, nullable=False)
    space_key = Column(String(128), ForeignKey("knowledge_spaces.key"), index=True, nullable=False)
    collection_key = Column(String(128), index=True, nullable=False)
    filename = Column(String(256), index=True, nullable=False)
    title = Column(String(256), default="")
    content_type = Column(String(128), default="application/octet-stream")
    size_bytes = Column(Integer, default=0)
    version = Column(Integer, default=1)
    status = Column(String(32), index=True, default="draft")
    classification = Column(String(32), index=True, default="internal")
    sensitivity = Column(String(32), index=True, default="normal")
    department = Column(String(64), index=True, default="general")
    tags = Column(JSON, default=list)  # FIX: JSON instead of Text
    extra_metadata = Column(JSON, default=dict)  # FIX: JSON instead of Text
    uploaded_by = Column(String(128), index=True, nullable=False)
    reviewed_by = Column(String(128), default="")
    review_reason = Column(Text, default="")
    approved_at = Column(DateTime(timezone=True), nullable=True)
    archived_at = Column(DateTime(timezone=True), nullable=True)
    qdrant_indexed = Column(Boolean, default=False)
    tenant_id = Column(String(64), index=True, nullable=False)
    workspace_id = Column(String(64), index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class KnowledgeVersion(Base):
    __tablename__ = "knowledge_versions"
    __table_args__ = (
        Index("ix_kver_doc_version", "document_id", "version"),
    )
    id = Column(Integer, primary_key=True)
    document_id = Column(String(128), ForeignKey("knowledge_documents.document_id"), index=True, nullable=False)
    version = Column(Integer, nullable=False)
    storage_path = Column(String(512), default="")
    checksum = Column(String(64), index=True, default="")
    change_note = Column(Text, default="")
    created_by = Column(String(128), index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class KnowledgePermission(Base):
    __tablename__ = "knowledge_permissions"
    __table_args__ = (
        Index("ix_kperm_resource_principal", "resource_type", "resource_key", "principal"),
    )
    id = Column(Integer, primary_key=True)
    resource_type = Column(String(32), index=True, nullable=False)
    resource_key = Column(String(128), index=True, nullable=False)
    principal_type = Column(String(32), index=True, default="role")
    principal = Column(String(128), index=True, nullable=False)
    permission = Column(String(64), index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class KnowledgeAnalyticsEvent(Base):
    __tablename__ = "knowledge_analytics_events"
    __table_args__ = (
        Index("ix_ka_event_tenant_created", "event_type", "tenant_id", "created_at"),
    )
    id = Column(Integer, primary_key=True)
    event_type = Column(String(64), index=True, nullable=False)
    resource_type = Column(String(32), index=True, default="knowledge")
    resource_key = Column(String(128), index=True, default="")
    actor = Column(String(128), index=True, nullable=False)
    query = Column(Text, default="")
    result_count = Column(Integer, default=0)
    latency_ms = Column(Integer, default=0)
    tenant_id = Column(String(64), index=True, nullable=False)
    workspace_id = Column(String(64), index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class DocumentApprovalEvent(Base):
    __tablename__ = "document_approval_events"
    __table_args__ = (
        Index("ix_dae_doc_action", "document_id", "action"),
    )
    id = Column(Integer, primary_key=True)
    document_id = Column(String(128), ForeignKey("knowledge_documents.document_id"), index=True, nullable=False)
    action = Column(String(32), index=True, nullable=False)
    actor = Column(String(128), index=True, nullable=False)
    from_status = Column(String(32), default="")
    to_status = Column(String(32), default="")
    reason = Column(Text, default="")
    tenant_id = Column(String(64), index=True, nullable=False)
    workspace_id = Column(String(64), index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ModelQualityRun(Base):
    __tablename__ = "model_quality_runs"
    id = Column(Integer, primary_key=True)
    run_id = Column(String(128), unique=True, index=True, nullable=False)
    model_name = Column(String(128), index=True, nullable=False)
    accuracy_score = Column(Float, nullable=True)  # FIX: nullable instead of 0.0
    groundedness_score = Column(Float, nullable=True)
    hallucination_risk = Column(Float, nullable=True)
    response_latency = Column(Float, nullable=True)
    arabic_quality_score = Column(Float, nullable=True)
    policy_compliance_score = Column(Float, nullable=True)
    report = Column(JSON, default=dict)  # FIX: JSON instead of Text
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# FIX: Renamed from ApprovalRequest to HumanApprovalRequest to avoid collision
class HumanApprovalRequest(Base):
    __tablename__ = "human_approval_requests"
    __table_args__ = (
        Index("ix_har_status_approver", "status", "approver"),
    )
    id = Column(Integer, primary_key=True)
    request_id = Column(String(128), unique=True, index=True, nullable=False)
    action_type = Column(String(64), index=True, nullable=False)
    resource_type = Column(String(64), index=True, default="")
    resource_id = Column(String(128), index=True, default="")
    requester = Column(String(128), index=True, nullable=False)
    approver = Column(String(128), index=True, default="")
    status = Column(String(32), index=True, default="pending")
    payload = Column(JSON, default=dict)  # FIX: JSON
    decision_reason = Column(Text, default="")
    tenant_id = Column(String(64), index=True, nullable=False)
    workspace_id = Column(String(64), index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    decided_at = Column(DateTime(timezone=True), nullable=True)


class LLMUsageLog(Base):
    __tablename__ = "llm_usage_logs"
    __table_args__ = (
        Index("ix_llm_dept_created", "department", "created_at"),
        Index("ix_llm_user_created", "user_id", "created_at"),
    )
    id = Column(Integer, primary_key=True)
    user_id = Column(String(128), index=True, nullable=False)
    department = Column(String(64), index=True, nullable=False)
    provider = Column(String(64), index=True, default="")
    model = Column(String(128), index=True, default="")
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    estimated_cost = Column(Float, default=0.0)
    operation_type = Column(String(64), index=True, default="chat")
    agent = Column(String(64), default="general")
    workspace_id = Column(String(64), index=True, nullable=False)
    project = Column(String(128), default="default")
    tenant_id = Column(String(64), index=True, nullable=False)
    request_id = Column(String(128), index=True, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AICostRecord(Base):
    __tablename__ = "ai_cost_records"
    __table_args__ = (
        Index("ix_acr_period_dept", "period", "department"),
    )
    id = Column(Integer, primary_key=True)
    period = Column(String(32), index=True, default="daily")
    period_key = Column(String(64), index=True, default="")
    user_id = Column(String(128), index=True, nullable=False)
    department = Column(String(64), index=True, nullable=False)
    model = Column(String(128), index=True, default="")
    agent = Column(String(64), default="general")
    total_input_tokens = Column(Integer, default=0)
    total_output_tokens = Column(Integer, default=0)
    total_cost = Column(Float, default=0.0)
    budget = Column(Float, default=0.0)
    alert_triggered = Column(Boolean, default=False)
    tenant_id = Column(String(64), index=True, nullable=False)
    workspace_id = Column(String(64), index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# Executive Dashboard models
class ExecutiveMetric(Base):
    __tablename__ = "executive_metrics"
    __table_args__ = (
        Index("ix_em_key_period", "metric_key", "period"),
    )
    id = Column(Integer, primary_key=True)
    metric_key = Column(String(64), index=True, nullable=False)
    metric_value = Column(Integer, default=0)
    metric_unit = Column(String(32), default="count")
    category = Column(String(64), index=True, default="platform")
    period = Column(String(32), index=True, default="today")
    tenant_id = Column(String(64), index=True, nullable=False)
    workspace_id = Column(String(64), index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class DepartmentMetric(Base):
    __tablename__ = "department_metrics"
    id = Column(Integer, primary_key=True)
    department = Column(String(64), index=True, nullable=False)
    active_users = Column(Integer, default=0)
    chats = Column(Integer, default=0)
    knowledge_searches = Column(Integer, default=0)
    agent_runs = Column(Integer, default=0)
    workflow_runs = Column(Integer, default=0)
    adoption_score = Column(Integer, default=0)
    tenant_id = Column(String(64), index=True, nullable=False)
    workspace_id = Column(String(64), index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ExecutiveAlert(Base):
    __tablename__ = "executive_alerts"
    __table_args__ = (
        Index("ix_ea_status_severity", "status", "severity"),
    )
    id = Column(Integer, primary_key=True)
    severity = Column(String(32), index=True, default="info")
    category = Column(String(64), index=True, default="platform")
    title = Column(String(256), nullable=False)
    description = Column(Text, default="")
    status = Column(String(32), index=True, default="open")
    owner = Column(String(128), index=True, default="AI Operations")
    tenant_id = Column(String(64), index=True, nullable=False)
    workspace_id = Column(String(64), index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ExecutiveUsageEvent(Base):
    __tablename__ = "executive_usage_events"
    __table_args__ = (
        Index("ix_eue_type_created", "event_type", "created_at"),
    )
    id = Column(Integer, primary_key=True)
    event_type = Column(String(64), index=True, nullable=False)
    department = Column(String(64), index=True, default="General")
    actor = Column(String(128), index=True, nullable=False)
    resource = Column(String(256), default="")
    value = Column(Integer, default=1)
    latency_ms = Column(Integer, default=0)
    success = Column(Boolean, default=False)  # FIX: default False
    tenant_id = Column(String(64), index=True, nullable=False)
    workspace_id = Column(String(64), index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class DepartmentAgent(Base):
    __tablename__ = "department_agents"
    __table_args__ = (
        Index("ix_dagent_dept_enabled", "department", "enabled"),
    )
    id = Column(Integer, primary_key=True)
    key = Column(String(64), index=True, nullable=False)
    name = Column(String(128), index=True, nullable=False)
    department = Column(String(64), index=True, default="general")
    description = Column(Text, default="")
    system_prompt = Column(Text, nullable=False)
    keywords = Column(JSON, default=list)  # FIX: JSON
    allowed_roles = Column(JSON, default=list)  # FIX: JSON
    knowledge_scopes = Column(JSON, default=list)  # FIX: JSON
    escalation_target = Column(String(128), default="")
    priority = Column(Integer, index=True, default=100)
    enabled = Column(Boolean, index=True, default=True)
    tenant_id = Column(String(64), index=True, nullable=False)
    workspace_id = Column(String(64), index=True, nullable=False)
    created_by = Column(String(128), nullable=False)
    updated_by = Column(String(128), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class DepartmentAgentRun(Base):
    __tablename__ = "department_agent_runs"
    __table_args__ = (
        Index("ix_dar_agent_created", "agent_key", "created_at"),
    )
    id = Column(Integer, primary_key=True)
    agent_key = Column(String(64), ForeignKey("department_agents.key"), index=True, nullable=False)
    department = Column(String(64), index=True, default="general")
    actor = Column(String(128), index=True, nullable=False)
    message = Column(Text, default="")
    score = Column(Float, default=0.0)
    success = Column(Boolean, default=False)
    latency_ms = Column(Integer, default=0)
    tenant_id = Column(String(64), index=True, nullable=False)
    workspace_id = Column(String(64), index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ─────────────────────────────────────────────────────────────────────
# v2.0: Added AgentLog + WorkflowExecution tables (real metrics, no fabrication)
# ─────────────────────────────────────────────────────────────────────

# FIX D-02: AgentLog is the SINGLE canonical ORM model for the `agent_logs`
# table. Previously `enterprise_os/models.py` redefined AgentLog with a
# different column set (request_id, agent_key, action, input_text, output_text,
# confidence, latency_ms) while this module defined it with (agent_name,
# message, answer, elapsed_ms, tokens_used, error). With `extend_existing=True`
# SQLAlchemy merged both definitions, so INSERTs issued through either module
# failed whenever the other module's NOT NULL columns were missing. The schema
# below matches the actual `agent_logs` table created by alembic migration
# 0001_initial_schema.py (request_id, agent_key, action, ...) and is the only
# definition imported throughout the codebase. `enterprise_os/models.py`
# now does `from backend_core.db.models import AgentLog` instead of
# redefining the class.
class AgentLog(Base):
    """Runtime log for agent executions — powers executive dashboards."""
    __tablename__ = "agent_logs"
    __table_args__ = (
        Index("ix_agent_logs_created_at", "created_at"),
        Index("ix_agent_logs_tenant_workspace", "tenant_id", "workspace_id"),
        Index("ix_agent_logs_agent_key", "agent_key"),
        Index("ix_agent_logs_success", "success"),
    )
    id = Column(Integer, primary_key=True)
    request_id = Column(String(128), unique=True, index=True, nullable=False)
    user_id = Column(String(128), index=True, default="system")
    agent_key = Column(String(128), nullable=False)  # index via __table_args__ ix_agent_logs_agent_key (FIX: removed duplicate index=True that collided in SQLite)
    action = Column(String(64), index=True, default="run")
    input_text = Column(Text, default="")
    output_text = Column(Text, default="")
    confidence = Column(Float, default=0.0)
    latency_ms = Column(Integer, default=0)
    success = Column(Boolean, default=True)
    tenant_id = Column(String(64), index=True, default="default")
    workspace_id = Column(String(64), index=True, default="default")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class WorkflowExecution(Base):
    """Workflow run history — powers workflow analytics dashboards."""
    __tablename__ = "workflow_executions"
    __table_args__ = (
        Index("ix_workflow_executions_status", "status"),
        Index("ix_workflow_executions_tenant_workspace", "tenant_id", "workspace_id"),
        Index("ix_workflow_executions_workflow_key", "workflow_key"),
        Index("ix_workflow_executions_created_at", "created_at"),
    )
    id = Column(Integer, primary_key=True)
    tenant_id = Column(String(64), nullable=False, default="default")
    workspace_id = Column(String(64), nullable=False, default="default")
    workflow_key = Column(String(128), nullable=False)
    execution_id = Column(String(128), unique=True)
    status = Column(String(32), nullable=False, default="pending")
    triggered_by = Column(String(128))
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    duration_seconds = Column(Float)
    current_step = Column(String(128))
    steps_total = Column(Integer, default=0)
    steps_completed = Column(Integer, default=0)
    error = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
