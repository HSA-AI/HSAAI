"""Add explicit scope to knowledge grants; retain legacy rows in default scope."""
from alembic import op
import sqlalchemy as sa
revision = "0008_knowledge_permission_scope"
down_revision = "0007_approval_controls"
branch_labels = None
depends_on = None


def upgrade():
    existing = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("knowledge_permissions")}
    for name in ("tenant_id", "workspace_id"):
        if name not in existing:
            op.add_column("knowledge_permissions", sa.Column(name, sa.String(64), nullable=False, server_default="default"))
            op.create_index(f"ix_knowledge_permissions_{name}", "knowledge_permissions", [name])


def downgrade():
    raise RuntimeError("Restore a verified backup; do not silently discard grant scope")
