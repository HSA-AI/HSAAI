"""
HSAAI v10.1 Security Closure — Test Suite
==========================================
Tests for:
  1. APIKeyManager (create/rotate/revoke/expire/validate)
  2. HealthService (liveness/readiness/details)
  3. MetricsService (Prometheus format)
  4. ModuleRegistry (register/validate/query)

Coverage target: >95% on enterprise_security_v101.py
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

import pytest

_BASE = Path(__file__).resolve().parents[2]
_SERVICES = _BASE / "services"
for _p in [str(_SERVICES), str(_BASE / "packages"), str(_BASE / "packages" / "common")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend_core.security.enterprise_security_v101 import (  # noqa: E402
    APIKeyError,
    APIKeyExpiredError,
    APIKeyManager,
    APIKeyNotFoundError,
    APIKeyRevokedError,
    Counter,
    HealthService,
    Histogram,
    MetricsService,
    ModuleRegistry,
    ModuleRegistryError,
    get_api_key_manager,
    get_health_service,
    get_metrics_service,
    get_module_registry,
)


# ═══════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════
@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singletons before each test."""
    import backend_core.security.enterprise_security_v101 as mod
    mod._api_key_manager = None
    mod._health_service = None
    mod._metrics_service = None
    mod._module_registry = None
    yield


# ═══════════════════════════════════════════════════════════════════════
# 1. APIKeyManager Tests
# ═══════════════════════════════════════════════════════════════════════
class TestAPIKeyManagerCreate:
    """Tests for API key creation."""

    def test_create_key_returns_plaintext_and_metadata(self):
        mgr = APIKeyManager()
        result = mgr.create_key(name="test-key", tenant_id="tenant_a")
        assert "plaintext_key" in result
        assert "key_id" in result
        assert result["state"] == "ACTIVE"
        assert result["name"] == "test-key"
        assert result["tenant_id"] == "tenant_a"
        assert "warning" in result

    def test_created_key_has_correct_length(self):
        mgr = APIKeyManager()
        result = mgr.create_key(name="test", tenant_id="t1")
        # 32 bytes hex = 64 chars
        assert len(result["plaintext_key"]) == 64

    def test_create_key_with_custom_ttl(self):
        mgr = APIKeyManager()
        result = mgr.create_key(name="test", tenant_id="t1", ttl_days=30)
        assert "expires_at" in result

    def test_create_key_with_scopes(self):
        mgr = APIKeyManager()
        result = mgr.create_key(name="test", tenant_id="t1", scopes=["read", "write"])
        assert result["scopes"] == ["read", "write"]

    def test_create_key_default_scope_is_wildcard(self):
        mgr = APIKeyManager()
        result = mgr.create_key(name="test", tenant_id="t1")
        assert result["scopes"] == ["*"]

    def test_create_key_empty_name_raises(self):
        mgr = APIKeyManager()
        with pytest.raises(APIKeyError, match="name is required"):
            mgr.create_key(name="", tenant_id="t1")

    def test_create_key_empty_tenant_raises(self):
        mgr = APIKeyManager()
        with pytest.raises(APIKeyError, match="Tenant ID is required"):
            mgr.create_key(name="test", tenant_id="")

    def test_plaintext_key_not_stored(self):
        """Ensure plaintext key is NOT stored in the manager."""
        mgr = APIKeyManager()
        result = mgr.create_key(name="test", tenant_id="t1")
        plaintext = result["plaintext_key"]
        # Check that plaintext is not in any stored record
        for record in mgr._keys.values():
            assert plaintext not in str(record)


class TestAPIKeyManagerValidate:
    """Tests for API key validation."""

    def test_validate_active_key_succeeds(self):
        mgr = APIKeyManager()
        created = mgr.create_key(name="test", tenant_id="t1")
        result = mgr.validate_key(created["plaintext_key"])
        assert result["state"] == "ACTIVE"
        assert result["name"] == "test"

    def test_validate_updates_use_count(self):
        mgr = APIKeyManager()
        created = mgr.create_key(name="test", tenant_id="t1")
        mgr.validate_key(created["plaintext_key"])
        mgr.validate_key(created["plaintext_key"])
        record = mgr._keys[created["key_id"]]
        assert record["use_count"] == 2

    def test_validate_empty_key_raises(self):
        mgr = APIKeyManager()
        with pytest.raises(APIKeyNotFoundError):
            mgr.validate_key("")

    def test_validate_invalid_key_raises(self):
        mgr = APIKeyManager()
        with pytest.raises(APIKeyNotFoundError):
            mgr.validate_key("invalid-key-12345")

    def test_validate_does_not_return_sensitive_fields(self):
        mgr = APIKeyManager()
        created = mgr.create_key(name="test", tenant_id="t1")
        result = mgr.validate_key(created["plaintext_key"])
        assert "key_hash" not in result
        assert "salt" not in result


class TestAPIKeyManagerRotate:
    """Tests for API key rotation."""

    def test_rotate_key_creates_new_key(self):
        mgr = APIKeyManager()
        original = mgr.create_key(name="test", tenant_id="t1")
        rotated = mgr.rotate_key(original["key_id"])
        assert rotated["new_key_id"] != original["key_id"]
        assert "plaintext_key" in rotated

    def test_rotate_key_marks_old_as_rotating(self):
        mgr = APIKeyManager()
        original = mgr.create_key(name="test", tenant_id="t1")
        mgr.rotate_key(original["key_id"])
        old_record = mgr._keys[original["key_id"]]
        assert old_record["state"] == "ROTATING"

    def test_rotated_old_key_still_valid(self):
        """During grace period, old key should still validate."""
        mgr = APIKeyManager()
        original = mgr.create_key(name="test", tenant_id="t1")
        mgr.rotate_key(original["key_id"])
        # Old key should still validate (ROTATING state)
        result = mgr.validate_key(original["plaintext_key"])
        assert result["state"] == "ROTATING"

    def test_rotate_nonexistent_key_raises(self):
        mgr = APIKeyManager()
        with pytest.raises(APIKeyNotFoundError):
            mgr.rotate_key("nonexistent")

    def test_rotate_revoked_key_raises(self):
        mgr = APIKeyManager()
        original = mgr.create_key(name="test", tenant_id="t1")
        mgr.revoke_key(original["key_id"])
        with pytest.raises(APIKeyRevokedError):
            mgr.rotate_key(original["key_id"])


class TestAPIKeyManagerRevoke:
    """Tests for API key revocation."""

    def test_revoke_key_changes_state(self):
        mgr = APIKeyManager()
        original = mgr.create_key(name="test", tenant_id="t1")
        result = mgr.revoke_key(original["key_id"])
        assert result["state"] == "REVOKED"

    def test_revoked_key_cannot_validate(self):
        mgr = APIKeyManager()
        original = mgr.create_key(name="test", tenant_id="t1")
        mgr.revoke_key(original["key_id"])
        with pytest.raises((APIKeyRevokedError, APIKeyNotFoundError)):
            mgr.validate_key(original["plaintext_key"])

    def test_revoke_key_with_reason(self):
        mgr = APIKeyManager()
        original = mgr.create_key(name="test", tenant_id="t1")
        result = mgr.revoke_key(original["key_id"], reason="security_incident")
        assert result.get("revocation_reason") == "security_incident"

    def test_revoke_nonexistent_key_raises(self):
        mgr = APIKeyManager()
        with pytest.raises(APIKeyNotFoundError):
            mgr.revoke_key("nonexistent")


class TestAPIKeyManagerExpire:
    """Tests for API key expiration."""

    def test_expire_key_changes_state(self):
        mgr = APIKeyManager()
        original = mgr.create_key(name="test", tenant_id="t1")
        result = mgr.expire_key(original["key_id"])
        assert result["state"] == "EXPIRED"

    def test_expired_key_cannot_validate(self):
        mgr = APIKeyManager()
        original = mgr.create_key(name="test", tenant_id="t1")
        mgr.expire_key(original["key_id"])
        with pytest.raises((APIKeyExpiredError, APIKeyNotFoundError)):
            mgr.validate_key(original["plaintext_key"])


class TestAPIKeyManagerList:
    """Tests for listing keys."""

    def test_list_keys_returns_all(self):
        mgr = APIKeyManager()
        mgr.create_key(name="k1", tenant_id="t1")
        mgr.create_key(name="k2", tenant_id="t1")
        mgr.create_key(name="k3", tenant_id="t2")
        all_keys = mgr.list_keys()
        assert len(all_keys) == 3

    def test_list_keys_filtered_by_tenant(self):
        mgr = APIKeyManager()
        mgr.create_key(name="k1", tenant_id="t1")
        mgr.create_key(name="k2", tenant_id="t1")
        mgr.create_key(name="k3", tenant_id="t2")
        t1_keys = mgr.list_keys(tenant_id="t1")
        assert len(t1_keys) == 2
        assert all(k["tenant_id"] == "t1" for k in t1_keys)

    def test_list_keys_excludes_sensitive_fields(self):
        mgr = APIKeyManager()
        mgr.create_key(name="k1", tenant_id="t1")
        keys = mgr.list_keys()
        for k in keys:
            assert "key_hash" not in k
            assert "salt" not in k


class TestAPIKeyManagerCleanup:
    """Tests for cleanup_expired."""

    def test_cleanup_expired_removes_expired_keys(self):
        mgr = APIKeyManager()
        # Create key with very short TTL
        original = mgr.create_key(name="test", tenant_id="t1", ttl_days=0)
        # Manually set expires_at to past
        mgr._keys[original["key_id"]]["expires_at"] = "2020-01-01T00:00:00+00:00"
        removed = mgr.cleanup_expired()
        assert removed == 1
        assert mgr._keys[original["key_id"]]["state"] == "EXPIRED"


class TestAPIKeyManagerSingleton:
    def test_get_api_key_manager_returns_singleton(self):
        m1 = get_api_key_manager()
        m2 = get_api_key_manager()
        assert m1 is m2


# ═══════════════════════════════════════════════════════════════════════
# 2. HealthService Tests
# ═══════════════════════════════════════════════════════════════════════
class TestHealthServiceLiveness:
    """Tests for liveness probe."""

    @pytest.mark.asyncio
    async def test_liveness_returns_healthy(self):
        svc = HealthService()
        result = await svc.check_liveness()
        assert result["status"] == "healthy"
        assert "version" in result
        assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_liveness_does_not_check_dependencies(self):
        """Liveness should be fast and not check dependencies."""
        svc = HealthService()
        svc.register_check("slow_dep", lambda: {"status": "healthy"})
        result = await svc.check_liveness()
        assert "services" not in result  # No dependency checks


class TestHealthServiceReadiness:
    """Tests for readiness probe."""

    @pytest.mark.asyncio
    async def test_readiness_healthy_when_all_deps_healthy(self):
        svc = HealthService()
        svc.register_check("qdrant", lambda: {"status": "healthy"})
        svc.register_check("database", lambda: {"status": "healthy"})
        result = await svc.check_readiness()
        assert result["status"] == "healthy"
        assert result["services"]["qdrant"] == "healthy"
        assert result["services"]["database"] == "healthy"

    @pytest.mark.asyncio
    async def test_readiness_degraded_when_dep_unhealthy(self):
        svc = HealthService()
        svc.register_check("qdrant", lambda: {"status": "unhealthy"})
        svc.register_check("database", lambda: {"status": "healthy"})
        result = await svc.check_readiness()
        assert result["status"] == "degraded"

    @pytest.mark.asyncio
    async def test_readiness_unhealthy_when_dep_raises(self):
        svc = HealthService()
        def failing_check():
            raise RuntimeError("Connection refused")
        svc.register_check("qdrant", failing_check)
        result = await svc.check_readiness()
        assert result["status"] == "unhealthy"
        assert "Connection refused" in result["services"]["qdrant"]

    @pytest.mark.asyncio
    async def test_readiness_with_no_checks(self):
        svc = HealthService()
        result = await svc.check_readiness()
        assert result["status"] == "healthy"
        assert result["services"] == {}

    @pytest.mark.asyncio
    async def test_readiness_caches_results(self):
        """Readiness should cache results to avoid overloading dependencies."""
        svc = HealthService()
        call_count = 0
        def counting_check():
            nonlocal call_count
            call_count += 1
            return {"status": "healthy"}
        svc.register_check("qdrant", counting_check)
        await svc.check_readiness()
        await svc.check_readiness()  # Should use cache
        assert call_count == 1  # Only called once due to cache

    @pytest.mark.asyncio
    async def test_readiness_supports_async_checks(self):
        svc = HealthService()
        async def async_check():
            return {"status": "healthy"}
        svc.register_check("async_dep", async_check)
        result = await svc.check_readiness()
        assert result["services"]["async_dep"] == "healthy"


class TestHealthServiceDetails:
    """Tests for /health/details endpoint."""

    @pytest.mark.asyncio
    async def test_details_includes_all_info(self):
        svc = HealthService()
        svc.register_check("qdrant", lambda: {"status": "healthy"})
        result = await svc.get_details()
        assert "status" in result
        assert "version" in result
        assert "services" in result
        assert "details" in result
        assert result["details"]["registered_checks"] == ["qdrant"]
        assert result["details"]["checks_count"] == 1


class TestHealthServiceSingleton:
    def test_get_health_service_returns_singleton(self):
        s1 = get_health_service()
        s2 = get_health_service()
        assert s1 is s2


# ═══════════════════════════════════════════════════════════════════════
# 3. MetricsService Tests
# ═══════════════════════════════════════════════════════════════════════
class TestCounter:
    def test_counter_starts_at_zero(self):
        c = Counter("test_total", "Test counter")
        assert c.get_value() == 0.0

    def test_counter_increment(self):
        c = Counter("test_total", "Test counter")
        c.inc()
        assert c.get_value() == 1.0
        c.inc(5)
        assert c.get_value() == 6.0

    def test_counter_with_labels(self):
        c = Counter("test_total", "Test", labels=["method"])
        c.inc(method="GET")
        c.inc(method="POST")
        c.inc(method="GET")
        assert c.get_value(method="GET") == 2.0
        assert c.get_value(method="POST") == 1.0

    def test_counter_prometheus_format(self):
        c = Counter("test_total", "Test counter", labels=["method"])
        c.inc(method="GET")
        output = c.format_prometheus()
        assert "# HELP test_total Test counter" in output
        assert "# TYPE test_total counter" in output
        assert 'test_total{method="GET"} 1.0' in output


class TestHistogram:
    def test_histogram_records_observations(self):
        h = Histogram("test_latency", "Test latency")
        h.observe(0.1)
        h.observe(0.5)
        assert len(h._observations[()]) == 2

    def test_histogram_prometheus_format(self):
        h = Histogram("test_latency", "Test latency")
        h.observe(0.1)
        h.observe(0.5)
        output = h.format_prometheus()
        assert "# HELP test_latency Test latency" in output
        assert "# TYPE test_latency histogram" in output
        assert "test_latency_bucket" in output
        assert "test_latency_sum" in output
        assert "test_latency_count" in output


class TestMetricsService:
    def test_record_qdrant_request(self):
        svc = MetricsService()
        svc.record_qdrant_request("search", "tenant_a", 0.15)
        assert svc.qdrant_requests_total.get_value(operation="search", tenant_id="tenant_a") == 1.0

    def test_record_qdrant_delete(self):
        svc = MetricsService()
        svc.record_qdrant_delete("tenant_a", "success")
        assert svc.qdrant_delete_operations_total.get_value(tenant_id="tenant_a", status="success") == 1.0

    def test_record_authorization_failure(self):
        svc = MetricsService()
        svc.record_authorization_failure("knowledge:delete", "ai_user")
        assert svc.authorization_failures_total.get_value(permission="knowledge:delete", role="ai_user") == 1.0

    def test_record_tenant_violation(self):
        svc = MetricsService()
        svc.record_tenant_violation("tenant_a", "tenant_b")
        assert svc.tenant_violation_attempts_total.get_value(source_tenant="tenant_a", target_tenant="tenant_b") == 1.0

    def test_record_api_key_rotation(self):
        svc = MetricsService()
        svc.record_api_key_rotation()
        svc.record_api_key_rotation()
        assert svc.api_key_rotation_total.get_value() == 2.0

    def test_record_security_event(self):
        svc = MetricsService()
        svc.record_security_event("auth_failure", "denied")
        assert svc.security_events_total.get_value(event_type="auth_failure", status="denied") == 1.0

    def test_record_http_request(self):
        svc = MetricsService()
        svc.record_http_request("GET", "/api/search", 200, 0.05)
        assert svc.http_requests_total.get_value(method="GET", endpoint="/api/search", status_code="200") == 1.0

    def test_record_application_error(self):
        svc = MetricsService()
        svc.record_application_error("ValueError", "rag_engine")
        assert svc.application_errors_total.get_value(error_type="ValueError", component="rag_engine") == 1.0

    def test_format_prometheus_includes_all_metrics(self):
        svc = MetricsService()
        svc.record_qdrant_request("search", "t1", 0.1)
        output = svc.format_prometheus()
        assert "qdrant_requests_total" in output
        assert "qdrant_delete_operations_total" in output
        assert "qdrant_errors_total" in output
        assert "qdrant_latency_seconds" in output
        assert "authorization_failures_total" in output
        assert "tenant_violation_attempts_total" in output
        assert "api_key_rotation_total" in output
        assert "security_events_total" in output
        assert "http_requests_total" in output
        assert "http_request_duration_seconds" in output
        assert "application_errors_total" in output

    def test_get_metrics_service_returns_singleton(self):
        s1 = get_metrics_service()
        s2 = get_metrics_service()
        assert s1 is s2


# ═══════════════════════════════════════════════════════════════════════
# 4. ModuleRegistry Tests
# ═══════════════════════════════════════════════════════════════════════
class TestModuleRegistryRegister:
    """Tests for module registration."""

    def _valid_module(self) -> dict[str, Any]:
        return {
            "name": "rag-engine",
            "name_en": "RAG Engine",
            "name_ar": "محرك RAG",
            "description": "Retrieval-Augmented Generation engine",
            "version": "9.1.0",
            "type": "ai-platform",
            "status": "production",
            "owner": "AI Platform Team",
            "dependencies": ["qdrant", "postgresql"],
            "interfaces": ["/v1/search", "/v1/ingest"],
            "health_endpoint": "/health",
            "metrics_endpoint": "/metrics",
            "security_level": "internal",
        }

    def test_register_valid_module(self):
        reg = ModuleRegistry()
        result = reg.register(self._valid_module())
        assert result["status"] == "registered"
        assert "module_id" in result

    def test_register_missing_required_field_raises(self):
        reg = ModuleRegistry()
        module = self._valid_module()
        del module["health_endpoint"]
        with pytest.raises(ModuleRegistryError, match="Missing required fields"):
            reg.register(module)

    def test_register_duplicate_name_raises(self):
        reg = ModuleRegistry()
        reg.register(self._valid_module())
        with pytest.raises(ModuleRegistryError, match="already registered"):
            reg.register(self._valid_module())

    def test_register_invalid_status_raises(self):
        reg = ModuleRegistry()
        module = self._valid_module()
        module["status"] = "invalid"
        with pytest.raises(ModuleRegistryError, match="Invalid status"):
            reg.register(module)

    def test_register_invalid_security_level_raises(self):
        reg = ModuleRegistry()
        module = self._valid_module()
        module["security_level"] = "top_secret"
        with pytest.raises(ModuleRegistryError, match="Invalid security_level"):
            reg.register(module)

    def test_register_self_dependency_detected(self):
        reg = ModuleRegistry()
        module = self._valid_module()
        module["dependencies"] = ["rag-engine"]  # Self-dependency
        reg.register(module)
        report = reg.validate_all()
        assert any("Self-dependency" in e for e in report["errors"])


class TestModuleRegistryQuery:
    """Tests for module querying."""

    def test_list_all_modules(self):
        reg = ModuleRegistry()
        reg.register(self._valid_module())
        module2 = self._valid_module()
        module2["name"] = "llm-gateway"
        reg.register(module2)
        assert len(reg.list_modules()) == 2

    def test_list_modules_by_category(self):
        reg = ModuleRegistry()
        reg.register(self._valid_module())
        module2 = self._valid_module()
        module2["name"] = "auth-service"
        module2["type"] = "security"
        reg.register(module2)
        ai_modules = reg.list_modules(category="ai-platform")
        assert len(ai_modules) == 1
        assert ai_modules[0]["name"] == "rag-engine"

    def test_get_module_by_id(self):
        reg = ModuleRegistry()
        result = reg.register(self._valid_module())
        module = reg.get_module(result["module_id"])
        assert module["name"] == "rag-engine"

    def test_get_nonexistent_module_raises(self):
        reg = ModuleRegistry()
        with pytest.raises(ModuleRegistryError, match="not found"):
            reg.get_module("nonexistent")

    def _valid_module(self) -> dict[str, Any]:
        return {
            "name": "rag-engine",
            "name_en": "RAG Engine",
            "name_ar": "محرك RAG",
            "description": "RAG engine",
            "version": "9.1.0",
            "type": "ai-platform",
            "status": "production",
            "owner": "AI Team",
            "dependencies": ["qdrant"],
            "interfaces": ["/v1/search"],
            "health_endpoint": "/health",
            "metrics_endpoint": "/metrics",
            "security_level": "internal",
            "capabilities": {
                "core": ["hybrid-search", "reranking"],
                "ai": ["rag"],
                "business": ["knowledge-retrieval"],
                "automation": ["auto-indexing"],
            },
        }

    def test_find_by_capability(self):
        reg = ModuleRegistry()
        reg.register(self._valid_module())
        results = reg.find_by_capability("hybrid-search")
        assert len(results) == 1
        assert results[0]["name"] == "rag-engine"

    def test_find_by_dependency(self):
        reg = ModuleRegistry()
        reg.register(self._valid_module())
        results = reg.find_by_dependency("qdrant")
        assert len(results) == 1
        assert results[0]["name"] == "rag-engine"


class TestModuleRegistryValidate:
    """Tests for registry validation."""

    def test_validate_all_returns_report(self):
        reg = ModuleRegistry()
        reg.register(self._valid_module())
        report = reg.validate_all()
        assert "total_modules" in report
        assert "valid_modules" in report
        assert "errors" in report
        assert "warnings" in report

    def test_validate_warns_on_non_slash_endpoint(self):
        reg = ModuleRegistry()
        module = self._valid_module()
        module["health_endpoint"] = "health"  # Missing leading /
        reg.register(module)
        report = reg.validate_all()
        assert any("should start with '/'" in w for w in report["warnings"])

    def _valid_module(self) -> dict[str, Any]:
        return {
            "name": "test-module",
            "name_en": "Test",
            "name_ar": "اختبار",
            "description": "Test module",
            "version": "1.0.0",
            "type": "test",
            "status": "production",
            "owner": "Test Team",
            "dependencies": [],
            "interfaces": [],
            "health_endpoint": "/health",
            "metrics_endpoint": "/metrics",
            "security_level": "internal",
        }

    def test_export_registry(self):
        reg = ModuleRegistry()
        reg.register(self._valid_module())
        export = reg.export_registry()
        assert export["registry_version"] == "1.0.0"
        assert export["total_modules"] == 1
        assert len(export["modules"]) == 1
