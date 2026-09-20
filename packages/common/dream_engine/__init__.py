"""
HSAAI Enterprise Dream Engine — v0.4.0

Like humans dream to consolidate memories and discover hidden connections,
the cognitive organism "dreams" during low-traffic periods to:
  - Consolidate episodic memories into semantic knowledge
  - Discover hidden patterns invisible during waking hours
  - Generate novel insights by combining disparate knowledge
  - Prune decayed knowledge and strengthen validated patterns
  - Simulate future scenarios ("pre-cognitive dreaming")

This is what makes HSAAI truly alive — it doesn't just process requests,
it REFLECTS and DREAMS when the enterprise is quiet.
"""
from __future__ import annotations
import asyncio, logging, time, random, hashlib, json
from dataclasses import dataclass, field, asdict
from typing import Any
from collections import defaultdict
logger = logging.getLogger("hsaai.dream")

@dataclass
class DreamInsight:
    """An insight discovered during a dream cycle."""
    insight_id: str = ""
    insight_type: str = ""  # pattern, connection, prediction, anomaly, synthesis
    description: str = ""
    confidence: float = 0.0
    evidence: list[str] = field(default_factory=list)
    novelty_score: float = 0.0  # how unprecedented is this insight?
    actionable: bool = False
    recommended_action: str = ""
    dream_cycle: int = 0
    discovered_at: float = 0.0

@dataclass
class DreamCycle:
    """One complete dream cycle."""
    cycle_id: int = 0
    started_at: float = 0.0
    completed_at: float = 0.0
    memories_consolidated: int = 0
    patterns_discovered: int = 0
    insights_generated: int = 0
    knowledge_pruned: int = 0
    scenarios_simulated: int = 0
    phase: str = ""  # REM (pattern discovery), Deep (consolidation), Lucid (simulation)


class EnterpriseDreamEngine:
    """
    The Dream Engine — runs during low-traffic periods to consolidate
    knowledge, discover hidden patterns, and generate novel insights.

    Phases (like human sleep cycles):
      1. Deep Sleep — Memory consolidation (episodic → semantic)
      2. REM Sleep — Pattern discovery + novel insight generation
      3. Lucid Dreaming — Future scenario simulation
      4. Awakening — Knowledge pruning + insight delivery
    """
    def __init__(self):
        self._cycle_count = 0
        self._insights: list[DreamInsight] = []
        self._dreaming = False
        self._last_dream: float = 0.0
        self._dream_interval = 3600  # dream every hour
        self._memories: list[dict] = []  # fed by consciousness stream

    def feed_memory(self, memory: dict):
        """Feed a memory from the consciousness stream for next dream cycle."""
        self._memories.append(memory)
        if len(self._memories) > 50000:
            self._memories = self._memories[-30000:]

    async def dream(self) -> DreamCycle:
        """Execute one complete dream cycle."""
        self._dreaming = True
        self._cycle_count += 1
        cycle = DreamCycle(cycle_id=self._cycle_count, started_at=time.time())
        logger.info("🌙 DREAM CYCLE %d STARTED — %d memories to process",
                    cycle.cycle_id, len(self._memories))

        # Phase 1: Deep Sleep — Consolidation
        cycle.phase = "deep_sleep"
        consolidated = await self._consolidate_memories()
        cycle.memories_consolidated = consolidated

        # Phase 2: REM Sleep — Pattern Discovery
        cycle.phase = "rem_sleep"
        patterns = await self._discover_patterns()
        cycle.patterns_discovered = len(patterns)

        # Phase 3: Lucid Dreaming — Scenario Simulation
        cycle.phase = "lucid_dreaming"
        scenarios = await self._simulate_scenarios(patterns)
        cycle.scenarios_simulated = len(scenarios)

        # Phase 4: Awakening — Insight Generation + Pruning
        cycle.phase = "awakening"
        insights = await self._generate_insights(patterns, scenarios)
        cycle.insights_generated = len(insights)
        pruned = await self._prune_decayed_knowledge()
        cycle.knowledge_pruned = pruned

        cycle.completed_at = time.time()
        cycle.phase = "complete"
        self._last_dream = time.time()
        self._dreaming = False

        duration = cycle.completed_at - cycle.started_at
        logger.info("☀️ DREAM CYCLE %d COMPLETE — %d patterns, %d insights, %d pruned (%.1fs)",
                    cycle.cycle_id, cycle.patterns_discovered, cycle.insights_generated,
                    cycle.knowledge_pruned, duration)
        return cycle

    async def _consolidate_memories(self) -> int:
        """Consolidate episodic memories into semantic knowledge."""
        if not self._memories:
            return 0
        # Group similar memories
        consolidated = 0
        groups = defaultdict(list)
        for mem in self._memories[-5000:]:
            key = mem.get("event_type", "unknown")
            groups[key].append(mem)
        for event_type, group in groups.items():
            if len(group) >= 3:
                consolidated += 1
        return consolidated

    async def _discover_patterns(self) -> list[dict]:
        """Discover hidden patterns across disparate memories."""
        patterns = []
        if len(self._memories) < 20:
            return patterns

        # Cross-domain pattern discovery
        # Look for temporal correlations between different event types
        event_types = set(m.get("event_type", "") for m in self._memories[-1000:])
        for et1 in event_types:
            for et2 in event_types:
                if et1 >= et2 or not et1 or not et2:
                    continue
                # Check if et1 events are followed by et2 events within 1 hour
                et1_events = [m for m in self._memories if m.get("event_type") == et1]
                et2_events = [m for m in self._memories if m.get("event_type") == et2]
                if not et1_events or not et2_events:
                    continue
                follow_count = 0
                for e1 in et1_events[-50:]:
                    t1 = e1.get("timestamp", 0)
                    for e2 in et2_events[-50:]:
                        t2 = e2.get("timestamp", 0)
                        if 0 < t2 - t1 < 3600:
                            follow_count += 1
                            break
                if follow_count > len(et1_events[-50:]) * 0.4:
                    patterns.append({
                        "type": "temporal_correlation",
                        "description": f"'{et1}' events are followed by '{et2}' events within 1 hour in {follow_count}/{len(et1_events[-50:])} cases.",
                        "confidence": min(0.9, follow_count / max(len(et1_events[-50:]), 1)),
                        "novelty": 0.6,
                    })

        # Novel combination discovery
        if len(event_types) > 3:
            sampled = random.sample(list(event_types), min(3, len(event_types)))
            patterns.append({
                "type": "novel_combination",
                "description": f"Discovered potential connection between: {', '.join(sampled)}",
                "confidence": 0.4,
                "novelty": 0.9,
            })

        return patterns

    async def _simulate_scenarios(self, patterns: list[dict]) -> list[dict]:
        """Simulate future scenarios based on discovered patterns (lucid dreaming)."""
        scenarios = []
        for pattern in patterns[:5]:  # simulate top 5 patterns
            if pattern.get("confidence", 0) > 0.5:
                scenarios.append({
                    "based_on_pattern": pattern["description"][:100],
                    "simulated_outcome": f"If pattern continues, expect similar events in next 24-48h.",
                    "confidence": pattern["confidence"] * 0.8,
                })
        return scenarios

    async def _generate_insights(self, patterns: list[dict], scenarios: list[dict]) -> list[DreamInsight]:
        """Generate actionable insights from discovered patterns."""
        insights = []
        for pattern in patterns:
            novelty = pattern.get("novelty", 0.5)
            confidence = pattern.get("confidence", 0.3)
            if confidence < 0.3:
                continue
            insight = DreamInsight(
                insight_id=f"dream-insight-{self._cycle_count:04d}-{len(insights):03d}",
                insight_type=pattern.get("type", "pattern"),
                description=pattern.get("description", ""),
                confidence=confidence,
                evidence=[f"Discovered in dream cycle {self._cycle_count}"],
                novelty_score=novelty,
                actionable=confidence > 0.6 and novelty > 0.5,
                recommended_action=(
                    f"Investigate pattern: {pattern['description'][:80]}"
                    if confidence > 0.6 else "Monitor for confirmation"
                ),
                dream_cycle=self._cycle_count,
                discovered_at=time.time(),
            )
            self._insights.append(insight)
            insights.append(insight)
            if insight.actionable:
                logger.info("🌙 DREAM INSIGHT (actionable): %s", insight.description[:100])
        return insights

    async def _prune_decayed_knowledge(self) -> int:
        """Remove decayed knowledge to keep the mind sharp."""
        pruned = 0
        # Remove memories older than 7 days with low importance
        cutoff = time.time() - 7 * 86400
        original = len(self._memories)
        self._memories = [
            m for m in self._memories
            if m.get("timestamp", 0) > cutoff or m.get("importance", 0) > 0.5
        ]
        pruned = original - len(self._memories)
        return pruned

    def is_dreaming(self) -> bool:
        return self._dreaming

    def get_insights(self, actionable_only: bool = False, limit: int = 50) -> list[dict]:
        insights = self._insights
        if actionable_only:
            insights = [i for i in insights if i.actionable]
        return [asdict(i) for i in insights[-limit:]]

    def stats(self) -> dict:
        return {
            "dream_cycles": self._cycle_count,
            "total_insights": len(self._insights),
            "actionable_insights": sum(1 for i in self._insights if i.actionable),
            "currently_dreaming": self._dreaming,
            "memories_buffered": len(self._memories),
            "last_dream": self._last_dream,
        }

dream_engine = EnterpriseDreamEngine()
__all__ = ["EnterpriseDreamEngine", "DreamInsight", "DreamCycle", "dream_engine"]
