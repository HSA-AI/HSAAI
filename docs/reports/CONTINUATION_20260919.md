# Continuation / download snapshot — 2026-09-19

Latest continuation: 2026-09-19. All previous source paths and fixes retained. Changes add verified tenant/workspace scope to seven CoE/FinOps/integration tables and migration 0009; scope executive metrics and audit reads; repair integration JSON fields and cost totals; propagate workspace to PostgreSQL transaction settings; replace false connection-success claims with configuration-only/not-tested status. Legacy rows remain default/default until documented owner assignment. No destructive downgrade is supplied.

The shared HTTP limiter now fails closed in production, bounds development memory and uses atomic Redis admission. Real native Redis tests cover 80 concurrent requests (7 admitted), outage denial and recovery after restart. All ten additional connectors redact exception details, bound Retry-After, reset successful circuits and isolate Dynamics token audience caches. 92 new tests (34 ownership,10 limiter,48 connectors); the focused regression ran 209 tests successfully.

RAG upload/read/delete findings were identified during review but were NOT changed in this download snapshot: a broad exception catches the PII block HTTPException; document retrieval omits document ACL enforcement; deletion omits workspace filtering and mutation authorization and can report success after a provider error. These remain release blockers. No real enterprise messages were sent in connector tests; HTTP transports are explicit unit boundaries.

Current result: 690 backend passes, zero failures/skips; coverage 56.56%, so the unchanged 80% coverage gate fails. Frontend38 and public E2E2/11 skipped are retained evidence from2026-09-14 and were not rerun in this round. Docker, kubectl and GPU tools remain unavailable.
