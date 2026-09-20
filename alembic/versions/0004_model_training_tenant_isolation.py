"""Add tenant_id to all model_training tables for tenant isolation.

Revision ID: 0004_model_training_tenant_isolation
Revises: 0003_enable_rls_all_tables
Create Date: 2026-07-09

FIX D-04 (HIGH — cross-tenant data leak):
    The model_training service tables (datasets, training_jobs, experiments,
    checkpoints, trained_models, deployments, training_logs, gpu_metrics) had
    NO tenant_id column. Any tenant's training data — datasets, model weights,
    experiment metrics, GPU utilisation — was visible to every other tenant
    because every query returned every row regardless of which tenant owned it.

    This migration:
      1. Adds a NOT NULL `tenant_id VARCHAR(64)` column to each table, with a
         server_default of 'default' so pre-existing rows backfill cleanly.
      2. Creates an index on tenant_id for each table (fast tenant-scoped scans).
      3. Enables ROW LEVEL SECURITY and creates a `tenant_isolation_<table>`
         policy on each table so the database — not just the application —
         enforces that a session can only see rows where
         `tenant_id = current_setting('app.tenant_id', true)`.

    The application is expected to `SET app.tenant_id = '<tenant>'` per
    connection (already done for the rest of the platform — see migration
    0003_enable_rls_all_tables.py).

    Downgrade drops the column and the RLS policy. Indexes and policies are
    created with IF NOT EXISTS so the migration is idempotent.
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_model_training_tenant_isolation"
down_revision = "0003_enable_rls_all_tables"
branch_labels = None
depends_on = None


# Every model_training table that needs tenant isolation. Keep this list in
# sync with services/model_training/db/models.py.
MODEL_TRAINING_TABLES = [
    "datasets",
    "training_jobs",
    "experiments",
    "checkpoints",
    "trained_models",
    "deployments",
    "training_logs",
    "gpu_metrics",
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    for table in MODEL_TRAINING_TABLES:
        if table not in existing_tables:
            # Table doesn't exist yet (e.g. running against a partial deploy).
            # Skip — the ORM will create the table with tenant_id already
            # present when the service first starts.
            continue

        columns = [c["name"] for c in inspector.get_columns(table)]

        if "tenant_id" not in columns:
            # Add tenant_id column with a server_default so existing rows
            # backfill to 'default' rather than failing the NOT NULL constraint.
            op.add_column(
                table,
                sa.Column(
                    "tenant_id",
                    sa.String(length=64),
                    nullable=False,
                    server_default="default",
                ),
            )
            op.execute(
                f'CREATE INDEX IF NOT EXISTS "ix_{table}_tenant_id" '
                f'ON "{table}" (tenant_id);'
            )

        # Enable RLS + tenant isolation policy (idempotent).
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY;')
        # FIX I-14: FORCE ROW LEVEL SECURITY — table owner is also subject to RLS.
        op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY;')
        op.execute(
            f'DROP POLICY IF EXISTS tenant_isolation_{table} ON "{table}";'
        )
        op.execute(
            f'CREATE POLICY tenant_isolation_{table} ON "{table}" '
            f"USING (tenant_id = current_setting('app.tenant_id', true));"
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    for table in MODEL_TRAINING_TABLES:
        if table not in existing_tables:
            continue
        op.execute(f'DROP POLICY IF EXISTS tenant_isolation_{table} ON "{table}";')
        op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY;')
        op.execute(f'DROP INDEX IF EXISTS "ix_{table}_tenant_id";')
        columns = [c["name"] for c in inspector.get_columns(table)]
        if "tenant_id" in columns:
            op.drop_column(table, "tenant_id")
