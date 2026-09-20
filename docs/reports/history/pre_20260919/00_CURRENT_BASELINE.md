# 00_CURRENT_BASELINE

Date: 2026-09-14. Work began from the current preserved project, not from a newly scaffolded replacement. Earlier claimed baseline: Backend 351 PASS, Frontend 38 PASS, 13 E2E skipped, Python coverage 41.92%. This is the historical baseline, not the final result.

Git status was executed and returned exit 128: not a Git repository. No commit SHA, branch or diff is invented. `evidence/baseline-manifest.json` contains SHA-256 for 1437 preserved files. Original/current archive manifests are also recorded in `docs/release/SOURCE_CHANGES.json`.

Internal backups were made before material changes and again before resuming: original baseline archive SHA-256 `5736070884aff0458f5426149026dab7ad35ad930012a0e35f036cf10da7bf2f`; historical HSAAI.zip SHA-256 `9b20669bf2796e931645307eaf7ef0c1becce253ce79ef5c68de33e9082ff444`. The current directory was snapshotted under preservation_20260914 before checkpoint restoration. Checkpoints were versioned; extraction restored a union of paths without deleting source. Temporary dependency/output directories were kept separate.

Architecture inventory: 33 Python service Dockerfiles plus Next.js frontend, 15 Compose files, canonical Kubernetes manifests and Helm, PostgreSQL/Redis/Qdrant/Neo4j, MinIO object storage, Kafka, Keycloak, Ollama/local model, MLflow, Vault/OPA, Prometheus/Grafana/Loki/Tempo/OpenTelemetry/Thanos. Production Compose defines 57 service entries: 33 default long-running, 22 extended-profile long-running, and 2 one-shot jobs. The root development Compose defines 56. The counts do not imply anything ran.

The exact lists of Dockerfiles, Compose, Kubernetes, Helm, CI workflows, services, migrations and tests are in `evidence/architecture-inventory.json` (baseline) and `evidence/architecture-current.json` (final). Main folders: `services`, `packages/common`, `apps/web`, `infrastructure`, `alembic`, `tests`, `.github/workflows`, `scripts`, `docs`, `deployment/native`, `runbooks`. Native/demo utilities are preserved and not presented as production identity/runtime.

Docker executable/socket, kubectl, GPU validation and a target cluster were unavailable. Actual command evidence is retained in `evidence/runtime-attempts.json`. This baseline restriction was never converted into a PASS.
