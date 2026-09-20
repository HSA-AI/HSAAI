
from __future__ import annotations
import json
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Float
from sqlalchemy.sql import func
from backend_core.db.database import Base

class EnterpriseAgentDefinition(Base):
    __tablename__ = "enterprise_agent_definitions"
    id = Column(Integer, primary_key=True)
    key = Column(String, index=True, nullable=False)
    name = Column(String, index=True, nullable=False)
    department = Column(String, index=True, default="general")
    capabilities_json = Column(Text, default="[]")
    required_roles_json = Column(Text, default="[]")
    tools_json = Column(Text, default="[]")
    system_prompt = Column(Text, default="")
    status = Column(String, index=True, default="active")
    health_status = Column(String, index=True, default="healthy")
    avg_latency_ms = Column(Integer, default=0)
    success_rate = Column(Float, default=1.0)
    tenant_id = Column(String, index=True, default="default")
    workspace_id = Column(String, index=True, default="default")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class EnterpriseAgentAuditLog(Base):
    __tablename__ = "enterprise_agent_audit_logs"
    id = Column(Integer, primary_key=True)
    run_id = Column(String, index=True, nullable=False)
    supervisor_decision = Column(String, index=True, default="")
    selected_agent = Column(String, index=True, default="")
    actor = Column(String, index=True, default="system")
    message = Column(Text, default="")
    allowed = Column(Boolean, default=True)
    reason = Column(Text, default="")
    latency_ms = Column(Integer, default=0)
    tenant_id = Column(String, index=True, default="default")
    workspace_id = Column(String, index=True, default="default")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class WorkflowTemplate(Base):
    __tablename__ = "enterprise_workflow_templates"
    id = Column(Integer, primary_key=True)
    key = Column(String, index=True, nullable=False)
    name = Column(String, index=True, nullable=False)
    category = Column(String, index=True, default="general")
    description = Column(Text, default="")
    definition_json = Column(Text, default="{}")
    enabled = Column(Boolean, index=True, default=True)
    tenant_id = Column(String, index=True, default="default")
    workspace_id = Column(String, index=True, default="default")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class WorkflowExecution(Base):
    __tablename__ = "enterprise_workflow_executions"
    id = Column(Integer, primary_key=True)
    execution_id = Column(String, unique=True, index=True, nullable=False)
    template_key = Column(String, index=True, nullable=False)
    status = Column(String, index=True, default="running")
    current_step = Column(String, index=True, default="start")
    requested_by = Column(String, index=True, default="system")
    payload_json = Column(Text, default="{}")
    sla_due_at = Column(DateTime(timezone=True), nullable=True)
    tenant_id = Column(String, index=True, default="default")
    workspace_id = Column(String, index=True, default="default")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

class EnterpriseConnector(Base):
    __tablename__ = "enterprise_connectors"
    id = Column(Integer, primary_key=True)
    key = Column(String, index=True, nullable=False)
    name = Column(String, index=True, nullable=False)
    connector_type = Column(String, index=True, nullable=False)
    auth_type = Column(String, index=True, default="none")
    base_url = Column(Text, default="")
    schedule = Column(String, index=True, default="manual")
    secrets_ref = Column(String, default="")
    enabled = Column(Boolean, index=True, default=True)
    health_status = Column(String, index=True, default="not_tested")
    last_sync_status = Column(String, index=True, default="never")
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    metadata_json = Column(Text, default="{}")
    tenant_id = Column(String, index=True, default="default")
    workspace_id = Column(String, index=True, default="default")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class EnterpriseMetricEvent(Base):
    __tablename__ = "enterprise_metric_events"
    id = Column(Integer, primary_key=True)
    metric_type = Column(String, index=True, nullable=False)
    category = Column(String, index=True, default="platform")
    name = Column(String, index=True, nullable=False)
    value = Column(Float, default=1.0)
    unit = Column(String, default="count")
    labels_json = Column(Text, default="{}")
    tenant_id = Column(String, index=True, default="default")
    workspace_id = Column(String, index=True, default="default")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class HumanApprovalRequest(Base):
    # FIX (runtime): table name 'human_approval_requests' collided with the
    # different-shaped HumanApprovalRequest in db/models.py (different columns).
    # SQLAlchemy raised "Table already defined" / "index already exists".
    # Renamed this (enterprise_upgrade-specific) table to a distinct name so
    # both schemas can coexist. No business logic changed.
    __tablename__ = "enterprise_upgrade_approval_requests"
    id = Column(Integer, primary_key=True)
    approval_id = Column(String, unique=True, index=True, nullable=False)
    title = Column(String, index=True, nullable=False)
    action_type = Column(String, index=True, nullable=False)
    resource_type = Column(String, index=True, nullable=False)
    resource_id = Column(String, index=True, nullable=False)
    recommendation = Column(Text, default="")
    risk_level = Column(String, index=True, default="medium")
    status = Column(String, index=True, default="pending")
    required_roles_json = Column(Text, default="[]")
    payload_json = Column(Text, default="{}")
    requested_by = Column(String, index=True, default="system")
    reviewed_by = Column(String, index=True, default="")
    review_comment = Column(Text, default="")
    tenant_id = Column(String, index=True, default="default")
    workspace_id = Column(String, index=True, default="default")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

DEFAULT_AGENT_BLUEPRINTS = [
    {"key":"supervisor","name":"Supervisor Agent","department":"enterprise","capabilities":["task_routing","policy_check","agent_coordination","monitoring"],"roles":["hsaai_admin","department_manager","ai_user"],"tools":["agent_registry","rbac","rag_router","workflow_engine"],"keywords":["حول","وجه","من المسؤول","من يتابع"]},
    {"key":"hr","name":"HR Agent","department":"hr","capabilities":["policies","leave_requests","employee_knowledge","hr_documents"],"roles":["hsaai_admin","department_manager","ai_user"],"tools":["hr_docs","rag","forms"],"keywords":["اجازة","دوام","موظف","توظيف","راتب"]},
    {"key":"finance","name":"Finance Agent","department":"finance","capabilities":["financial_procedures","budgets","procurement","expense_analysis"],"roles":["hsaai_admin","department_manager"],"tools":["finance_rag","tables","reports"],"keywords":["مالية","ميزانية","مصروف","شراء","فاتورة"]},
    {"key":"it","name":"IT Agent","department":"it","capabilities":["technical_support","infrastructure_knowledge","incident_analysis","knowledge_retrieval"],"roles":["hsaai_admin","department_manager","ai_user"],"tools":["tickets","runbooks","logs"],"keywords":["تقنية","دعم","vpn","شبكة","نظام","مشكلة"]},
    {"key":"legal","name":"Legal Agent","department":"legal","capabilities":["compliance","contracts","legal_documents","governance_rules"],"roles":["hsaai_admin","department_manager"],"tools":["legal_rag","contracts","approval_queue"],"keywords":["قانوني","عقد","امتثال","لائحة","حوكمة"]},
]

def to_json(value):
    return json.dumps(value, ensure_ascii=False)

def now_id(prefix: str) -> str:
    return f"{prefix}-{int(datetime.utcnow().timestamp() * 1000)}"
