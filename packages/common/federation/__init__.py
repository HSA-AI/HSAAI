"""
HSAAI Cross-Organization Federation — v0.3.0

Enables intelligence sharing across departments, branches, subsidiaries,
and partners. The Global Intelligence Mesh.

Trust tiers:
  - subsidiary:   Full trust (same parent org)
  - partner:      Limited trust (contractual)
  - external:     Verified only (read-only)
"""
from __future__ import annotations
import asyncio, logging, time, hashlib, json
from dataclasses import dataclass, field, asdict
from typing import Any
from enum import Enum
logger = logging.getLogger("hsaai.federation")

class TrustTier(str, Enum):
    SUBSIDIARY = "subsidiary"
    PARTNER = "partner"
    EXTERNAL = "external"

@dataclass
class FederationNode:
    node_id: str = ""
    name: str = ""
    org_type: str = ""  # department, branch, subsidiary, partner
    trust_tier: TrustTier = TrustTier.PARTNER
    endpoint: str = ""
    shared_intelligence: list[str] = field(default_factory=list)  # what they share
    consumed_intelligence: list[str] = field(default_factory=list)  # what they consume
    last_sync: float = 0.0
    trust_score: float = 0.5

@dataclass
class FederationQuery:
    query_id: str = ""
    from_node: str = ""
    to_node: str = ""
    query_type: str = ""  # intelligence_query, wisdom_lookup, pattern_match
    payload: dict = field(default_factory=dict)
    timestamp: float = 0.0

@dataclass
class FederationResponse:
    query_id: str = ""
    from_node: str = ""
    to_node: str = ""
    result: dict = field(default_factory=dict)
    trust_verified: bool = True
    timestamp: float = 0.0

class FederationMesh:
    """Manages cross-organization intelligence sharing."""
    def __init__(self):
        self._nodes: dict[str, FederationNode] = {}
        self._query_log: list[FederationQuery] = []
        self._intelligence_shared: int = 0

    def register_node(self, node: FederationNode):
        self._nodes[node.node_id] = node
        logger.info("Federation: Registered node '%s' (tier: %s)", node.name, node.trust_tier.value)

    async def query_intelligence(self, from_node: str, to_node: str,
                                  query_type: str, payload: dict) -> FederationResponse:
        """Query intelligence from another node in the mesh."""
        query = FederationQuery(
            query_id=hashlib.sha256(f"{from_node}:{to_node}:{time.time()}".encode()).hexdigest()[:16],
            from_node=from_node, to_node=to_node,
            query_type=query_type, payload=payload, timestamp=time.time(),
        )
        self._query_log.append(query)
        target = self._nodes.get(to_node)
        if not target:
            return FederationResponse(query_id=query.query_id, from_node=to_node,
                                       to_node=from_node, result={"error": "node not found"},
                                       trust_verified=False, timestamp=time.time())

        # Trust verification
        if target.trust_tier == TrustTier.EXTERNAL and query_type == "wisdom_lookup":
            return FederationResponse(query_id=query.query_id, from_node=to_node,
                                       to_node=from_node, result={"error": "external nodes cannot query wisdom"},
                                       trust_verified=False, timestamp=time.time())

        # Simulate intelligence retrieval
        result = {
            "query_type": query_type,
            "payload_summary": str(payload)[:200],
            "intelligence_available": True,
            "trust_tier": target.trust_tier.value,
        }
        self._intelligence_shared += 1
        return FederationResponse(
            query_id=query.query_id, from_node=to_node, to_node=from_node,
            result=result, trust_verified=True, timestamp=time.time()
        )

    def list_nodes(self) -> list[dict]:
        return [asdict(n) for n in self._nodes.values()]

    def stats(self) -> dict:
        return {
            "total_nodes": len(self._nodes),
            "total_queries": len(self._query_log),
            "intelligence_shared": self._intelligence_shared,
            "trust_tiers": {
                "subsidiary": sum(1 for n in self._nodes.values() if n.trust_tier == TrustTier.SUBSIDIARY),
                "partner": sum(1 for n in self._nodes.values() if n.trust_tier == TrustTier.PARTNER),
                "external": sum(1 for n in self._nodes.values() if n.trust_tier == TrustTier.EXTERNAL),
            },
        }

federation_mesh = FederationMesh()
__all__ = ["FederationMesh", "FederationNode", "FederationQuery", "FederationResponse", "TrustTier", "federation_mesh"]
