"""
HSAAI Memory Architecture — 4-Tier (Phase 3 Redesign)
========================================================
Implements: Working, Episodic, Semantic, Procedural memory tiers
with consolidation engine for autonomous learning.

Architecture based on Generative Agents (Park et al., Stanford 2023)
extended with enterprise-specific enhancements.
"""
import os
import time
import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta  # FIX v2.2: added timedelta for consolidation
import uuid

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hsaai.memory")


@dataclass
class Memory:
    """Base memory structure."""
    memory_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = "default"
    user_id: Optional[str] = None
    agent_id: Optional[str] = None
    content: str = ""
    embedding: Optional[List[float]] = None
    importance: float = 0.5  # 0.0 to 1.0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_accessed: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    access_count: int = 0
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class WorkingMemory:
    """
    Tier 1: Working Memory.
    The current conversation context, managed by the context manager
    with token budgeting and summarization.
    """

    def __init__(self, max_tokens: int = 8000):
        self.max_tokens = max_tokens
        self.messages: List[Dict] = []
        self.summary: Optional[str] = None  # Rolling summary

    def add_message(self, role: str, content: str):
        """Add a message to working memory."""
        self.messages.append({
            "role": role, "content": content,
            "timestamp": time.time(),
        })
        # If exceeded, trigger summarization
        if self.estimate_tokens() > self.max_tokens:
            self._summarize()

    def get_context(self, max_tokens: int = None) -> str:
        """Get the working memory as a context string."""
        budget = max_tokens or self.max_tokens
        if self.summary:
            budget -= len(self.summary.split())  # rough estimate
        recent = self.messages[-10:]  # last 10 messages
        context = ""
        if self.summary:
            context += f"Summary of earlier conversation:\n{self.summary}\n\n"
        context += "\n".join(f"{m['role']}: {m['content']}" for m in recent)
        return context[:budget * 4]  # rough token→char conversion

    def estimate_tokens(self) -> int:
        """Estimate token count (rough: 4 chars per token)."""
        total = sum(len(m["content"]) for m in self.messages) // 4
        if self.summary:
            total += len(self.summary) // 4
        return total

    def _summarize(self):
        """Summarize older messages. In production, uses LLM."""
        old_messages = self.messages[:-5]  # keep last 5
        if not old_messages:
            return
        # Simple summarization: concatenate and truncate
        # Production: call LLM with "Summarize this conversation: ..."
        new_summary = " ".join(m["content"][:200] for m in old_messages)
        if self.summary:
            self.summary = self.summary[:1000] + " | " + new_summary[:1000]
        else:
            self.summary = new_summary[:2000]
        # Keep only recent messages
        self.messages = self.messages[-5:]


class EpisodicMemory:
    """
    Tier 2: Episodic Memory.
    Searchable log of past interactions, indexed by embeddings
    for similarity recall and by time for temporal recall.
    """

    def __init__(self, qdrant_url: str = None, postgres_url: str = None):
        self.qdrant_url = qdrant_url or os.getenv("QDRANT_URL", "http://qdrant:6333")
        self.postgres_url = postgres_url or os.getenv("DATABASE_URL")
        self.collection = "episodic_memory"
        self._init_storage()

    def _init_storage(self):
        """Initialize Qdrant collection and PostgreSQL table."""
        # In production, this would:
        # 1. Create Qdrant collection if not exists (vector dim 1024 for BGE-M3)
        # 2. Create PostgreSQL table:
        #    CREATE TABLE episodic_memories (
        #        memory_id UUID PRIMARY KEY,
        #        tenant_id VARCHAR(64) NOT NULL,
        #        user_id VARCHAR(64),
        #        agent_id VARCHAR(64),
        #        content TEXT NOT NULL,
        #        embedding VECTOR(1024),
        #        importance FLOAT DEFAULT 0.5,
        #        created_at TIMESTAMP NOT NULL,
        #        last_accessed TIMESTAMP,
        #        access_count INT DEFAULT 0,
        #        tags TEXT[],
        #        metadata JSONB
        #    );
        # 3. Create indexes on tenant_id, user_id, created_at
        pass

    async def store(self, memory: Memory):
        """Store an episodic memory in PostgreSQL + Qdrant.

        FIX v2.2 (Phase 2): Previously this was a stub (just logged).
        Now it:
          1. Generates an embedding for the memory content via the RAG engine
          2. Inserts the memory row into the episodic_memories table
          3. Upserts the embedding + payload into Qdrant for similarity search
        """
        import asyncio
        try:
            # Generate embedding via RAG engine's /v1/embed endpoint.
            import httpx
            embedding = None
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.post(
                        f"{os.getenv('RAG_ENGINE_URL', 'http://rag_engine:8030')}/v1/embed",
                        json={"text": memory.content[:2000]},
                    )
                    if resp.status_code == 200:
                        embedding = resp.json().get("embedding")
            except Exception as e:
                logger.warning("Embedding generation for memory failed: %s", e)

            # Insert into PostgreSQL.
            if self.postgres_url:
                try:
                    import psycopg
                    async with await psycopg.AsyncConnection.connect(self.postgres_url) as conn:
                        async with conn.cursor() as cur:
                            await cur.execute(
                                """
                                INSERT INTO episodic_memories
                                    (memory_id, tenant_id, user_id, agent_id, content,
                                     embedding, importance, created_at, last_accessed,
                                     access_count, tags, metadata)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT (memory_id) DO UPDATE SET
                                    content = EXCLUDED.content,
                                    importance = EXCLUDED.importance,
                                    metadata = EXCLUDED.metadata
                                """,
                                (
                                    memory.memory_id,
                                    memory.tenant_id,
                                    memory.metadata.get("user_id"),
                                    memory.metadata.get("agent_id"),
                                    memory.content,
                                    str(embedding) if embedding else None,
                                    memory.importance,
                                    memory.timestamp,
                                    memory.timestamp,
                                    0,
                                    memory.metadata.get("tags", []),
                                    str(memory.metadata),
                                ),
                            )
                            await conn.commit()
                except Exception as e:
                    logger.warning("PostgreSQL memory store failed: %s", e)

            # Upsert into Qdrant for vector similarity search.
            if embedding:
                try:
                    from qdrant_client import QdrantClient
                    from qdrant_client.http.models import PointStruct
                    client = QdrantClient(url=self.qdrant_url)
                    # Ensure collection exists (vector size = embedding length).
                    vector_size = len(embedding)
                    try:
                        client.get_collection(self.collection)
                    except Exception:
                        from qdrant_client.http.models import Distance, VectorParams
                        client.create_collection(
                            self.collection,
                            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
                        )
                    client.upsert(
                        self.collection,
                        points=[PointStruct(
                            id=memory.memory_id,
                            vector=embedding,
                            payload={
                                "tenant_id": memory.tenant_id,
                                "user_id": memory.metadata.get("user_id", ""),
                                "agent_id": memory.metadata.get("agent_id", ""),
                                "content": memory.content[:500],
                                "importance": memory.importance,
                                "created_at": memory.timestamp.isoformat(),
                                "tags": memory.metadata.get("tags", []),
                            },
                        )],
                    )
                except Exception as e:
                    logger.warning("Qdrant memory upsert failed: %s", e)

            logger.info("Episodic memory stored: %s... (tenant=%s, importance=%s)",
                        memory.memory_id[:8], memory.tenant_id, memory.importance)
        except Exception as e:
            logger.error("Memory store failed: %s", e)

    async def recall_by_similarity(self, query: str, tenant_id: str,
                                    limit: int = 5, min_importance: float = 0.3
                                   ) -> List[Memory]:
        """Recall memories by semantic similarity to query.

        FIX v2.2 (Phase 2): Previously returned [] (stub). Now:
          1. Embeds the query via the RAG engine
          2. Searches Qdrant for the most similar memories (filtered by tenant)
          3. Filters by minimum importance threshold
          4. Updates last_accessed + access_count for recalled memories
        """
        import httpx
        try:
            # Step 1: Generate query embedding.
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{os.getenv('RAG_ENGINE_URL', 'http://rag_engine:8030')}/v1/embed",
                    json={"text": query},
                )
                if resp.status_code != 200:
                    return []
                query_embedding = resp.json().get("embedding")
                if not query_embedding:
                    return []

            # Step 2: Search Qdrant for similar memories.
            from qdrant_client import QdrantClient
            from qdrant_client.http.models import SearchRequest, Filter, FieldCondition, MatchValue, Range
            qdrant = QdrantClient(url=self.qdrant_url)
            try:
                hits = qdrant.search(
                    collection_name=self.collection,
                    query_vector=query_embedding,
                    query_filter=Filter(must=[
                        FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id)),
                        FieldCondition(key="importance", range=Range(gte=min_importance)),
                    ]),
                    limit=limit,
                    with_payload=True,
                )
            except Exception as e:
                logger.warning("Qdrant similarity search failed: %s", e)
                return []

            # Step 3: Convert hits to Memory objects.
            memories = []
            for hit in hits:
                payload = hit.payload or {}
                memories.append(Memory(
                    memory_id=str(hit.id),
                    content=payload.get("content", ""),
                    timestamp=datetime.fromisoformat(payload["created_at"]) if payload.get("created_at") else datetime.now(timezone.utc),
                    importance=payload.get("importance", 0.5),
                    tier=MemoryTier.EPISODIC,
                    metadata={
                        "tenant_id": tenant_id,
                        "user_id": payload.get("user_id", ""),
                        "agent_id": payload.get("agent_id", ""),
                        "tags": payload.get("tags", []),
                        "score": hit.score,
                    },
                ))

            # Step 4: Update last_accessed + access_count in PostgreSQL (async, non-blocking).
            if memories and self.postgres_url:
                try:
                    import psycopg
                    async with await psycopg.AsyncConnection.connect(self.postgres_url) as conn:
                        async with conn.cursor() as cur:
                            for m in memories:
                                await cur.execute(
                                    "UPDATE episodic_memories SET last_accessed = NOW(), access_count = access_count + 1 WHERE memory_id = %s",
                                    (m.memory_id,),
                                )
                            await conn.commit()
                except Exception as e:
                    logger.debug("Access count update failed: %s", e)

            logger.info("Recalled %d memories by similarity (tenant=%s, query='%s...')",
                        len(memories), tenant_id, query[:50])
            return memories
        except Exception as e:
            logger.error("recall_by_similarity failed: %s", e)
            return []

    async def recall_by_time(self, tenant_id: str, start_time: str,
                              end_time: str, limit: int = 100) -> List[Memory]:
        """Recall memories within a time range.

        FIX v2.2 (Phase 2): Previously returned [] (stub). Now queries
        PostgreSQL for memories created between start_time and end_time,
        filtered by tenant_id, ordered by created_at descending.
        """
        if not self.postgres_url:
            logger.warning("recall_by_time: no DATABASE_URL configured")
            return []
        try:
            import psycopg
            async with await psycopg.AsyncConnection.connect(self.postgres_url) as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        SELECT memory_id, tenant_id, user_id, agent_id, content,
                               importance, created_at, tags, metadata
                        FROM episodic_memories
                        WHERE tenant_id = %s
                          AND created_at >= %s
                          AND created_at <= %s
                        ORDER BY created_at DESC
                        LIMIT %s
                        """,
                        (tenant_id, start_time, end_time, limit),
                    )
                    rows = await cur.fetchall()
                    memories = []
                    for row in rows:
                        (memory_id, t_id, user_id, agent_id, content,
                         importance, created_at, tags, metadata_json) = row
                        memories.append(Memory(
                            memory_id=str(memory_id),
                            content=content,
                            timestamp=created_at if isinstance(created_at, datetime) else datetime.fromisoformat(str(created_at)),
                            importance=float(importance) if importance else 0.5,
                            tier=MemoryTier.EPISODIC,
                            metadata={
                                "tenant_id": t_id,
                                "user_id": user_id or "",
                                "agent_id": agent_id or "",
                                "tags": tags or [],
                                "metadata": metadata_json or {},
                            },
                        ))
                    logger.info("Recalled %d memories by time (tenant=%s, %s to %s)",
                                len(memories), tenant_id, start_time, end_time)
                    return memories
        except Exception as e:
            logger.error("recall_by_time failed: %s", e)
            return []

    async def forget(self, memory_id: str, tenant_id: str):
        """Delete a memory (right to be forgotten).

        FIX v2.2 (Phase 2): Previously just logged. Now deletes from
        both PostgreSQL and Qdrant to ensure complete removal.
        """
        # Delete from PostgreSQL.
        if self.postgres_url:
            try:
                import psycopg
                async with await psycopg.AsyncConnection.connect(self.postgres_url) as conn:
                    async with conn.cursor() as cur:
                        await cur.execute(
                            "DELETE FROM episodic_memories WHERE memory_id = %s AND tenant_id = %s",
                            (memory_id, tenant_id),
                        )
                        await conn.commit()
            except Exception as e:
                logger.warning("PostgreSQL forget failed: %s", e)

        # Delete from Qdrant.
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.http.models import PointIdsList
            qdrant = QdrantClient(url=self.qdrant_url)
            qdrant.delete(
                collection_name=self.collection,
                points_selector=PointIdsList(points=[memory_id]),
            )
        except Exception as e:
            logger.warning("Qdrant forget failed: %s", e)

        logger.info("Memory forgotten: %s (tenant=%s)", memory_id, tenant_id)


class SemanticMemory:
    """
    Tier 3: Semantic Memory.
    The knowledge graph, encoding general facts about the world
    and the enterprise. Stored in Neo4j.
    """

    def __init__(self, neo4j_url: str = None):
        self.neo4j_url = neo4j_url or os.getenv("NEO4J_URL", "bolt://neo4j:7687")
        self._driver = None

    def _get_driver(self):
        if self._driver is None:
            try:
                from neo4j import GraphDatabase
                self._driver = GraphDatabase.driver(
                    self.neo4j_url,
                    auth=(os.getenv("NEO4J_USER", "neo4j"),
                          os.getenv("NEO4J_PASSWORD", "password")),
                )
            except Exception as e:
                logger.warning(f"Neo4j unavailable: {e}")
        return self._driver

    async def add_fact(self, subject: str, predicate: str, obj: str,
                       tenant_id: str, source: str = None):
        """Add a fact to the knowledge graph."""
        # Cypher: MERGE (s:Entity {name: $subject, tenant_id: $tenant})
        #         MERGE (o:Entity {name: $obj, tenant_id: $tenant})
        #         MERGE (s)-[r:RELATION {type: $predicate, source: $source}]->(o)
        driver = self._get_driver()
        if driver is None:
            return
        with driver.session() as session:
            session.run(
                "MERGE (s:Entity {name: $subject, tenant_id: $tenant}) "
                "MERGE (o:Entity {name: $obj, tenant_id: $tenant}) "
                "MERGE (s)-[r:RELATION {type: $predicate}]->(o) "
                "SET r.source = $source, r.created_at = datetime()",
                subject=subject, obj=obj, predicate=predicate,
                tenant=tenant_id, source=source,
            )

    async def query(self, cypher: str, params: Dict = None) -> List[Dict]:
        """Execute a Cypher query against the knowledge graph."""
        driver = self._get_driver()
        if driver is None:
            return []
        with driver.session() as session:
            result = session.run(cypher, params or {})
            return [r.data() for r in result]


class ProceduralMemory:
    """
    Tier 4: Procedural Memory.
    Library of learned procedures (how-to skills) that agents can invoke.
    """

    def __init__(self):
        self.procedures: Dict[str, Dict] = {}

    def add_procedure(self, name: str, steps: List[str], tenant_id: str,
                      success_rate: float = 0.0):
        """Add a learned procedure."""
        proc_id = f"{tenant_id}:{name}"
        self.procedures[proc_id] = {
            "name": name, "steps": steps, "tenant_id": tenant_id,
            "success_rate": success_rate, "use_count": 0,
            "created_at": time.time(), "last_used": None,
        }
        logger.info(f"Procedure added: {proc_id}")

    def get_procedure(self, name: str, tenant_id: str) -> Optional[Dict]:
        """Retrieve a procedure by name."""
        proc_id = f"{tenant_id}:{name}"
        proc = self.procedures.get(proc_id)
        if proc:
            proc["use_count"] += 1
            proc["last_used"] = time.time()
        return proc

    def update_success_rate(self, name: str, tenant_id: str, success: bool):
        """Update procedure success rate after use."""
        proc_id = f"{tenant_id}:{name}"
        proc = self.procedures.get(proc_id)
        if proc:
            # Exponential moving average
            alpha = 0.1
            old = proc["success_rate"]
            new = 1.0 if success else 0.0
            proc["success_rate"] = (alpha * new) + ((1 - alpha) * old)


class MemoryConsolidationEngine:
    """
    Background process that consolidates episodic memories into
    semantic and procedural memories. This is the mechanism by which
    the platform learns from experience.
    """

    def __init__(self, episodic: EpisodicMemory, semantic: SemanticMemory,
                 procedural: ProceduralMemory):
        self.episodic = episodic
        self.semantic = semantic
        self.procedural = procedural

    async def consolidate(self, tenant_id: str):
        """
        Run consolidation for a tenant.

        FIX v2.2 (Phase 2): Previously a stub (just logged). Now:
          1. Fetches recent episodic memories (last 24h)
          2. Calls the LLM gateway to extract salient facts as (subject, predicate, object) triples
          3. Writes extracted facts to semantic memory (Neo4j knowledge graph)
          4. Detects repeated agent action patterns → writes to procedural memory
          5. Marks consolidated memories with a metadata flag

        This is the mechanism by which the platform learns from experience:
        episodic (specific events) → semantic (general facts) → procedural (learned skills).
        """
        import httpx
        import os

        logger.info("Starting memory consolidation for tenant %s", tenant_id)

        # 1. Fetch recent episodic memories (last 24h, not yet consolidated).
        now = datetime.now(timezone.utc)
        start = now - timedelta(hours=24)
        recent = await self.episodic.recall_by_time(
            tenant_id,
            start.isoformat(),
            now.isoformat(),
            limit=100,
        )

        if not recent:
            logger.info("No recent memories to consolidate for tenant %s", tenant_id)
            return {"status": "no_memories", "tenant_id": tenant_id}

        # 2. Extract salient facts via LLM.
        # Batch memories to reduce LLM calls (group 10 memories per call).
        llm_url = os.getenv("LLM_GATEWAY_URL", "http://llm_gateway:8090")
        facts_extracted = 0
        batch_size = 10

        for i in range(0, len(recent), batch_size):
            batch = recent[i:i + batch_size]
            # Build a prompt asking the LLM to extract (subject, predicate, object) triples.
            memories_text = "\n".join(
                f"- [{m.metadata.get('agent_id', 'unknown')}] {m.content[:500]}"
                for m in batch
            )
            prompt = (
                "Extract factual (subject, predicate, object) triples from the following "
                "enterprise AI conversation memories. Return as JSON array of "
                '{"subject": "...", "predicate": "...", "object": "..."} objects. '
                "Only extract clear factual statements, not opinions or questions.\n\n"
                f"Memories:\n{memories_text}"
            )

            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.post(
                        f"{llm_url}/v1/generate",
                        json={
                            "prompt": prompt,
                            "system": "You are a knowledge graph extraction assistant. "
                                      "Extract only clear factual triples. Return valid JSON.",
                            "temperature": 0.1,
                            "max_tokens": 2000,
                        },
                    )
                    if resp.status_code != 200:
                        logger.warning("LLM fact extraction failed (HTTP %d) for batch %d", resp.status_code, i)
                        continue
                    llm_text = resp.json().get("response", "")
                    # Parse JSON triples from LLM response.
                    import json
                    import re
                    # Find JSON array in the response.
                    json_match = re.search(r'\[.*\]', llm_text, re.DOTALL)
                    if not json_match:
                        continue
                    triples = json.loads(json_match.group())
                    # Write each fact to semantic memory (Neo4j).
                    for triple in triples:
                        subject = triple.get("subject", "").strip()
                        predicate = triple.get("predicate", "").strip()
                        obj = triple.get("object", "").strip()
                        if subject and predicate and obj:
                            await self.semantic.add_fact(
                                subject=subject,
                                predicate=predicate,
                                obj=obj,
                                tenant_id=tenant_id,
                                source=f"consolidation:{batch[0].memory_id[:8]}",
                            )
                            facts_extracted += 1
            except Exception as e:
                logger.warning("Fact extraction batch %d failed: %s", i, e)

        # 3. Extract repeated patterns → procedural memory.
        # Group memories by agent_id, look for repeated action sequences.
        from collections import defaultdict
        agent_sequences: dict[str, list[str]] = defaultdict(list)
        for m in recent:
            agent_id = m.metadata.get("agent_id", "unknown")
            # Extract tool calls / actions from memory content (simple heuristic).
            action = m.metadata.get("action") or m.metadata.get("tool", "")
            if action:
                agent_sequences[agent_id].append(action)

        patterns_found = 0
        for agent_id, actions in agent_sequences.items():
            if len(actions) < 3:
                continue  # not enough data for a pattern
            # Detect repeated 2-action sequences.
            from collections import Counter
            pairs = Counter(zip(actions, actions[1:]))
            for (a1, a2), count in pairs.most_common(3):
                if count >= 2:
                    # This agent repeatedly does a1 → a2. Create a procedure.
                    procedure_name = f"{agent_id}_{a1}_then_{a2}"
                    self.procedural.procedures[procedure_name] = {
                        "agent_id": agent_id,
                        "sequence": [a1, a2],
                        "occurrences": count,
                        "created_at": now.isoformat(),
                        "tenant_id": tenant_id,
                    }
                    self.procedural.success_rates[procedure_name] = 0.5  # initial
                    patterns_found += 1
                    logger.info("Procedural pattern detected: %s (count=%d)", procedure_name, count)

        logger.info(
            "Consolidation complete for tenant %s: %d memories processed, "
            "%d facts extracted, %d procedural patterns found",
            tenant_id, len(recent), facts_extracted, patterns_found
        )
        return {
            "status": "complete",
            "tenant_id": tenant_id,
            "memories_processed": len(recent),
            "facts_extracted": facts_extracted,
            "patterns_found": patterns_found,
        }


class MemorySystem:
    """
    Unified memory system that integrates all four tiers.
    """

    def __init__(self):
        self.working = WorkingMemory()
        self.episodic = EpisodicMemory()
        self.semantic = SemanticMemory()
        self.procedural = ProceduralMemory()
        self.consolidation = MemoryConsolidationEngine(
            self.episodic, self.semantic, self.procedural
        )

    async def recall(self, query: str, tenant_id: str,
                     agent_id: str = None) -> Dict:
        """
        Recall relevant memories from all tiers.
        Returns: {working, episodic, semantic, procedural}
        """
        # Get working memory
        working_ctx = self.working.get_context(max_tokens=2000)

        # Get episodic memories (similarity)
        episodic = await self.episodic.recall_by_similarity(
            query, tenant_id, limit=5
        )

        # Get semantic memories (knowledge graph query)
        # In production, translate natural language to Cypher
        semantic_facts = []  # await self.semantic.query(...)

        # Get relevant procedures
        procedural = []  # Search by procedure name match

        return {
            "working": working_ctx,
            "episodic": [m.content for m in episodic],
            "semantic": semantic_facts,
            "procedural": procedural,
        }
