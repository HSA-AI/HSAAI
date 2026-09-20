"""
HSAAI Intelligence Genealogy — v0.4.0

Tracks the lineage of every piece of knowledge — which decision begat
which insight begat which wisdom. Like a family tree for intelligence.

Every knowledge artifact knows its ancestors and descendants.
"""
from __future__ import annotations
import logging, time, hashlib, json
from dataclasses import dataclass, field, asdict
from typing import Any
from collections import defaultdict, deque
logger = logging.getLogger("hsaai.genealogy")

@dataclass
class KnowledgeNode:
    """A node in the intelligence family tree."""
    node_id: str = ""
    node_type: str = ""  # event, decision, insight, pattern, wisdom, failure
    content_summary: str = ""
    created_at: float = 0.0
    parent_ids: list[str] = field(default_factory=list)  # ancestors
    child_ids: list[str] = field(default_factory=list)  # descendants
    generation: int = 0  # depth in the tree
    lineage_hash: str = ""  # hash of all ancestor IDs
    value: float = 0.0  # measured value to the enterprise
    branch: str = "main"  # knowledge branch (finance, hr, ops, etc.)


class IntelligenceGenealogy:
    """
    Tracks the ancestry and descendants of every knowledge artifact.
    Answers: "Where did this wisdom come from?" and "What decisions
    were influenced by this insight?"
    """
    def __init__(self):
        self._nodes: dict[str, KnowledgeNode] = {}
        self._lineage_cache: dict[str, list[str]] = {}

    def register(self, node_id: str, node_type: str, content: str,
                 parent_ids: list[str] | None = None, branch: str = "main",
                 value: float = 0.0) -> KnowledgeNode:
        """Register a new knowledge node with its parentage."""
        parent_ids = parent_ids or []
        # Calculate generation
        generation = 0
        for pid in parent_ids:
            parent = self._nodes.get(pid)
            if parent and parent.generation >= generation:
                generation = parent.generation + 1

        # Calculate lineage hash
        lineage_parts = sorted(parent_ids + [node_id])
        lineage_hash = hashlib.sha256("|".join(lineage_parts).encode()).hexdigest()[:16]

        node = KnowledgeNode(
            node_id=node_id, node_type=node_type,
            content_summary=content[:200],
            created_at=time.time(),
            parent_ids=parent_ids,
            generation=generation,
            lineage_hash=lineage_hash,
            branch=branch,
            value=value,
        )
        self._nodes[node_id] = node

        # Update parents' child lists
        for pid in parent_ids:
            parent = self._nodes.get(pid)
            if parent and node_id not in parent.child_ids:
                parent.child_ids.append(node_id)

        return node

    def get_ancestry(self, node_id: str, max_depth: int = 10) -> list[dict]:
        """Get all ancestors of a knowledge node."""
        ancestors = []
        visited = set()
        queue = deque([(node_id, 0)])
        while queue:
            nid, depth = queue.popleft()
            if depth >= max_depth or nid in visited:
                continue
            visited.add(nid)
            node = self._nodes.get(nid)
            if not node:
                continue
            if nid != node_id:
                ancestors.append(asdict(node))
            for pid in node.parent_ids:
                queue.append((pid, depth + 1))
        return ancestors

    def get_descendants(self, node_id: str, max_depth: int = 10) -> list[dict]:
        """Get all descendants of a knowledge node."""
        descendants = []
        visited = set()
        queue = deque([(node_id, 0)])
        while queue:
            nid, depth = queue.popleft()
            if depth >= max_depth or nid in visited:
                continue
            visited.add(nid)
            node = self._nodes.get(nid)
            if not node:
                continue
            if nid != node_id:
                descendants.append(asdict(node))
            for cid in node.child_ids:
                queue.append((cid, depth + 1))
        return descendants

    def trace_lineage(self, node_id: str) -> dict:
        """Full lineage trace: ancestors → node → descendants."""
        node = self._nodes.get(node_id)
        if not node:
            return {"error": "Node not found"}
        return {
            "node": asdict(node),
            "ancestry": self.get_ancestry(node_id),
            "descendants": self.get_descendants(node_id),
            "total_ancestors": len(self.get_ancestry(node_id)),
            "total_descendants": len(self.get_descendants(node_id)),
            "generation": node.generation,
            "lineage_hash": node.lineage_hash,
        }

    def find_roots(self, branch: str | None = None) -> list[dict]:
        """Find root knowledge nodes (no parents)."""
        roots = [n for n in self._nodes.values() if not n.parent_ids]
        if branch:
            roots = [r for r in roots if r.branch == branch]
        return [asdict(r) for r in roots]

    def most_influential(self, limit: int = 10) -> list[dict]:
        """Find the most influential knowledge nodes (most descendants)."""
        sorted_nodes = sorted(self._nodes.values(),
                              key=lambda n: len(n.child_ids), reverse=True)
        return [{"node_id": n.node_id, "type": n.node_type,
                 "summary": n.content_summary[:100],
                 "descendants": len(n.child_ids),
                 "value": n.value}
                for n in sorted_nodes[:limit]]

    def stats(self) -> dict:
        type_counts = defaultdict(int)
        for node in self._nodes.values():
            type_counts[node.node_type] += 1
        return {
            "total_nodes": len(self._nodes),
            "by_type": dict(type_counts),
            "max_generation": max((n.generation for n in self._nodes.values()), default=0),
            "root_nodes": sum(1 for n in self._nodes.values() if not n.parent_ids),
            "leaf_nodes": sum(1 for n in self._nodes.values() if not n.child_ids),
        }

genealogy_engine = IntelligenceGenealogy()
__all__ = ["IntelligenceGenealogy", "KnowledgeNode", "genealogy_engine"]
