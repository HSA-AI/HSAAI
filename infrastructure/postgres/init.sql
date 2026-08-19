-- HSAAI PostgreSQL Bootstrap (FIX D-05)
-- ====================================================================
-- IMPORTANT: This file ONLY enables PostgreSQL extensions and creates
-- the database-level roles / default privileges that the application
-- needs BEFORE alembic runs. It does NOT create any application tables,
-- indexes, RLS policies, or seed data — those are ALL owned by Alembic
-- migrations under /alembic/versions/*.py.
--
-- FIX D-05 (HIGH — orphan tables):
--   Previously this file CREATEd five application tables (tenants, users,
--   episodic_memories, documents, audit_log) with NO corresponding ORM
--   models. The application actually uses different, schema-prefixed
--   tables (created by Alembic migration 0001_initial_schema.py:
--   messages, audit_logs, knowledge_documents, etc.). The five tables
--   here were therefore orphaned: nothing read from them, nothing wrote
--   to them, and the row-level security policies + indexes defined on
--   them gave a false sense of tenant isolation for tables that the
--   application never touched. They have been removed. Alembic is the
--   single source of truth for schema; this file only handles extensions
--   and roles.
--
--   The seed data for HSA business-unit tenants (hsa-foods, hsa-retail,
--   ...) has also been removed from here. Tenants are now seeded via
--   Alembic data migrations so the seed step is versioned alongside the
--   schema it depends on.

-- ─── Extensions ──────────────────────────────────────────────────
-- Enable the PostgreSQL extensions the platform depends on. These are
-- safe to CREATE IF NOT EXISTS on every container start.
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";       -- for embeddings (Qdrant fallback / pgvector)
CREATE EXTENSION IF NOT EXISTS "pg_trgm";      -- for fuzzy text search
CREATE EXTENSION IF NOT EXISTS "pgaudit";      -- for database-level audit logging

-- ─── Roles & Default Privileges ──────────────────────────────────
-- The application connects as `hsaai_app`. Alembic migrations run as
-- `hsaai_admin` (the migration role). `platform_svc` is reserved for
-- cross-region logical replication and batch jobs; it carries BYPASSRLS
-- so it can replicate tenant-scoped rows without per-tenant policies
-- firing.
--
-- These roles are created here (rather than in Alembic) because they
-- must exist BEFORE the first migration runs — Alembic needs to GRANT
-- privileges on the schema it creates.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'hsaai_admin') THEN
        CREATE ROLE hsaai_admin WITH LOGIN NOINHERIT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'hsaai_app') THEN
        CREATE ROLE hsaai_app WITH LOGIN NOINHERIT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'platform_svc') THEN
        CREATE ROLE platform_svc WITH LOGIN BYPASSRLS NOINHERIT;
    END IF;
END $$;

-- Default privileges: objects created by hsaai_admin (i.e. by Alembic)
-- are automatically readable/writable by the application role, so we do
-- not have to re-GRANT after every migration.
ALTER DEFAULT PRIVILEGES FOR ROLE hsaai_admin IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO hsaai_app;
ALTER DEFAULT PRIVILEGES FOR ROLE hsaai_admin IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO hsaai_app;

-- The replication/batch role can read everything (it carries BYPASSRLS
-- so RLS policies are not evaluated against it).
ALTER DEFAULT PRIVILEGES FOR ROLE hsaai_admin IN SCHEMA public
    GRANT SELECT ON TABLES TO platform_svc;

DO $$ BEGIN
    RAISE NOTICE 'HSAAI bootstrap complete — extensions + roles ready. Schema is owned by Alembic.';
END $$;
