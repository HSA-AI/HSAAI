import importlib
from types import SimpleNamespace


def test_explainability_no_infra_record_missing_and_low_trust(monkeypatch):
    m = importlib.import_module("common.governance.explainability")
    monkeypatch.setattr(m, "_REDIS_AVAILABLE", False)
    monkeypatch.setattr(m, "_SQLALCHEMY_AVAILABLE", False)

    engine = m.ExplainabilityEngine()
    rec = m.DecisionRecord(
        decision_id="d1",
        user_id="u1",
        tenant_id="t1",
        model="mock-model",
        prompt="policy?",
        output="answer",
        confidence=0.4,
        rag_chunks=[],
        factors={"rag_grounding": 0.0, "citation_density": 0.0, "freshness": 0.0},
        safety_filter_passed=False,
    )
    assert engine.record(rec) == "d1"

    missing = engine.explain("missing")
    assert missing["composite_score"] == 0.0
    assert "record_missing" in missing["caveats"]

    monkeypatch.setattr(engine, "get", lambda decision_id: rec)
    explained = engine.explain("d1")
    assert "low_model_confidence" in explained["caveats"]
    assert "no_rag_grounding" in explained["caveats"]
    assert "safety_filter_failed" in explained["caveats"]
    assert explained["composite_score"] < 0.5


def test_risk_engine_init_and_hash_chained_audit_without_services(monkeypatch):
    m = importlib.import_module("common.governance.risk_engine")
    monkeypatch.setattr(m, "_REDIS_AVAILABLE", False)
    monkeypatch.setattr(m, "_SQLALCHEMY_AVAILABLE", False)

    engine = m.RiskEngine()
    assert engine._last_hash == "genesis"
    assert m.risk_level_for_score(10) == m.RiskLevel.LOW
    assert m.risk_level_for_score(50) == m.RiskLevel.MEDIUM
    assert m.risk_level_for_score(70) == m.RiskLevel.HIGH
    assert m.risk_level_for_score(90) == m.RiskLevel.CRITICAL
    assert engine._factor_action_type("delete:document") >= 70
    assert engine._factor_time_of_day("2026-01-01T02:00:00+00:00") == 10

    result = m.RiskResult(
        score=75,
        level=m.RiskLevel.HIGH,
        factors={"action": 70},
        auto_approve=False,
        requires_human_approval=True,
        requires_two_person_rule=False,
        requires_committee_notify=False,
        request_id="r1",
        context_snapshot={"tenant_id": "t1", "user_role": "employee", "action_type": "delete:document"},
    )
    engine._audit(result)
    first = engine._last_hash
    assert first != "genesis"
    engine._audit(result)
    assert engine._last_hash != first
    assert engine.query_audit() == []
    assert engine.verify_integrity() is True


def test_policy_engine_loads_extra_yaml_and_deny_overrides_allow(tmp_path, monkeypatch):
    m = importlib.import_module("common.governance.policy_engine")
    monkeypatch.setattr(m, "_REDIS_AVAILABLE", False)

    policy_dir = tmp_path / "policies"
    policy_dir.mkdir()
    (policy_dir / "extra.yaml").write_text(
        """
policies:
  - id: allow_docs
    version: "1"
    effect: allow
    when:
      action: read:document
  - id: deny_prod_docs
    version: "1"
    effect: deny
    when:
      action: read:document
      env.is_production: true
""",
        encoding="utf-8",
    )
    (policy_dir / "broken.yaml").write_text("policies: [", encoding="utf-8")
    monkeypatch.setenv("POLICY_DIR", str(policy_dir))

    engine = m.PolicyEngine(policy_paths=[str(tmp_path / "does-not-exist.yaml")])
    ids = {p["id"] for p in engine.list_policies()}
    assert "allow_docs" in ids
    assert "deny_prod_docs" in ids

    req = m.Request(
        subject={"roles": ["employee"], "tenant_id": "t1"},
        action="read:document",
        resource={"classification": "public", "tenant_id": "t1"},
        env={"is_production": True},
    )
    decision = engine.evaluate(req)
    assert decision.allowed is False
    assert decision.denied_by is not None
