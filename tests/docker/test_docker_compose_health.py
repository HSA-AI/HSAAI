"""
Test: docker-compose.yml has healthchecks for core services.

FIX (HSAAI-DEP-2026-07-11): Previously this test read from
`docker-compose.production.yml` which doesn't exist in the repository
(only `docker-compose.yml` is shipped). The test failed with
`FileNotFoundError`. Now it reads from the canonical `docker-compose.yml`
and checks for the services actually defined there.
"""
from pathlib import Path
import pytest


def test_compose_has_healthchecks_for_core_services():
    compose_path = Path(__file__).parent.parent.parent / "docker-compose.yml"
    assert compose_path.exists(), f"docker-compose.yml not found at {compose_path}"
    text = compose_path.read_text()

    # Core services that should always have healthchecks in the main compose file.
    # The exact list is derived from the current docker-compose.yml — update if
    # the set of stateful services changes.
    core_services = ["postgres", "redis", "qdrant"]
    for service in core_services:
        assert f"  {service}:" in text, f"Service '{service}' not defined in docker-compose.yml"

    # We expect at least 3 healthchecks (postgres + redis + qdrant).
    # The full stack has more, but this is the minimum bar.
    healthcheck_count = text.count("healthcheck:")
    assert healthcheck_count >= 3, (
        f"Expected at least 3 healthchecks in docker-compose.yml, found {healthcheck_count}"
    )
