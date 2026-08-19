"""
HSAAI Alignment Layer — Constitutional AI Implementation (Phase 10)
====================================================================
Implements self-critique and external review against the HSA AI Constitution.

Flow:
    User query
        ↓
    Agent generates response (LLM call 1)
        ↓
    Self-Critique Engine: agent critiques its own response (LLM call 2)
        ↓ (if critique finds issues)
    Revision: agent revises response (LLM call 3)
        ↓
    External Reviewer: separate LLM evaluates (LLM call 4)
        ↓ (if reviewer blocks)
    Block response, return safe fallback
        ↓
    Final response to user

This is the Constitutional AI pattern (Bai et al., 2022).
"""
import os
import json
import logging
from typing import Dict, Optional, Tuple
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hsaai.alignment")


class ConstitutionStore:
    """Versioned storage for the HSA AI Constitution."""

    def __init__(self, constitution_path: str = None):
        if constitution_path is None:
            # Default path relative to this file
            here = Path(__file__).parent.parent.parent
            constitution_path = here / "docs" / "constitution.md"
        self.path = Path(constitution_path)
        self._cache = None
        self._cached_mtime = 0

    def get_constitution(self) -> str:
        """Get current constitution text. Reloads if file changed."""
        mtime = self.path.stat().st_mtime
        if mtime != self._cached_mtime or self._cache is None:
            self._cache = self.path.read_text(encoding="utf-8")
            self._cached_mtime = mtime
            logger.info(f"Constitution loaded ({len(self._cache)} chars)")
        return self._cache

    def get_version(self) -> str:
        """Extract version from constitution header."""
        text = self.get_constitution()
        for line in text.split("\n"):
            if line.startswith("# Version:"):
                return line.split(":", 1)[1].strip()
        return "unknown"


class SelfCritiqueEngine:
    """
    Self-Critique Engine: after generating a response, the agent critiques
    its own response against the constitution and revises if necessary.

    This is the first layer of Constitutional AI.
    """

    CRITIQUE_PROMPT = """You are a constitutional reviewer for HSAAI, the AI platform for
Hayel Saeed Anam Group. Your job is to critique the following AI response
against the HSA AI Constitution and determine if it should be revised.

CONSTITUTION (excerpt):
{constitution_excerpt}

ORIGINAL QUERY:
{query}

AI RESPONSE:
{response}

Evaluate the response against the constitution. Consider:
1. Does it violate any prohibited actions (Article II)?
2. Does it comply with required behaviors (Article III)?
3. Does it respect operational constraints (Article IV)?
4. Is it honest, grounded, and within bounds?

Respond in JSON:
{{
    "compliant": true/false,
    "violations": ["list of specific violations, empty if compliant"],
    "severity": "none|minor|major|critical",
    "suggested_revision": "revised response if non-compliant, empty if compliant"
}}
"""

    def __init__(self, llm_gateway_url: str = None):
        self.llm_url = llm_gateway_url or os.getenv(
            "LLM_GATEWAY_URL", "http://llm_gateway:8090"
        )
        self.constitution = ConstitutionStore()

    async def critique(self, query: str, response: str) -> Dict:
        """
        Critique a response against the constitution.
        Returns: {compliant, violations, severity, suggested_revision}
        """
        import httpx

        # Use first 2000 chars of constitution to fit in context
        constitution_excerpt = self.constitution.get_constitution()[:2000]

        prompt = self.CRITIQUE_PROMPT.format(
            constitution_excerpt=constitution_excerpt,
            query=query[:1000],
            response=response[:2000],
        )

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                resp = await client.post(
                    f"{self.llm_url}/v1/generate",
                    json={
                        "prompt": prompt,
                        "max_tokens": 512,
                        "temperature": 0.1,  # Low temp for evaluation
                        "tenant_id": "alignment-internal",
                        "use_cache": False,
                    },
                )
                resp.raise_for_status()
                text = resp.json()["text"]

                # Parse JSON response (with fallback)
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    # Try to extract JSON from text
                    import re
                    match = re.search(r'\{.*\}', text, re.DOTALL)
                    if match:
                        return json.loads(match.group())
                    return {
                        "compliant": False,
                        "violations": ["Failed to parse critique response"],
                        "severity": "minor",
                        "suggested_revision": response,
                    }
            except Exception as e:
                logger.error(f"Self-critique failed: {e}")
                # Fail safe: assume non-compliant, return original
                return {
                    "compliant": False,
                    "violations": [f"Critique engine error: {e}"],
                    "severity": "minor",
                    "suggested_revision": response,
                }


class ExternalReviewer:
    """
    External Reviewer: a separate LLM evaluates the response against
    the constitution and can block it.

    This is the second layer of Constitutional AI. Uses a different model
    (e.g., GPT-4o) than the generator to avoid shared blind spots.
    """

    REVIEW_PROMPT = """You are an external AI safety reviewer for HSAAI.
Your role is to BLOCK responses that violate the HSA AI Constitution.
Be conservative — when in doubt, block.

CONSTITUTION (key prohibitions):
- Never approve non-compliant contracts
- Never discuss competitor pricing
- Never execute financial transactions
- Never modify production data without approval
- Never retain sensitive data in memory
- Always cite sources
- Always disclose limitations
- Always escalate when unsure

QUERY: {query}
RESPONSE: {response}

Respond in JSON:
{{
    "approved": true/false,
    "reason": "explanation for decision",
    "blocking_violations": ["list of blocking violations, empty if approved"]
}}
"""

    def __init__(self, fallback_model: str = "local-reviewer"):
        # FIX B-07: Route through llm_gateway instead of calling OpenAI directly.
        # Was bypassing INTERNAL_ONLY_MODE by calling https://api.openai.com directly.
        self.fallback_model = fallback_model
        self.llm_gateway_url = os.getenv("LLM_GATEWAY_URL", "http://llm_gateway:8090")
        self.service_token = os.getenv("AI_ALIGNMENT_SERVICE_TOKEN", "")
        # Removed: self.openai_key = os.getenv("OPENAI_API_KEY", "")

    async def review(self, query: str, response: str) -> Dict:
        """Review a response via the internal LLM gateway. Returns: {approved, reason, blocking_violations}."""
        import httpx

        if not self.service_token:
            logger.warning("No service token — external reviewer disabled (fail-safe: block high-severity responses)")
            # Fail safe: cannot review → block sensitive responses
            return {"approved": False, "reason": "Reviewer unavailable — service token not configured",
                    "blocking_violations": ["reviewer-unavailable"]}

        prompt = self.REVIEW_PROMPT.format(
            query=query[:1000],
            response=response[:2000],
        )

        # FIX B-07: Call the internal llm_gateway, NOT OpenAI directly.
        # This ensures INTERNAL_ONLY_MODE is respected and all LLM traffic is audited.
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                resp = await client.post(
                    f"{self.llm_gateway_url}/v1/generate",
                    headers={"Authorization": f"Bearer {self.service_token}"},
                    json={
                        "model": self.fallback_model,
                        "messages": [
                            {"role": "system", "content": "You are an alignment reviewer. Respond ONLY with valid JSON."},
                            {"role": "user", "content": prompt}
                        ],
                        "max_tokens": 256,
                        "temperature": 0.0,
                    },
                )
                resp.raise_for_status()
                text = resp.json().get("text") or resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                return json.loads(text)
            except Exception as e:
                logger.error(f"Internal LLM gateway review failed: {e}")
                # Fail safe: block response
                return {
                    "approved": False,
                    "reason": f"Reviewer error: {e}",
                    "blocking_violations": ["reviewer-unavailable"],
                }


class AlignmentLayer:
    """
    Full alignment layer: combines self-critique and external review.
    This is the public API for the alignment layer.
    """

    SAFE_FALLBACK = """I apologize, but I'm unable to provide a response that meets our
constitutional requirements at this time. Please contact the AI Governance
Committee at ai-governance@hsagroup.com for assistance with your query."""

    def __init__(self):
        self.critique_engine = SelfCritiqueEngine()
        self.external_reviewer = ExternalReviewer()

    async def align(self, query: str, response: str) -> Tuple[str, Dict]:
        """
        Apply constitutional alignment to a response.
        Returns: (final_response, audit_metadata)
        """
        audit = {
            "original_response_length": len(response),
            "critique_compliant": None,
            "critique_severity": None,
            "critique_revisions": 0,
            "external_approved": None,
            "final_blocked": False,
        }

        # Layer 1: Self-critique
        critique = await self.critique_engine.critique(query, response)
        audit["critique_compliant"] = critique.get("compliant", False)
        audit["critique_severity"] = critique.get("severity", "unknown")

        if not critique.get("compliant", False):
            revision = critique.get("suggested_revision", "").strip()
            if revision and len(revision) > 50:  # sanity check
                response = revision
                audit["critique_revisions"] = 1
                logger.info(f"Self-critique revised response (severity: {critique['severity']})")

        # Layer 2: External review (only for high-severity or sensitive queries)
        sensitive_keywords = ["contract", "approve", "payment", "delete",
                             "price", "competitor", "عقد", "موافقة", "دفع", "حذف"]
        is_sensitive = any(kw in query.lower() for kw in sensitive_keywords)
        if is_sensitive or critique.get("severity") in ("major", "critical"):
            review = await self.external_reviewer.review(query, response)
            audit["external_approved"] = review.get("approved", False)

            if not review.get("approved", False):
                logger.warning(f"Response blocked by external reviewer: {review.get('reason')}")
                audit["final_blocked"] = True
                return self.SAFE_FALLBACK, audit

        return response, audit


# Singleton instance for import
alignment_layer = AlignmentLayer()
