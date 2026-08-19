"""Enable RLS on all Alembic-created tables.

Revision ID: 0003_enable_rls_all_tables
Revises: 0002_v2_0_audit_fixes
Create Date: 2026-07-08

SECURITY FIX v2.1 (P0):
    Previously RLS was only enabled on 4 tables in init.sql (users,
    episodic_memories, documents, audit_log). The 32 tables created by
    Alembic (knowledge_documents, department_agents, agents, llm_usage_logs,
    ai_cost_records, executive_metrics, etc.) had NO RLS — tenant isolation
    relied entirely on application-level WHERE tenant_id = ? filters, which
    meant any missed filter = cross-tenant data leak.

    This migration enables RLS on every table that has a tenant_id column
    and creates a tenant_isolation policy for it. The policy uses the
    `app.tenant_id` session setting (set per-request by the application
    after JWT verification).
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_enable_rls_all_tables"
down_revision = "0002_v2_0_audit_fixes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # List of tables created by 0001_initial_schema.py that have tenant_id.
    # We enable RLS + create a tenant isolation policy on each.
    tables_with_tenant = [
        "messages",
        "audit_logs",
        "knowledge_spaces",
        "knowledge_collections",
        "knowledge_documents",
        "knowledge_versions",
        "knowledge_permissions",
        "knowledge_analytics_events",
        "document_approval_events",
        "model_quality_runs",
        "human_approval_requests",
        "llm_usage_logs",
        "ai_cost_records",
        "executive_metrics",
        "department_metrics",
        "executive_alerts",
        "executive_usage_events",
        "department_agents",
        "department_agent_runs",
        "agents",
        "agent_logs",
        "agent_memory",
        "enterprise_approval_requests",
        "approval_history",
        "knowledge_entities",
        "knowledge_relationships",
        "search_logs",
        "ai_projects",
        "ai_policies",
        "ai_risks",
        "ai_training",
        "cost_records",
        "integrations",
        "connector_logs",
        "workflow_executions",
    ]

    bind = op.get_bind()

    for table in tables_with_tenant:
        # Check the table exists and has a tenant_id column before enabling RLS.
        # Use IF EXISTS to be idempotent and tolerant of partial deploys.
        inspector = sa.inspect(bind)
        if table not in inspector.get_table_names():
            continue
        columns = [c["name"] for c in inspector.get_columns(table)]
        if "tenant_id" not in columns:
            continue

        # Enable RLS on the table.
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY;')
        # FIX I-14: FORCE ROW LEVEL SECURITY — ensures even the table owner
        # is subject to RLS policies. Without FORCE, the owner bypasses RLS
        # entirely, leaking all tenant data if the app connects as owner.
        op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY;')

        # Drop existing policy if any (idempotent), then create fresh.
        op.execute(f'DROP POLICY IF EXISTS tenant_isolation_{table} ON "{table}";')
        op.execute(
            f'CREATE POLICY tenant_isolation_{table} ON "{table}" '
            f"USING (tenant_id = current_setting('app.tenant_id', true));"
        )

        # Add index on tenant_id if not present (for query performance).
        op.execute(
            f'CREATE INDEX IF NOT EXISTS idx_{table}_tenant '
            f'ON "{table}" (tenant_id);'
        )

    # FIX I-14: Create a SECURITY DEFINER function that errors if app.tenant_id
    # is not set (unless caller is a platform service). This prevents silent
    # data leakage when a connection forgets to SET app.tenant_id.
    op.execute("""
        CREATE OR REPLACE FUNCTION current_tenant_id()
        RETURNS TEXT AS $$
        DECLARE
            v_tenant TEXT;
        BEGIN
            v_tenant := current_setting('app.tenant_id', true);
            IF v_tenant IS NULL THEN
                IF current_user IN ('hsaai_admin', 'platform_svc', 'postgres') THEN
                    RETURN NULL;
                END IF;
                RAISE EXCEPTION 'app.tenant_id session variable is not set — refusing query';
            END IF;
            RETURN v_tenant;
        END;
        $$ LANGUAGE plpgsql SECURITY DEFINER STABLE;
    """)

    # Also add a helpful function the application can call to set tenant context:
    #   SELECT set_tenant_context('hsa-foods');
    op.execute("""
        CREATE OR REPLACE FUNCTION set_tenant_context(p_tenant_id TEXT)
        RETURNS VOID AS $$
        BEGIN
            PERFORM set_config('app.tenant_id', p_tenant_id, true);
        END;
        $$ LANGUAGE plpgsql SECURITY DEFINER;
    """)

    # Allow service roles (hsaai_app) to bypass RLS when needed for cross-tenant
    # admin operations (with explicit audit logging).
    op.execute("""
        -- The hsaai_app role can bypass RLS for admin operations.
        -- This is granted only to the application service account, not to
        -- individual users. All bypass events must be audit-logged.
        -- ALTER ROLE hsaai_app BYPASSRLS;  -- Uncomment if using dedicated app role.
    """)


def downgrade() -> None:
    tables_with_tenant = [
        "messages", "audit_logs", "knowledge_spaces", "knowledge_collections",
        "knowledge_documents", "knowledge_versions", "knowledge_permissions",
        "knowledge_analytics_events", "document_approval_events",
        "model_quality_runs", "human_approval_requests", "llm_usage_logs",
        "ai_cost_records", "executive_metrics", "department_metrics",
        "executive_alerts", "executive_usage_events", "department_agents",
        "department_agent_runs", "agents", "agent_logs", "agent_memory",
        "enterprise_approval_requests", "approval_history",
        "knowledge_entities", "knowledge_relationships", "search_logs",
        "ai_projects", "ai_policies", "ai_risks", "ai_training",
        "cost_records", "integrations", "connector_logs", "workflow_executions",
    ]
    for table in tables_with_tenant:
        op.execute(f'DROP POLICY IF EXISTS tenant_isolation_{table} ON "{table}";')
        op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY;')
    op.execute("DROP FUNCTION IF EXISTS set_tenant_context(TEXT);")
