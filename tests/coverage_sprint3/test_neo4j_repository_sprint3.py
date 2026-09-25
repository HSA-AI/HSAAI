import pytest

class Result:
    def __init__(self, single=None, rows=None):
        self._single = single
        self._rows = rows or []
    def single(self):
        return self._single
    def __iter__(self):
        return iter(self._rows)

class Session:
    def __init__(self):
        self.closed = 0
        self.calls = []
        self.mode = "default"
    def run(self, query, params=None):
        self.calls.append((query, params))
        q = " ".join(query.split())
        if "RETURN e" in q and "MERGE" in q:
            return Result({"e": {"entity_key": "document:test", "name": "Test"}})
        if "MATCH (e:Entity {entity_key:" in q and "RETURN e" in q:
            return Result({"e": {"entity_key": "document:test", "name": "Test"}})
        if "RETURN e" in q and "LIMIT" in q:
            return Result(rows=[{"e": {"entity_key": "a"}}, {"e": {"entity_key": "b"}}])
        if "RETURN r" in q:
            return Result({"r": {"type": "MENTIONS"}})
        if "type(r) as rel_type" in q:
            return Result(rows=[{"rel_type": "MENTIONS", "direction": "outgoing"}])
        if "path_nodes" in q:
            return Result({"path_nodes": [{"entity_key": "a"}, {"entity_key": "b"}],
                           "path_rels": ["MENTIONS"]})
        if "gds.louvain.stream" in q:
            return Result(rows=[{"communityId": 1, "members": ["a", "b"], "size": 2}])
        if "gds.pageRank.stream" in q:
            return Result(rows=[{"entity_key": "a", "name": "A", "entity_type": "Document", "score": 1.0}])
        return Result()
    def close(self):
        self.closed += 1


def _repo_with(session):
    from backend_core.knowledge_graph.neo4j_repository import Neo4jGraphRepository
    repo = Neo4jGraphRepository.__new__(Neo4jGraphRepository)
    repo.uri = "bolt://unit"
    repo.username = "neo4j"
    repo.password = ""
    repo._driver = None
    repo._get_session = lambda: session
    return repo


def test_neo4j_crud_relationships_traversal_and_audit():
    s = Session()
    repo = _repo_with(s)

    entity = repo.upsert_entity({"name": "Test", "entity_type": "Document"})
    assert entity["name"] == "Test"

    got = repo.get_entity("document:test")
    assert got["entity_key"] == "document:test"

    assert len(repo.list_entities()) == 2
    assert len(repo.list_entities("Document")) == 2

    rel = repo.add_relationship({
        "source_key": "a",
        "target_key": "b",
        "relationship_type": "MENTIONS",
    })
    assert rel["type"] == "MENTIONS"

    with pytest.raises(ValueError):
        repo.add_relationship({
            "source_key": "a",
            "target_key": "b",
            "relationship_type": "DROP TABLE",
        })

    for direction in ("incoming", "outgoing", "both"):
        rows = repo.get_relationships("a", direction=direction)
        assert rows and rows[0]["rel_type"] == "MENTIONS"

    path = repo.shortest_path("a", "b")
    assert path["length"] == 1
    assert path["relationships"] == ["MENTIONS"]

    communities = repo.find_communities()
    assert communities[0]["size"] == 2

    central = repo.find_central_entities()
    assert central[0]["entity_key"] == "a"

    repo.audit("read", "tester", "entity", "a", {"ok": True})
    assert any("AuditLog" in q for q, _ in s.calls)


def test_neo4j_no_session_fail_safe():
    from backend_core.knowledge_graph.neo4j_repository import Neo4jGraphRepository
    repo = Neo4jGraphRepository.__new__(Neo4jGraphRepository)
    repo._driver = None

    assert repo._get_session() is None
    assert repo.upsert_entity({"name": "x"}) is None
    assert repo.get_entity("x") is None
    assert repo.list_entities() == []
    assert repo.add_relationship({"relationship_type": "MENTIONS"}) is None
    assert repo.get_relationships("x") == []
    assert repo.shortest_path("a", "b") == []
    assert repo.find_communities() == []
    assert repo.find_central_entities() == []
    assert repo.audit("x", "a", "r", "id") is None
