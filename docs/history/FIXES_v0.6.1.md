# HSAAI v0.6.1 — Corrections & Post-Audit Fixes

> This release corrects every defect discovered during a full engineering audit
> (static + runtime) of v0.6.0. All fixes were **verified by actually booting the
> platform** (PostgreSQL 17 + Redis 8 + Qdrant 1.19 + backend_core + Next.js 15),
> not by code review alone.

## Critical fixes (prevented any fresh deployment from working)

### C-01 · IndentationError in `packages/common/imagination/__init__.py` (line 102+)
Multi-line implicit string concatenation without parentheses raised
`IndentationError` at import time — the module could never load.
**Fix:** wrapped the three concatenated f-strings in parentheses
(counterfactual, combination, paradigm_shift branches).

### C-02 · Missing `alembic` dependency in `services/backend_core/requirements.txt`
`db/database.py` runs `alembic upgrade head` by default (`USE_ALEMBIC=true`),
but `alembic` was never declared → `FileNotFoundError` on every fresh start.
**Fix:** added `alembic==1.14.0` (compatible with pinned SQLAlchemy 2.0.36).

### C-03 · Invalid FK: `department_agent_runs.agent_key → department_agents.key`
The FK target column had no UNIQUE constraint. PostgreSQL rejects this
(`psycopg.errors.InvalidForeignKey`), so `alembic upgrade head` failed on every
fresh database. It was invisible in dev because SQLite (default
`DATABASE_URL=sqlite:///./hsaai.db`) does not enforce FKs by default.
**Fix (3 layers):**
- `services/backend_core/db/models.py`: `key = Column(String(64), unique=True, index=True, nullable=False)`
- `alembic/versions/0001_initial_schema.py`: `unique=True` for fresh installs
- **new** `alembic/versions/0005_dagent_key_unique.py`: idempotent migration that
  detects existing deployments and adds the constraint safely.

### C-04 · Hardcoded `/data` paths crash at import time outside Docker
Module-level `mkdir` on `/data/...` (Docker volume mount) raised
`PermissionError` on any non-Docker environment (bare metal, VM, dev laptop):
- `services/backend_core/security/audit.py` (audit logs)
- `services/rag_engine/main.py` (uploads storage + events DB)
- `services/backend_core/security/encryption.py` (encryption salt)
**Fix:** graceful fallback to `HSAAI_HOME/data/...` (or `cwd/data`) with a clear
warning; Docker behaviour unchanged; `AUDIT_LOG_DIR` / `LOCAL_FILE_STORAGE` /
`RAG_EVENT_DB` / `ENCRYPTION_SALT_PATH` env overrides still take priority.

### C-05 · `/ready` endpoint always returned HTTP 500
`qdrant_health()` is async but was called without `await` inside a sync handler
(`AttributeError: 'coroutine' object has no attribute 'get'`). Same bug class
as FIX-14 (which only fixed `ensure_collection` in startup).
**Fix:** endpoint made `async def`, health call awaited.

## High-priority fixes

### H-01 · Client/server API port mismatch broke browser auth
`apps/web/lib/auth-provider.tsx` fell back to `http://localhost:8080` (the
Keycloak port in docker-compose) while SSR code (`server-auth.ts`) uses
`:8000` (the API gateway). Browser login could never reach the API with
default settings.
**Fix:** client fallback aligned to `http://localhost:8000`.

### H-02 · Duplicate `redis` pin in `services/backend_core/requirements.txt`
`redis==5.2.0` and `redis>=5.0.0` both present (drift risk).
**Fix:** removed the redundant unpinned duplicate.

## Verification performed (runtime, on a fresh PostgreSQL cluster)

| Check | Result |
|---|---|
| Python syntax sweep — 342 files (`services`, `packages`, …) | 0 errors |
| docker-compose.yml parse + build contexts + depends_on | OK (33 services) |
| `.env*` ↔ `backend_core/config.py` env alignment | 0 missing keys |
| `alembic upgrade head` on fresh PostgreSQL 17.11 | OK — 59 tables |
| backend_core boot (uvicorn :8000) | OK |
| `GET /health` | `{"status":"ok"}` |
| `GET /ready` | `ready`, postgresql ok, qdrant `hsaai_knowledge` ok |
| Qdrant collection auto-provision | OK (404 → PUT 200) |
| Next.js 15 production build (`next build`) | OK — 33 static pages |
| Web standalone server (:3000) | OK — auth redirect + `/login` 200 |
| RAG/Qdrant reachability from backend | OK |

## Notes for operators

- Redis default in dev was fine (`redis://localhost:6379/0`); for production set
  `REDIS_URL` explicitly in `.env` (see `.env.production.example`).
- `output: 'standalone'` requires starting with
  `node .next/standalone/server.js` (see `deployment/native/`).
- See `deployment/native/README-NATIVE.md` for the Dockerless deployment path
  (sandboxed environments / CI runners without privileged containers).
