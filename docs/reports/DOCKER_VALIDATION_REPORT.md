# DOCKER_VALIDATION_REPORT

**Build: BLOCKED. Runtime: BLOCKED. Containers healthy observed: 0/33 required long-running.** The environment has no docker executable, daemon/socket or GPU container runtime. The commands were actually attempted and failed at tool availability (exit 127); this is not an image build failure and cannot establish that images build.

`docker version`, `docker compose version`, `docker info`, `docker compose config`, `docker compose build`, `docker compose up -d`, `docker compose ps`, `docker compose logs`, `docker stats --no-stream`, `docker compose down`, `docker compose build --no-cache`, and the second `up -d` are recorded in `evidence/runtime-attempts.json`. No down command reached a daemon and no existing data volume was deleted. `docker inspect`, DNS/service connectivity and container restart behavior cannot run without containers and remain NOT TESTED.

33 Python Dockerfiles plus a frontend Dockerfile are preserved. Earlier multi-stage/non-root/shared-package/COPY/context fixes remain. Canonical Compose static checks verify source/build context references, dependencies, mounts and network/service declarations. 15/15 Compose YAML files parse successfully; parsing alternate/legacy Compose files is not equivalent to Compose resolution or building each profile.

| Compose file | YAML | Service entries |
|---|---|---|
| docker-compose.gpu.yml | PASS | 1 |
| docker-compose.yml | PASS | 56 |
| docker-compose.production.yml | PASS | 57 |
| infrastructure/mtls/docker-compose.mtls.yml | PASS | 8 |
| infrastructure/monitoring/docker-compose.monitoring.yml | PASS | 6 |
| infrastructure/loki/docker-compose.logging.yml | PASS | 2 |
| infrastructure/redis-sentinel/docker-compose.sentinel.yml | PASS | 6 |
| infrastructure/opa/docker-compose.opa.yml | PASS | 1 |
| infrastructure/qdrant-cluster/docker-compose.cluster.yml | PASS | 4 |
| infrastructure/patroni/docker-compose.ha.yml | PASS | 9 |
| infrastructure/docker/docker-compose.production.yml | PASS | 13 |
| infrastructure/docker/docker-compose.dev.yml | PASS | 16 |
| infrastructure/docker/docker-compose.hsa-internal.yml | PASS | 18 |
| infrastructure/vault/docker-compose.vault.yml | PASS | 2 |
| services/model_training/docker-compose.yml | PASS | 4 |


Production has 57 entries: 33 default long-running, 22 extended-profile services and 2 one-shot jobs (db-migrate/minio-init). All are listed in `evidence/production-service-inventory.json`, including declared Compose checks and Dockerfile HEALTHCHECK where available. Third-party images without an explicit check still need an effective healthcheck review and runtime tests. No checks were disabled to manufacture health.

Reviewed statically: base-image references, multi-stage installation, context/COPY/entrypoints/CMD/ports/volumes/networks, non-root settings, restart/resources, env placeholders, external secrets and debug-off settings. The new backend encryption key is required by Compose and generated privately; its salt stays in the persistent `/data` volume. TLS/reverse proxy/secret ownership must be supplied on the host. Image sizes, digest-level reproducibility, installed dependency resolution, vulnerability scans of images, DNS, logs, CPU/RAM and clean builds remain unverified.

Follow `docs/operations/PRODUCTION_HANDOVER_RUNBOOK_AR.md` on the acceptance host. Do not interpret a valid YAML or passing `scripts/validate_release.py` as Docker build/runtime PASS.
