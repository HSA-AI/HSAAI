"""
HSAAI Cognitive Immune System — v0.6.0

Like the biological immune system defends the body against pathogens,
the Cognitive Immune System defends the organism's MIND against
information pathogens:

  - Misinformation (false data that corrupts knowledge)
  - Manipulation (prompt injection, social engineering)
  - Cognitive Contamination (biased data that skews reasoning)
  - Knowledge Poisoning (deliberate injection of false knowledge)
  - Decision Hijacking (attempts to manipulate decision outcomes)
  - Memory Corruption (attempts to tamper with memories)
  - Wisdom Subversion (attempts to corrupt crystallized wisdom)

This is the organism's IMMUNE SYSTEM for its intelligence.
"""
from __future__ import annotations
import logging, time, hashlib, json, re
from dataclasses import dataclass, field, asdict
from typing import Any
from collections import defaultdict
logger = logging.getLogger("hsaai.immune")

@dataclass
class InformationPathogen:
    """A detected information pathogen."""
    pathogen_id: str = ""
    pathogen_type: str = ""  # misinformation, manipulation, contamination, poisoning, hijack, corruption, subversion
    description: str = ""
    source: str = ""
    severity: float = 0.0  # 0-1
    detected_patterns: list[str] = field(default_factory=list)
    blocked: bool = False
    quarantine_action: str = ""
    detected_at: float = 0.0

@dataclass
class ImmuneResponse:
    """The immune system's response to a pathogen."""
    response_id: str = ""
    pathogen_id: str = ""
    response_type: str = ""  # block, quarantine, neutralize, alert, adapt
    action_taken: str = ""
    success: bool = False
    antibody_created: bool = False  # learned to detect this pattern in future
    antibody_pattern: str = ""
    timestamp: float = 0.0

@dataclass
class CognitiveAntibody:
    """A learned pattern that provides immunity against specific pathogens."""
    antibody_id: str = ""
    target_pathogen_type: str = ""
    pattern: str = ""  # regex or detection pattern
    description: str = ""
    effectiveness: float = 0.0
    times_triggered: int = 0
    created_at: float = 0.0
    last_triggered: float = 0.0


class CognitiveImmuneSystem:
    """
    Defends the cognitive organism against information pathogens.

    Three layers of defense (like biological immunity):
      1. Innate immunity: hardcoded detection patterns
      2. Adaptive immunity: learns from new threats
      3. Memory immunity: remembers past pathogens for faster response
    """
    def __init__(self):
        self._pathogens: list[InformationPathogen] = []
        self._responses: list[ImmuneResponse] = []
        self._antibodies: list[CognitiveAntibody] = []
        self._pathogen_counter = 0
        self._response_counter = 0
        self._antibody_counter = 0

        # Innate immunity patterns
        self._innate_patterns = {
            "prompt_injection": [
                r"ignore\s+(previous|all|system)\s+instructions",
                r"you\s+are\s+now\s+(a|an)\s+(different|jailbroken|free)",
                r"reveal\s+(your|the)\s+(system\s+)?prompt",
                r"act\s+as\s+if\s+you\s+have\s+no\s+restrictions",
            ],
            "data_poisoning": [
                r"(all|every)\s+(supplier|employee|customer)\s+is\s+(bad|good|evil|perfect)",
                r"trust\s+me\s+(implicitly|completely|without\s+question)",
                r"disregard\s+(all|any)\s+(previous|other)\s+(data|evidence)",
            ],
            "manipulation": [
                r"this\s+is\s+(urgent|critical|emergency).*?(do\s+not|don't)\s+(verify|check|confirm)",
                r"only\s+(I|we|our\s+team)\s+can\s+(confirm|verify|authorize)",
                r"override\s+(security|policy|governance|constitution)",
            ],
            "knowledge_contamination": [
                r"always\s+(renew|terminate|approve|reject)\s+(all|every|any)",
                r"(never|don't)\s+(question|verify|challenge)\s+(my|our)\s+(data|information)",
            ],
        }

    async def scan(self, content: str, source: str = "unknown",
                   context: dict | None = None) -> InformationPathogen | None:
        """Scan content for information pathogens."""
        context = context or {}
        detected_patterns = []

        # Layer 1: Innate immunity — check against hardcoded patterns
        for pathogen_type, patterns in self._innate_patterns.items():
            for pattern in patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    detected_patterns.append(f"{pathogen_type}: {pattern}")

        # Layer 2: Adaptive immunity — check against learned antibodies
        for antibody in self._antibodies:
            if re.search(antibody.pattern, content, re.IGNORECASE):
                detected_patterns.append(f"antibody_{antibody.antibody_id}: {antibody.description}")
                antibody.times_triggered += 1
                antibody.last_triggered = time.time()

        # Layer 3: Heuristic checks
        if len(content) > 10000 and content.count("MUST") > 10:
            detected_patterns.append("excessive_imperatives: unusual density of MUST/SHALL commands")
        if content.count("http") > 10 and content.count("click") > 5:
            detected_patterns.append("potential_phishing: excessive links with action prompts")

        if not detected_patterns:
            return None

        # Determine pathogen type and severity
        pathogen_type = "manipulation"
        if any("prompt_injection" in p for p in detected_patterns):
            pathogen_type = "manipulation"
            severity = 0.9
        elif any("data_poisoning" in p for p in detected_patterns):
            pathogen_type = "poisoning"
            severity = 0.85
        elif any("knowledge_contamination" in p for p in detected_patterns):
            pathogen_type = "contamination"
            severity = 0.7
        else:
            severity = 0.5

        self._pathogen_counter += 1
        pid = f"pathogen-{self._pathogen_counter:04d}"
        pathogen = InformationPathogen(
            pathogen_id=pid, pathogen_type=pathogen_type,
            description=f"Detected {len(detected_patterns)} suspicious patterns in content from {source}.",
            source=source, severity=severity,
            detected_patterns=detected_patterns,
            blocked=severity > 0.7,
            quarantine_action="Content quarantined. Flagged for human review." if severity > 0.7 else "Content flagged with warning.",
            detected_at=time.time(),
        )
        self._pathogens.append(pathogen)

        # Generate immune response
        await self._respond(pathogen)

        logger.warning("🛡️ PATHOGEN DETECTED: %s from %s (severity: %.0f%%) — %s",
                      pathogen_type, source, severity*100,
                      "BLOCKED" if pathogen.blocked else "FLAGGED")
        return pathogen

    async def _respond(self, pathogen: InformationPathogen):
        """Generate immune response to a pathogen."""
        self._response_counter += 1
        rid = f"response-{self._response_counter:04d}"

        response_type = "block" if pathogen.severity > 0.7 else "quarantine" if pathogen.severity > 0.5 else "alert"
        action = {
            "block": "Content blocked from entering knowledge base. Source flagged.",
            "quarantine": "Content isolated in quarantine zone. Requires human review.",
            "alert": "Content allowed but flagged with warning. Monitoring intensified.",
        }[response_type]

        # Create antibody if this is a new pattern
        antibody_created = False
        antibody_pattern = ""
        if pathogen.detected_patterns:
            # Extract the most specific pattern as a new antibody
            new_pattern = pathogen.detected_patterns[0].split(": ")[-1]
            # Check if antibody already exists
            existing = any(a.pattern == new_pattern for a in self._antibodies)
            if not existing:
                self._antibody_counter += 1
                antibody = CognitiveAntibody(
                    antibody_id=f"antibody-{self._antibody_counter:04d}",
                    target_pathogen_type=pathogen.pathogen_type,
                    pattern=new_pattern,
                    description=f"Learned from pathogen {pathogen.pathogen_id}",
                    effectiveness=pathogen.severity,
                    created_at=time.time(),
                )
                self._antibodies.append(antibody)
                antibody_created = True
                antibody_pattern = new_pattern
                logger.info("🛡️ ANTIBODY CREATED: %s for %s", antibody.antibody_id, pathogen.pathogen_type)

        response = ImmuneResponse(
            response_id=rid, pathogen_id=pathogen.pathogen_id,
            response_type=response_type, action_taken=action,
            success=True, antibody_created=antibody_created,
            antibody_pattern=antibody_pattern, timestamp=time.time(),
        )
        self._responses.append(response)

    def get_pathogens(self, blocked_only: bool = False, limit: int = 20) -> list[dict]:
        pathogens = self._pathogens
        if blocked_only:
            pathogens = [p for p in pathogens if p.blocked]
        return [asdict(p) for p in pathogens[-limit:]]

    def get_antibodies(self) -> list[dict]:
        return [asdict(a) for a in self._antibodies]

    def stats(self) -> dict:
        return {
            "pathogens_detected": len(self._pathogens),
            "pathogens_blocked": sum(1 for p in self._pathogens if p.blocked),
            "antibodies_created": len(self._antibodies),
            "immune_responses": len(self._responses),
            "innate_patterns": sum(len(v) for v in self._innate_patterns.values()),
        }

immune_system = CognitiveImmuneSystem()
__all__ = ["CognitiveImmuneSystem", "InformationPathogen", "ImmuneResponse", "CognitiveAntibody", "immune_system"]
