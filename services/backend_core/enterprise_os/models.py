from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Float, JSON
from sqlalchemy.sql import func
from backend_core.db.database import Base

# FIX D-02: Consolidate duplicate AgentLog definitions.
# `backend_core/db/models.py` is now the SINGLE canonical home for the AgentLog
# ORM model mapped to the `agent_logs` table. Previously this file redefined
# AgentLog with a different column set, and with `extend_existing=True`
# SQLAlchemy merged both definitions — causing INSERTs from one module to fail
# when NOT NULL columns defined only in the other module were missing.
# We import the canonical class here so existing call sites that do
# `from backend_core.enterprise_os.models import AgentLog` keep working, while
# the underlying model is defined in exactly one place.
from backend_core.db.models import AgentLog  # noqa: E402,F401  (re-exported)

class EnterpriseAgent(Base):
    __tablename__ = "agents"
    __table_args__ = {"extend_existing": True}
    id = Column(Integer, primary_key=True)
    agent_key = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, index=True, nullable=False)
    department = Column(String, index=True, default="general")
    description = Column(Text, default="")
    system_prompt = Column(Text, default="")
    model_key = Column(String, index=True, default="local-default")
    status = Column(String, index=True, default="draft")
    risk_level = Column(String, index=True, default="medium")
    tools = Column(JSON, default=list)  # FIX: JSON type
    knowledge_sources = Column(JSON, default=list)
    permissions = Column(JSON, default=list)
    approval_required = Column(Boolean, default=False)
    health_status = Column(String, index=True, default="unknown")
    enabled = Column(Boolean, index=True, default=True)
    version = Column(Integer, default=1)
    tenant_id = Column(String, index=True, default="default")
    workspace_id = Column(String, index=True, default="default")
    created_by = Column(String, index=True, default="system")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

# FIX D-02: AgentLog class intentionally removed — see the import at the top
# of this file. The canonical definition lives in `backend_core/db/models.py`.
# (Previously a second AgentLog class was defined here mapped to the same
# `agent_logs` table with different columns; SQLAlchemy's `extend_existing`
# silently merged them and INSERTs from one module failed when columns from
# the other were missing.)

class AgentMemory(Base):
    __tablename__ = "agent_memory"
    __table_args__ = {"extend_existing": True}
    id = Column(Integer, primary_key=True)
    agent_key = Column(String, index=True, nullable=False)
    scope = Column(String, index=True, default="conversation")
    subject = Column(String, index=True, default="")
    content = Column(Text, default="")
    tenant_id = Column(String, index=True, default="default")
    workspace_id = Column(String, index=True, default="default")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ApprovalRequest(Base):
    __tablename__ = "enterprise_approval_requests"
    __table_args__ = {"extend_existing": True}  # FIX: Renamed to avoid collision with db/models.py
    id = Column(Integer, primary_key=True)
    approval_id = Column(String, unique=True, index=True, nullable=False)
    title = Column(String, index=True, nullable=False)
    action_type = Column(String, index=True, nullable=False)
    resource_type = Column(String, index=True, default="general")
    resource_id = Column(String, index=True, default="")
    recommendation = Column(Text, default="")
    payload = Column(JSON, default=dict)
    risk_level = Column(String, index=True, default="medium")
    status = Column(String, index=True, default="pending")
    current_step = Column(Integer, default=1)
    required_roles = Column(JSON, default=list)
    sla_hours = Column(Integer, default=24)
    requested_by = Column(String, index=True, default="system")
    reviewed_by = Column(String, index=True, default="")
    reject_reason = Column(Text, default="")
    tenant_id = Column(String, index=True, default="default")
    workspace_id = Column(String, index=True, default="default")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

class ApprovalHistory(Base):
    __tablename__ = "approval_history"
    __table_args__ = {"extend_existing": True}
    id = Column(Integer, primary_key=True)
    approval_id = Column(String, index=True, nullable=False)
    step_no = Column(Integer, default=1)
    actor = Column(String, index=True, default="system")
    decision = Column(String, index=True, default="pending")
    comment = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class KnowledgeEntity(Base):
    __tablename__ = "knowledge_entities"
    __table_args__ = {"extend_existing": True}
    id = Column(Integer, primary_key=True)
    entity_key = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, index=True, nullable=False)
    entity_type = Column(String, index=True, nullable=False)
    description = Column(Text, default="")
    source_ref = Column(String, index=True, default="")
    confidence = Column(Float, default=0.0)
    classification = Column(String, index=True, default="internal")
    extra_metadata = Column(JSON, default=dict)
    tenant_id = Column(String, index=True, default="default")
    workspace_id = Column(String, index=True, default="default")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class KnowledgeRelationship(Base):
    __tablename__ = "knowledge_relationships"
    __table_args__ = {"extend_existing": True}
    id = Column(Integer, primary_key=True)
    source_key = Column(String, index=True, nullable=False)
    relationship_type = Column(String, index=True, nullable=False)
    target_key = Column(String, index=True, nullable=False)
    source_ref = Column(String, index=True, default="")
    confidence = Column(Float, default=0.0)
    extra_metadata = Column(JSON, default=dict)
    tenant_id = Column(String, index=True, default="default")
    workspace_id = Column(String, index=True, default="default")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class SearchLog(Base):
    __tablename__ = "search_logs"
    __table_args__ = {"extend_existing": True}
    id = Column(Integer, primary_key=True)
    query = Column(Text, default="")
    search_type = Column(String, index=True, default="hybrid")
    result_count = Column(Integer, default=0)
    latency_ms = Column(Integer, default=0)
    trust_score = Column(Float, default=0.0)
    user_id = Column(String, index=True, default="system")
    tenant_id = Column(String, index=True, default="default")
    workspace_id = Column(String, index=True, default="default")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class AICoEProject(Base):
    __tablename__ = "ai_projects"
    __table_args__ = {"extend_existing": True}
    id = Column(Integer, primary_key=True)
    project_key = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, index=True, nullable=False)
    owner = Column(String, index=True, default="AI CoE")
    department = Column(String, index=True, default="enterprise")
    status = Column(String, index=True, default="planned")
    progress = Column(Integer, default=0)
    expected_roi = Column(Float, default=0.0)
    cost_estimate = Column(Float, default=0.0)
    risk_level = Column(String, index=True, default="medium")
    description = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class AIPolicy(Base):
    __tablename__ = "ai_policies"
    __table_args__ = {"extend_existing": True}
    id = Column(Integer, primary_key=True)
    policy_key = Column(String, unique=True, index=True, nullable=False)
    title = Column(String, index=True, nullable=False)
    category = Column(String, index=True, default="governance")
    classification = Column(String, index=True, default="internal")
    status = Column(String, index=True, default="active")
    enforcement = Column(String, index=True, default="monitor")
    content = Column(Text, default="")
    owner = Column(String, index=True, default="AI Governance")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class AIRisk(Base):
    __tablename__ = "ai_risks"
    __table_args__ = {"extend_existing": True}
    id = Column(Integer, primary_key=True)
    risk_key = Column(String, unique=True, index=True, nullable=False)
    title = Column(String, index=True, nullable=False)
    category = Column(String, index=True, default="model")
    likelihood = Column(String, default="medium")
    impact = Column(String, default="medium")
    severity = Column(String, index=True, default="medium")
    mitigation = Column(Text, default="")
    owner = Column(String, index=True, default="AI Risk")
    status = Column(String, index=True, default="open")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class AITraining(Base):
    __tablename__ = "ai_training"
    __table_args__ = {"extend_existing": True}
    id = Column(Integer, primary_key=True)
    course_key = Column(String, unique=True, index=True, nullable=False)
    title = Column(String, index=True, nullable=False)
    audience = Column(String, index=True, default="all")
    level = Column(String, index=True, default="foundation")
    status = Column(String, index=True, default="active")
    completion_rate = Column(Float, default=0.0)
    description = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class CostRecord(Base):
    __tablename__ = "cost_records"
    __table_args__ = {"extend_existing": True}
    id = Column(Integer, primary_key=True)
    record_key = Column(String, unique=True, index=True, nullable=False)
    user_id = Column(String, index=True, default="system")
    department = Column(String, index=True, default="general")
    business_unit = Column(String, index=True, default="enterprise")
    project = Column(String, index=True, default="HSAAI")
    agent_key = Column(String, index=True, default="")
    model_key = Column(String, index=True, default="local-default")
    workflow_key = Column(String, index=True, default="")
    tokens = Column(Integer, default=0)
    api_calls = Column(Integer, default=0)
    embedding_cost = Column(Float, default=0.0)
    vector_storage_cost = Column(Float, default=0.0)
    compute_cost = Column(Float, default=0.0)
    total_cost = Column(Float, default=0.0)
    latency_ms = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Integration(Base):
    __tablename__ = "integrations"
    __table_args__ = {"extend_existing": True}
    id = Column(Integer, primary_key=True)
    connector_key = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, index=True, nullable=False)
    system_type = Column(String, index=True, nullable=False)
    auth_type = Column(String, default="oauth2")
    base_url = Column(Text, default="")
    enabled = Column(Boolean, default=False)
    health_status = Column(String, index=True, default="not_configured")
    sync_status = Column(String, index=True, default="never")
    permissions_mapping = Column(JSON, default=dict)
    data_mapping = Column(JSON, default=dict)
    retry_policy = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ConnectorLog(Base):
    __tablename__ = "connector_logs"
    __table_args__ = {"extend_existing": True}
    id = Column(Integer, primary_key=True)
    connector_key = Column(String, index=True, nullable=False)
    action = Column(String, index=True, nullable=False)
    success = Column(Boolean, default=True)
    message = Column(Text, default="")
    latency_ms = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
