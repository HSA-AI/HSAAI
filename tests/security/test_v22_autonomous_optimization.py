"""HSAAI v22 — Autonomous Optimization + Connection Pool + Circuit Breaker + Telemetry Tests"""
from __future__ import annotations
import asyncio, sys, time
from pathlib import Path
from typing import Any
import pytest

_BASE = Path(__file__).resolve().parents[2]
_SERVICES = _BASE / "services"
for _p in [str(_SERVICES), str(_BASE / "packages"), str(_BASE / "packages" / "common")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend_core.observability.v22_autonomous_optimization import (  # noqa: E402
    AutonomousOptimizer, CircuitBreakerV2, ConnectionPool, ConnectionPoolError,
    OptimizationError, TelemetryIntegration, retry_with_backoff,
    get_circuit_breaker, get_connection_pool, get_optimizer, get_telemetry,
)

@pytest.fixture(autouse=True)
def reset_singletons():
    import backend_core.observability.v22_autonomous_optimization as mod
    mod._connection_pool = None
    mod._circuit_breaker = None
    mod._telemetry = None
    mod._optimizer = None
    yield


# ═══ ConnectionPool ═══
class TestConnectionPool:
    @pytest.mark.asyncio
    async def test_get_client_creates_client(self):
        pool = ConnectionPool()
        client = await pool.get_client()
        assert client is not None
        assert pool.is_healthy is True
        await pool.close()

    @pytest.mark.asyncio
    async def test_get_client_reuses(self):
        pool = ConnectionPool()
        c1 = await pool.get_client()
        c2 = await pool.get_client()
        assert c1 is c2
        await pool.close()

    @pytest.mark.asyncio
    async def test_stats_tracking(self):
        pool = ConnectionPool()
        await pool.get_client()
        await pool.get_client()
        stats = pool.get_stats()
        assert stats["total_created"] == 1
        assert stats["total_reused"] == 1
        await pool.close()

    @pytest.mark.asyncio
    async def test_close_releases_client(self):
        pool = ConnectionPool()
        await pool.get_client()
        await pool.close()
        assert pool.is_healthy is False

    @pytest.mark.asyncio
    async def test_active_connections(self):
        pool = ConnectionPool()
        assert pool.active_connections == 0
        await pool.close()

    def test_singleton(self):
        assert get_connection_pool() is get_connection_pool()


# ═══ CircuitBreakerV2 ═══
class TestCircuitBreakerV2:
    @pytest.mark.asyncio
    async def test_initial_state_closed(self):
        cb = CircuitBreakerV2(name="test")
        assert cb.state == "closed"
        assert cb.is_closed is True

    @pytest.mark.asyncio
    async def test_opens_after_threshold(self):
        cb = CircuitBreakerV2(name="test", failure_threshold=3)
        await cb.record_failure()
        await cb.record_failure()
        assert cb.state == "closed"
        await cb.record_failure()
        assert cb.state == "open"

    @pytest.mark.asyncio
    async def test_rejects_when_open(self):
        cb = CircuitBreakerV2(name="test", failure_threshold=1)
        await cb.record_failure()
        assert await cb.can_execute() is False

    @pytest.mark.asyncio
    async def test_half_open_after_recovery(self):
        cb = CircuitBreakerV2(name="test", failure_threshold=1, recovery_timeout=0.1)
        await cb.record_failure()
        assert cb.state == "open"
        await asyncio.sleep(0.15)
        assert await cb.can_execute() is True
        assert cb.state == "half_open"

    @pytest.mark.asyncio
    async def test_closes_after_success_threshold(self):
        cb = CircuitBreakerV2(name="test", failure_threshold=1, recovery_timeout=0.1, success_threshold=2)
        await cb.record_failure()
        await asyncio.sleep(0.15)
        await cb.can_execute()  # → half_open
        await cb.record_success()
        assert cb.state == "half_open"
        await cb.record_success()
        assert cb.state == "closed"

    @pytest.mark.asyncio
    async def test_half_open_failure_reopens(self):
        cb = CircuitBreakerV2(name="test", failure_threshold=1, recovery_timeout=0.1)
        await cb.record_failure()
        await asyncio.sleep(0.15)
        await cb.can_execute()  # → half_open
        await cb.record_failure()
        assert cb.state == "open"

    @pytest.mark.asyncio
    async def test_execute_success(self):
        cb = CircuitBreakerV2(name="test")
        async def func(): return "ok"
        result = await cb.execute(func)
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_execute_failure_opens_circuit(self):
        cb = CircuitBreakerV2(name="test", failure_threshold=1)
        async def func(): raise RuntimeError("fail")
        with pytest.raises(RuntimeError):
            await cb.execute(func)
        assert cb.state == "open"

    @pytest.mark.asyncio
    async def test_fallback_when_open(self):
        called_fallback = False
        def fallback():
            nonlocal called_fallback
            called_fallback = True
            return "fallback"
        cb = CircuitBreakerV2(name="test", failure_threshold=1, fallback=fallback)
        async def func(): raise RuntimeError("fail")
        with pytest.raises(RuntimeError):
            await cb.execute(func)
        # Now circuit is open
        result = await cb.execute(func)
        assert result == "fallback"
        assert called_fallback is True

    @pytest.mark.asyncio
    async def test_get_stats(self):
        cb = CircuitBreakerV2(name="test")
        async def func(): return "ok"
        await cb.execute(func)
        stats = cb.get_stats()
        assert stats["total_requests"] == 1
        assert stats["total_successes"] == 1

    def test_singleton(self):
        assert get_circuit_breaker() is get_circuit_breaker()


# ═══ Retry Logic ═══
class TestRetryLogic:
    @pytest.mark.asyncio
    async def test_no_retry_on_success(self):
        call_count = 0
        @retry_with_backoff(max_retries=3, initial_delay=0.01)
        async def func():
            nonlocal call_count
            call_count += 1
            return "ok"
        result = await func()
        assert result == "ok"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_timeout(self):
        call_count = 0
        @retry_with_backoff(max_retries=3, initial_delay=0.01)
        async def func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                import httpx
                raise httpx.TimeoutException("timeout")
            return "recovered"
        result = await func()
        assert result == "recovered"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        import httpx
        call_count = 0
        @retry_with_backoff(max_retries=2, initial_delay=0.01)
        async def func():
            nonlocal call_count
            call_count += 1
            raise httpx.TimeoutException("always timeout")
        with pytest.raises(httpx.TimeoutException):
            await func()
        assert call_count == 3  # initial + 2 retries

    @pytest.mark.asyncio
    async def test_non_retryable_exception_propagates(self):
        call_count = 0
        @retry_with_backoff(max_retries=3, initial_delay=0.01)
        async def func():
            nonlocal call_count
            call_count += 1
            raise ValueError("not retryable")
        with pytest.raises(ValueError):
            await func()
        assert call_count == 1  # No retry


# ═══ TelemetryIntegration ═══
class TestTelemetry:
    def test_record_latency(self):
        tel = TelemetryIntegration()
        tel.record_latency("search", 25.5)
        tel.record_latency("search", 30.0)
        metrics = tel.get_metrics()
        assert "latency_search" in metrics["latency"]
        assert metrics["latency"]["latency_search"]["count"] == 2

    def test_record_error(self):
        tel = TelemetryIntegration()
        tel.record_error("search", "timeout")
        tel.record_error("search", "timeout")
        metrics = tel.get_metrics()
        assert metrics["counters"]["errors_search_timeout"] == 2

    def test_set_gauge(self):
        tel = TelemetryIntegration()
        tel.set_gauge("active_connections", 5)
        metrics = tel.get_metrics()
        assert metrics["gauges"]["active_connections"] == 5

    def test_start_end_span(self):
        tel = TelemetryIntegration()
        span_id = tel.start_span("operation")
        assert span_id is not None
        time.sleep(0.01)
        span = tel.end_span(span_id)
        assert span["duration_ms"] is not None
        assert span["duration_ms"] > 0

    def test_get_metrics(self):
        tel = TelemetryIntegration()
        tel.record_latency("op1", 10)
        tel.record_error("op1", "error")
        tel.set_gauge("g1", 42)
        metrics = tel.get_metrics()
        assert "latency" in metrics
        assert "counters" in metrics
        assert "gauges" in metrics

    def test_singleton(self):
        assert get_telemetry() is get_telemetry()


# ═══ AutonomousOptimizer ═══
class TestAutonomousOptimizer:
    def test_observe(self):
        opt = AutonomousOptimizer()
        result = opt.observe("capacity_optimization", {"cpu_avg": 75})
        assert result["domain"] == "capacity_optimization"

    def test_observe_unknown_domain_raises(self):
        opt = AutonomousOptimizer()
        with pytest.raises(OptimizationError, match="Unknown"):
            opt.observe("unknown_domain", {})

    def test_analyze_no_data(self):
        opt = AutonomousOptimizer()
        result = opt.analyze("cache_optimization")
        assert result["status"] == "no_data"

    def test_analyze_capacity_scale_up(self):
        opt = AutonomousOptimizer()
        for _ in range(5):
            opt.observe("capacity_optimization", {"cpu_avg": 80})
        result = opt.analyze("capacity_optimization")
        assert result["status"] == "analyzed"
        assert len(result["opportunities"]) > 0
        assert result["opportunities"][0]["type"] == "scale_up"

    def test_analyze_capacity_scale_down(self):
        opt = AutonomousOptimizer()
        for _ in range(5):
            opt.observe("capacity_optimization", {"cpu_avg": 20})
        result = opt.analyze("capacity_optimization")
        assert any(o["type"] == "scale_down" for o in result["opportunities"])

    def test_analyze_cache_optimization(self):
        opt = AutonomousOptimizer()
        for _ in range(5):
            opt.observe("cache_optimization", {"hit_rate": 0.5})
        result = opt.analyze("cache_optimization")
        assert any(o["type"] == "increase_cache_size" for o in result["opportunities"])

    def test_create_optimization(self):
        opt = AutonomousOptimizer()
        result = opt.create_optimization(
            "capacity_optimization", "scale_up",
            risk="low", reason="high CPU", expected_impact="reduced latency",
            explanation="CPU usage above 70% for 5 observations",
            rollback_plan="scale back down",
        )
        assert result["status"] == "recommended"
        assert result["auto_applied"] is False

    def test_create_optimization_auto_applied(self):
        opt = AutonomousOptimizer()
        opt._mode = "autonomous"
        result = opt.create_optimization(
            "capacity_optimization", "scale_up",
            risk="low", reason="high CPU", expected_impact="reduced latency",
            explanation="CPU above threshold",
            rollback_plan="scale down",
            governance_approved=True,
        )
        assert result["auto_applied"] is True
        assert result["status"] == "applied"

    def test_create_optimization_abac_denied(self):
        opt = AutonomousOptimizer()
        with pytest.raises(OptimizationError, match="ABAC denied"):
            opt.create_optimization(
                "capacity_optimization", "scale_up",
                risk="low", reason="test", expected_impact="test",
                explanation="test", rollback_plan="test",
                abac_decision={"decision": "DENY"},
            )

    def test_create_optimization_unknown_domain(self):
        opt = AutonomousOptimizer()
        with pytest.raises(OptimizationError, match="Unknown domain"):
            opt.create_optimization("unknown", "test", risk="low", reason="",
                                     expected_impact="", explanation="", rollback_plan="")

    def test_verify_optimization(self):
        opt = AutonomousOptimizer()
        optimization = opt.create_optimization(
            "capacity_optimization", "scale_up",
            risk="low", reason="test", expected_impact="reduced latency",
            explanation="test", rollback_plan="scale down",
        )
        verification = opt.verify_optimization(
            optimization["optimization_id"],
            before_metrics={"latency_ms": 200, "cost": 100},
            after_metrics={"latency_ms": 150, "cost": 80},
        )
        assert verification["status"] == "verified"
        assert "latency_ms" in verification["improvements"]

    def test_verify_unknown_optimization_raises(self):
        opt = AutonomousOptimizer()
        with pytest.raises(OptimizationError, match="not found"):
            opt.verify_optimization("unknown", before_metrics={}, after_metrics={})

    def test_get_stats(self):
        opt = AutonomousOptimizer()
        opt.observe("capacity_optimization", {"cpu_avg": 75})
        opt.create_optimization("capacity_optimization", "scale_up",
                                 risk="low", reason="test", expected_impact="test",
                                 explanation="test", rollback_plan="test")
        stats = opt.get_stats()
        assert stats["total_observations"] == 1
        assert stats["total_optimizations"] == 1

    def test_knowledge_base_updated(self):
        opt = AutonomousOptimizer()
        optimization = opt.create_optimization(
            "capacity_optimization", "scale_up",
            risk="low", reason="test", expected_impact="test",
            explanation="test", rollback_plan="test",
        )
        opt.verify_optimization(optimization["optimization_id"],
                                 before_metrics={"latency": 200}, after_metrics={"latency": 150})
        kb = opt.get_knowledge_base()
        assert len(kb) == 1
        assert kb[0]["domain"] == "capacity_optimization"

    def test_singleton(self):
        assert get_optimizer() is get_optimizer()
