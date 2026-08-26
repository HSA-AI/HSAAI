"""Create model_training tables with tenant isolation.

Revision ID: 0006_create_model_training_tables
Revises: 0005
Create Date: 2026-08-20
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0006_create_model_training_tables"
down_revision = "0005"
branch_labels = None
depends_on = None


TENANT_LENGTH = 64

TABLES = [
    "datasets",
    "training_jobs",
    "experiments",
    "checkpoints",
    "trained_models",
    "deployments",
    "training_logs",
    "gpu_metrics",
]


def _enable_tenant_rls(table: str) -> None:
    op.execute(
        f'CREATE INDEX IF NOT EXISTS "ix_{table}_tenant_id" '
        f'ON "{table}" ("tenant_id")'
    )

    op.execute(
        f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'
    )

    op.execute(
        f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'
    )

    op.execute(
        f'DROP POLICY IF EXISTS "tenant_isolation_{table}" ON "{table}"'
    )

    op.execute(
        f'''
        CREATE POLICY "tenant_isolation_{table}"
        ON "{table}"
        USING (
            "tenant_id" = current_setting('app.tenant_id', true)
        )
        '''
    )


def upgrade() -> None:
    # ------------------------------------------------------------------
    # datasets
    # ------------------------------------------------------------------
    op.create_table(
        "datasets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(TENANT_LENGTH),
            nullable=False,
            server_default="default",
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("version", sa.String(64), nullable=False, server_default="v1"),
        sa.Column("format", sa.String(32), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("records_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "validation_status",
            sa.String(32),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "statistics",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_by",
            sa.String(255),
            nullable=False,
            server_default="system",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_index("ix_datasets_tenant_id", "datasets", ["tenant_id"])
    op.create_index("ix_datasets_name", "datasets", ["name"])

    # ------------------------------------------------------------------
    # training_jobs
    # ------------------------------------------------------------------
    op.create_table(
        "training_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(TENANT_LENGTH),
            nullable=False,
            server_default="default",
        ),
        sa.Column("training_name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("base_model", sa.String(255), nullable=False),
        sa.Column(
            "dataset_id",
            sa.Integer(),
            sa.ForeignKey("datasets.id"),
            nullable=True,
        ),
        sa.Column("dataset_path", sa.Text(), nullable=True),
        sa.Column("method", sa.String(32), nullable=False),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="Pending",
        ),
        sa.Column("gpu_device", sa.String(128), nullable=True),
        sa.Column("cpu_limit", sa.String(64), nullable=True),
        sa.Column("ram_limit", sa.String(64), nullable=True),
        sa.Column("vram_limit", sa.String(64), nullable=True),
        sa.Column(
            "created_by",
            sa.String(255),
            nullable=False,
            server_default="system",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column(
            "config",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("output_dir", sa.Text(), nullable=True),
    )

    op.create_index(
        "ix_training_jobs_tenant_id",
        "training_jobs",
        ["tenant_id"],
    )
    op.create_index(
        "ix_training_jobs_training_name",
        "training_jobs",
        ["training_name"],
    )
    op.create_index(
        "ix_training_jobs_base_model",
        "training_jobs",
        ["base_model"],
    )
    op.create_index(
        "ix_training_jobs_status",
        "training_jobs",
        ["status"],
    )
    op.create_index(
        "ix_training_jobs_dataset_id",
        "training_jobs",
        ["dataset_id"],
    )

    # ------------------------------------------------------------------
    # experiments
    # ------------------------------------------------------------------
    op.create_table(
        "experiments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(TENANT_LENGTH),
            nullable=False,
            server_default="default",
        ),
        sa.Column(
            "job_id",
            sa.Integer(),
            sa.ForeignKey("training_jobs.id"),
            nullable=False,
        ),
        sa.Column(
            "hyperparameters",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "metrics",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "runtime_seconds",
            sa.Float(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "gpu_usage",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_index("ix_experiments_tenant_id", "experiments", ["tenant_id"])
    op.create_index("ix_experiments_job_id", "experiments", ["job_id"])

    # ------------------------------------------------------------------
    # checkpoints
    # ------------------------------------------------------------------
    op.create_table(
        "checkpoints",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(TENANT_LENGTH),
            nullable=False,
            server_default="default",
        ),
        sa.Column(
            "job_id",
            sa.Integer(),
            sa.ForeignKey("training_jobs.id"),
            nullable=False,
        ),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("step", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("epoch", sa.Float(), nullable=False, server_default="0"),
        sa.Column(
            "metrics",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_index("ix_checkpoints_tenant_id", "checkpoints", ["tenant_id"])
    op.create_index("ix_checkpoints_job_id", "checkpoints", ["job_id"])

    # ------------------------------------------------------------------
    # trained_models
    # ------------------------------------------------------------------
    op.create_table(
        "trained_models",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(TENANT_LENGTH),
            nullable=False,
            server_default="default",
        ),
        sa.Column("model_name", sa.String(255), nullable=False),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("base_model", sa.String(255), nullable=False),
        sa.Column(
            "dataset_id",
            sa.Integer(),
            sa.ForeignKey("datasets.id"),
            nullable=True,
        ),
        sa.Column("method", sa.String(32), nullable=False),
        sa.Column(
            "metrics",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "owner",
            sa.String(255),
            nullable=False,
            server_default="system",
        ),
        sa.Column("artifact_path", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    op.create_index(
        "ix_trained_models_tenant_id",
        "trained_models",
        ["tenant_id"],
    )
    op.create_index(
        "ix_trained_models_model_name",
        "trained_models",
        ["model_name"],
    )
    op.create_index(
        "ix_trained_models_dataset_id",
        "trained_models",
        ["dataset_id"],
    )

    # ------------------------------------------------------------------
    # deployments
    # ------------------------------------------------------------------
    op.create_table(
        "deployments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(TENANT_LENGTH),
            nullable=False,
            server_default="default",
        ),
        sa.Column(
            "model_id",
            sa.Integer(),
            sa.ForeignKey("trained_models.id"),
            nullable=False,
        ),
        sa.Column("target", sa.String(64), nullable=False),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="Pending",
        ),
        sa.Column("endpoint_url", sa.Text(), nullable=True),
        sa.Column(
            "config",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_index(
        "ix_deployments_tenant_id",
        "deployments",
        ["tenant_id"],
    )
    op.create_index(
        "ix_deployments_model_id",
        "deployments",
        ["model_id"],
    )

    # ------------------------------------------------------------------
    # training_logs
    # ------------------------------------------------------------------
    op.create_table(
        "training_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(TENANT_LENGTH),
            nullable=False,
            server_default="default",
        ),
        sa.Column(
            "job_id",
            sa.Integer(),
            sa.ForeignKey("training_jobs.id"),
            nullable=False,
        ),
        sa.Column(
            "level",
            sa.String(20),
            nullable=False,
            server_default="INFO",
        ),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_index(
        "ix_training_logs_tenant_id",
        "training_logs",
        ["tenant_id"],
    )
    op.create_index(
        "ix_training_logs_job_id",
        "training_logs",
        ["job_id"],
    )

    # ------------------------------------------------------------------
    # gpu_metrics
    # ------------------------------------------------------------------
    op.create_table(
        "gpu_metrics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(TENANT_LENGTH),
            nullable=False,
            server_default="default",
        ),
        sa.Column(
            "job_id",
            sa.Integer(),
            sa.ForeignKey("training_jobs.id"),
            nullable=True,
        ),
        sa.Column("gpu_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "gpu_name",
            sa.String(255),
            nullable=False,
            server_default="unknown",
        ),
        sa.Column("gpu_usage", sa.Float(), nullable=False, server_default="0"),
        sa.Column("vram_usage", sa.Float(), nullable=False, server_default="0"),
        sa.Column("vram_total", sa.Float(), nullable=False, server_default="0"),
        sa.Column("temperature", sa.Float(), nullable=False, server_default="0"),
        sa.Column("power_usage", sa.Float(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_index(
        "ix_gpu_metrics_tenant_id",
        "gpu_metrics",
        ["tenant_id"],
    )
    op.create_index(
        "ix_gpu_metrics_job_id",
        "gpu_metrics",
        ["job_id"],
    )

    # ------------------------------------------------------------------
    # RLS
    # ------------------------------------------------------------------
    for table in TABLES:
        _enable_tenant_rls(table)


def downgrade() -> None:
    # Disable/drop RLS policies first.
    for table in reversed(TABLES):
        op.execute(
            f'DROP POLICY IF EXISTS "tenant_isolation_{table}" ON "{table}"'
        )
        op.execute(
            f'ALTER TABLE "{table}" NO FORCE ROW LEVEL SECURITY'
        )
        op.execute(
            f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY'
        )

    # Drop in reverse dependency order.
    op.drop_table("gpu_metrics")
    op.drop_table("training_logs")
    op.drop_table("deployments")
    op.drop_table("trained_models")
    op.drop_table("checkpoints")
    op.drop_table("experiments")
    op.drop_table("training_jobs")
    op.drop_table("datasets")
