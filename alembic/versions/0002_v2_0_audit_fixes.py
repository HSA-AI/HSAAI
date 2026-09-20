"""v2.0 audit fix — add agent_logs, workflow_executions tables + missing indexes

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-24 00:00:00.000000

v2.0 fixes:
  - Adds agent_logs table (powers real agent metrics in executive dashboards).
  - Adds workflow_executions table (powers real workflow metrics).
  - Adds missing indexes on audit_logs.actor, llm_usage_logs.model/created_at,
    knowledge_documents.checksum, knowledge_relationships.source_key/target_key.

FIX D-01: Corrected table name from kg_relationships → knowledge_relationships
(matching 0001_initial_schema). Was preventing all migrations from running.
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # agent_logs — runtime log for agent executions
    op.execute("""
        CREATE TABLE IF NOT EXISTS agent_logs (
            id BIGSERIAL PRIMARY KEY,
            tenant_id VARCHAR(64) NOT NULL DEFAULT 'default',
            workspace_id VARCHAR(64) NOT NULL DEFAULT 'default',
            agent_name VARCHAR(128) NOT NULL,
            user_id VARCHAR(128),
            message TEXT,
            answer TEXT,
            success BOOLEAN NOT NULL DEFAULT false,
            elapsed_ms INTEGER,
            tokens_used INTEGER DEFAULT 0,
            error TEXT,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_agent_logs_created_at ON agent_logs (created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_agent_logs_tenant_workspace ON agent_logs (tenant_id, workspace_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_agent_logs_agent_name ON agent_logs (agent_name)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_agent_logs_success ON agent_logs (success)")

    # workflow_executions — runtime log for workflow runs
    op.execute("""
        CREATE TABLE IF NOT EXISTS workflow_executions (
            id BIGSERIAL PRIMARY KEY,
            tenant_id VARCHAR(64) NOT NULL DEFAULT 'default',
            workspace_id VARCHAR(64) NOT NULL DEFAULT 'default',
            workflow_key VARCHAR(128) NOT NULL,
            execution_id VARCHAR(128) UNIQUE,
            status VARCHAR(32) NOT NULL DEFAULT 'pending',
            triggered_by VARCHAR(128),
            started_at TIMESTAMP WITH TIME ZONE,
            completed_at TIMESTAMP WITH TIME ZONE,
            duration_seconds REAL,
            current_step VARCHAR(128),
            steps_total INTEGER DEFAULT 0,
            steps_completed INTEGER DEFAULT 0,
            error TEXT,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_workflow_executions_status ON workflow_executions (status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_workflow_executions_tenant_workspace ON workflow_executions (tenant_id, workspace_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_workflow_executions_workflow_key ON workflow_executions (workflow_key)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_workflow_executions_created_at ON workflow_executions (created_at)")

    # v2.0: Add missing indexes for performance
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_actor ON audit_logs (actor)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_created_at ON audit_logs (created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_llm_usage_logs_model ON llm_usage_logs (model)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_llm_usage_logs_created_at ON llm_usage_logs (created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_llm_usage_logs_tenant_workspace ON llm_usage_logs (tenant_id, workspace_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_knowledge_documents_checksum ON knowledge_documents (checksum)")
    # FIX D-01: was 'kg_relationships' — actual table name in 0001 is 'knowledge_relationships'.
    op.execute("CREATE INDEX IF NOT EXISTS ix_knowledge_relationships_source_key ON knowledge_relationships (source_key)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_knowledge_relationships_target_key ON knowledge_relationships (target_key)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_human_approval_requests_approver ON human_approval_requests (approver)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_human_approval_requests_status ON human_approval_requests (status)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_human_approval_requests_status")
    op.execute("DROP INDEX IF EXISTS ix_human_approval_requests_approver")
    op.execute("DROP INDEX IF EXISTS ix_knowledge_relationships_target_key")
    op.execute("DROP INDEX IF EXISTS ix_knowledge_relationships_source_key")
    op.execute("DROP INDEX IF EXISTS ix_knowledge_documents_checksum")
    op.execute("DROP INDEX IF EXISTS ix_llm_usage_logs_tenant_workspace")
    op.execute("DROP INDEX IF EXISTS ix_llm_usage_logs_created_at")
    op.execute("DROP INDEX IF EXISTS ix_llm_usage_logs_model")
    op.execute("DROP INDEX IF EXISTS ix_audit_logs_created_at")
    op.execute("DROP INDEX IF EXISTS ix_audit_logs_actor")
    op.execute("DROP TABLE IF EXISTS workflow_executions")
    op.execute("DROP TABLE IF EXISTS agent_logs")
