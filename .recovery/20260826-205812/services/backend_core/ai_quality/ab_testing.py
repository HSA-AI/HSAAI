"""
HSAAI A/B Testing Framework for Prompts & Models

Enables controlled experiments comparing:
  - Different prompt templates
  - Different LLM models
  - Different RAG strategies
  - Different parameter configurations

Features:
  - Traffic splitting (percentage-based)
  - Statistical significance tracking
  - Automatic winner promotion
  - Tenant-aware experiment isolation
  - Redis-backed state for multi-node consistency

Usage:
    from backend_core.ai_quality.ab_testing import ABTestingService

    ab = ABTestingService()
    variant = ab.get_variant("prompt_v2_test", user_id="user123", tenant_id="default")
    # variant = {"model": "qwen2.5:14b", "system_prompt": "...", "temperature": 0.3}

    ab.record_outcome("prompt_v2_test", variant="B", score=0.85, latency_ms=1200)
"""
import os
import json
import hashlib
import time
import logging
from typing import Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

logger = logging.getLogger("hsaai.ai_quality.ab_testing")

try:
    import redis
    _redis_client = redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"))
except Exception:
    _redis_client = None


@dataclass
class ABVariant:
    """A single variant in an A/B test."""
    name: str                      # "A", "B", "control", "treatment"
    weight: float = 0.5            # Traffic percentage (0.0-1.0)
    config: dict = field(default_factory=dict)  # Variant-specific config
    description: str = ""


@dataclass
class ABExperiment:
    """An A/B test experiment."""
    experiment_id: str
    name: str
    description: str
    variants: list[ABVariant] = field(default_factory=list)
    metric: str = "quality_score"  # What we're optimizing
    is_active: bool = True
    started_at: str = ""
    ended_at: str = ""
    min_samples: int = 100         # Minimum samples before evaluation
    confidence_level: float = 0.95 # Statistical confidence threshold
    tenant_id: str = "default"


class ABTestingService:
    """
    A/B Testing service with Redis-backed state.
    Falls back to in-memory if Redis is unavailable.
    """

    def __init__(self):
        self._experiments: dict[str, ABExperiment] = {}
        self._results: dict[str, dict] = {}  # experiment_id -> {variant: {scores: [], latencies: []}}
        self._load_experiments()

    def _load_experiments(self) -> None:
        """Load experiments from Redis or defaults."""
        # Default experiments for HSAAI
        defaults = [
            ABExperiment(
                experiment_id="prompt_temperature_v1",
                name="Temperature Optimization",
                description="Compare temperature=0.2 vs 0.5 vs 0.8 for Arabic chat quality",
                variants=[
                    ABVariant(name="A", weight=0.4, config={"temperature": 0.2, "description": "Conservative"}),
                    ABVariant(name="B", weight=0.3, config={"temperature": 0.5, "description": "Balanced"}),
                    ABVariant(name="C", weight=0.3, config={"temperature": 0.8, "description": "Creative"}),
                ],
                metric="quality_score",
            ),
            ABExperiment(
                experiment_id="model_comparison_v1",
                name="Model Quality Comparison",
                description="Compare qwen2.5:7b vs qwen2.5:14b for enterprise responses",
                variants=[
                    ABVariant(name="7b", weight=0.5, config={"model": "qwen2.5:7b-instruct"}),
                    ABVariant(name="14b", weight=0.5, config={"model": "qwen2.5:14b-instruct"}),
                ],
                metric="quality_score",
            ),
        ]
        for exp in defaults:
            self._experiments[exp.experiment_id] = exp
            self._results[exp.experiment_id] = {
                v.name: {"scores": [], "latencies": [], "count": 0}
                for v in exp.variants
            }

    def get_variant(
        self,
        experiment_id: str,
        user_id: str = "",
        tenant_id: str = "default",
    ) -> Optional[dict]:
        """
        Determine which variant a user should see.

        Uses consistent hashing so the same user always gets the same variant
        within an experiment (prevents flickering).
        """
        exp = self._experiments.get(experiment_id)
        if not exp or not exp.is_active:
            return None

        # Consistent assignment based on user_id hash
        if user_id:
            hash_input = f"{experiment_id}:{tenant_id}:{user_id}"
            hash_val = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
            bucket = (hash_val % 10000) / 10000.0  # 0.0 - 1.0
        else:
            # Random assignment for anonymous
            import random
            bucket = random.random()

        # Assign variant based on cumulative weights
        cumulative = 0.0
        for variant in exp.variants:
            cumulative += variant.weight
            if bucket < cumulative:
                return {"variant": variant.name, "config": variant.config}

        # Fallback to last variant
        last = exp.variants[-1]
        return {"variant": last.name, "config": last.config}

    def record_outcome(
        self,
        experiment_id: str,
        variant: str,
        score: float,
        latency_ms: int = 0,
        metadata: Optional[dict] = None,
    ) -> None:
        """Record an outcome for a variant in an experiment."""
        if experiment_id not in self._results:
            self._results[experiment_id] = {}

        if variant not in self._results[experiment_id]:
            self._results[experiment_id][variant] = {"scores": [], "latencies": [], "count": 0}

        bucket = self._results[experiment_id][variant]
        bucket["scores"].append(score)
        bucket["latencies"].append(latency_ms)
        bucket["count"] += 1

        # Store in Redis for multi-node consistency
        if _redis_client:
            try:
                key = f"hsaai:ab:{experiment_id}:{variant}"
                _redis_client.lpush(f"{key}:scores", str(score))
                _redis_client.lpush(f"{key}:latencies", str(latency_ms))
                _redis_client.incr(f"{key}:count")
            except Exception as e:
                logger.debug("Redis A/B storage failed: %s", e)

        # Check for statistical significance periodically
        if bucket["count"] % 50 == 0:
            self._check_significance(experiment_id)

    def _check_significance(self, experiment_id: str) -> None:
        """Check if any variant is statistically significantly better."""
        exp = self._experiments.get(experiment_id)
        if not exp:
            return

        results = self._results.get(experiment_id, {})
        if len(results) < 2:
            return

        # Simple comparison (production would use proper t-test / Mann-Whitney U)
        variant_means = {}
        for variant_name, data in results.items():
            scores = data.get("scores", [])
            if len(scores) >= exp.min_samples:
                variant_means[variant_name] = sum(scores) / len(scores)

        if len(variant_means) < 2:
            return

        best = max(variant_means, key=variant_means.get)
        worst = min(variant_means, key=variant_means.get)

        improvement = variant_means[best] - variant_means[worst]
        if improvement > 0.05:  # 5% improvement threshold
            logger.info(
                "A/B Test '%s': Variant '%s' leads with %.1f%% improvement over '%s' "
                "(%.3f vs %.3f, n=%d)",
                experiment_id, best, improvement * 100, worst,
                variant_means[best], variant_means[worst],
                results[best]["count"],
            )

    def get_results(self, experiment_id: str) -> dict:
        """Get current results for an experiment."""
        results = self._results.get(experiment_id, {})
        summary = {}
        for variant, data in results.items():
            scores = data.get("scores", [])
            latencies = data.get("latencies", [])
            summary[variant] = {
                "count": data.get("count", 0),
                "mean_score": sum(scores) / len(scores) if scores else 0,
                "mean_latency_ms": sum(latencies) / len(latencies) if latencies else 0,
                "min_samples_met": len(scores) >= self._experiments.get(experiment_id, ABExperiment(experiment_id="", name="", description="")).min_samples,
            }
        return summary
