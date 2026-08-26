"""
HSAAI Bulkhead — Concurrency Isolation

Implements the Bulkhead pattern to limit concurrent execution
per service/dependency, preventing cascade failures.

Types:
  - SemaphoreBulkhead: Limits concurrent calls (thread-safe)
  - ThreadPoolBulkhead: Isolates calls to separate thread pools

Usage:
    from packages.common.resilience.bulkhead import Bulkhead, get_bulkhead

    bulkhead = get_bulkhead("llm_gateway")

    async with bulkhead:
        result = await call_llm(prompt)
"""
import os
import time
import threading
import logging
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger("hsaai.resilience.bulkhead")

try:
    from prometheus_client import Counter, Gauge
    BH_REJECTED_TOTAL = Counter(
        "hsaai_bulkhead_rejected_total",
        "Total rejected requests due to bulkhead capacity",
        ["name"],
    )
    BH_ACTIVE_GAUGE = Gauge(
        "hsaai_bulkhead_active",
        "Currently active calls in bulkhead",
        ["name"],
    )
except ImportError:
    BH_REJECTED_TOTAL = None
    BH_ACTIVE_GAUGE = None


@dataclass
class BulkheadConfig:
    max_concurrent: int = 10
    max_queue: int = 5          # Max waiting calls
    timeout: float = 30.0       # Queue wait timeout


class BulkheadFullError(Exception):
    """Raised when bulkhead capacity is exceeded."""
    pass


class SemaphoreBulkhead:
    """
    Thread-safe bulkhead using a bounded semaphore.

    Limits how many concurrent calls can be active for a
    specific service/dependency. Excess calls either wait
    (up to timeout) or are rejected immediately.
    """

    def __init__(self, name: str, max_concurrent: int = 10, max_queue: int = 5, timeout: float = 30.0):
        self.name = name
        self.max_concurrent = max_concurrent
        self.max_queue = max_queue
        self.timeout = timeout
        self._semaphore = threading.Semaphore(max_concurrent)
        self._queue_semaphore = threading.Semaphore(max_concurrent + max_queue)
        self._active = 0
        self._lock = threading.Lock()

    async def __aenter__(self):
        acquired = self._queue_semaphore.acquire(timeout=self.timeout)
        if not acquired:
            if BH_REJECTED_TOTAL:
                BH_REJECTED_TOTAL.labels(name=self.name).inc()
            raise BulkheadFullError(
                f"Bulkhead '{self.name}' is full ({self._active}/{self.max_concurrent} active, "
                f"queue full). Try again later."
            )
        with self._lock:
            self._active += 1
        if BH_ACTIVE_GAUGE:
            BH_ACTIVE_GAUGE.labels(name=self.name).set(self._active)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        with self._lock:
            self._active = max(0, self._active - 1)
        self._semaphore.release()
        self._queue_semaphore.release()
        if BH_ACTIVE_GAUGE:
            BH_ACTIVE_GAUGE.labels(name=self.name).set(self._active)
        return False


# ── Pre-configured bulkheads ──

_bulkheads: dict[str, SemaphoreBulkhead] = {}

BULKHEAD_CONFIGS = {
    "llm_gateway": {"max_concurrent": 20, "max_queue": 10, "timeout": 60},
    "rag_engine": {"max_concurrent": 15, "max_queue": 10, "timeout": 30},
    "qdrant": {"max_concurrent": 10, "max_queue": 5, "timeout": 15},
    "ollama": {"max_concurrent": 5, "max_queue": 5, "timeout": 120},
    "auth_service": {"max_concurrent": 30, "max_queue": 10, "timeout": 10},
    "neo4j": {"max_concurrent": 5, "max_queue": 3, "timeout": 15},
    "embedding": {"max_concurrent": 8, "max_queue": 5, "timeout": 30},
}

def get_bulkhead(service_name: str) -> SemaphoreBulkhead:
    """Get or create a bulkhead for a service."""
    if service_name not in _bulkheads:
        config = BULKHEAD_CONFIGS.get(service_name, {"max_concurrent": 10, "max_queue": 5})
        _bulkheads[service_name] = SemaphoreBulkhead(service_name, **config)
    return _bulkheads[service_name]
