# HSAAI Performance Guide

> Comprehensive performance engineering playbook for the HSAAI platform.
> Covers startup optimisation, memory profiling, DB query tuning,
> caching strategy, load testing, and per-endpoint performance budgets.

---

## Table of Contents

1. [Startup Optimisation Checklist](#1-startup-optimisation-checklist)
2. [Memory Profiling Guide](#2-memory-profiling-guide)
3. [Database Query Optimisation](#3-database-query-optimisation)
4. [Caching Strategy](#4-caching-strategy)
5. [Load Testing Methodology](#5-load-testing-methodology)
6. [Performance Budgets per Endpoint](#6-performance-budgets-per-endpoint)
7. [Continuous Performance Monitoring](#7-continuous-performance-monitoring)

---

## 1. Startup Optimisation Checklist

Cold-start latency directly affects autoscaling responsiveness and the
user experience after a deploy. Target: **< 5s cold start for any
service**, < 2s warm.

### Pre-import
- [ ] Use `python -X importtime main.py` to identify slow imports. Any
      import > 100ms is a candidate for lazy loading.
- [ ] Lazy-load heavy optional deps (`boto3`, `sentence_transformers`,
      `torch`) inside the functions that use them, not at module top.
- [ ] Move `import matplotlib`, `import pandas` (and similar data-science
      stacks) behind feature flags so services that don't need them
      don't pay the 1-2s import cost.

### Application startup
- [ ] Run all I/O initialisation (DB pool warmup, Redis ping, model
      download) in `asyncio.gather(...)` so they run in parallel rather
      than sequentially.
- [ ] Use `@app.on_event("startup")` for FastAPI; for non-FastAPI
      services use `asyncio.create_task(...)` and await before
      `app.run()`.
- [ ] Pre-warm the connection pool with `get_client()` at startup
      (see `packages/common/performance/connection_pool.py`) so the
      first request doesn't pay the TLS handshake cost.
- [ ] Pre-warm the L1 cache with `cache.warm(warmup_fn)` for hot keys
      (top 50 documents, top 10 agents).

### Model loading (LLM gateway)
- [ ] Use vLLM with `--tensor-parallel-size` matching GPU count.
- [ ] Enable prefix caching (`--enable-prefix-caching`) — 30-50%
      latency reduction for system-prompt-heavy workloads.
- [ ] Pre-load the model in a background task while the API is starting
      so the `/health` endpoint is reachable before the model is ready
      (better Kubernetes readiness probe behaviour).

### Settings & config
- [ ] Load `.env` once at process start; do not call `os.getenv()` in
      hot paths.
- [ ] Compile regex patterns at module load (not per-request).
- [ ] Pre-compute JWT signing keys (JWK) at startup, not per-request.

### Verification
```bash
# Time cold start vs warm start
time curl -s http://localhost:8011/health    # cold (after restart)
time curl -s http://localhost:8011/health    # warm (immediately after)
# Difference should be < 100ms
```

---

## 2. Memory Profiling Guide

HSAAI services are long-running async processes. Memory leaks manifest
as gradual RSS growth until OOM-killed. Target: **steady-state RSS
within ±5% over 24h soak test**.

### Tooling
- **`memray`** — modern Python memory profiler. Attach to a running
  process with `memray attach <PID>`; produces a flame graph.
- **`tracemalloc`** — stdlib; good for unit-test-level allocations.
- **`pympler`** — track size of live objects by class.
- **`objgraph`** — visualise reference graphs to find leaks.

### Setup
```bash
pip install memray pympler objgraph
```

### Profiling a service
```python
# In main.py — enable tracemalloc at startup
import tracemalloc
tracemalloc.start(25)  # 25 frames of context per allocation

# Add an admin endpoint to dump the top allocators
@app.get("/debug/memory")
async def memory_snapshot():
    import tracemalloc
    snapshot = tracemalloc.take_snapshot()
    top = snapshot.statistics("lineno")
    return {"top_allocations": [str(s) for s in top[:20]]}
```

### Continuous memory monitoring
```python
# In middleware — record RSS every 60s
import psutil, asyncio
async def memory_monitor():
    while True:
        rss = psutil.Process().memory_info().rss / 1024 / 1024
        # push to Prometheus: hsaai_process_rss_megabytes
        await asyncio.sleep(60)
```

### Common leak patterns in HSAAI
1. **Unbounded in-process caches** — use `LRUCache(max_entries=...)`
   (see `packages/common/performance/cache_strategy.py`), never a raw
   `dict`.
2. **Closures capturing large locals** — avoid `lambda` inside loops
   that capture loop variables.
3. **`httpx.AsyncClient` per request** — use the shared pool from
   `packages/common/performance/connection_pool.py`.
4. **Background tasks without cancellation** — `asyncio.create_task()`
   without storing the Task reference can leak. Always keep the ref
   and cancel on shutdown.
5. **Logging entire request bodies** — use structured logging with
   truncation (see `packages/common/security/structured_logging.py`).

---

## 3. Database Query Optimisation

Target: **p99 query latency < 50ms for indexed reads, < 200ms for
aggregations**.

### Index strategy
- Every foreign key should have an index on the referenced column.
- Every query that filters by `tenant_id` must have a composite index
  `(tenant_id, <other_filter>)` — tenant isolation is the hottest path.
- Use `EXPLAIN ANALYZE` on every new query in code review. Reject PRs
  that introduce sequential scans on tables > 100k rows.

### N+1 query elimination
- Use SQLAlchemy `selectinload()` or `joinedload()` for related rows:
  ```python
  db.query(Document).options(selectinload(Document.chunks)).all()
  ```
- Enable SQL echo in dev: `echo=True` on the engine; grep for `SELECT`
  counts per request — if > 5 for a single endpoint, refactor.

### Connection pool sizing
- Default `pool_size=10` is too small for AI workloads (long-running
  LLM calls hold the connection). Use `pool_size=20, max_overflow=40`
  for backend_core.
- Use `pool_pre_ping=True` to detect stale connections (avoids
  `OperationalError: server closed the connection unexpectedly`).
- Monitor `pool.checkedout()` — if consistently > 80% of pool size,
  scale up.

### Query patterns to avoid
- `SELECT *` — always specify columns (lets Postgres use index-only
  scans).
- `COUNT(*)` on large tables — use estimated counts from `pg_class`
  for dashboards.
- `ORDER BY RANDOM()` — pre-compute a random sample or use
  `TABLESAMPLE BERNOULLI(1)`.
- Cross-tenant JOINs — enforce tenant isolation in the ORM layer, not
  in application code.

### Read replicas
- Route dashboard / analytics queries to a read replica via
  `DATABASE_REPLICA_URL`. Writes stay on primary.
- Use `use_replica=True` on `get_db()` for read-only endpoints.

### Migration safety
- Add indexes with `CREATE INDEX CONCURRENTLY` (Alembic: `op.create_index(..., postgresql_concurrently=True)`).
- Never `ALTER TABLE` a > 1M-row table without a backfill migration
  (see `services/backend_core/run_migrations.py`).

---

## 4. Caching Strategy

HSAAI uses a **three-tier cache** (`packages/common/performance/cache_strategy.py`)
with cache-aside + refresh-ahead.

### Tier responsibilities
| Tier | Latency | Capacity | Use for |
|------|---------|----------|---------|
| L1 (in-process LRU) | < 1ms | ~1k entries | Per-instance hot keys (e.g. RBAC decisions) |
| L2 (Redis) | ~1ms | ~1M entries | Cross-instance shared state (e.g. session, rate-limit counters) |
| L3 (Postgres) | ~10ms | unlimited | Source of truth + cold cache |

### What to cache
- ✅ Document chunks (after embedding) — key: `doc:{doc_id}:chunk:{chunk_id}`
- ✅ Embedding vectors — key: `emb:{model_version}:{sha256(text)[:16]}`
- ✅ Agent routing decisions — key: `route:{agent_id}:{sha256(query)[:16]}`
- ✅ Reranker output for top-K — key: `rerank:{query_hash}:{k}`
- ✅ Compliance policy assessment — key: `compliance:{framework}:{date}`

### What NOT to cache
- ❌ Live user session data (use Redis directly with TTL)
- ❌ Approval workflow state (Postgres is the source of truth)
- ❌ Anything containing PII without encryption at rest

### TTL guidelines
- **Hot reference data** (policies, configs): 1 hour + tag invalidation
- **Document chunks**: 24 hours (re-embed on document update)
- **Embeddings**: 30 days (model_version-tagged, auto-invalidates on swap)
- **Compliance reports**: 7 days (regenerate weekly)

### Tag-based invalidation
When document `d-001` is updated:
```python
await cache.invalidate("doc:d-001", is_tag=True)
# Drops: chunks, embeddings, reranker outputs, RAG responses — anything
# tagged with "doc:d-001" across all three tiers.
```

### Refresh-ahead
For the top 100 most-accessed documents, register a refresh callback:
```python
cache.register_refresh(
    key=f"doc:{doc_id}:summary",
    fetch_fn=lambda: load_summary(doc_id),
    ttl=3600,
)
cache.start_refresh_ahead(interval_seconds=60)
```
The cache proactively refreshes entries before they expire, so users
never wait for a cold L3 fetch.

---

## 5. Load Testing Methodology

### Tools
- **k6** (primary) — `tests/load/k6_loadtest.js`, `tests/load/k6-stress.js`
- **locust** (alt) — `tests/load/locustfile.py`

### Test types
1. **Smoke test** — 10 VUs, 1 minute. Verifies the endpoint works.
2. **Load test** — ramp to expected peak (200 VUs), hold 10 minutes.
   Target: p99 < budget, error rate < 0.1%.
3. **Stress test** — ramp to 2× peak, hold 5 minutes. Identifies the
   cliff (where latency goes parabolic).
4. **Soak test** — 50 VUs, 24 hours. Identifies memory leaks.
5. **Spike test** — instant jump from 10 to 500 VUs. Validates
   autoscaling + circuit breaker behaviour.

### k6 example
```bash
# Smoke
k6 run --vus 10 --duration 1m tests/load/k6_loadtest.js

# Load (200 VUs, 10 min)
k6 run --vus 200 --duration 10m tests/load/k6_loadtest.js

# Stress (find the cliff)
k6 run tests/load/k6-stress.js
```

### What to measure
- **p50, p95, p99 latency** — primary SLIs
- **Error rate** — split by 4xx vs 5xx
- **Throughput (req/s)** — should scale linearly with VUs until the cliff
- **CPU / memory on each service** — `docker stats` or `cadvisor`
- **DB connections** — `pg_stat_activity` count
- **Redis hit rate** — `INFO stats:keyspace_hits / (keyspace_hits + keyspace_misses)`

### Pass criteria
- p99 < budget (see section 6) for 99% of the test window
- Error rate < 0.1% (4xx are user errors, not server faults)
- No OOM kills
- No circuit-breaker trips that don't auto-recover

---

## 6. Performance Budgets per Endpoint

Budgets are **p99 latency targets**. Alerts fire when p99 exceeds the
budget for 5 consecutive minutes.

### API Gateway
| Endpoint | Budget | Notes |
|----------|--------|-------|
| `GET /health` | 50ms | Liveness/readiness probe |
| `POST /v1/chat` (non-streaming) | 5s | Includes LLM call |
| `POST /v1/chat/stream` (TTFT) | 500ms | Time to first token |
| `POST /v1/search` | 800ms | RAG retrieve + rerank |
| `GET /v1/documents/{id}` | 100ms | Cache-aside hit |
| `POST /v1/documents` | 2s | Includes embedding + Qdrant upsert |

### LLM Gateway
| Endpoint | Budget | Notes |
|----------|--------|-------|
| `POST /v1/generate` | 30s | Bounded by model size + prompt length |
| `POST /v1/stream` (TTFT) | 1s | First token |
| `POST /v1/stream` (full) | 60s | Full response |
| `GET /v1/models` | 50ms | Static config |
| `GET /v1/health` | 50ms | GPU ping |

### RAG Engine
| Endpoint | Budget | Notes |
|----------|--------|-------|
| `POST /v1/search` | 500ms | Hybrid (vector + keyword) |
| `POST /v1/embed` | 200ms | Batch of 8 |
| `POST /v1/ingest` | 5s | Per-document, includes chunking |
| `GET /v1/collections` | 100ms | Index lookup |

### Governance
| Endpoint | Budget | Notes |
|----------|--------|-------|
| `POST /v1/access/check` | 50ms | RBAC + ABAC in-memory |
| `POST /v1/risk/score` | 100ms | Pure compute |
| `POST /v1/policy/evaluate` | 100ms | Pure compute |
| `GET /v1/audit/query` | 200ms | Redis cache, falls back to Postgres |
| `POST /v1/governance/evaluate` | 200ms | Risk + policy (no LLM) |

### Backend Core
| Endpoint | Budget | Notes |
|----------|--------|-------|
| `POST /v1/approvals` | 100ms | DB insert + notification (async) |
| `GET /v1/approvals` | 150ms | DB query + serialise |
| `POST /v1/approvals/{id}/decision` | 100ms | DB update + audit |
| `GET /v1/explainability/{id}` | 100ms | Redis L1 hit |
| `GET /v1/explainability/{id}/explain` | 200ms | Compute + Redis |

### Token / cost budgets (per request)
| Operation | Token budget | Notes |
|-----------|--------------|-------|
| Chat (single turn) | 4k input + 1k output | Default context window |
| Chat (multi-turn) | 16k input + 2k output | Sliding window |
| RAG search | 0 tokens | Embedding only |
| Document summary | 8k input + 500 output | Single document |
| Agent reasoning | 32k input + 4k output | Multi-step with tools |

---

## 7. Continuous Performance Monitoring

### Prometheus metrics (from `packages/common/performance/metrics.py`)
- `hsaai_request_latency_seconds` — HTTP latency histogram
- `hsaai_token_usage_total` — LLM token consumption
- `hsaai_cache_hits_total` / `hsaai_cache_misses_total` — cache efficacy
- `hsaai_db_query_duration_seconds` — DB query latency
- `hsaai_in_flight_requests` — concurrency gauge
- `hsaai_errors_total` — error counter

### Grafana dashboards
- **Service overview** — p50/p95/p99 latency, error rate, throughput
- **LLM gateway** — tokens/s, $/hour, TTFT, GPU utilisation
- **RAG engine** — embedding throughput, Qdrant latency, cache hit rate
- **Governance** — risk score distribution, policy deny rate, approval SLA
- **Infra** — CPU, memory, disk, network per service

### Alerting rules (Prometheus)
```yaml
- alert: HighLatencyP99
  expr: histogram_quantile(0.99, rate(hsaai_request_latency_seconds_bucket[5m])) > 1
  for: 5m
  labels: { severity: warning }
  annotations:
    summary: "p99 latency above 1s for {{ $labels.service }}"

- alert: HighErrorRate
  expr: rate(hsaai_errors_total[5m]) > 0.01
  for: 2m
  labels: { severity: critical }

- alert: LowCacheHitRate
  expr: |
    rate(hsaai_cache_hits_total[10m])
    / (rate(hsaai_cache_hits_total[10m]) + rate(hsaai_cache_misses_total[10m]))
    < 0.7
  for: 10m
  labels: { severity: warning }
  annotations:
    summary: "Cache hit rate below 70% for {{ $labels.service }}"
```

### Performance regression testing
- Run the k6 load test in CI on every PR that touches a service.
- Compare p99 against the main branch; fail the build if regression > 10%.
- Use `k6 cloud` or a self-hosted Grafana k6 instance for distributed
  load tests.

---

## Appendix: Quick wins checklist

- [ ] Switch all `httpx.AsyncClient()` per-request calls to the shared
      `get_client()` pool.
- [ ] Add `selectinload()` to every endpoint that returns nested objects.
- [ ] Enable vLLM prefix caching.
- [ ] Pre-warm the L1 cache with the top 50 documents on startup.
- [ ] Set up the `hsaai_request_latency_seconds` histogram on every
      FastAPI service.
- [ ] Add `EXPLAIN ANALYZE` to the code-review checklist for any new
      SQL query.
- [ ] Run a 24-hour soak test before every major release.
