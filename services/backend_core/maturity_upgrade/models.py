from __future__ import annotations
from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text
from sqlalchemy.sql import func
from backend_core.db.database import Base

class AgentInvocationLog(Base):
    __tablename__ = "advanced_agent_invocation_logs"
    id = Column(Integer, primary_key=True)
    request_id = Column(String, unique=True, index=True, nullable=False)
    user_id = Column(String, index=True, default="system")
    tenant_id = Column(String, index=True, default="default")
    workspace_id = Column(String, index=True, default="default")
    message = Column(Text, default="")
    selected_agent = Column(String, index=True, nullable=False)
    supervisor_decision = Column(Text, default="")
    confidence = Column(Float, default=0.0)
    required_connectors_json = Column(Text, default="[]")
    permission_status = Column(String, index=True, default="allowed")
    latency_ms = Column(Integer, default=0)
    success = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class AgentMemoryRecord(Base):
    __tablename__ = "advanced_agent_memory_records"
    id = Column(Integer, primary_key=True)
    agent_key = Column(String, index=True, nullable=False)
    memory_scope = Column(String, index=True, default="department")
    subject = Column(String, index=True, default="")
    content = Column(Text, default="")
    tenant_id = Column(String, index=True, default="default")
    workspace_id = Column(String, index=True, default="default")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class WorkflowExecution(Base):
    __tablename__ = "advanced_workflow_executions"
    id = Column(Integer, primary_key=True)
    execution_id = Column(String, unique=True, index=True, nullable=False)
    template_key = Column(String, index=True, nullable=False)
    title = Column(String, index=True, nullable=False)
    status = Column(String, index=True, default="running")
    current_step = Column(String, index=True, default="start")
    requested_by = Column(String, index=True, default="system")
    payload_json = Column(Text, default="{}")
    steps_json = Column(Text, default="[]")
    sla_status = Column(String, index=True, default="within_sla")
    tenant_id = Column(String, index=True, default="default")
    workspace_id = Column(String, index=True, default="default")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

class WorkflowAuditEvent(Base):
    __tablename__ = "advanced_workflow_audit_events"
    id = Column(Integer, primary_key=True)
    execution_id = Column(String, index=True, nullable=False)
    actor = Column(String, index=True, default="system")
    action = Column(String, index=True, nullable=False)
    comment = Column(Text, default="")
    status_after = Column(String, index=True, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ConnectorRuntimeState(Base):
    __tablename__ = "advanced_connector_runtime_states"
    id = Column(Integer, primary_key=True)
    connector_key = Column(String, index=True, nullable=False)
    health_status = Column(String, index=True, default="unknown")
    sync_status = Column(String, index=True, default="never")
    last_error = Column(Text, default="")
    latency_ms = Column(Integer, default=0)
    rate_limit_remaining = Column(Integer, default=0)
    circuit_state = Column(String, index=True, default="closed")
    success_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    tenant_id = Column(String, index=True, default="default")
    workspace_id = Column(String, index=True, default="default")
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

class ObservabilityMetric(Base):
    __tablename__ = "advanced_observability_metrics"
    id = Column(Integer, primary_key=True)
    event_type = Column(String, index=True, nullable=False)
    component = Column(String, index=True, nullable=False)
    status = Column(String, index=True, default="ok")
    latency_ms = Column(Integer, default=0)
    tokens = Column(Integer, default=0)
    model = Column(String, index=True, default="")
    agent = Column(String, index=True, default="")
    workflow = Column(String, index=True, default="")
    connector = Column(String, index=True, default="")
    error_message = Column(Text, default="")
    tenant_id = Column(String, index=True, default="default")
    workspace_id = Column(String, index=True, default="default")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
