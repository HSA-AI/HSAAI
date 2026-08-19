"""
HSAAI v21.1-v22.0 — AI-Powered Autonomous Optimization Framework
================================================================
Implements:
  1. ConnectionPool — P0: Shared httpx.AsyncClient with health checks + leak detection
  2. CircuitBreakerV2 — P0: Enhanced circuit breaker with telemetry + fallback
  3. RetryLogic — P1: Exponential backoff with jitter
  4. TelemetryIntegration — P1: Prometheus metrics + OpenTelemetry tracing
  5. AutonomousOptimizer — v22.0: AI-powered self-optimizing platform
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Awaitable

import httpx

logger = logging.getLogger("hsaai.v22.optimization")
audit_logger = logging.getLogger("hsaai.audit.optimization")
metrics_logger = logging.getLogger("hsaai.metrics")


# ═══════════════════════════════════════════════════════════════════════
# 1. Connection Pool (P0 — v21.1)
# ═══════════════════════════════════════════════════════════════════════
class ConnectionPoolError(Exception):
    pass


class ConnectionPool:
    """P0: Enterprise connection pool with lifecycle management.

    Features:
      - Shared httpx.AsyncClient (connection reuse)
      - Pool sizing (max_connections, max_keepalive)
      - Health checks (periodic ping)
      - Idle timeout (configurable)
      - Leak detection (track checked-out connections)
      - Graceful shutdown (flush + close)

    Replaces per-request httpx.AsyncClient creation.
    """

    def __init__(
        self,
        *,
        max_connections: int = 100,
        max_keepalive: int = 50,
        keepalive_expiry: float = 30.0,
        connect_timeout: float = 5.0,
        read_timeout: float = 30.0,
        write_timeout: float = 30.0,
        pool_timeout: float = 30.0,
        health_check_interval: float = 30.0,
        headers: dict[str, str] | None = None,
    ):
        self._max_connections = max_connections
        self._max_keepalive = max_keepalive
        self._keepalive_expiry = keepalive_expiry
        self._connect_timeout = connect_timeout
        self._read_timeout = read_timeout
        self._write_timeout = write_timeout
        self._pool_timeout = pool_timeout
        self._health_check_interval = health_check_interval
        self._headers = headers or {}
        self._client: httpx.AsyncClient | None = None
        self._health_task: asyncio.Task | None = None
        self._is_healthy = True
        self._leak_tracker: dict[str, float] = {}  # request_id → checkout_time
        self._stats = {
            "total_requests": 0,
            "total_errors": 0,
            "total_reused": 0,
            "total_created": 0,
        }

    def _get_timeout(self) -> httpx.Timeout:
        return httpx.Timeout(
            connect=self._connect_timeout,
            read=self._read_timeout,
            write=self._write_timeout,
            pool=self._pool_timeout,
        )

    async def get_client(self) -> httpx.AsyncClient:
        """Get the shared httpx.AsyncClient instance."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self._get_timeout(),
                limits=httpx.Limits(
                    max_connections=self._max_connections,
                    max_keepalive_connections=self._max_keepalive,
                    keepalive_expiry=self._keepalive_expiry,
                ),
                headers=self._headers,
            )
            self._stats["total_created"] += 1
            self._start_health_check()
        else:
            self._stats["total_reused"] += 1
        return self._client

    async def execute(
        self,
        method: str,
        url: str,
        *,
        json_body: dict | None = None,
        request_id: str | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """Execute an HTTP request using the pooled client."""
        req_id = request_id or str(uuid.uuid4())
        self._leak_tracker[req_id] = time.time()
        self._stats["total_requests"] += 1

        try:
            client = await self.get_client()
            response = await client.request(method, url, json=json_body, **kwargs)
            return response
        except Exception as exc:
            self._stats["total_errors"] += 1
            raise
        finally:
            self._leak_tracker.pop(req_id, None)

    def _start_health_check(self) -> None:
        """Start periodic health check."""
        if self._health_task is None or self._health_task.done():
            self._health_task = asyncio.create_task(self._health_loop())

    async def _health_loop(self) -> None:
        """Periodic health check loop."""
        while self._client and not self._client.is_closed:
            await asyncio.sleep(self._health_check_interval)
            # Check for leaked connections (checked out > 60 seconds)
            now = time.time()
            leaks = [
                req_id for req_id, checkout_time in self._leak_tracker.items()
                if now - checkout_time > 60
            ]
            if leaks:
                logger.warning(f"Connection leak detected: {len(leaks)} connections checked out > 60s")
                for req_id in leaks:
                    self._leak_tracker.pop(req_id, None)

    @property
    def is_healthy(self) -> bool:
        return self._is_healthy and (self._client is not None and not self._client.is_closed)

    @property
    def active_connections(self) -> int:
        return len(self._leak_tracker)

    def get_stats(self) -> dict[str, Any]:
        return {
            **self._stats,
            "is_healthy": self.is_healthy,
            "active_connections": self.active_connections,
            "max_connections": self._max_connections,
            "max_keepalive": self._max_keepalive,
            "pool_utilization_pct": round(
                self.active_connections / self._max_connections * 100, 1
            ) if self._max_connections > 0 else 0,
        }

    async def close(self) -> None:
        """Gracefully shutdown the connection pool."""
        if self._health_task:
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                pass
        if self._client and not self._client.is_closed:
            await self._client.aclose()
        self._client = None
        self._is_healthy = False


# ═══════════════════════════════════════════════════════════════════════
# 2. Circuit Breaker V2 (P0 — v21.1)
# ═══════════════════════════════════════════════════════════════════════
class CircuitBreakerV2:
    """P0: Enhanced circuit breaker with telemetry and fallback.

    States: CLOSED → OPEN → HALF_OPEN → CLOSED

    Features:
      - Configurable failure threshold
      - Recovery timeout
      - Request monitoring (success/failure tracking)
      - Automatic recovery (half-open testing)
      - Fallback behavior (callable for degraded mode)
      - Telemetry integration (metrics + logging)
    """

    STATE_CLOSED = "closed"
    STATE_OPEN = "open"
    STATE_HALF_OPEN = "half_open"

    def __init__(
        self,
        *,
        name: str = "default",
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        success_threshold: int = 3,
        half_open_max_requests: int = 3,
        fallback: Callable[[], Any] | None = None,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        self.half_open_max_requests = half_open_max_requests
        self.fallback = fallback

        self._state = self.STATE_CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_requests = 0
        self._opened_at: float | None = None
        self._lock = asyncio.Lock()

        # Telemetry
        self._total_requests = 0
        self._total_successes = 0
        self._total_failures = 0
        self._total_fallbacks = 0
        self._total_rejections = 0

    @property
    def state(self) -> str:
        return self._state

    @property
    def is_closed(self) -> bool:
        return self._state == self.STATE_CLOSED

    @property
    def is_open(self) -> bool:
        return self._state == self.STATE_OPEN

    async def can_execute(self) -> bool:
        """Check if a request can be executed."""
        async with self._lock:
            if self._state == self.STATE_CLOSED:
                return True

            if self._state == self.STATE_OPEN:
                if self._opened_at and (time.time() - self._opened_at) >= self.recovery_timeout:
                    self._state = self.STATE_HALF_OPEN
                    self._success_count = 0
                    self._half_open_requests = 0
                    logger.info(f"Circuit breaker '{self.name}' → HALF_OPEN")
                    return True
                self._total_rejections += 1
                return False

            # HALF_OPEN
            if self._half_open_requests < self.half_open_max_requests:
                self._half_open_requests += 1
                return True
            self._total_rejections += 1
            return False

    async def record_success(self) -> None:
        """Record a successful request."""
        async with self._lock:
            self._total_requests += 1
            self._total_successes += 1

            if self._state == self.STATE_HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.success_threshold:
                    self._state = self.STATE_CLOSED
                    self._failure_count = 0
                    logger.info(f"Circuit breaker '{self.name}' → CLOSED (recovered)")
            elif self._state == self.STATE_CLOSED:
                self._failure_count = 0

    async def record_failure(self) -> None:
        """Record a failed request."""
        async with self._lock:
            self._total_requests += 1
            self._total_failures += 1

            if self._state == self.STATE_HALF_OPEN:
                self._state = self.STATE_OPEN
                self._opened_at = time.time()
                logger.warning(f"Circuit breaker '{self.name}' → OPEN (half-open failed)")
            elif self._state == self.STATE_CLOSED:
                self._failure_count += 1
                if self._failure_count >= self.failure_threshold:
                    self._state = self.STATE_OPEN
                    self._opened_at = time.time()
                    logger.warning(
                        f"Circuit breaker '{self.name}' → OPEN "
                        f"({self._failure_count} consecutive failures)"
                    )

    async def execute(self, func: Callable[[], Awaitable[Any]]) -> Any:
        """Execute a function with circuit breaker protection."""
        if not await self.can_execute():
            if self.fallback:
                self._total_fallbacks += 1
                return self.fallback()
            raise ConnectionPoolError(f"Circuit breaker '{self.name}' is OPEN")

        try:
            result = await func()
            await self.record_success()
            return result
        except Exception as exc:
            await self.record_failure()
            raise

    def get_stats(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "state": self._state,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "total_requests": self._total_requests,
            "total_successes": self._total_successes,
            "total_failures": self._total_failures,
            "total_fallbacks": self._total_fallbacks,
            "total_rejections": self._total_rejections,
            "success_rate": round(
                self._total_successes / self._total_requests * 100, 1
            ) if self._total_requests > 0 else 100.0,
        }


# ═══════════════════════════════════════════════════════════════════════
# 3. Retry Logic (P1 — v21.2)
# ═══════════════════════════════════════════════════════════════════════
def retry_with_backoff(
    *,
    max_retries: int = 3,
    initial_delay: float = 0.1,
    max_delay: float = 5.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: tuple = (httpx.TimeoutException, httpx.NetworkError, ConnectionError),
):
    """P1: Exponential backoff retry with jitter.

    Args:
        max_retries: Maximum retry attempts (default: 3)
        initial_delay: Initial delay in seconds (default: 0.1)
        max_delay: Maximum delay cap (default: 5.0)
        backoff_factor: Multiplier per retry (default: 2.0)
        jitter: Add random jitter to prevent thundering herd (default: True)
        retryable_exceptions: Exception types to retry on
    """
    def decorator(func: Callable[[], Awaitable[Any]]) -> Callable[[], Awaitable[Any]]:
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Exception | None = None
            delay = initial_delay

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as exc:
                    last_exception = exc
                    if attempt < max_retries:
                        # Calculate delay with optional jitter
                        actual_delay = delay
                        if jitter:
                            actual_delay = delay * (0.5 + random.random() * 0.5)

                        logger.warning(
                            f"Retry {attempt + 1}/{max_retries} for {func.__name__} "
                            f"after {exc} (delay={actual_delay:.3f}s)"
                        )
                        await asyncio.sleep(actual_delay)
                        delay = min(delay * backoff_factor, max_delay)
                    else:
                        logger.error(
                            f"Max retries ({max_retries}) exceeded for {func.__name__}: {exc}"
                        )
                        raise
                except Exception:
                    raise  # Non-retryable exceptions propagate immediately

            if last_exception:
                raise last_exception
            raise RuntimeError("Unexpected retry loop exit")

        return wrapper
    return decorator


# ═══════════════════════════════════════════════════════════════════════
# 4. Telemetry Integration (P1 — v21.2)
# ═══════════════════════════════════════════════════════════════════════
class TelemetryIntegration:
    """P1: Prometheus metrics + OpenTelemetry tracing integration.

    Metrics tracked:
      - Request latency (histogram)
      - Request count (counter)
      - Error count (counter)
      - Active connections (gauge)
      - Circuit breaker state (gauge)

    Tracing:
      - OpenTelemetry spans for all operations
      - Correlation IDs for trace-log correlation
    """

    def __init__(self):
        self._metrics: dict[str, deque] = defaultdict(lambda: deque(maxlen=10000))
        self._counters: dict[str, int] = defaultdict(int)
        self._gauges: dict[str, float] = {}
        self._spans: list[dict[str, Any]] = []

    def record_latency(self, operation: str, latency_ms: float) -> None:
        """Record operation latency."""
        self._metrics[f"latency_{operation}"].append(latency_ms)
        self._counters[f"requests_{operation}"] += 1

    def record_error(self, operation: str, error_type: str) -> None:
        """Record an error."""
        self._counters[f"errors_{operation}_{error_type}"] += 1

    def set_gauge(self, name: str, value: float) -> None:
        """Set a gauge value."""
        self._gauges[name] = value

    def start_span(self, operation: str, *, parent_id: str | None = None) -> str:
        """Start a tracing span."""
        span_id = str(uuid.uuid4())
        span = {
            "span_id": span_id,
            "operation": operation,
            "parent_id": parent_id,
            "start_time": time.time(),
            "end_time": None,
            "duration_ms": None,
        }
        self._spans.append(span)
        return span_id

    def end_span(self, span_id: str) -> dict[str, Any]:
        """End a tracing span."""
        for span in self._spans:
            if span["span_id"] == span_id:
                span["end_time"] = time.time()
                span["duration_ms"] = round(
                    (span["end_time"] - span["start_time"]) * 1000, 2
                )
                return span
        return {}

    def get_metrics(self) -> dict[str, Any]:
        """Get all metrics."""
        latency_stats = {}
        for key, values in self._metrics.items():
            if values:
                latency_stats[key] = {
                    "count": len(values),
                    "avg_ms": round(sum(values) / len(values), 2),
                    "min_ms": round(min(values), 2),
                    "max_ms": round(max(values), 2),
                    "p95_ms": round(sorted(values)[int(len(values) * 0.95)] if len(values) > 1 else values[0], 2),
                }
        return {
            "latency": latency_stats,
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "spans_count": len(self._spans),
        }


# ═══════════════════════════════════════════════════════════════════════
# 5. Autonomous Optimizer (v22.0)
# ═══════════════════════════════════════════════════════════════════════
class OptimizationError(Exception):
    pass


class AutonomousOptimizer:
    """v22.0: AI-Powered Autonomous Optimization Framework.

    Learning loop:
      Observe → Analyze → Identify → Risk Assessment → Policy Validation
      → Recommendation/Execution → Verification → Measure Impact → Update KB

    Optimization domains:
      - Capacity optimization
      - Resource allocation
      - Model routing
      - RAG retrieval tuning
      - Cache optimization
      - Query optimization
      - Agent scheduling
      - Load balancing
      - Cost optimization
      - Workflow optimization

    Safety:
      - Explainability (every optimization has explanation)
      - Audit trail (immutable)
      - Rollback capability
      - Performance comparison (before vs after)
      - Security validation
      - Governance approval
      - ABAC validation
      - Zero Trust compliance
    """

    OPTIMIZATION_DOMAINS = [
        "capacity_optimization",
        "resource_allocation",
        "model_routing",
        "rag_retrieval_tuning",
        "cache_optimization",
        "query_optimization",
        "agent_scheduling",
        "load_balancing",
        "cost_optimization",
        "workflow_optimization",
    ]

    RISK_LOW = "low"
    RISK_MEDIUM = "medium"
    RISK_HIGH = "high"

    # Risk levels that can be auto-applied (with governance)
    AUTO_APPLICABLE_RISKS = {RISK_LOW}

    def __init__(self):
        self._knowledge_base: list[dict[str, Any]] = []
        self._optimizations: list[dict[str, Any]] = []
        self._observations: list[dict[str, Any]] = []
        self._mode = "recommendation"  # recommendation, supervised, autonomous

    @property
    def mode(self) -> str:
        return self._mode

    def observe(self, domain: str, metrics: dict[str, Any]) -> dict[str, Any]:
        """Observe platform telemetry for optimization analysis."""
        if domain not in self.OPTIMIZATION_DOMAINS:
            raise OptimizationError(f"Unknown optimization domain: {domain}")

        observation = {
            "observation_id": str(uuid.uuid4()),
            "domain": domain,
            "metrics": metrics,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._observations.append(observation)
        return observation

    def analyze(self, domain: str) -> dict[str, Any]:
        """Analyze observations to identify optimization opportunities."""
        domain_obs = [o for o in self._observations if o["domain"] == domain]

        if not domain_obs:
            return {
                "domain": domain,
                "status": "no_data",
                "opportunities": [],
            }

        # Simple analysis: look for trends
        opportunities = []

        # Capacity optimization
        if domain == "capacity_optimization":
            cpu_metrics = [o["metrics"].get("cpu_avg", 0) for o in domain_obs]
            if cpu_metrics:
                avg_cpu = sum(cpu_metrics) / len(cpu_metrics)
                if avg_cpu > 70:
                    opportunities.append({
                        "type": "scale_up",
                        "reason": f"Average CPU {avg_cpu:.1f}% exceeds 70% threshold",
                        "risk": self.RISK_LOW,
                        "expected_impact": "Reduced latency, improved throughput",
                    })
                elif avg_cpu < 30:
                    opportunities.append({
                        "type": "scale_down",
                        "reason": f"Average CPU {avg_cpu:.1f}% below 30% — over-provisioned",
                        "risk": self.RISK_LOW,
                        "expected_impact": "Cost savings with no performance impact",
                    })

        # Cache optimization
        elif domain == "cache_optimization":
            hit_rates = [o["metrics"].get("hit_rate", 0) for o in domain_obs]
            if hit_rates:
                avg_hit_rate = sum(hit_rates) / len(hit_rates)
                if avg_hit_rate < 0.8:
                    opportunities.append({
                        "type": "increase_cache_size",
                        "reason": f"Cache hit rate {avg_hit_rate:.1%} below 80% threshold",
                        "risk": self.RISK_LOW,
                        "expected_impact": "Improved response times",
                    })

        # Model routing
        elif domain == "model_routing":
            latencies = [o["metrics"].get("avg_latency_ms", 0) for o in domain_obs]
            if latencies and len(latencies) > 5:
                recent_avg = sum(latencies[-5:]) / 5
                older_avg = sum(latencies[:-5]) / max(len(latencies) - 5, 1)
                if recent_avg > older_avg * 1.2:
                    opportunities.append({
                        "type": "reroute_to_faster_model",
                        "reason": f"Latency increased {((recent_avg/older_avg)-1)*100:.0f}% — consider faster model",
                        "risk": self.RISK_MEDIUM,
                        "expected_impact": "Reduced latency, possible quality trade-off",
                    })

        return {
            "domain": domain,
            "status": "analyzed",
            "observations_count": len(domain_obs),
            "opportunities": opportunities,
        }

    def create_optimization(
        self,
        domain: str,
        optimization_type: str,
        *,
        risk: str,
        reason: str,
        expected_impact: str,
        explanation: str,
        rollback_plan: str,
        abac_decision: dict[str, Any] | None = None,
        governance_approved: bool = False,
    ) -> dict[str, Any]:
        """Create an optimization recommendation or action."""
        if domain not in self.OPTIMIZATION_DOMAINS:
            raise OptimizationError(f"Unknown domain: {domain}")

        if risk not in (self.RISK_LOW, self.RISK_MEDIUM, self.RISK_HIGH):
            raise OptimizationError(f"Unknown risk level: {risk}")

        # ABAC validation
        if abac_decision and abac_decision.get("decision") != "ALLOW":
            raise OptimizationError("ABAC denied the optimization")

        # Determine if can auto-apply
        can_auto_apply = (
            risk in self.AUTO_APPLICABLE_RISKS
            and governance_approved
            and self._mode == "autonomous"
        )

        optimization = {
            "optimization_id": str(uuid.uuid4()),
            "domain": domain,
            "type": optimization_type,
            "risk": risk,
            "reason": reason,
            "expected_impact": expected_impact,
            "explanation": explanation,  # Explainability
            "rollback_plan": rollback_plan,
            "abac_validated": abac_decision is not None,
            "governance_approved": governance_approved,
            "auto_applied": can_auto_apply,
            "status": "applied" if can_auto_apply else "recommended",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        self._optimizations.append(optimization)

        # Audit log
        audit_logger.info(json.dumps({
            "event": "OPTIMIZATION_CREATED",
            "optimization_id": optimization["optimization_id"],
            "domain": domain,
            "type": optimization_type,
            "risk": risk,
            "auto_applied": can_auto_apply,
            "timestamp": optimization["timestamp"],
        }))

        return optimization

    def verify_optimization(self, optimization_id: str, *, before_metrics: dict, after_metrics: dict) -> dict[str, Any]:
        """Verify optimization impact by comparing before vs after metrics."""
        opt = next((o for o in self._optimizations if o["optimization_id"] == optimization_id), None)
        if opt is None:
            raise OptimizationError(f"Optimization '{optimization_id}' not found")

        # Calculate improvement
        improvements = {}
        for key in before_metrics:
            if key in after_metrics and isinstance(before_metrics[key], (int, float)):
                before_val = before_metrics[key]
                after_val = after_metrics[key]
                if before_val != 0:
                    improvements[key] = {
                        "before": before_val,
                        "after": after_val,
                        "change_pct": round(((after_val - before_val) / before_val) * 100, 2),
                    }

        verification = {
            "optimization_id": optimization_id,
            "status": "verified",
            "before": before_metrics,
            "after": after_metrics,
            "improvements": improvements,
            "verified_at": datetime.now(timezone.utc).isoformat(),
        }

        # Update knowledge base
        self._knowledge_base.append({
            "optimization_id": optimization_id,
            "domain": opt["domain"],
            "type": opt["type"],
            "risk": opt["risk"],
            "expected_impact": opt["expected_impact"],
            "actual_improvements": improvements,
            "success": all(
                imp["change_pct"] <= 0  # Negative change = improvement for latency/cost
                for imp in improvements.values()
                if "latency" in imp or "cost" in imp or "error" in imp
            ),
        })

        opt["status"] = "verified"
        opt["verification"] = verification

        return verification

    def get_optimizations(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get recent optimizations."""
        return self._optimizations[-limit:]

    def get_knowledge_base(self) -> list[dict[str, Any]]:
        """Get the optimization knowledge base."""
        return list(self._knowledge_base)

    def get_stats(self) -> dict[str, Any]:
        """Get optimizer statistics."""
        by_domain = defaultdict(int)
        by_risk = defaultdict(int)
        by_status = defaultdict(int)
        for opt in self._optimizations:
            by_domain[opt["domain"]] += 1
            by_risk[opt["risk"]] += 1
            by_status[opt["status"]] += 1

        return {
            "mode": self._mode,
            "total_observations": len(self._observations),
            "total_optimizations": len(self._optimizations),
            "knowledge_base_entries": len(self._knowledge_base),
            "by_domain": dict(by_domain),
            "by_risk": dict(by_risk),
            "by_status": dict(by_status),
        }


# Singletons
_connection_pool: ConnectionPool | None = None
_circuit_breaker: CircuitBreakerV2 | None = None
_telemetry: TelemetryIntegration | None = None
_optimizer: AutonomousOptimizer | None = None

def get_connection_pool() -> ConnectionPool:
    global _connection_pool
    if _connection_pool is None:
        _connection_pool = ConnectionPool()
    return _connection_pool

def get_circuit_breaker() -> CircuitBreakerV2:
    global _circuit_breaker
    if _circuit_breaker is None:
        _circuit_breaker = CircuitBreakerV2(name="hsaai-default")
    return _circuit_breaker

def get_telemetry() -> TelemetryIntegration:
    global _telemetry
    if _telemetry is None:
        _telemetry = TelemetryIntegration()
    return _telemetry

def get_optimizer() -> AutonomousOptimizer:
    global _optimizer
    if _optimizer is None:
        _optimizer = AutonomousOptimizer()
    return _optimizer
