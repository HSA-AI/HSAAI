"""
HSAAI Semantic Gravity Engine — v0.6.0

Knowledge attracts knowledge — like gravity. Related concepts cluster
together, forming knowledge galaxies. The Semantic Gravity Engine
models this attraction and maps the knowledge universe's structure.

This reveals hidden relationships through gravitational clustering:
concepts that orbit each other are deeply related, even if no explicit
link exists.
"""
from __future__ import annotations
import logging, time, math, hashlib
from dataclasses import dataclass, field, asdict
from typing import Any
from collections import defaultdict
logger = logging.getLogger("hsaai.gravity")

@dataclass
class KnowledgeBody:
    """A body in the knowledge universe — a concept with gravitational mass."""
    body_id: str = ""
    concept: str = ""
    mass: float = 0.0  # importance × frequency × confidence
    position: tuple = (0.0, 0.0)  # position in knowledge space
    velocity: tuple = (0.0, 0.0)  # how fast it's moving (evolving)
    orbiting: str = ""  # what larger body it orbits
    satellites: list[str] = field(default_factory=list)  # what orbits it

@dataclass
class KnowledgeGalaxy:
    """A cluster of knowledge bodies bound by semantic gravity."""
    galaxy_id: str = ""
    name: str = ""
    center_concept: str = ""
    members: list[str] = field(default_factory=list)
    total_mass: float = 0.0
    stability: float = 0.0  # how stable this cluster is
    discovered_at: float = 0.0


class SemanticGravityEngine:
    """
    Models knowledge attraction and clustering through semantic gravity.

    Like celestial mechanics:
      - More important knowledge has more "mass" → stronger attraction
      - Related concepts orbit each other → form galaxies
      - Distant concepts have weak gravity → independent
      - Collisions merge concepts → new knowledge
    """
    def __init__(self):
        self._bodies: dict[str, KnowledgeBody] = {}
        self._galaxies: list[KnowledgeGalaxy] = []
        self._gravity_matrix: dict[tuple, float] = {}  # (body1, body2) → force
        self._body_counter = 0
        self._galaxy_counter = 0

    def add_body(self, concept: str, mass: float = 1.0,
                 position: tuple = (0, 0)) -> KnowledgeBody:
        """Add a knowledge body to the universe."""
        self._body_counter += 1
        bid = f"body-{self._body_counter:04d}"
        body = KnowledgeBody(
            body_id=bid, concept=concept, mass=mass,
            position=position, velocity=(0, 0),
        )
        self._bodies[bid] = body
        return body

    async def compute_gravity(self) -> dict:
        """Compute gravitational forces between all knowledge bodies."""
        bodies = list(self._bodies.values())
        if len(bodies) < 2:
            return {"forces": 0, "galaxies": 0}

        forces = {}
        for i, b1 in enumerate(bodies):
            for b2 in bodies[i+1:]:
                # Semantic distance (simplified: based on concept word overlap)
                w1 = set(b1.concept.lower().split())
                w2 = set(b2.concept.lower().split())
                overlap = len(w1 & w2)
                total = len(w1 | w2)
                if total == 0:
                    distance = 1.0
                else:
                    distance = 1.0 - (overlap / total)

                # Gravitational force: F = G * m1 * m2 / d²
                if distance > 0:
                    force = (b1.mass * b2.mass) / (distance ** 2)
                else:
                    force = b1.mass * b2.mass * 10  # same concept → very strong

                self._gravity_matrix[(b1.body_id, b2.body_id)] = force
                if force > 1.0:
                    forces[f"{b1.concept} ↔ {b2.concept}"] = force

        # Form galaxies from strong gravitational bonds
        await self._form_galaxies()
        return {
            "forces_computed": len(self._gravity_matrix),
            "strong_bonds": len(forces),
            "top_bonds": dict(sorted(forces.items(), key=lambda x: x[1], reverse=True)[:5]),
            "galaxies_formed": len(self._galaxies),
        }

    async def _form_galaxies(self):
        """Form knowledge galaxies from gravitational clusters."""
        # Simple clustering: bodies with strong gravity → same galaxy
        assigned = set()
        for (bid1, bid2), force in sorted(self._gravity_matrix.items(), key=lambda x: x[1], reverse=True):
            if force < 1.0:
                break
            if bid1 in assigned and bid2 in assigned:
                continue
            # Find or create galaxy
            galaxy = None
            for g in self._galaxies:
                if bid1 in g.members or bid2 in g.members:
                    galaxy = g
                    break
            if not galaxy:
                self._galaxy_counter += 1
                galaxy = KnowledgeGalaxy(
                    galaxy_id=f"galaxy-{self._galaxy_counter:04d}",
                    name=f"Cluster around {self._bodies[bid1].concept}",
                    center_concept=self._bodies[bid1].concept,
                    members=[], total_mass=0, discovered_at=time.time(),
                )
                self._galaxies.append(galaxy)
            for bid in [bid1, bid2]:
                if bid not in galaxy.members:
                    galaxy.members.append(bid)
                    galaxy.total_mass += self._bodies[bid].mass
                    assigned.add(bid)
                    # Set orbiting relationship
                    if bid != bid1:
                        self._bodies[bid].orbiting = bid1
                        if bid not in self._bodies[bid1].satellites:
                            self._bodies[bid1].satellites.append(bid)

        for g in self._galaxies:
            g.stability = min(1.0, g.total_mass / (len(g.members) * 2))
            logger.info("🌌 GALAXY '%s': %d members, mass=%.1f, stability=%.2f",
                       g.name, len(g.members), g.total_mass, g.stability)

    def get_universe_map(self) -> dict:
        return {
            "total_bodies": len(self._bodies),
            "total_galaxies": len(self._galaxies),
            "galaxies": [asdict(g) for g in self._galaxies],
            "bodies": [asdict(b) for b in self._bodies.values()],
        }

    def stats(self) -> dict:
        return {
            "knowledge_bodies": len(self._bodies),
            "knowledge_galaxies": len(self._galaxies),
            "gravity_bonds": len(self._gravity_matrix),
            "strong_bonds": sum(1 for v in self._gravity_matrix.values() if v > 1.0),
        }

gravity_engine = SemanticGravityEngine()
__all__ = ["SemanticGravityEngine", "KnowledgeBody", "KnowledgeGalaxy", "gravity_engine"]
