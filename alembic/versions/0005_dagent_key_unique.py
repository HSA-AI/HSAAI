"""add unique constraint on department_agents.key

FIX (post-audit): department_agent_runs.agent_key holds a ForeignKey to
department_agents.key, but the target column was not UNIQUE. PostgreSQL
rejects such FKs (InvalidForeignKey) so `alembic upgrade head` (and hence
application startup) failed on every fresh deployment. SQLite used in dev
silently ignored FK enforcement, which is why the bug went unnoticed.

- Fresh deployments: 0001 now creates the column as UNIQUE; this migration
  detects that and becomes a no-op.
- Existing deployments: adds the unique constraint (requires no duplicate
  keys in department_agents, which is the documented invariant).

Revision ID: 0005_dagent_key_unique
Revises: 0004_model_training_tenant_isolation
Create Date: 2026-08-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0005_dagent_key_unique"
down_revision = "0004_model_training_tenant_isolation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "department_agents"
CONSTRAINT = "uq_department_agents_key"


def _unique_already_present(inspector, table_name: str, column_name: str) -> bool:
    """True if a UNIQUE constraint or UNIQUE index already covers column."""
    for uc in inspector.get_unique_constraints(table_name):
        cols = uc.get("column_names") or []
        if cols == [column_name]:
            return True
    for idx in inspector.get_indexes(table_name):
        if idx.get("unique") and list(idx.get("column_names") or []) == [column_name]:
            return True
    return False


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if TABLE not in inspector.get_table_names():
        # Nothing to do (schema created by create_all in dev).
        return
    if _unique_already_present(inspector, TABLE, "key"):
        return
    op.create_unique_constraint(CONSTRAINT, TABLE, ["key"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if TABLE not in inspector.get_table_names():
        return
    if _unique_already_present(inspector, TABLE, "key"):
        try:
            op.drop_constraint(CONSTRAINT, TABLE, type_="unique")
        except Exception:
            # Constraint has a different generated name (pre-0005 installs).
            pass
