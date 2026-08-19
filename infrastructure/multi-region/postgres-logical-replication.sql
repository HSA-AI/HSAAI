# HSAAI Cross-Region PostgreSQL Logical Replication (Phase 3 — Scale)
#
# FIX v2.3 (Phase 3): Enables logical replication between PostgreSQL clusters
# in different regions. Each region can be a write-primary for specific tenants,
# with changes propagated to all other regions asynchronously.
#
# Architecture:
#   me-west-1 (write primary for Gulf tenants)
#     ├── Publication: hsaai_gulf_pub (all tables WHERE tenant_id IN Gulf tenants)
#     └── Subscription: hsaai_south_asia_sub, hsaai_europe_sub
#
#   me-south-1 (write primary for South Asia tenants)
#     ├── Publication: hsaai_south_asia_pub (all tables WHERE tenant_id IN South Asia tenants)
#     └── Subscription: hsaai_gulf_sub, hsaai_europe_sub
#
# Conflict resolution: last-write-wins via updated_at column (all tables have it).
#
# FIX I-13: The original SQL used shell-style $REPLICATION_PASSWORD inside the
# CONNECTION string. PostgreSQL does NOT interpolate shell env vars in SQL —
# psql would store the literal string "$REPLICATION_PASSWORD" as the password,
# silently breaking replication. This file now uses psql \set meta-commands to
# read the env var (via `:env ...` backtick expansion) and references it with
# :'var' (quoted-string interpolation). The companion wrapper
# apply-replication.sh exports REPLICATION_PASSWORD and invokes psql against
# this script, ensuring the value is interpolated exactly once per execution.

-- psql reads REPLICATION_PASSWORD from the environment (set by apply-replication.sh)
-- and binds it to a psql variable. :'replication_password' is then expanded as a
-- properly-escaped quoted SQL string literal at the wire level — never as a raw
-- token, never as the literal "$REPLICATION_PASSWORD".
\set REPLICATION_PASSWORD `echo "$REPLICATION_PASSWORD"`

-- ═══════════════════════════════════════════════════════════════
-- me-west-1: Publication for Gulf tenants (source of truth for Gulf data)
-- ═══════════════════════════════════════════════════════════════

-- Create a publication for all HSAAI tables, filtered to Gulf tenants.
-- Only the write-primary region publishes; other regions subscribe.
CREATE PUBLICATION hsaai_gulf_pub FOR ALL TABLES;

-- Add row filters for tenant-scoped tables (Gulf tenants only).
-- This ensures South Asia tenants' data is NOT replicated from this region
-- (their write-primary is me-south-1).
ALTER PUBLICATION hsaai_gulf_pub SET TABLE
  messages,
  audit_logs,
  knowledge_documents,
  knowledge_collections,
  knowledge_spaces,
  department_agents,
  department_agent_runs,
  agents,
  agent_logs,
  agent_memory,
  llm_usage_logs,
  ai_cost_records,
  executive_metrics,
  department_metrics,
  episodic_memories,
  workflow_executions,
  human_approval_requests,
  enterprise_approval_requests
  WHERE (tenant_id IN ('hsa-foods', 'hsa-retail', 'hsa-packaging', 'hsa-corporate'));

-- ═══════════════════════════════════════════════════════════════
-- me-west-1: Subscriptions to other regions (receive their data)
-- ═══════════════════════════════════════════════════════════════

-- FIX I-13: password is interpolated by psql via :'REPLICATION_PASSWORD'
-- (a properly quoted SQL string literal), NOT a raw $REPLICATION_PASSWORD token.
-- Subscribe to me-south-1 (South Asia tenants' data).
CREATE SUBSCRIPTION hsaai_south_asia_sub
  CONNECTION 'host=postgres.me-south-1.hsaai.internal port=5432 dbname=hsaai user=replicator password=' || :'REPLICATION_PASSWORD' || ' sslmode=require'
  PUBLICATION hsaai_south_asia_pub
  WITH (
    copy_data = true,           -- copy existing data on first sync
    create_slot = true,         -- create a replication slot
    slot_name = 'hsaai_south_asia_slot',
    enabled = true,
    synchronous_commit = off,   -- async for performance (eventual consistency)
    binary = true               -- binary format for faster transfer
  );

-- FIX I-13: same interpolation pattern as above.
-- Subscribe to eu-west-1 (Europe read replica's regional writes, if any).
CREATE SUBSCRIPTION hsaai_europe_sub
  CONNECTION 'host=postgres.eu-west-1.hsaai.internal port=5432 dbname=hsaai user=replicator password=' || :'REPLICATION_PASSWORD' || ' sslmode=require'
  PUBLICATION hsaai_europe_pub
  WITH (
    copy_data = true,
    create_slot = true,
    slot_name = 'hsaai_europe_slot',
    enabled = true,
    synchronous_commit = off,
    binary = true
  );

-- ═══════════════════════════════════════════════════════════════
-- Conflict resolution: last-write-wins via updated_at trigger
-- ═══════════════════════════════════════════════════════════════

-- Create a function that resolves conflicts by taking the row with the
-- most recent updated_at timestamp. This is applied via a trigger on
-- every replicated table.
CREATE OR REPLACE FUNCTION resolve_conflict_last_write_wins()
RETURNS TRIGGER AS $$
BEGIN
  -- If the incoming row (NEW) has an older updated_at than the existing
  -- row, skip the update (keep the newer local version).
  -- This prevents stale data from overwriting newer writes during
  -- network partitions.
  IF NEW.updated_at < OLD.updated_at THEN
    RETURN NULL;  -- skip this update
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply the conflict resolution trigger to all replicated tables.
-- (In practice, this is applied via the migration 0004_add_updated_at_and_conflict_triggers.py)
DO $$
DECLARE
  tbl TEXT;
BEGIN
  FOR tbl IN
    SELECT tablename FROM pg_tables
    WHERE schemaname = 'public'
      AND tablename IN (
        'messages', 'audit_logs', 'knowledge_documents', 'knowledge_collections',
        'department_agents', 'agents', 'agent_logs', 'llm_usage_logs',
        'ai_cost_records', 'executive_metrics', 'episodic_memories',
        'workflow_executions'
      )
  LOOP
    EXECUTE format('
      DROP TRIGGER IF EXISTS conflict_resolution_%I ON %I;
      CREATE TRIGGER conflict_resolution_%I
        BEFORE UPDATE ON %I
        FOR EACH ROW
        EXECUTE FUNCTION resolve_conflict_last_write_wins();
    ', tbl, tbl, tbl, tbl);
  END LOOP;
END $$;

-- ═══════════════════════════════════════════════════════════════
-- Replication monitoring views
-- ═══════════════════════════════════════════════════════════════

CREATE OR REPLACE VIEW v_replication_status AS
SELECT
  subname AS subscription_name,
  received_lsn,
  latest_end_lsn,
  latest_end_time,
  NOW() - latest_end_time AS replication_lag,
  CASE
    WHEN NOW() - latest_end_time > INTERVAL '5 minutes' THEN 'critical'
    WHEN NOW() - latest_end_time > INTERVAL '1 minute' THEN 'warning'
    ELSE 'healthy'
  END AS health_status
FROM pg_stat_subscription;
