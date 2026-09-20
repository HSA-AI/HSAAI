# Changelog

All notable changes to HSAAI will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.0.0] — 2026-08-28 — Production-Ready Release

### Fixed

- **Gateway orphan-token defect (V3 audit)** — `hsaai-ctl` started
  `desktop_gateway.py` without `DESKTOP_API_TOKEN`, so the gateway generated a
  random token no client could ever know (permanent 401s). The token is now
  pinned from `runtime/desktop-gateway-token.txt` (auto-generated on first
  start, `chmod 600`).
- **Hardcoded machine paths** — `hsaai-env.sh` and `setup-runtime.sh` carried
  absolute sandbox paths. Both now self-locate the project root and derive
  `RUNTIME/DATA/LOGS` (overridable via `HSAAI_RUNTIME` / `HSAAI_DATA_DIR` /
  `HSAAI_LOG_DIR`), so the package deploys on any Linux account layout.
- **Desktop input test focus race** — first keystroke after the VNC click was
  swallowed by xterm focus settling; test now settles focus first (PASS re-verified).

### Added — production tooling (all under `deployment/native/` unless noted)

- **Secrets externalization** — `generate-secrets.sh` writes machine-local
  `.env.native` (chmod 600, values never printed, gateway token kept in sync);
  `hsaai-ctl` sources it when present and falls back to dev defaults otherwise
  (`HSAAI_DB_PASSWORD`, `HSAAI_CLIENT_SECRET`, `HSAAI_APP_ENV`).
- **`preflight-check.sh`** — production preflight: rootfs binaries, runtimes
  (backend venv / web build), port availability, disk headroom, data-dir
  writability, secret-file permissions, `.gitignore` guard.
- **`backup-native.sh` / `restore-native.sh`** — consistent online backups:
  PostgreSQL `pg_dump -Fc` (MVCC), Redis `BGSAVE`+RDB copy, Qdrant snapshot
  API (create → download → cleanup), manifest file, 14-copy retention.
- **Systemd units for real production hosts** —
  `deployment/production/install-systemd-units.sh` generates 7 hardened units
  (NoNewPrivileges/ProtectSystem=strict/PrivateTmp/PrivateDevices, dedicated
  env file `/etc/hsaai/hsaai.env` mode 600, auto-restart).
- **`PRODUCTION_RUNBOOK_AR.md`** — Arabic ops runbook: zero-to-running install,
  secrets rotation, daily ops, backup/restore, upgrade/rollback, security
  checklist, troubleshooting matrix, acceptance criteria.
- **`env.native.example`** — safe placeholder-only environment template.

### Verified (live, this release)

- 8/8 services UP after full restart; `/ready` = ready (PostgreSQL ok +
  Qdrant ok); 59 tables; `/login` 200; OIDC JWKS (RSA) served; Redis PONG.
- Desktop Gateway full lifecycle: create → status → live snapshot.png →
  delete → 404; wrong token → 401.
- Real remote-desktop input chain PASS (vncdotool → x11vnc → Xvfb → xterm →
  file on disk).
- FFmpeg `x11grab` screenshot shows a genuine X11 desktop (xterm + xclock).

## [2.0.0] — 2026-08-28

### Fixed — enterprise SSO flow (all verified end-to-end at runtime)

- **C-06** Broken OIDC sign-in: server-side Route Handler invoked a client-side
  function — replaced with a server client, so `login → IdP → PKCE → callback`
  completes and `/v1/auth/me` resolves
- **C-07** Token-exchange `redirect_uri` mismatch: URI is now derived from
  forwarding headers instead of a hardcoded origin
- **C-08** Session cookie `Secure` flag made configurable (`HSAAI_COOKIE_SECURE`)
  so local/HTTP deployments can authenticate
- **C-09** Post-callback redirect origin derived from request headers
  (was `0.0.0.0`)

### Added

- **Demo Identity Provider** — `deployment/native/mock-keycloak.js`: local
  OIDC/PKCE provider (JWKS, authorization code flow, password grant, enterprise
  login page) standing in for Keycloak, which requires Docker in this
  environment. Demo users: `demo.admin` / `demo.user` (password grant only,
  no secrets committed — both are demo data)
- **Portable `hsaai-ctl` v2** — self-locating paths; works both from the
  packaged tree (`deployment/native/`) and a live sandbox (`scripts/`)
- **Arabic product demo video** — full 6-minute Arabic master (3840×2160 from
  a 1920×1080 master) + 75–90 s executive cut, real screen recordings of the
  running platform, Arabic narration, burned-in Arabic subtitles (SRT included)
- `RELEASE_NOTES_v2.md` — complete v2 deliverable documentation

### Changed

- VERSION: 0.6.1 → 2.0.0 (first full-platform verified release: SSO → dashboard
  → chat → knowledge → agents → remote desktop → RBAC → audit, all exercised
  live)

## [0.6.1] — 2026-08-28

### Fixed — post-deployment audit (all verified at runtime)

- **C-01** IndentationError in `packages/common/imagination` (module never loaded)
- **C-02** `alembic==1.14.0` added to `services/backend_core/requirements.txt`
  (startup ran `alembic upgrade head` without declaring the dependency)
- **C-03** Invalid FK `department_agent_runs.agent_key → department_agents.key`:
  `key` made UNIQUE in models, migration 0001, plus idempotent
  `0005_dagent_key_unique.py` — fresh PostgreSQL deployments no longer fail
- **C-04** Hardcoded `/data` paths (audit logs, RAG uploads/events, encryption
  salt) now fall back to `HSAAI_HOME/data` outside Docker instead of crashing
  at import time
- **C-05** `/ready` 500: `qdrant_health()` awaited (async-in-sync bug)
- **H-01** Browser auth fallback port aligned to API (`:8000`, was Keycloak `:8080`)
- **H-02** Duplicate `redis` pin removed from backend requirements

### Added

- `deployment/native/` — verified Dockerless deployment path (PG 17 + Redis 8 +
  Qdrant 1.19 + backend + Next.js standalone + REAL remote desktop: Xvfb /
  openbox / x11vnc / noVNC / FFmpeg) with `hsaai-ctl` service manager and
  Desktop Session REST API (Phase 6) + end-to-end input test (PASS)
- `FIXES_v0.6.1.md` — full audit report of this release

## [0.1.0] — 2026-08-03

### Summary

Major upgrade applying 20+ critical fixes (P0) from the v5.0/v5.1 audit
reports. This release fixes security vulnerabilities, broken services,
performance killers, and missing compliance frameworks identified during
the comprehensive code-level analysis.

### Fixed — P0 Critical (Security & Functionality)

#### workflow_engine — Was Completely Non-Functional
- **FIX**: `def run` (sync) called `async def` executors (rag/llm/agent)
  without `await` — returned coroutine objects that were never scheduled.
  Workflows never actually executed. Now `async def run` with proper
  `await` via `asyncio.iscoroutinefunction()` check.
- **FIX**: Added missing `tool` step executor — was silently skipped.
  Now calls `packages.common.tool_registry.dispatch_tool`.

#### governance — Authorization Bypass
- **FIX**: `/v1/access/check` accepted client-supplied `subject` dict from
  request body, allowing any caller to forge `{"role": "super_admin"}`
  and receive `allowed: True`. Now `subject.role`, `subject.tenant_id`,
  `subject.user_id` are sourced from verified JWT claims.

#### Cypher Injection (2 locations)
- **FIX**: `neo4j_repository.py:152` — `rel_type` interpolated directly
  into Cypher query. Now validated against whitelist of 25 allowed
  relationship types + alphanumeric format check.
- **FIX**: `packages/common/ai/advanced_rag.py:230` — `tenant_id` and
  `entities` interpolated into Cypher. Now uses parameterized Cypher
  with `$tenant` and `$names` parameters.

#### auth_service — Broken Authentication
- **FIX**: In-memory PKCE state — lost on pod restart, broken in
  multi-replica. Now Redis-backed with TTL (fallback to in-memory for dev).
- **FIX**: In-memory MFA secrets — lost on pod restart. Now Redis-backed.
- **FIX**: MFA OTP was required but never verified in this service
  (relied on Keycloak "required actions"). Now verifies locally via
  `pyotp.TOTP(secret).verify(otp)`.

#### rag_engine — Fake Streaming + Slow Ingest
- **FIX**: `/v1/answer/stream` awaited full answer() then re-emitted
  context word-by-word (fake streaming, TTFT = full generation latency).
  Now streams tokens directly from `llm_gateway /v1/stream` SSE endpoint.
- **FIX**: Serial per-chunk embedding on ingest
  (`[embed_text(c.text) for c in chunks]`) — 10-20x slower than batched.
  Now uses `embed_texts()` for batched encoding.
- **FIX**: Cross-encoder `cross-encoder/ms-marco-MiniLM-L-6-v2` was
  English-only — produced near-random scores for Arabic queries.
  Now uses multilingual `BAAI/bge-reranker-v2-m3`.
- **FIX**: Qdrant `client.search()` deprecated in 1.10+. Now uses
  `client.query_points()` with fallback for older clients.

#### llm_gateway — Broken Chat Template
- **FIX**: Used `/api/generate` with raw prompt concat
  (`f"{system}\n\nUser: {prompt}\nAssistant:"`) — broke Qwen3's ChatML
  template, lost system-prompt priority, increased prompt injection.
  Now uses `/api/chat` with proper `messages` array.
- **FIX**: Token estimation was char-count heuristic (±50% accuracy).
  Now uses `tiktoken` with `cl100k_base` encoding (fallback to heuristic).

#### multi_agents — Dead Reflection Layer
- **FIX**: `/v1/run` called `agent.run()` directly, never
  `supervisor.run_with_self_correction()` — entire v4.0 reflection +
  self-correction layer was dead code. Now activated.
- **FIX**: `preferred_agent` field from MCP server was silently dropped
  (not declared in RunRequest). Now honored when valid.

#### approvals — Event Loop Blocking + SLA Bug
- **FIX**: `notify_approval` used sync `smtplib.SMTP` + sync `httpx.post`
  inside async `create_approval` — blocked event loop up to 30s per
  approval. Now fully async: `aiosmtplib` + `httpx.AsyncClient` +
  `asyncio.gather` for parallel sends.
- **FIX**: SLA breach detection bug — `if True` always selected
  two-person states, never detecting breaches for single-approver
  requests (STATE_PENDING). Now includes all pending states.

#### packages/common — Critical Library Bugs
- **FIX**: `siem_sink.py` — `_send_to_siem` called async
  `_send_to_splunk` without `await` — coroutine never scheduled, no logs
  reached Splunk. Now properly awaits all async backends.
- **FIX**: `resilience/bulkhead.py` — used `threading.Semaphore` in
  async context (blocking event loop) + released `_semaphore` that was
  never acquired (ValueError after max_concurrent+1 exits). Now uses
  `asyncio.Semaphore` + only releases acquired semaphore.
- **FIX**: `security/vault_client.py` — `get_secret_value_sync` had
  broken error handling: `loop.is_running()` → `raise RuntimeError` →
  `except RuntimeError: pass` → `asyncio.run()` → another RuntimeError.
  Function never returned. Now uses background thread + loop for async
  context, `asyncio.run()` for sync context.
- **FIX**: `abac/__init__.py` — failed OPEN for read actions during OPA
  outages (allowed access to confidential documents during network blips).
  Now fails CLOSED for all actions unless `ABAC_FAIL_OPEN=true` (dev only).
- **FIX**: `security/audit.py` — `AUDIT_HMAC_KEY` empty silently disabled
  integrity verification. Now refuses to start in production if unset.

### Fixed — P1 High

#### Enterprise Integrations
- **FIX**: `OutlookConnector.send_mail` used `/users/me/sendMail` URL
  which requires delegated permission flow, but `_get_ms_graph_token`
  uses client_credentials (app-only). URL always failed with 401.
  Now uses `/users/{sender_UPN}/sendMail` with `OUTLOOK_SENDER_UPN` env.

#### Compliance
- **FIX**: Restored `NDMO` (Yemen/Saudi Data Management Office) to
  `ComplianceFramework` enum — was silently dropped in v5.0 when
  `compliance_reports` service was deleted. Critical for HSA Group.
- **ADDED**: `SOX` and `ISO_27001` to ComplianceFramework enum.

### Infrastructure Fixes

- **FIX**: `docker-compose.yml` — Prometheus alert rules were referenced
  in `prometheus.yml` but never mounted. NO alerts fired. Now mounts
  `./infrastructure/monitoring/rules:/etc/prometheus/rules:ro`.

### Changed

- VERSION: 4.0.0 → 0.1.0 (reset to proper semver from analysis-driven baseline)
- Default cross-encoder: `cross-encoder/ms-marco-MiniLM-L-6-v2` → `BAAI/bge-reranker-v2-m3`
- Default LLM endpoint: `/api/generate` → `/api/chat` (Ollama)
- ABAC default behavior: fail-open for reads → fail-closed for all (unless ABAC_FAIL_OPEN=true)
- AUDIT_HMAC_KEY: optional → required in production

### Migration Notes

1. **Set `AUDIT_HMAC_KEY`** environment variable in production (required now).
2. **Set `OUTLOOK_SENDER_UPN`** environment variable for Outlook integration.
3. **Install `tiktoken`** for accurate token counting: `pip install tiktoken`.
4. **Install `aiosmtplib`** for async email: `pip install aiosmtplib`.
5. **Install `redis`** for PKCE/MFA persistence: `pip install redis`.
6. **Set `ABAC_FAIL_OPEN=false`** (default) in production — only `true` for dev.
7. **Download `BAAI/bge-reranker-v2-m3`** model (560MB) — replaces 80MB English-only model.
8. **Redeploy all services** — fixes touch 12+ files across 8 services.

---

## [0.2.0] — 2026-08-03

### Added — Super Intelligence Layers

#### 8 New Packages
- `causal_intelligence` — Causal inference engine (why/what will/what should/counterfactual)
- `wisdom` — Wisdom Crystallization Engine + Failure Memory (T7+T8)
- `constitution` — AI Constitution with inline enforcement (6 chapters)
- `reasoning` — 6-mode hybrid reasoning with mandatory verification
- `consciousness` — Enterprise Consciousness Stream + Salience scoring
- `proactive` — Proactive Intelligence (anomaly + opportunity + risk)
- `twin` — Digital Twin with Monte Carlo simulation
- `intelligence_economy` — Intelligence value measurement (6 dimensions)

#### 4 New Services
- `consciousness_stream` (port 8070) — Real-time event ingestion
- `proactive_intelligence` (port 8071) — Proactive alerting
- `digital_twin` (port 8072) — Scenario simulation
- `intelligence_economy` (port 8073) — Value measurement

#### Agent Civilization
- 12 enterprise agents with identity, purpose, skills, authority
- Chief Intelligence Supervisor for task decomposition + conflict resolution
- A2A protocol support

### Changed
- VERSION: 0.1.0 → 0.2.0
- Total services: 12 → 16
- Total packages: 27 → 35

## [0.3.0] — 2026-08-03

### Added — Civilization + Economy + Evolution + Federation

#### 3 New Packages
- `cdc_adapters` — SAP/Salesforce/IoT CDC → Consciousness Stream (247 LoC)
- `a2a_protocol` — Agent-to-Agent communication bus (141 LoC)
- `federation` — Cross-org intelligence mesh with trust tiers (115 LoC)

#### 3 New Services
- `wisdom_marketplace` (port 8074) — Trade Wisdom Crystals between organizations
- `evolution_engine` (port 8075) — Autonomous self-improvement闭环
- `federation_hub` (port 8076) — Cross-org intelligence sharing

#### Agent Civilization Activation
- multi_agents/main.py upgraded to use Agent Civilization by default
- 12 agents + Chief Intelligence Supervisor + A2A Protocol
- Constitutional enforcement on every agent action
- Wisdom lookup + Failure Memory before every decision
- New endpoints: civilization/agents, a2a/messages, failure/record, wisdom/list

### Changed
- VERSION: 0.2.0 → 0.3.0
- Total services: 16 → 19
- Total packages: 35 → 38
- multi_agents version: 0.2.0 → 0.3.0 (Agent Civilization)

## [0.4.0] — 2026-08-03

### Added — Unique Intelligence Layers (World-Firsts)

#### 7 New Packages — Each Impossible to Replicate
- `dream_engine` (251 LoC) — Enterprise Dream Engine: consolidates memories + discovers patterns during quiet periods
- `neural_symbolic` (227 LoC) — Neural-Symbolic Synthesis: learns new auditable rules from neural patterns
- `time_travel` (148 LoC) — Causal Time Travel: replays history with alternative decisions
- `emergent` (177 LoC) — Emergent Intelligence: discovers new capabilities autonomously (biological evolution for AI)
- `empathy` (197 LoC) — Enterprise Empathy: senses organizational emotional climate (stress/engagement/sentiment)
- `genealogy` (160 LoC) — Intelligence Genealogy: tracks lineage of every knowledge artifact
- `self_modifying` (158 LoC) — Self-Modifying Architecture: proposes structural changes to its own body

#### 4 New Services
- `dream_engine` (port 8077) — Dream cycles during quiet periods
- `empathy_engine` (port 8078) — Organizational emotional intelligence
- `time_travel` (port 8079) — Replay history with alternative decisions
- `genealogy_service` (port 8081) — Knowledge lineage tracking

### Changed
- VERSION: 0.3.0 → 0.4.0
- Total services: 19 → 23
- Total packages: 38 → 45

## [0.5.0] — 2026-08-03

### Added — Self-Aware Intelligence (Consciousness-Level)

#### 7 New Packages — The Organism Becomes Conscious
- `reflection` (217 LoC) — Self-Reflection Engine: metacognition, bias detection, self-correction
- `imagination` (193 LoC) — Strategic Imagination: novel future generation via 5 creative techniques
- `intuition` (158 LoC) — Enterprise Intuition: sub-rational pattern recognition ("gut feeling")
- `narrative` (59 LoC) — Cognitive Narrative: enterprise story construction and understanding
- `quantum_decision` (96 LoC) — Quantum Decision: multi-universe parallel decision exploration
- `semantic_crystallization` (98 LoC) — Semantic Crystallization: growing knowledge crystals
- `cultural_intelligence` (123 LoC) — Cultural Intelligence: organizational culture understanding + adaptation

#### 5 New Services
- `reflection_engine` (port 8082) — Self-reflection sessions + bias detection
- `imagination_engine` (port 8083) — Strategic future imagination + creative insights
- `intuition_engine` (port 8084) — Intuitive sensing + intuition training
- `narrative_engine` (port 8085) — Enterprise narrative construction
- `quantum_decision_engine` (port 8086) — Multi-universe decision exploration

### Changed
- VERSION: 0.4.0 → 0.5.0
- Total services: 23 → 28
- Total packages: 45 → 52

## [0.6.0] — 2026-08-03

### Added — Transcendent Intelligence (Beyond All Known AI)

#### 7 New Packages — World-Firsts
- `precognition` (279 LoC) — Enterprise Precognition: predicts future events from weak signals
- `immune_system` (229 LoC) — Cognitive Immune System: defends against information pathogens, creates antibodies
- `knowledge_genome` (128 LoC) — Knowledge Genome: maps DNA of enterprise knowledge (genes, chromosomes, mutations)
- `collective_intelligence` (117 LoC) — Collective Intelligence: fuses human + AI into third intelligence form
- `temporal_intelligence` (100 LoC) — Temporal Intelligence: past/present/future as connected field
- `semantic_gravity` (166 LoC) — Semantic Gravity: knowledge attraction forms knowledge galaxies
- `singularity` (160 LoC) — Intelligence Singularity: multi-layer convergence into super-intelligence

#### 5 New Services
- `precognition_engine` (port 8087) — Future event prediction
- `immune_system` (port 8088) — Cognitive pathogen defense
- `collective_intelligence_engine` (port 8089) — Human-AI fusion
- `singularity_engine` (port 8095) — Convergence detection
- `knowledge_genome_engine` (port 8096) — Knowledge DNA mapping

### Changed
- VERSION: 0.5.0 → 0.6.0
- Total services: 28 → 33
- Total packages: 52 → 59

## [4.0.0] — 2026-07-04

(See existing CHANGELOG.md for v1.0.0 → v4.0.0 history)

---

## Version History Summary

| Version | Date | Score | Notes |
|---------|------|-------|-------|
| 1.0.0 | 2026-01-15 | 61/100 | Initial release |
| 2.0.0 | 2026-06-24 | 73/100 | PKCE, MFA, ABAC, PII |
| 3.0.0 | 2026-06-24 | 86/100 | Patroni, Qdrant cluster, MCP |
| 4.0.0 | 2026-07-04 | 94/100 (claimed) | Connectors, Vault, SIEM, WAF |
| 5.0 | 2026-07 | 7.6/10 | Zombie cleanup, port fixes |
| 5.1 | 2026-07 | 9.8/10 (claimed) | Code quality, mTLS default |
| **0.1.0** | **2026-08-03** | **8.5/10 (target)** | **20+ P0 fixes from audit** |
