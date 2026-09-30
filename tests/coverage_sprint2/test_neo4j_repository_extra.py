
def test_neo4j_repository_import():

    from services.backend_core.knowledge_graph import neo4j_repository

    assert neo4j_repository is not None


def test_repository_classes_exist():

    from services.backend_core.knowledge_graph.neo4j_repository import (
        Neo4jGraphRepository
    )

    assert Neo4jGraphRepository is not None
