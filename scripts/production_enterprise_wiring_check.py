#!/usr/bin/env python3

import json
import sys
from pathlib import Path

CONFIG = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/hsaai-production-compose.json")

if not CONFIG.exists():
    raise SystemExit(f"ERROR: rendered compose JSON not found: {CONFIG}")

data = json.loads(CONFIG.read_text())
services = data.get("services", {})

required = {
    "api-gateway",
    "auth-service",
    "backend-core",
    "web",
    "postgres",
    "redis",
    "qdrant",
    "keycloak",
    "neo4j",
    "minio",
    "minio-init",
    "kafka",
    "ollama",
    "mlflow",
    "model-training",
    "prometheus",
    "grafana",
    "loki",
    "tempo",
    "otel-collector",
    "vault",
    "opa",
    "thanos-sidecar",
    "thanos-store",
    "thanos-query",
    "thanos-compactor",
    "thanos-ruler",
}

missing = sorted(required - set(services))

print("===== REQUIRED ENTERPRISE SERVICES =====")
for name in sorted(required):
    print(("PASS" if name in services else "FAIL"), name)

if missing:
    raise SystemExit(
        "ERROR: missing required production services: " + ", ".join(missing)
    )


def env(service):
    raw = services[service].get("environment", {})
    if isinstance(raw, dict):
        return {str(k): "" if v is None else str(v) for k, v in raw.items()}

    result = {}
    if isinstance(raw, list):
        for item in raw:
            if "=" in str(item):
                k, v = str(item).split("=", 1)
                result[k] = v
    return result


def deps(service):
    raw = services[service].get("depends_on", {})
    if isinstance(raw, dict):
        return set(raw)
    if isinstance(raw, list):
        return set(raw)
    return set()


def require_env_fragment(service, keys, fragment):
    e = env(service)

    for key in keys:
        if fragment in e.get(key, ""):
            print(f"PASS {service}: {key} -> {fragment}")
            return

    raise SystemExit(
        f"ERROR: {service} is not wired to {fragment} through {keys}"
    )


def require_dependency(service, dependency):
    if dependency not in deps(service):
        raise SystemExit(
            f"ERROR: {service} does not depend on {dependency}"
        )

    print(f"PASS {service} -> {dependency}")


# LLM production path.
require_env_fragment(
    "llm-gateway",
    ["OLLAMA_BASE_URL"],
    "ollama:11434",
)

# ML lifecycle.
require_env_fragment(
    "mlflow",
    ["AWS_S3_ENDPOINT", "MLFLOW_S3_ENDPOINT"],
    "minio:9000",
)

require_env_fragment(
    "model-training",
    ["MLFLOW_TRACKING_URI"],
    "mlflow:5000",
)

require_env_fragment(
    "model-training",
    ["MINIO_ENDPOINT", "MLFLOW_S3_ENDPOINT", "AWS_S3_ENDPOINT"],
    "minio:9000",
)

require_dependency("model-training", "mlflow")
require_dependency("model-training", "minio")

# MinIO initialization must wait for MinIO.
require_dependency("minio-init", "minio")

# Thanos topology.
require_dependency("thanos-query", "thanos-sidecar")
require_dependency("thanos-query", "thanos-store")
require_dependency("thanos-sidecar", "minio")
require_dependency("thanos-compactor", "minio")

# Kafka must be referenced by at least one production service.
kafka_refs = []

for service_name in services:
    for key, value in env(service_name).items():
        if "kafka:9092" in value:
            kafka_refs.append((service_name, key))

if not kafka_refs:
    raise SystemExit(
        "ERROR: no production service references kafka:9092"
    )

print("PASS Kafka consumers:")
for service_name, key in kafka_refs:
    print(f"  {service_name}: {key}")

# Validate observability configuration wiring.
otel = Path("infrastructure/monitoring/otel-collector.yaml").read_text()

for expected in (
    "tempo:4317",
    "loki:3100",
):
    if expected not in otel:
        raise SystemExit(
            f"ERROR: OTel collector missing endpoint {expected}"
        )
    print(f"PASS OTel -> {expected}")

# Validate Thanos object-store wiring.
objstore = Path("infrastructure/thanos/objstore.yml").read_text()

if "minio:9000" not in objstore:
    raise SystemExit(
        "ERROR: Thanos object store is not wired to MinIO"
    )

print("PASS Thanos -> MinIO object storage")

print()
print("HSAAI PRODUCTION ENTERPRISE WIRING: PASS")
