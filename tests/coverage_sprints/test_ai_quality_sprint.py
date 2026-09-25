import importlib

import pytest


def _module():
    return importlib.import_module("backend_core.ai_quality.eval_pipeline")


@pytest.mark.asyncio
async def test_hallucination_detector_basic_supported_and_contradiction_paths(monkeypatch):
    m = _module()
    detector = m.HallucinationDetector()

    basic = await detector.detect("Revenue was 123 in 2026.", [])
    assert basic["total_claims"] >= 1
    assert basic["hallucination_risk"] > 0
    assert basic["unsupported_facts"]

    monkeypatch.setattr(detector, "_extract_claims", lambda text: ["Revenue was 100."])
    monkeypatch.setattr(detector, "_claim_context_similarity", lambda claim, doc: 0.9)
    supported = await detector.detect("x", ["Revenue was 100."])
    assert supported["hallucination_risk"] == 0.0
    assert supported["flagged_claims"] == []

    monkeypatch.setattr(detector, "_claim_context_similarity", lambda claim, doc: 0.0)
    monkeypatch.setattr(detector, "_has_contradiction_signals", lambda claim, doc: True)
    contradicted = await detector.detect("x", ["Revenue was not 100."])
    assert contradicted["contradictions"]
    assert contradicted["hallucination_risk"] == 1.0


@pytest.mark.asyncio
async def test_evaluate_response_pass_and_issue_collection(monkeypatch):
    m = _module()

    async def safe_detect(self, response, context_documents, threshold=0.3):
        return {
            "hallucination_risk": 0.0,
            "flagged_claims": [],
            "unsupported_facts": [],
            "contradictions": [],
            "total_claims": 1,
        }
    monkeypatch.setattr(m.HallucinationDetector, "detect", safe_detect)
    good = await m.evaluate_response(
        "prompt",
        "This is a grounded enterprise response.",
        context_documents=["This is a grounded enterprise response."],
        model="mock",
        tenant_id="t1",
    )
    assert good.hallucination_risk == 0.0
    assert good.policy_compliance == 1.0
    assert good.overall_score > 0.5

    async def risky_detect(self, response, context_documents, threshold=0.3):
        return {
            "hallucination_risk": 0.8,
            "flagged_claims": ["unsupported"],
            "unsupported_facts": ["unsupported fact 2026"],
            "contradictions": [],
            "total_claims": 1,
        }
    monkeypatch.setattr(m.HallucinationDetector, "detect", risky_detect)
    bad = await m.evaluate_response(
        "prompt",
        "api_key=ABCDEFGHIJKLMNOPQRSTUV exploit user@example.com",
        context_documents=[],
        policy_rules=["default"],
    )
    assert bad.passed is False
    assert bad.policy_compliance < 0.8
    assert any("Hallucination" in issue for issue in bad.issues)
    assert any("Policy compliance" in issue for issue in bad.issues)


def test_arabic_quality_and_policy_compliance_security_signals():
    m = _module()
    assert m._evaluate_arabic_quality("plain English answer") == 1.0
    assert m._evaluate_arabic_quality("قصير") < 1.0

    safe = m._evaluate_policy_compliance("normal enterprise response", [])
    leaked = m._evaluate_policy_compliance(
        "api_key=ABCDEFGHIJKLMNOPQRSTUV phone 123-456-7890 exploit", []
    )
    assert safe == 1.0
    assert leaked <= 0.2
