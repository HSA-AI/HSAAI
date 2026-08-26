"""Add enterprise analytics tables

Revision: 0005
Revises: 0004
Create Date: 2026-07-15

Purpose:
    Add analytics_metrics, ai_insights, anomaly_events, analytics_reports tables
    for the Enterprise AI Analytics Center (APP-ANALYTICS)

Risk Level:
    low — New tables only, no changes to existing tables

Backward Compatibility:
    Yes — Adds new tables only

Rollback Strategy:
    DROP TABLE IF EXISTS for all new tables

Safety Notes:
    - Uses IF NOT EXISTS for idempotency
    - All tables include tenant_id, workspace_id, department_id for RLS
    - Composite indexes for tenant-scoped queries
    - GIN indexes on JSONB columns
    - RLS policies enabled on all tables

Author: HSAAI Platform Team <platform@hsaai.group>
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: Union[str, None] = "0004_model_training_tenant_isolation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply the migration."""

    # analytics_metrics
    op.create_table(
        "analytics_metrics",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("metric_key", sa.String(100), nullable=False),
        sa.Column("metric_value", sa.Float, nullable=False),
        sa.Column("metric_unit", sa.String(50), server_default="count"),
        sa.Column("category", sa.String(50), server_default="general"),
        sa.Column("department_id", sa.String(100), server_default="default"),
        sa.Column("workspace_id", sa.String(100), server_default="default"),
        sa.Column("tenant_id", sa.String(100), server_default="default", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        if_not_exists=True,
    )
    op.create_index("idx_analytics_metrics_tenant_dept", "analytics_metrics",
                    ["tenant_id", "department_id", "category"], if_not_exists=True)
    op.create_index("idx_analytics_metrics_key", "analytics_metrics",
                    ["metric_key", "tenant_id"], if_not_exists=True)

    # ai_insights
    op.create_table(
        "ai_insights",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("category", sa.String(50), server_default="general"),
        sa.Column("severity", sa.String(20), server_default="info"),
        sa.Column("confidence_score", sa.Float, server_default="0.85"),
        sa.Column("source_data", postgresql.JSONB(), server_default="{}"),
        sa.Column("model_name", sa.String(100), server_default="hsaai-analytics"),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("tenant_id", sa.String(100), server_default="default", nullable=False),
        sa.Column("workspace_id", sa.String(100), server_default="default"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        if_not_exists=True,
    )
    op.create_index("idx_ai_insights_tenant_severity", "ai_insights",
                    ["tenant_id", "severity", "status"], if_not_exists=True)
    op.execute("CREATE INDEX IF NOT EXISTS idx_ai_insights_source_gin ON ai_insights USING GIN (source_data)")

    # anomaly_events
    op.create_table(
        "anomaly_events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("metric_name", sa.String(100), nullable=False),
        sa.Column("expected_value", sa.Float, nullable=False),
        sa.Column("actual_value", sa.Float, nullable=False),
        sa.Column("deviation_score", sa.Float, nullable=False),
        sa.Column("severity", sa.String(20), server_default="medium"),
        sa.Column("detected_by", sa.String(50), server_default="statistical"),
        sa.Column("status", sa.String(20), server_default="open"),
        sa.Column("tenant_id", sa.String(100), server_default="default", nullable=False),
        sa.Column("workspace_id", sa.String(100), server_default="default"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        if_not_exists=True,
    )
    op.create_index("idx_anomaly_events_tenant_severity", "anomaly_events",
                    ["tenant_id", "severity", "status"], if_not_exists=True)

    # analytics_reports
    op.create_table(
        "analytics_reports",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("report_key", sa.String(100), nullable=False, unique=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, server_default=""),
        sa.Column("report_type", sa.String(50), server_default="dashboard"),
        sa.Column("dashboard_url", sa.String(500), server_default=""),
        sa.Column("powerbi_report_id", sa.String(100), nullable=True),
        sa.Column("permissions", postgresql.JSONB(), server_default="{}"),
        sa.Column("tenant_id", sa.String(100), server_default="default", nullable=False),
        sa.Column("workspace_id", sa.String(100), server_default="default"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        if_not_exists=True,
    )
    op.create_index("idx_analytics_reports_tenant", "analytics_reports",
                    ["tenant_id", "report_type"], if_not_exists=True)
    op.execute("CREATE INDEX IF NOT EXISTS idx_analytics_reports_perms_gin ON analytics_reports USING GIN (permissions)")

    # Enable RLS on all analytics tables
    for table in ["analytics_metrics", "ai_insights", "anomaly_events", "analytics_reports"]:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY tenant_isolation_{table} ON {table} "
                   f"USING (tenant_id = current_setting('app.tenant_id', true)::text)")


def downgrade() -> None:
    """Rollback the migration."""
    for table in ["analytics_reports", "anomaly_events", "ai_insights", "analytics_metrics"]:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
