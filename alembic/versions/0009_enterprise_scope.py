"""Add enterprise ownership; preserve legacy records in default/default.

Assign historic rows only after a documented ownership review, never by guessing.
"""
from alembic import op
import sqlalchemy as sa

revision = "0009_enterprise_scope"
down_revision = "0008_knowledge_permission_scope"
branch_labels = None
depends_on = None
TABLES = ("ai_projects", "ai_policies", "ai_risks", "ai_training", "cost_records", "integrations", "connector_logs")


def upgrade():
    bind = op.get_bind()
    for table in TABLES:
        inspector = sa.inspect(bind)
        columns = {column["name"] for column in inspector.get_columns(table)}
        indexes = {index["name"] for index in inspector.get_indexes(table)}
        for name in ("tenant_id", "workspace_id"):
            if name not in columns:
                op.add_column(table, sa.Column(name, sa.String(128), nullable=False, server_default="default"))
            index_name = f"ix_{table}_{name}"
            if index_name not in indexes:
                op.create_index(index_name, table, [name])
        if bind.dialect.name == "postgresql":
            predicate = "tenant_id = current_setting('app.tenant_id', true) AND workspace_id = current_setting('app.workspace_id', true)"
            op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
            op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
            op.execute(f'DROP POLICY IF EXISTS tenant_isolation_{table} ON "{table}"')
            op.execute(f'CREATE POLICY tenant_isolation_{table} ON "{table}" USING ({predicate}) WITH CHECK ({predicate})')


def downgrade():
    raise RuntimeError("Restore a verified backup; downgrading would discard enterprise ownership")
