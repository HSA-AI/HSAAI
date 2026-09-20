"""Complete missing ORM tables/columns while preserving existing data.
DDL is frozen beside this revision; it never depends on future ORM changes.
"""
import json
from pathlib import Path
from alembic import op
import sqlalchemy as sa
revision = '0006_complete_schema'
down_revision = '0005_dagent_key_unique'
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    if bind.dialect.name != 'postgresql':
        raise RuntimeError('Production migrations require PostgreSQL')
    snapshot = json.loads(Path(__file__).with_name('0006_schema_snapshot.json').read_text())
    existing = set(sa.inspect(bind).get_table_names())
    for table in snapshot:
        if table['name'] not in existing:
            op.execute(sa.text(table['create']))
            for statement in table['indexes']: op.execute(sa.text(statement))
    quote = bind.dialect.identifier_preparer.quote
    for table in ('knowledge_documents', 'knowledge_entities', 'knowledge_relationships'):
        columns = {column['name'] for column in sa.inspect(bind).get_columns(table)}
        if 'extra_metadata' not in columns:
            op.add_column(table, sa.Column('extra_metadata', sa.JSON(), server_default='{}'))
            if 'metadata' in columns:
                name = quote(table)
                op.execute(sa.text(f'ALTER TABLE {name} NO FORCE ROW LEVEL SECURITY'))
                op.execute(sa.text(f'UPDATE {name} SET extra_metadata = "metadata"'))
    inspector = sa.inspect(bind)
    for table in inspector.get_table_names():
        if 'tenant_id' not in {column['name'] for column in inspector.get_columns(table)}: continue
        name, policy = quote(table), quote('tenant_isolation_'+table)
        condition = "tenant_id = NULLIF(current_setting('app.tenant_id', true), '')"
        op.execute(sa.text(f'ALTER TABLE {name} ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'ALTER TABLE {name} FORCE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'DROP POLICY IF EXISTS {policy} ON {name}'))
        op.execute(sa.text(f'CREATE POLICY {policy} ON {name} USING ({condition}) WITH CHECK ({condition})'))
    if bind.execute(sa.text("SELECT 1 FROM pg_roles WHERE rolname='hsaai_app'")).scalar():
        op.execute('GRANT USAGE ON SCHEMA public TO hsaai_app')
        op.execute('GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO hsaai_app')
        op.execute('GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO hsaai_app')
        op.execute('REVOKE INSERT, UPDATE, DELETE ON alembic_version FROM hsaai_app')

def downgrade():
    raise RuntimeError('Non-destructive revision: use a tested backup for schema rollback')
