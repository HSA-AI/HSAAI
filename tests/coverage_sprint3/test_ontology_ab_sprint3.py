import random

def test_ontology_constraints_and_catalog_are_consistent():
    from backend_core.knowledge_graph.ontology import (
        EntityType,
        RelationshipType,
        ENTITY_DEFINITIONS,
        RELATIONSHIP_DEFINITIONS,
        INFERENCE_RULES,
        ENTITY_RESOLUTION_RULES,
        TAXONOMY,
        get_cypher_schema_constraints,
    )

    assert EntityType.EMPLOYEE.value == "Employee"
    assert RelationshipType.WORKS_IN.value == "WORKS_IN"
    assert len(ENTITY_DEFINITIONS) >= 8
    assert len(RELATIONSHIP_DEFINITIONS) >= 10
    assert len(INFERENCE_RULES) >= 4
    assert len(ENTITY_RESOLUTION_RULES) >= 4
    assert "Document" in TAXONOMY and "Policy" in TAXONOMY["Document"]

    constraints = get_cypher_schema_constraints()
    assert constraints
    assert any("CREATE CONSTRAINT" in c for c in constraints)
    assert any("CREATE INDEX" in c for c in constraints)
    assert any("Employee" in c for c in constraints)


def test_ab_testing_assignment_results_and_inactive(monkeypatch):
    import backend_core.ai_quality.ab_testing as ab

    monkeypatch.setattr(ab, "_redis_client", None)
    svc = ab.ABTestingService()

    first = svc.get_variant("prompt_temperature_v1", user_id="u-123", tenant_id="t1")
    second = svc.get_variant("prompt_temperature_v1", user_id="u-123", tenant_id="t1")
    assert first == second
    assert first["variant"] in {"A", "B", "C"}
    assert isinstance(first["config"], dict)

    assert svc.get_variant("does-not-exist", user_id="x") is None

    exp = svc._experiments["prompt_temperature_v1"]
    exp.min_samples = 2
    svc.record_outcome("prompt_temperature_v1", "A", 0.95, 100)
    svc.record_outcome("prompt_temperature_v1", "A", 0.90, 120)
    svc.record_outcome("prompt_temperature_v1", "B", 0.50, 180)
    svc.record_outcome("prompt_temperature_v1", "B", 0.55, 200)
    svc._check_significance("prompt_temperature_v1")

    result = svc.get_results("prompt_temperature_v1")
    assert result["A"]["count"] == 2
    assert result["A"]["mean_score"] > result["B"]["mean_score"]
    assert result["A"]["min_samples_met"] is True

    exp.is_active = False
    assert svc.get_variant("prompt_temperature_v1", user_id="u-123") is None


def test_ab_testing_anonymous_and_new_bucket(monkeypatch):
    import backend_core.ai_quality.ab_testing as ab

    monkeypatch.setattr(ab, "_redis_client", None)
    monkeypatch.setattr(random, "random", lambda: 0.99999)
    svc = ab.ABTestingService()

    out = svc.get_variant("model_comparison_v1", user_id="")
    assert out["variant"] == "14b"

    svc.record_outcome("new-exp", "Z", 0.75, 321)
    assert svc._results["new-exp"]["Z"]["count"] == 1
    assert svc.get_results("new-exp")["Z"]["mean_latency_ms"] == 321
