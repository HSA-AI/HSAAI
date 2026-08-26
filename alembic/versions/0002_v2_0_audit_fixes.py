"""v2.0 audit fixes — canonical runtime audit/workflow schema.

Revision ID: 0002
Revises: 0001
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


# ---------------------------------------------------------------------------
# Alembic revision identifiers
# ---------------------------------------------------------------------------

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# Upgrade
# ---------------------------------------------------------------------------

def upgrade() -> None:
    """Apply v2.0 audit/runtime fixes.

    Important:
    - agent_logs is already created by 0001_initial_schema.
    - The canonical column is agent_key, NOT agent_name.
    - Therefore this migration must NOT recreate agent_logs.
    - This migration only adds the missing canonical indexes and creates
      workflow_executions.
    """

    # -----------------------------------------------------------------------
    # agent_logs
    # -----------------------------------------------------------------------
    # agent_logs already exists in migration 0001.
    # Its canonical schema contains:
    #
    #   agent_key
    #   action
    #   input_text
    #   output_text
    #   confidence
    #   latency_ms
    #   success
    #   tenant_id
    #   workspace_id
    #   created_at
    #
    # DO NOT reference agent_name here.

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_agent_logs_created_at
        ON agent_logs (created_at)
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_agent_logs_tenant_workspace
        ON agent_logs (tenant_id, workspace_id)
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_agent_logs_agent_key
        ON agent_logs (agent_key)
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_agent_logs_success
        ON agent_logs (success)
        """
    )

    # -----------------------------------------------------------------------
    # workflow_executions
    # -----------------------------------------------------------------------
    # Runtime history for workflow execution analytics.

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS workflow_executions (
            id BIGSERIAL PRIMARY KEY,

            tenant_id VARCHAR(64) NOT NULL DEFAULT 'default',

            workspace_id VARCHAR(64) NOT NULL DEFAULT 'default',

            workflow_key VARCHAR(128) NOT NULL,

            execution_id VARCHAR(128) UNIQUE,

            status VARCHAR(32) NOT NULL DEFAULT 'pending',

            triggered_by VARCHAR(128),

            started_at TIMESTAMP WITH TIME ZONE,

            completed_at TIMESTAMP WITH TIME ZONE,

            duration_seconds REAL,

            result JSONB,

            error TEXT,

            created_at TIMESTAMP WITH TIME ZONE
                NOT NULL DEFAULT NOW()
        )
        """
    )

    # -----------------------------------------------------------------------
    # workflow_executions indexes
    # -----------------------------------------------------------------------

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_workflow_executions_status
        ON workflow_executions (status)
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_workflow_executions_tenant_workspace
        ON workflow_executions (tenant_id, workspace_id)
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_workflow_executions_workflow_key
        ON workflow_executions (workflow_key)
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_workflow_executions_created_at
        ON workflow_executions (created_at)
        """
    )


# ---------------------------------------------------------------------------
# Downgrade
# ---------------------------------------------------------------------------

def downgrade() -> None:
    """Revert v2.0 audit/runtime fixes.

    agent_logs belongs to migration 0001 and MUST NOT be dropped here.
    """

    op.execute(
        """
        DROP INDEX IF EXISTS ix_workflow_executions_created_at
        """
    )

    op.execute(
        """
        DROP INDEX IF EXISTS ix_workflow_executions_workflow_key
        """
    )

    op.execute(
        """
        DROP INDEX IF EXISTS ix_workflow_executions_tenant_workspace
        """
    )

    op.execute(
        """
        DROP INDEX IF EXISTS ix_workflow_executions_status
        """
    )

    op.execute(
        """
        DROP TABLE IF EXISTS workflow_executions
        """
    )

    op.execute(
        """
        DROP INDEX IF EXISTS ix_agent_logs_success
        """
    )

    op.execute(
        """
        DROP INDEX IF EXISTS ix_agent_logs_agent_key
        """
    )

    op.execute(
        """
        DROP INDEX IF EXISTS ix_agent_logs_tenant_workspace
        """
    )

    op.execute(
        """
        DROP INDEX IF EXISTS ix_agent_logs_created_at
        """
    )
