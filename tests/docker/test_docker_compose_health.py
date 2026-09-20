from pathlib import Path

# FIXED (audit): this test used a CWD-relative path and FAILED (not skipped)
# when run from the repo root — the file actually lives at
# infrastructure/docker/docker-compose.production.yml.
COMPOSE = Path(__file__).resolve().parents[2] / "infrastructure" / "docker" / "docker-compose.production.yml"

def test_production_compose_has_healthchecks_for_core_services():
    text = COMPOSE.read_text()
    # FIXED (audit): service list aligned with the real compose (no `ollama`
    # service exists in this file; llm_gateway does).
    for service in ["frontend", "backend", "postgres", "redis", "qdrant", "keycloak", "llm_gateway", "nginx"]:
        assert f"  {service}:" in text
    assert text.count("healthcheck:") >= 8
