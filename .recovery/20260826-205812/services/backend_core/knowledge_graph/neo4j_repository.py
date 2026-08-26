"""
HSAAI Knowledge Graph — Neo4j Real Implementation (v4.0)

Replaces the SQL-based graph_repository with native Neo4j Cypher queries.
Unlocks real graph traversal: shortest path, community detection, PageRank.

Architecture:
  ┌─────────────────┐
  │  GraphService   │
  └────────┬────────┘
           │
  ┌────────▼────────┐
  │ GraphRepository │  ← this file (Cypher queries)
  └────────┬────────┘
           │
  ┌────────▼────────┐
  │    Neo4j        │  (bolt://neo4j:7687)
  │   (native)      │
  └─────────────────┘
"""
from __future__ import annotations

import os
import logging
from typing import Any
from datetime import datetime, timezone

logger = logging.getLogger("hsaai.graph_repository")

# Try to import neo4j driver
try:
    from neo4j import GraphDatabase, Driver, Session
    from neo4j.exceptions import ServiceUnavailable, AuthError
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    logger.warning("neo4j driver not installed — graph_repository will use SQL fallback")


class Neo4jGraphRepository:
    """Neo4j-backed graph repository with native Cypher queries."""

    def __init__(self):
        self.uri = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
        self.username = os.getenv("NEO4J_USERNAME", "neo4j")
        self.password = os.getenv("NEO4J_PASSWORD", "")
        self._driver: Driver | None = None

        if NEO4J_AVAILABLE:
            try:
                self._driver = GraphDatabase.driver(self.uri, auth=(self.username, self.password))
                logger.info("Neo4j driver initialized: %s", self.uri)
            except Exception as exc:
                logger.warning("Neo4j connection failed: %s — will use SQL fallback", exc)
                self._driver = None
        else:
            logger.warning("Neo4j driver not available — graph operations will be no-ops")

    def _get_session(self) -> Session | None:
        if self._driver is None:
            return None
        return self._driver.session()

    # ─── Entity Operations ───

    def upsert_entity(self, entity: dict[str, Any], actor: str = "system",
                      tenant_id: str = "default", workspace_id: str = "default") -> Any:
        """Create or update an entity node in Neo4j."""
        session = self._get_session()
        if session is None:
            return None

        entity_key = entity.get("entity_key", f"{entity.get('entity_type', 'Document').lower()}:{entity.get('name', '').lower()}")
        query = """
        MERGE (e:Entity {entity_key: $entity_key, tenant_id: $tenant_id, workspace_id: $workspace_id})
        SET e.name = $name,
            e.entity_type = $entity_type,
            e.description = $description,
            e.classification = $classification,
            e.source_ref = $source_ref,
            e.confidence = $confidence,
            e.updated_by = $actor,
            e.updated_at = datetime()
        RETURN e
        """
        result = session.run(query, {
            "entity_key": entity_key,
            "tenant_id": tenant_id,
            "workspace_id": workspace_id,
            "name": entity.get("name", ""),
            "entity_type": entity.get("entity_type", "Document"),
            "description": entity.get("description", ""),
            "classification": entity.get("classification", "internal"),
            "source_ref": entity.get("source_ref", ""),
            "confidence": entity.get("confidence", 0.5),
            "actor": actor,
        })
        record = result.single()
        session.close()
        return record["e"] if record else None

    def get_entity(self, entity_key: str, tenant_id: str = "default") -> dict[str, Any] | None:
        """Get an entity by key."""
        session = self._get_session()
        if session is None:
            return None
        query = """
        MATCH (e:Entity {entity_key: $entity_key, tenant_id: $tenant_id})
        RETURN e
        """
        result = session.run(query, {"entity_key": entity_key, "tenant_id": tenant_id})
        record = result.single()
        session.close()
        if record:
            node = record["e"]
            return dict(node)
        return None

    def list_entities(self, entity_type: str | None = None, tenant_id: str = "default",
                      limit: int = 100) -> list[dict[str, Any]]:
        """List entities, optionally filtered by type."""
        session = self._get_session()
        if session is None:
            return []
        if entity_type:
            query = """
            MATCH (e:Entity {tenant_id: $tenant_id, entity_type: $entity_type})
            RETURN e
            LIMIT $limit
            """
            result = session.run(query, {"tenant_id": tenant_id, "entity_type": entity_type, "limit": limit})
        else:
            query = """
            MATCH (e:Entity {tenant_id: $tenant_id})
            RETURN e
            LIMIT $limit
            """
            result = session.run(query, {"tenant_id": tenant_id, "limit": limit})
        entities = [dict(record["e"]) for record in result]
        session.close()
        return entities

    # ─── Relationship Operations ───

    def add_relationship(self, rel: dict[str, Any], actor: str = "system",
                         tenant_id: str = "default", workspace_id: str = "default") -> Any:
        """Create a relationship between two entities."""
        session = self._get_session()
        if session is None:
            return None

        rel_type = rel.get("relationship_type", "MENTIONS").upper()
        query = f"""
        MATCH (source:Entity {{entity_key: $source_key, tenant_id: $tenant_id}})
        MATCH (target:Entity {{entity_key: $target_key, tenant_id: $tenant_id}})
        MERGE (source)-[r:{rel_type}]->(target)
        SET r.label = $label,
            r.confidence = $confidence,
            r.source_ref = $source_ref,
            r.created_by = $actor,
            r.created_at = datetime()
        RETURN r
        """
        result = session.run(query, {
            "source_key": rel.get("source_key"),
            "target_key": rel.get("target_key"),
            "tenant_id": tenant_id,
            "label": rel.get("label", rel_type),
            "confidence": rel.get("confidence", 0.5),
            "source_ref": rel.get("source_ref", ""),
            "actor": actor,
        })
        record = result.single()
        session.close()
        return record["r"] if record else None

    def get_relationships(self, entity_key: str, tenant_id: str = "default",
                          direction: str = "both") -> list[dict[str, Any]]:
        """Get relationships for an entity (incoming, outgoing, or both)."""
        session = self._get_session()
        if session is None:
            return []

        if direction == "outgoing":
            query = """
            MATCH (e:Entity {entity_key: $entity_key, tenant_id: $tenant_id})-[r]->(target:Entity)
            RETURN type(r) as rel_type, r.label as label, r.confidence as confidence,
                   target.entity_key as target_key, target.name as target_name, target.entity_type as target_type
            """
        elif direction == "incoming":
            query = """
            MATCH (source:Entity)-[r]->(e:Entity {entity_key: $entity_key, tenant_id: $tenant_id})
            RETURN type(r) as rel_type, r.label as label, r.confidence as confidence,
                   source.entity_key as source_key, source.name as source_name, source.entity_type as source_type
            """
        else:
            query = """
            MATCH (e:Entity {entity_key: $entity_key, tenant_id: $tenant_id})-[r]-(other:Entity)
            RETURN type(r) as rel_type, r.label as label, r.confidence as confidence,
                   other.entity_key as other_key, other.name as other_name, other.entity_type as other_type,
                   CASE WHEN startNode(r) = e THEN 'outgoing' ELSE 'incoming' END as direction
            """

        result = session.run(query, {"entity_key": entity_key, "tenant_id": tenant_id})
        rels = [dict(record) for record in result]
        session.close()
        return rels

    # ─── Graph Traversal (Native Neo4j — impossible with SQL) ───

    def shortest_path(self, source_key: str, target_key: str, tenant_id: str = "default",
                      max_depth: int = 5) -> list[dict[str, Any]]:
        """Find the shortest path between two entities.

        This is a native Neo4j operation that cannot be done efficiently in SQL.
        """
        session = self._get_session()
        if session is None:
            return []
        query = """
        MATCH (source:Entity {entity_key: $source_key, tenant_id: $tenant_id}),
              (target:Entity {entity_key: $target_key, tenant_id: $tenant_id})
        CALL apoc.algo.shortestPath(source, target, 5, 'MENTIONS|DEPENDS_ON|GOVERNED_BY|USES')
        YIELD path
        RETURN [node IN nodes(path) | {entity_key: node.entity_key, name: node.name, entity_type: node.entity_type}] as path_nodes,
               [rel IN relationships(path) | type(rel)] as path_rels
        LIMIT 1
        """
        try:
            result = session.run(query, {
                "source_key": source_key,
                "target_key": target_key,
                "tenant_id": tenant_id,
            })
            record = result.single()
            session.close()
            if record:
                return {
                    "nodes": record["path_nodes"],
                    "relationships": record["path_rels"],
                    "length": len(record["path_nodes"]) - 1,
                }
            return {"nodes": [], "relationships": [], "length": 0}
        except Exception as exc:
            logger.warning("shortest_path failed (APOC may not be installed): %s", exc)
            # Fallback: simple MATCH p=shortestPath
            query_fallback = """
            MATCH p=shortestPath((source:Entity {entity_key: $source_key, tenant_id: $tenant_id})-[*..5]-(target:Entity {entity_key: $target_key, tenant_id: $tenant_id}))
            RETURN [node IN nodes(p) | {entity_key: node.entity_key, name: node.name, entity_type: node.entity_type}] as path_nodes,
                   [rel IN relationships(p) | type(rel)] as path_rels
            LIMIT 1
            """
            result = session.run(query_fallback, {
                "source_key": source_key,
                "target_key": target_key,
                "tenant_id": tenant_id,
            })
            record = result.single()
            session.close()
            if record:
                return {
                    "nodes": record["path_nodes"],
                    "relationships": record["path_rels"],
                    "length": len(record["path_nodes"]) - 1,
                }
            return {"nodes": [], "relationships": [], "length": 0}

    def find_communities(self, tenant_id: str = "default", algorithm: str = "louvain") -> list[dict[str, Any]]:
        """Detect communities in the graph using Louvain or Label Propagation.

        This is a native Neo4j operation (requires GDS library).
        """
        session = self._get_session()
        if session is None:
            return []
        query = """
        CALL gds.louvain.stream('hsaai_graph')
        YIELD nodeId, communityId
        RETURN communityId, collect(gds.util.asNode(nodeId).entity_key) as members, count(*) as size
        ORDER BY size DESC
        """
        try:
            result = session.run(query)
            communities = [
                {"community_id": record["communityId"], "members": record["members"], "size": record["size"]}
                for record in result
            ]
            session.close()
            return communities
        except Exception as exc:
            logger.warning("Community detection failed (GDS may not be installed): %s", exc)
            session.close()
            return []

    def find_central_entities(self, tenant_id: str = "default", algorithm: str = "pagerank",
                              limit: int = 20) -> list[dict[str, Any]]:
        """Find the most central entities using PageRank or Betweenness.

        This is a native Neo4j operation (requires GDS library).
        """
        session = self._get_session()
        if session is None:
            return []
        query = """
        CALL gds.pageRank.stream('hsaai_graph')
        YIELD nodeId, score
        RETURN gds.util.asNode(nodeId).entity_key as entity_key,
               gds.util.asNode(nodeId).name as name,
               gds.util.asNode(nodeId).entity_type as entity_type,
               score
        ORDER BY score DESC
        LIMIT $limit
        """
        try:
            result = session.run(query, {"limit": limit})
            entities = [dict(record) for record in result]
            session.close()
            return entities
        except Exception as exc:
            logger.warning("PageRank failed (GDS may not be installed): %s", exc)
            session.close()
            # Fallback: degree centrality (count relationships)
            query_fallback = """
            MATCH (e:Entity {tenant_id: $tenant_id})-[r]-()
            RETURN e.entity_key as entity_key, e.name as name, e.entity_type as entity_type, count(r) as degree
            ORDER BY degree DESC
            LIMIT $limit
            """
            result = session.run(query_fallback, {"tenant_id": tenant_id, "limit": limit})
            entities = [dict(record) for record in result]
            session.close()
            return entities

    # ─── Audit ───

    def audit(self, action: str, actor: str, resource_type: str, resource_id: str,
              detail: dict | None = None, tenant_id: str = "default",
              workspace_id: str = "default") -> None:
        """Write an audit log entry."""
        session = self._get_session()
        if session is None:
            return
        query = """
        CREATE (a:AuditLog {
            action: $action,
            actor: $actor,
            resource_type: $resource_type,
            resource_id: $resource_id,
            detail: $detail,
            tenant_id: $tenant_id,
            workspace_id: $workspace_id,
            created_at: datetime()
        })
        """
        import json
        session.run(query, {
            "action": action,
            "actor": actor,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "detail": json.dumps(detail or {}),
            "tenant_id": tenant_id,
            "workspace_id": workspace_id,
        })
        session.close()

    def close(self):
        """Close the Neo4j driver."""
        if self._driver:
            self._driver.close()


# Singleton instance
_neo4j_repo: Neo4jGraphRepository | None = None


def get_neo4j_repository() -> Neo4jGraphRepository:
    """Get the singleton Neo4j repository instance."""
    global _neo4j_repo
    if _neo4j_repo is None:
        _neo4j_repo = Neo4jGraphRepository()
    return _neo4j_repo
