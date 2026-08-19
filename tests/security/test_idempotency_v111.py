"""
HSAAI v11.1 — Idempotency & Department Agents Test Suite
=========================================================
Tests for:
  1. IdempotencyKeyManager (create, replay, conflict, expire, concurrency)
  2. Department Agents Registry (21 agents)

Coverage target: >95%
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

from backend_core.security.idempotency_v111 import (  # noqa: E402
    DEPARTMENT_AGENTS,
    IdempotencyError,
    IdempotencyKeyConflictError,
    IdempotencyKeyManager,
    get_all_department_agents,
    get_agent_by_name,
    get_agents_by_department,
    get_idempotency_manager,
)


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singletons before each test."""
    import backend_core.security.idempotency_v111 as mod
    mod._idempotency_manager = None
    yield


# ═══════════════════════════════════════════════════════════════════════
# 1. IdempotencyKeyManager Tests
# ═══════════════════════════════════════════════════════════════════════
class TestIdempotencyKeyValidation:
    """Tests for idempotency key validation."""

    @pytest.mark.asyncio
    async def test_empty_key_raises(self):
        mgr = IdempotencyKeyManager()
        async def executor():
            return {"result": "ok"}
        with pytest.raises(IdempotencyError, match="empty"):
            await mgr.execute_idempotent(
                "", "test_op", {"param": 1}, "t1", "u1", executor
            )

    @pytest.mark.asyncio
    async def test_invalid_key_format_raises(self):
        mgr = IdempotencyKeyManager()
        async def executor():
            return {"result": "ok"}
        with pytest.raises(IdempotencyError, match="pattern"):
            await mgr.execute_idempotent(
                "key with spaces!", "test_op", {}, "t1", "u1", executor
            )

    @pytest.mark.asyncio
    async def test_key_too_long_raises(self):
        mgr = IdempotencyKeyManager()
        async def executor():
            return {"result": "ok"}
        long_key = "x" * 129
        with pytest.raises(IdempotencyError, match="pattern"):
            await mgr.execute_idempotent(
                long_key, "test_op", {}, "t1", "u1", executor
            )

    @pytest.mark.asyncio
    async def test_valid_key_accepted(self):
        mgr = IdempotencyKeyManager()
        async def executor():
            return {"result": "ok"}
        result = await mgr.execute_idempotent(
            "valid-key-123", "test_op", {}, "t1", "u1", executor
        )
        assert result["status"] == "executed"


class TestIdempotencyExecution:
    """Tests for idempotent execution."""

    @pytest.mark.asyncio
    async def test_first_request_executes(self):
        mgr = IdempotencyKeyManager()
        call_count = 0
        async def executor():
            nonlocal call_count
            call_count += 1
            return {"result": "data"}
        result = await mgr.execute_idempotent(
            "key-1", "test_op", {"x": 1}, "t1", "u1", executor
        )
        assert result["status"] == "executed"
        assert result["response_data"] == {"result": "data"}
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_duplicate_request_returns_cached_result(self):
        mgr = IdempotencyKeyManager()
        call_count = 0
        async def executor():
            nonlocal call_count
            call_count += 1
            return {"result": "data"}
        # First call
        await mgr.execute_idempotent("key-2", "test_op", {"x": 1}, "t1", "u1", executor)
        # Second call with same key + params
        result = await mgr.execute_idempotent("key-2", "test_op", {"x": 1}, "t1", "u1", executor)
        assert result["status"] == "replayed"
        assert result["response_data"] == {"result": "data"}
        # Executor should only be called once
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_different_params_same_key_raises_conflict(self):
        mgr = IdempotencyKeyManager()
        async def executor():
            return {"result": "data"}
        # First call with params A
        await mgr.execute_idempotent("key-3", "test_op", {"x": 1}, "t1", "u1", executor)
        # Second call with same key but different params
        with pytest.raises(IdempotencyKeyConflictError, match="already used"):
            await mgr.execute_idempotent("key-3", "test_op", {"x": 2}, "t1", "u1", executor)

    @pytest.mark.asyncio
    async def test_different_tenant_same_key_allowed(self):
        """Same idempotency key in different tenants is allowed (tenant isolation)."""
        mgr = IdempotencyKeyManager()
        async def executor():
            return {"result": "data"}
        # Tenant A
        result_a = await mgr.execute_idempotent(
            "shared-key", "test_op", {"x": 1}, "tenant_a", "u1", executor
        )
        assert result_a["status"] == "executed"
        # Tenant B with same key
        result_b = await mgr.execute_idempotent(
            "shared-key", "test_op", {"x": 1}, "tenant_b", "u2", executor
        )
        assert result_b["status"] == "executed"

    @pytest.mark.asyncio
    async def test_failed_operation_recorded(self):
        mgr = IdempotencyKeyManager()
        async def executor():
            raise ValueError("Operation failed")
        with pytest.raises(ValueError):
            await mgr.execute_idempotent("key-fail", "test_op", {}, "t1", "u1", executor)
        # Check status
        status = await mgr.get_status("key-fail", "t1")
        assert status["status"] == "failed"
        assert "Operation failed" in status["error"]

    @pytest.mark.asyncio
    async def test_failed_operation_retry_returns_previous_failure(self):
        """Failed operation returns 'previously_failed' on retry."""
        mgr = IdempotencyKeyManager()
        call_count = 0
        async def executor():
            nonlocal call_count
            call_count += 1
            raise ValueError("Always fails")
        # First attempt fails
        with pytest.raises(ValueError):
            await mgr.execute_idempotent("key-fail-2", "test_op", {}, "t1", "u1", executor)
        # Second attempt with same key
        result = await mgr.execute_idempotent("key-fail-2", "test_op", {}, "t1", "u1", executor)
        assert result["status"] == "previously_failed"
        assert call_count == 1  # Executor not called again


class TestIdempotencyExpiration:
    """Tests for TTL expiration."""

    @pytest.mark.asyncio
    async def test_expired_key_allows_reexecution(self):
        mgr = IdempotencyKeyManager(ttl_hours=0)
        # Manually set very short TTL
        call_count = 0
        async def executor():
            nonlocal call_count
            call_count += 1
            return {"result": "data"}
        # First call
        await mgr.execute_idempotent("key-exp", "test_op", {}, "t1", "u1", executor)
        # Manually expire the entry
        for key in mgr._store:
            mgr._store[key]["expires_at"] = "2020-01-01T00:00:00+00:00"
        # Second call should re-execute (expired)
        result = await mgr.execute_idempotent("key-exp", "test_op", {}, "t1", "u1", executor)
        assert result["status"] == "executed"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_cleanup_expired_removes_old_entries(self):
        mgr = IdempotencyKeyManager()
        async def executor():
            return {"result": "ok"}
        await mgr.execute_idempotent("key-old", "test_op", {}, "t1", "u1", executor)
        # Expire the entry
        for key in mgr._store:
            mgr._store[key]["expires_at"] = "2020-01-01T00:00:00+00:00"
        removed = await mgr.cleanup_expired()
        assert removed == 1
        assert len(mgr._store) == 0


class TestIdempotencyConcurrency:
    """Tests for concurrent request handling."""

    @pytest.mark.asyncio
    async def test_concurrent_same_key_returns_in_flight(self):
        """Two concurrent requests with same key — second returns 'in_flight'."""
        mgr = IdempotencyKeyManager()
        started = asyncio.Event()
        proceed = asyncio.Event()

        async def slow_executor():
            started.set()
            await proceed.wait()
            return {"result": "done"}

        # Start first request in background
        task1 = asyncio.create_task(
            mgr.execute_idempotent("conc-key", "test_op", {"x": 1}, "t1", "u1", slow_executor)
        )
        # Wait for first to start
        await started.wait()
        # Start second concurrent request
        result2 = await mgr.execute_idempotent(
            "conc-key", "test_op", {"x": 1}, "t1", "u1", slow_executor
        )
        assert result2["status"] == "in_flight"
        # Allow first to complete
        proceed.set()
        result1 = await task1
        assert result1["status"] == "executed"


class TestIdempotencyStats:
    """Tests for stats and management."""

    @pytest.mark.asyncio
    async def test_get_stats_returns_summary(self):
        mgr = IdempotencyKeyManager()
        async def executor():
            return {"result": "ok"}
        await mgr.execute_idempotent("k1", "op1", {}, "t1", "u1", executor)
        await mgr.execute_idempotent("k2", "op2", {}, "t1", "u1", executor)
        stats = mgr.get_stats()
        assert stats["total_entries"] == 2
        assert stats["by_status"]["completed"] == 2

    @pytest.mark.asyncio
    async def test_reset_tenant_clears_entries(self):
        mgr = IdempotencyKeyManager()
        async def executor():
            return {"result": "ok"}
        await mgr.execute_idempotent("k1", "op", {}, "t1", "u1", executor)
        await mgr.execute_idempotent("k2", "op", {}, "t2", "u1", executor)
        removed = await mgr.reset_tenant("t1")
        assert removed == 1
        stats = mgr.get_stats()
        assert stats["total_entries"] == 1

    @pytest.mark.asyncio
    async def test_get_status_returns_none_for_unknown_key(self):
        mgr = IdempotencyKeyManager()
        result = await mgr.get_status("unknown", "t1")
        assert result is None

    def test_singleton_returns_same_instance(self):
        m1 = get_idempotency_manager()
        m2 = get_idempotency_manager()
        assert m1 is m2


# ═══════════════════════════════════════════════════════════════════════
# 2. Department Agents Registry Tests
# ═══════════════════════════════════════════════════════════════════════
class TestDepartmentAgentsRegistry:
    """Tests for the 21 department agents registry."""

    def test_all_21_agents_registered(self):
        assert len(DEPARTMENT_AGENTS) == 21

    def test_all_agents_have_required_fields(self):
        required_fields = {
            "name", "name_en", "name_ar", "department", "description",
            "version", "owner", "status", "model_tier", "role",
            "responsibilities", "skills", "tools", "knowledge_sources",
            "rag_collections", "required_permissions", "data_classification",
        }
        for agent in DEPARTMENT_AGENTS:
            missing = required_fields - set(agent.keys())
            assert not missing, f"Agent '{agent.get('name')}' missing fields: {missing}"

    def test_all_agent_names_unique(self):
        names = [a["name"] for a in DEPARTMENT_AGENTS]
        assert len(names) == len(set(names)), "Duplicate agent names found"

    def test_get_agent_by_name(self):
        agent = get_agent_by_name("finance-agent")
        assert agent is not None
        assert agent["department"] == "Finance"

    def test_get_agent_by_name_not_found(self):
        assert get_agent_by_name("nonexistent-agent") is None

    def test_get_agents_by_department(self):
        # Finance department should have at least finance-agent
        finance_agents = get_agents_by_department("Finance")
        assert len(finance_agents) >= 1
        assert all(a["department"] == "Finance" for a in finance_agents)

    def test_all_agents_have_valid_status(self):
        valid_statuses = {"production", "staging", "development", "deprecated"}
        for agent in DEPARTMENT_AGENTS:
            assert agent["status"] in valid_statuses

    def test_all_agents_have_valid_model_tier(self):
        valid_tiers = {"premium", "standard"}
        for agent in DEPARTMENT_AGENTS:
            assert agent["model_tier"] in valid_tiers

    def test_all_agents_have_valid_data_classification(self):
        valid_classifications = {"public", "internal", "confidential", "restricted"}
        for agent in DEPARTMENT_AGENTS:
            assert agent["data_classification"] in valid_classifications

    def test_all_agents_have_at_least_one_permission(self):
        for agent in DEPARTMENT_AGENTS:
            assert len(agent["required_permissions"]) >= 1

    def test_all_agents_have_at_least_one_tool(self):
        for agent in DEPARTMENT_AGENTS:
            assert len(agent["tools"]) >= 1

    def test_all_agents_have_rag_collections(self):
        for agent in DEPARTMENT_AGENTS:
            assert len(agent["rag_collections"]) >= 1

    def test_get_all_department_agents_returns_list(self):
        agents = get_all_department_agents()
        assert isinstance(agents, list)
        assert len(agents) == 21

    @pytest.mark.parametrize("agent_name", [
        "executive-agent", "finance-agent", "hr-agent", "accounting-agent",
        "treasury-agent", "procurement-agent", "supply-chain-agent",
        "manufacturing-agent", "warehouse-agent", "logistics-agent",
        "sales-agent", "marketing-agent", "legal-agent", "audit-agent",
        "compliance-agent", "cybersecurity-agent", "quality-agent",
        "research-agent", "customer-service-agent", "executive-assistant",
        "knowledge-assistant",
    ])
    def test_specific_agent_exists(self, agent_name: str):
        agent = get_agent_by_name(agent_name)
        assert agent is not None, f"Agent '{agent_name}' not found"
