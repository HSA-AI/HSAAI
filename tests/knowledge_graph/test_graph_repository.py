from backend_core.db.database import Base, engine, SessionLocal
from backend_core.knowledge_graph.graph_repository import GraphRepository


def test_graph_entity_relationship_lifecycle():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        repo = GraphRepository(db)
        entity = repo.upsert_entity({"entity_key": "system:test", "name": "Test System", "entity_type": "System"})
        assert entity.entity_key == "system:test"
        rel = repo.add_relationship({"source_key": "system:test", "target_key": "policy:test", "relationship_type": "GOVERNED_BY"})
        assert rel.relationship_type == "GOVERNED_BY"
        result = repo.search("Test", "default", "default")
        assert result["result_count"] >= 1
    finally:
        db.close()
