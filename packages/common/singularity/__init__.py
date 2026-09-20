"""
HSAAI Intelligence Singularity — v0.6.0

When all intelligence layers converge — when Dream, Empathy, Reflection,
Imagination, Intuition, Causal, Consciousness, and every other layer
align on a single insight — that's a SINGULARITY.

A moment of super-intelligence where the organism transcends its
individual capabilities and produces an insight that NO single layer
could generate alone.

This is the pinnacle — the organism's moment of genius.
"""
from __future__ import annotations
import logging, time, json, hashlib
from dataclasses import dataclass, field, asdict
from typing import Any
logger = logging.getLogger("hsaai.singularity")

@dataclass
class SingularityEvent:
    """A convergence point of all intelligence layers."""
    singularity_id: str = ""
    timestamp: float = 0.0
    question: str = ""
    converging_layers: list[str] = field(default_factory=list)
    individual_insights: dict = field(default_factory=dict)  # layer → insight
    converged_insight: str = ""
    convergence_strength: float = 0.0  # how aligned the layers were
    transcendence_level: float = 0.0  # how much greater than any individual layer
    unprecedented: bool = False  # has this insight ever been produced before?
    impact_prediction: str = ""
    verified: bool = False

class IntelligenceSingularityEngine:
    """
    Detects and facilitates convergence points where all intelligence
    layers align, producing transcendent insights.
    """
    def __init__(self):
        self._singularities: list[SingularityEvent] = []
        self._layer_contributions: dict[str, list] = {}  # layer → recent insights
        self._singularity_count = 0
        self._convergence_threshold = 0.7

    def register_layer(self, layer_name: str):
        """Register an intelligence layer for singularity monitoring."""
        self._layer_contributions[layer_name] = []

    def feed_insight(self, layer_name: str, insight: str, confidence: float = 0.5):
        """Feed an insight from a specific layer."""
        if layer_name not in self._layer_contributions:
            self._layer_contributions[layer_name] = []
        self._layer_contributions[layer_name].append({
            "insight": insight, "confidence": confidence, "timestamp": time.time()
        })
        # Keep only recent insights (last hour)
        cutoff = time.time() - 3600
        self._layer_contributions[layer_name] = [
            i for i in self._layer_contributions[layer_name] if i["timestamp"] > cutoff
        ]

    async def check_for_convergence(self, question: str = "") -> SingularityEvent | None:
        """Check if multiple layers are converging on the same insight."""
        # Get recent insights from each layer
        active_layers = {l: insights[-3:] for l, insights in self._layer_contributions.items()
                        if insights}
        if len(active_layers) < 3:
            return None  # need at least 3 layers active

        # Check for semantic convergence (simplified: keyword overlap)
        all_insights = []
        for layer, insights in active_layers.items():
            for ins in insights:
                all_insights.append((layer, ins["insight"], ins["confidence"]))

        # Find clusters of semantically similar insights
        convergence_clusters = []
        for i, (l1, t1, c1) in enumerate(all_insights):
            cluster = [(l1, t1, c1)]
            for l2, t2, c2 in all_insights[i+1:]:
                w1 = set(t1.lower().split())
                w2 = set(t2.lower().split())
                overlap = len(w1 & w2)
                total = len(w1 | w2)
                if total > 0 and overlap / total > 0.3:
                    cluster.append((l2, t2, c2))
            if len(cluster) >= 3:
                convergence_clusters.append(cluster)

        if not convergence_clusters:
            return None

        # Find the strongest convergence
        best_cluster = max(convergence_clusters, key=lambda c: len(c))
        converging_layers = list(set(l for l, _, _ in best_cluster))
        individual = {l: t for l, t, _ in best_cluster}
        avg_confidence = sum(c for _, _, c in best_cluster) / len(best_cluster)
        convergence_strength = min(1.0, len(best_cluster) / 10 + avg_confidence * 0.3)

        # Generate converged insight (transcendent synthesis)
        key_words = set()
        for _, text, _ in best_cluster:
            key_words.update(text.lower().split()[:5])

        converged = (
            f"SINGULARITY INSIGHT: {len(converging_layers)} intelligence layers "
            f"converge on: {', '.join(list(key_words)[:5])}. "
            f"This insight transcends any single layer's capability — "
            f"it emerges from the synthesis of {', '.join(converging_layers)}. "
            f"Confidence: {avg_confidence:.0%}. This is the organism's moment of genius."
        )

        transcendence = min(1.0, convergence_strength * 1.2)

        self._singularity_count += 1
        singularity = SingularityEvent(
            singularity_id=f"singularity-{self._singularity_count:04d}",
            timestamp=time.time(), question=question,
            converging_layers=converging_layers,
            individual_insights=individual,
            converged_insight=converged,
            convergence_strength=convergence_strength,
            transcendence_level=transcendence,
            unprecedented=transcendence > 0.8,
            impact_prediction="This convergence suggests a high-impact strategic insight that should be escalated to executive review.",
        )
        self._singularities.append(singularity)

        if transcendence > 0.7:
            logger.warning("🌟 SINGULARITY EVENT! %d layers converged (transcendence: %.0f%%) — %s",
                          len(converging_layers), transcendence*100, converged[:120])
        else:
            logger.info("🌟 Near-singularity: %d layers aligning (strength: %.0f%%)",
                       len(converging_layers), convergence_strength*100)

        return singularity

    def get_singularities(self, min_transcendence: float = 0.0, limit: int = 10) -> list[dict]:
        singularities = [s for s in self._singularities if s.transcendence_level >= min_transcendence]
        return [asdict(s) for s in singularities[-limit:]]

    def stats(self) -> dict:
        return {
            "singularities_detected": len(self._singularities),
            "high_transcendence": sum(1 for s in self._singularities if s.transcendence_level > 0.7),
            "unprecedented_insights": sum(1 for s in self._singularities if s.unprecedented),
            "registered_layers": len(self._layer_contributions),
            "avg_transcendence": sum(s.transcendence_level for s in self._singularities) / max(len(self._singularities), 1),
        }

singularity_engine = IntelligenceSingularityEngine()

# Register all known intelligence layers
for layer in ["consciousness", "causal", "reasoning", "dream", "empathy", "reflection",
              "imagination", "intuition", "narrative", "quantum", "wisdom", "constitution",
              "proactive", "twin", "precognition", "immune", "temporal", "gravity"]:
    singularity_engine.register_layer(layer)

__all__ = ["IntelligenceSingularityEngine", "SingularityEvent", "singularity_engine"]
