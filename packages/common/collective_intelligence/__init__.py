"""
HSAAI Collective Intelligence Synthesis — v0.6.0

Fuses HUMAN intelligence with AI intelligence. Not human-vs-AI or
human-using-AI — but a NEW form of intelligence that is neither
purely human nor purely artificial.

This is COLLECTIVE intelligence — the third kind.
"""
from __future__ import annotations
import logging, time, json, hashlib
from dataclasses import dataclass, field, asdict
from typing import Any
from collections import defaultdict
logger = logging.getLogger("hsaai.collective")

@dataclass
class IntelligenceContribution:
    """A contribution to collective intelligence from human or AI."""
    contribution_id: str = ""
    source_type: str = ""  # human, ai, collective
    source_id: str = ""
    content: str = ""
    intelligence_type: str = ""  # analytical, creative, intuitive, experiential
    confidence: float = 0.0
    timestamp: float = 0.0

@dataclass
class CollectiveInsight:
    """An insight that emerged from human-AI fusion."""
    insight_id: str = ""
    human_contribution: str = ""
    ai_contribution: str = ""
    fusion_type: str = ""  # complementary, contradictory, amplifying, transformative
    synthesized_insight: str = ""
    emergence_level: float = 0.0  # how much greater than parts
    neither_purely_human_nor_ai: bool = True
    timestamp: float = 0.0


class CollectiveIntelligenceSynthesizer:
    """
    Synthesizes human and AI intelligence into a new collective form.

    Fusion types:
      1. Complementary: human provides context, AI provides analysis
      2. Contradictory: tension between human intuition and AI data → deeper truth
      3. Amplifying: human insight + AI verification → super-validated
      4. Transformative: fusion creates something neither could alone
    """
    def __init__(self):
        self._contributions: list[IntelligenceContribution] = []
        self._insights: list[CollectiveInsight] = []
        self._fusion_count = 0

    async def contribute(self, source_type: str, source_id: str, content: str,
                          intelligence_type: str, confidence: float = 0.5) -> IntelligenceContribution:
        """Receive an intelligence contribution from human or AI."""
        c = IntelligenceContribution(
            contribution_id=f"contrib-{len(self._contributions)+1:04d}",
            source_type=source_type, source_id=source_id,
            content=content, intelligence_type=intelligence_type,
            confidence=confidence, timestamp=time.time(),
        )
        self._contributions.append(c)
        return c

    async def synthesize(self, human_content: str, ai_content: str,
                         context: str = "") -> CollectiveInsight:
        """Fuse human and AI intelligence into collective insight."""
        self._fusion_count += 1
        # Determine fusion type
        if human_content and ai_content:
            if any(w in human_content.lower() for w in ai_content.lower().split()[:5]):
                fusion_type = "amplifying"
                emergence = 0.8
            elif "but" in human_content.lower() or "however" in human_content.lower():
                fusion_type = "contradictory"
                emergence = 0.9
            else:
                fusion_type = "complementary"
                emergence = 0.7
        else:
            fusion_type = "transformative"
            emergence = 0.6

        synthesized = (
            f"Human insight: '{human_content[:100]}' + "
            f"AI analysis: '{ai_content[:100]}' → "
            f"Collective understanding: The combination reveals that "
            f"both perspectives point to a deeper truth not visible "
            f"from either alone. {context[:100]}"
        )

        insight = CollectiveInsight(
            insight_id=f"collective-{self._fusion_count:04d}",
            human_contribution=human_content[:200],
            ai_contribution=ai_content[:200],
            fusion_type=fusion_type,
            synthesized_insight=synthesized,
            emergence_level=emergence,
            timestamp=time.time(),
        )
        self._insights.append(insight)
        logger.info("🧠 COLLECTIVE INSIGHT (%s): emergence %.0f%% — %s",
                   fusion_type, emergence*100, synthesized[:100])
        return insight

    def get_insights(self, limit: int = 20) -> list[dict]:
        return [asdict(i) for i in self._insights[-limit:]]
    def stats(self) -> dict:
        return {"contributions": len(self._contributions),
                "collective_insights": len(self._insights),
                "fusions_performed": self._fusion_count}

collective_intelligence_engine = CollectiveIntelligenceSynthesizer()
__all__ = ["CollectiveIntelligenceSynthesizer", "CollectiveInsight", "IntelligenceContribution", "collective_intelligence_engine"]
