"""Persist critical approval controls without deleting existing requests."""
from alembic import op
import sqlalchemy as sa
revision = "0007_approval_controls"
down_revision = "0006_complete_schema"
branch_labels = None
depends_on = None


def upgrade():
    existing = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("human_approval_requests")}
    columns = [
        sa.Column("risk_level", sa.String(16), nullable=False, server_default="medium"),
        sa.Column("requires_two_person", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("second_approver", sa.String(128), nullable=False, server_default=""),
        sa.Column("sla_hours", sa.Integer(), nullable=False, server_default="24"),
        sa.Column("sla_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("escalated", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("escalation_count", sa.Integer(), nullable=False, server_default="0"),
    ]
    for column in columns:
        if column.name not in existing:
            op.add_column("human_approval_requests", column)
    op.execute(sa.text("UPDATE human_approval_requests SET requires_two_person = true "
                       "WHERE status IN ('pending_first_approval', 'pending_second_approval')"))


def downgrade():
    raise RuntimeError("Non-destructive rollback required: restore the verified pre-upgrade backup")
