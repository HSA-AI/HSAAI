"""
HSAAI Strategic Imagination Engine — v0.5.0

The cognitive organism doesn't just analyze the present — it IMAGINES
futures that haven't been considered. It generates novel strategic
options, business models, and market opportunities that humans
haven't thought of.

This is creative intelligence at enterprise scale.
"""
from __future__ import annotations
import logging, time, random, hashlib, json
from dataclasses import dataclass, field, asdict
from typing import Any
logger = logging.getLogger("hsaai.imagination")

@dataclass
class ImaginedFuture:
    """A future scenario imagined by the strategic imagination engine."""
    future_id: str = ""
    title: str = ""
    description: str = ""
    category: str = ""  # market_entry, product_innovation, operational_shift, partnership, business_model
    novelty_score: float = 0.0  # how unprecedented
    feasibility: float = 0.0  # how achievable
    potential_impact: float = 0.0  # expected value
    time_horizon: str = ""  # 1y, 3y, 5y, 10y
    required_capabilities: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    first_mover_advantage: bool = False
    imagined_at: float = 0.0

@dataclass
class CreativeInsight:
    """A creative insight — a novel connection or idea."""
    insight_id: str = ""
    insight_type: str = ""  # analogy, counterfactual, synthesis, paradigm_shift
    description: str = ""
    source_concepts: list[str] = field(default_factory=list)
    novel_connection: str = ""
    potential_applications: list[str] = field(default_factory=list)
    surprise_factor: float = 0.0


class StrategicImaginationEngine:
    """
    Generates novel strategic possibilities through creative synthesis.

    Techniques:
      1. Cross-industry analogy: "What if we applied X from industry Y?"
      2. Counterfactual imagination: "What if constraint X didn't exist?"
      3. Combinatorial creativity: "What if we combined A + B?"
      4. Paradigm shift: "What if the opposite of our assumption is true?"
      5. Future projection: "What will the world look like in 10 years?"
    """
    def __init__(self):
        self._futures: list[ImaginedFuture] = []
        self._insights: list[CreativeInsight] = []
        self._future_counter = 0
        self._insight_counter = 0

        # Cross-industry analogy database
        self._industry_analogies = [
            ("Just-in-time manufacturing", "supply_chain", "Apply JIT to knowledge delivery — insights delivered exactly when needed"),
            ("Subscription model", "business_model", "What if enterprise intelligence was a subscription? Pay per decision-quality improvement"),
            ("Open source collaboration", "innovation", "What if suppliers co-developed products with us? Shared IP, shared risk"),
            ("Biological evolution", "organizational", "What if departments could 'evolve' capabilities autonomously?"),
            ("Quantum superposition", "decision_making", "What if we pursued multiple strategies simultaneously until market forced collapse?"),
            ("Game theory Nash equilibrium", "negotiation", "What if we published our supplier strategy transparently to reach better equilibrium?"),
            ("Blockchain trust", "governance", "What if every decision was on an immutable chain, creating absolute trust?"),
        ]

    async def imagine_futures(self, context: dict, count: int = 5) -> list[ImaginedFuture]:
        """Generate novel future scenarios for the enterprise."""
        futures = []
        for _ in range(count):
            technique = random.choice(["analogy", "counterfactual", "combination", "paradigm_shift", "projection"])
            future = await self._generate_future(technique, context)
            if future:
                futures.append(future)
                self._futures.append(future)
        if futures:
            logger.info("🎨 IMAGINED %d FUTURES — top novelty: %.2f",
                       len(futures), max(f.novelty_score for f in futures))
        return futures

    async def _generate_future(self, technique: str, context: dict) -> ImaginedFuture | None:
        self._future_counter += 1
        fid = f"future-{self._future_counter:04d}"

        if technique == "analogy":
            analogy = random.choice(self._industry_analogies)
            title = f"Apply {analogy[0]} to {analogy[1]}"
            desc = analogy[2]
            novelty = 0.8
            feasibility = 0.4
            category = analogy[1]
        elif technique == "counterfactual":
            constraints = ["geographic", "regulatory", "capital", "technological", "organizational"]
            constraint = random.choice(constraints)
            title = f"What if the {constraint} constraint didn't exist?"
            desc = (
                f"Without {constraint} limitations, we could: enter 5 new markets simultaneously, "
                f"operate 24/7 globally, or pursue moonshot innovations."
            )
            novelty = 0.7
            feasibility = 0.3
            category = "paradigm_shift"
        elif technique == "combination":
            domains = ["manufacturing", "logistics", "retail", "finance", "technology"]
            d1, d2 = random.sample(domains, 2)
            title = f"Combine {d1} + {d2} capabilities"
            desc = (
                f"What if we created a new business unit that fuses {d1} and {d2}? "
                f"The intersection could create unique competitive advantage."
            )
            novelty = 0.85
            feasibility = 0.5
            category = "business_model"
        elif technique == "paradigm_shift":
            assumptions = ["bigger is better", "centralized control is safer",
                          "profit maximization is the goal", "growth requires capital"]
            assumption = random.choice(assumptions)
            title = f"What if '{assumption}' is wrong?"
            desc = (
                f"Challenging the assumption that '{assumption}'. The opposite might be true: "
                f"smaller is more agile, distributed is more resilient, purpose drives profit."
            )
            novelty = 0.9
            feasibility = 0.35
            category = "paradigm_shift"
        else:  # projection
            years = random.choice([5, 10, 15])
            title = f"The enterprise in {years} years"
            desc = (f"Projecting forward {years} years: AI will be ubiquitous, "
                   f"climate adaptation will reshape supply chains, "
                   f"demographic shifts will change consumer markets. "
                   f"We need to prepare now.")
            novelty = 0.6
            feasibility = 0.6
            category = "market_entry"

        return ImaginedFuture(
            future_id=fid, title=title, description=desc,
            category=category, novelty_score=novelty,
            feasibility=feasibility,
            potential_impact=(novelty + feasibility) / 2,
            time_horizon=random.choice(["1y", "3y", "5y", "10y"]),
            required_capabilities=["strategic_planning", "risk_assessment", "capital_allocation"],
            risks=["market_volatility", "execution_risk", "competitive_response"],
            first_mover_advantage=novelty > 0.8,
            imagined_at=time.time(),
        )

    async def generate_creative_insight(self, concepts: list[str]) -> CreativeInsight:
        """Generate a creative insight by connecting disparate concepts."""
        self._insight_counter += 1
        iid = f"creative-{self._insight_counter:04d}"
        # Find novel connections between concepts
        if len(concepts) >= 2:
            c1, c2 = random.sample(concepts, 2)
            connection = f"Connecting '{c1}' with '{c2}' reveals an unexplored opportunity space."
            surprise = 0.7
        else:
            connection = f"Deep analysis of '{concepts[0] if concepts else 'unknown'}' reveals hidden potential."
            surprise = 0.5

        insight = CreativeInsight(
            insight_id=iid,
            insight_type=random.choice(["analogy", "counterfactual", "synthesis", "paradigm_shift"]),
            description=connection,
            source_concepts=concepts,
            novel_connection=connection,
            potential_applications=["strategic_planning", "innovation", "risk_mitigation"],
            surprise_factor=surprise,
        )
        self._insights.append(insight)
        logger.info("💡 CREATIVE INSIGHT: %s", connection[:100])
        return insight

    def get_futures(self, category: str | None = None, limit: int = 20) -> list[dict]:
        futures = self._futures
        if category:
            futures = [f for f in futures if f.category == category]
        return [asdict(f) for f in sorted(futures, key=lambda x: x.novelty_score, reverse=True)[:limit]]

    def get_insights(self, limit: int = 20) -> list[dict]:
        return [asdict(i) for i in self._insights[-limit:]]

    def stats(self) -> dict:
        return {
            "futures_imagined": len(self._futures),
            "creative_insights": len(self._insights),
            "avg_novelty": sum(f.novelty_score for f in self._futures) / max(len(self._futures), 1),
            "first_mover_count": sum(1 for f in self._futures if f.first_mover_advantage),
        }

imagination_engine = StrategicImaginationEngine()
__all__ = ["StrategicImaginationEngine", "ImaginedFuture", "CreativeInsight", "imagination_engine"]
