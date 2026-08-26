"""Enable Row Level Security on all enterprise tables.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-20

Purpose:
    Enable PostgreSQL Row Level Security (RLS) on application tables
    that contain tenant-scoped data.

Safety:
    - Does not delete or alter existing data.
    - Uses IF EXISTS / IF NOT EXISTS where applicable.
    - Enables RLS only on existing tables.
    - Creates tenant isolation policies only when the required
      tenant_id column exists.

Important:
    This migration is intentionally defensive. Some installations
    may contain tables created by different schema revisions.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# ---------------------------------------------------------------------------
# Alembic revision identifiers
# ---------------------------------------------------------------------------

revision: str = "0003_enable_rls_all_tables"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# Tables that are expected to be tenant-scoped.
#
# RLS is only enabled when the table actually exists.
# A policy is only created when tenant_id exists.
# ---------------------------------------------------------------------------

TENANT_TABLES = (
    "agent_logs",
    "workflow_executions",
    "agent_memory",
    "agents",
    "ai_cost_records",
    "ai_policies",
    "ai_projects",
    "ai_risks",
    "ai_training",
    "approval_history",
    "audit_logs",
    "connector_logs",
    "cost_records",
    "department_agent_runs",
    "department_agents",
    "department_metrics",
    "document_approval_events",
    "enterprise_approval_requests",
    "executive_alerts",
    "executive_metrics",
    "executive_usage_events",
    "human_approval_requests",
    "integrations",
    "knowledge_analytics_events",
    "knowledge_collections",
    "knowledge_documents",
    "knowledge_entities",
    "knowledge_permissions",
    "knowledge_relationships",
    "knowledge_spaces",
    "knowledge_versions",
    "llm_usage_logs",
    "messages",
    "model_quality_runs",
    "search_logs",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _table_exists(table_name: str) -> bool:
    """Return True when a public table exists."""
    bind = op.get_bind()

    result = bind.execute(
        sa.text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = :table_name
            )
            """
        ),
        {"table_name": table_name},
    )

    return bool(result.scalar())


def _column_exists(table_name: str, column_name: str) -> bool:
    """Return True when a column exists on a public table."""
    bind = op.get_bind()

    result = bind.execute(
        sa.text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = :table_name
                  AND column_name = :column_name
            )
            """
        ),
        {
            "table_name": table_name,
            "column_name": column_name,
        },
    )

    return bool(result.scalar())


def _enable_rls(table_name: str) -> None:
    """Enable RLS safely on an existing table."""
    if not _table_exists(table_name):
        return

    quoted = table_name.replace('"', '""')

    op.execute(
        sa.text(
            f'ALTER TABLE public."{quoted}" ENABLE ROW LEVEL SECURITY'
        )
    )


def _create_tenant_policy(table_name: str) -> None:
    """
    Create a conservative tenant policy.

    The policy uses PostgreSQL's current_setting() with a safe fallback.
    Applications may set:

        SET app.tenant_id = 'tenant-name';

    When no tenant context is supplied, the fallback is 'default'.
    """
    if not _table_exists(table_name):
        return

    if not _column_exists(table_name, "tenant_id"):
        return

    quoted = table_name.replace('"', '""')

    policy_name = f"tenant_isolation_{table_name}".replace('"', '""')

    op.execute(
        sa.text(
            f"""
            DROP POLICY IF EXISTS "{policy_name}"
            ON public."{quoted}"
            """
        )
    )

    op.execute(
        sa.text(
            f"""
            CREATE POLICY "{policy_name}"
            ON public."{quoted}"
            AS PERMISSIVE
            FOR ALL
            USING (
                tenant_id = current_setting(
                    'app.tenant_id',
                    true
                )
                OR (
                    current_setting(
                        'app.tenant_id',
                        true
                    ) IS NULL
                    AND tenant_id = 'default'
                )
            )
            WITH CHECK (
                tenant_id = current_setting(
                    'app.tenant_id',
                    true
                )
                OR (
                    current_setting(
                        'app.tenant_id',
                        true
                    ) IS NULL
                    AND tenant_id = 'default'
                )
            )
            """
        )
    )


# ---------------------------------------------------------------------------
# Upgrade
# ---------------------------------------------------------------------------


def upgrade() -> None:
    """
    Enable RLS and tenant isolation on compatible existing tables.
    """

    for table_name in TENANT_TABLES:
        if not _table_exists(table_name):
            continue

        _enable_rls(table_name)

        if _column_exists(table_name, "tenant_id"):
            _create_tenant_policy(table_name)


# ---------------------------------------------------------------------------
# Downgrade
# ---------------------------------------------------------------------------


def downgrade() -> None:
    """
    Remove the tenant-isolation policies and disable RLS.

    Existing data and tables are preserved.
    """

    for table_name in reversed(TENANT_TABLES):
        if not _table_exists(table_name):
            continue

        if _column_exists(table_name, "tenant_id"):
            quoted = table_name.replace('"', '""')
            policy_name = f"tenant_isolation_{table_name}".replace('"', '""')

            op.execute(
                sa.text(
                    f"""
                    DROP POLICY IF EXISTS "{policy_name}"
                    ON public."{quoted}"
                    """
                )
            )

        quoted = table_name.replace('"', '""')

        op.execute(
            sa.text(
                f'ALTER TABLE public."{quoted}" DISABLE ROW LEVEL SECURITY'
            )
        )
