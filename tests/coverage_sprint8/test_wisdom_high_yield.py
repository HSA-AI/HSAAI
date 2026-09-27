import pytest


def _m():
    import common.wisdom as module
    return module


def test_wisdom_and_failure_serialization():
    m = _m()

    crystal = m.WisdomCrystal(
        wisdom_id="wisdom-1",
        statement="Use audited data",
        confidence=0.91,
        domain="finance",
    )

    data = crystal.to_dict()

    assert data["wisdom_id"] == "wisdom-1"
    assert data["statement"] == "Use audited data"
    assert data["confidence"] == 0.91

    rebuilt = m.WisdomCrystal.from_dict(
        {
            **data,
            "unknown_field": "ignored",
        }
    )

    assert rebuilt.wisdom_id == "wisdom-1"
    assert not hasattr(
        rebuilt,
        "unknown_field",
    )

    failure = m.FailureRecord(
        failure_id="failure-1",
        what_happened="Deployment failed",
        what_was_expected="Deployment succeeds",
        root_cause="Configuration",
    )

    assert failure.to_dict()[
        "root_cause"
    ] == "Configuration"


@pytest.mark.asyncio
async def test_crystallize_insufficient_evidence():
    m = _m()

    engine = m.WisdomCrystallizationEngine()

    result = await engine.crystallize(
        [
            {
                "decision_id": "d1",
                "outcome": "success",
            }
        ],
        min_evidence=2,
    )

    assert result == []
    assert engine.list_wisdom() == []


@pytest.mark.asyncio
async def test_crystallize_creates_only_high_confidence(
    monkeypatch,
):
    m = _m()

    engine = m.WisdomCrystallizationEngine()

    async def patterns(*args, **kwargs):
        return [
            {
                "statement": "Low confidence",
                "confidence": 0.40,
            },
            {
                "statement": "Prefer audited inputs",
                "confidence": 0.92,
                "conditions": "source == 'audited'",
                "counter_examples": 1,
            },
        ]

    monkeypatch.setattr(
        engine,
        "_extract_patterns",
        patterns,
    )

    monkeypatch.setattr(
        m.time,
        "time",
        lambda: 1234.5,
    )

    decisions = [
        {
            "decision_id": f"d{i}",
            "outcome": "success",
        }
        for i in range(12)
    ]

    result = await engine.crystallize(
        decisions,
        domain="finance",
        tenant_id="tenant-1",
        min_confidence=0.7,
        min_evidence=10,
    )

    assert len(result) == 1

    crystal = result[0]

    assert crystal.wisdom_id == "wisdom-0001"
    assert (
        crystal.statement
        == "Prefer audited inputs"
    )
    assert crystal.domain == "finance"
    assert crystal.tenant_id == "tenant-1"
    assert crystal.counter_examples == 1
    assert crystal.crystallized_at == 1234.5
    assert len(crystal.derived_from) == 12

    assert (
        engine.get_wisdom(
            "wisdom-0001"
        )
        is crystal
    )


@pytest.mark.asyncio
async def test_extract_patterns_success_vs_failure():
    m = _m()

    engine = m.WisdomCrystallizationEngine()

    decisions = [
        {
            "decision_id": "s1",
            "outcome": "success",
            "strategy": "audited",
            "region": "mena",
        },
        {
            "decision_id": "s2",
            "outcome": "success",
            "strategy": "audited",
            "region": "mena",
        },
        {
            "decision_id": "s3",
            "outcome": "success",
            "strategy": "audited",
            "region": "mena",
        },
        {
            "decision_id": "f1",
            "outcome": "failure",
            "strategy": "manual",
            "region": "mena",
        },
    ]

    patterns = await engine._extract_patterns(
        decisions,
        "finance",
    )

    assert patterns
    assert any(
        "strategy='audited'"
        in p["statement"]
        for p in patterns
    )

    strategy = next(
        p
        for p in patterns
        if "strategy='audited'"
        in p["statement"]
    )

    assert strategy["confidence"] == 0.75
    assert strategy["counter_examples"] == 1


def test_find_common_attributes_paths():
    m = _m()

    engine = m.WisdomCrystallizationEngine()

    assert (
        engine._find_common_attributes([])
        == {}
    )

    common = engine._find_common_attributes(
        [
            {
                "region": "mena",
                "optional": "x",
            },
            {
                "region": "mena",
            },
            {
                "region": "mena",
            },
            {
                "region": "mena",
                "optional": None,
            },
        ]
    )

    assert common["region"] == "mena"
    assert "optional" not in common


def test_wisdom_listing_applicability_and_application(
    monkeypatch,
):
    m = _m()

    engine = m.WisdomCrystallizationEngine()

    c1 = m.WisdomCrystal(
        wisdom_id="w1",
        statement="General tenant wisdom",
        tenant_id="t1",
        domain="finance",
        applicable_when="",
    )

    c2 = m.WisdomCrystal(
        wisdom_id="w2",
        statement="Finance only",
        tenant_id="t1",
        domain="finance",
        applicable_when="department == 'finance'",
    )

    c3 = m.WisdomCrystal(
        wisdom_id="w3",
        statement="Other tenant",
        tenant_id="t2",
        domain="hr",
        applicable_when="",
    )

    engine._crystals = {
        "w1": c1,
        "w2": c2,
        "w3": c3,
    }

    assert len(
        engine.list_wisdom()
    ) == 3

    assert engine.list_wisdom(
        "finance"
    ) == [c1, c2]

    applicable = (
        engine.find_applicable_wisdom(
            {
                "tenant_id": "t1",
                "department": "finance",
            }
        )
    )

    assert c1 in applicable
    assert c2 in applicable
    assert c3 not in applicable

    monkeypatch.setattr(
        m.time,
        "time",
        lambda: 999.0,
    )

    engine.record_application("w1")

    assert c1.application_count == 1
    assert c1.last_applied == 999.0

    engine.record_application("missing")
    assert (
        engine.get_wisdom("missing")
        is None
    )


def test_failure_memory_full_lifecycle():
    m = _m()

    memory = m.FailureMemory()

    first = memory.record_failure(
        what_happened=(
            "supplier invoice sync failed"
        ),
        what_was_expected="sync succeeds",
        root_cause="timeout",
        cost_estimate=120.5,
        lesson_learned=(
            "Use redundant supplier endpoint"
        ),
        avoidance_strategy="retry",
        domain="finance",
        tenant_id="t1",
    )

    second = memory.record_failure(
        what_happened=(
            "supplier payment sync failed"
        ),
        what_was_expected="payment succeeds",
        root_cause="network",
        cost_estimate=79.5,
        lesson_learned=(
            "Validate network before sync"
        ),
        domain="finance",
        tenant_id="t1",
    )

    third = memory.record_failure(
        what_happened="employee import failed",
        what_was_expected="import succeeds",
        root_cause="schema",
        cost_estimate=50,
        domain="hr",
        tenant_id="t2",
    )

    assert first.failure_id == "failure-0001"
    assert second.failure_id == "failure-0002"
    assert third.failure_id == "failure-0003"

    # Stabilize ordering without monkeypatching the global time module.
    first.occurred_at = 100.0
    second.occurred_at = 200.0
    third.occurred_at = 300.0

    assert (
        memory.get_failure(
            "failure-0001"
        )
        is first
    )

    assert memory.get_failure(
        "missing"
    ) is None

    similar = memory.find_similar_failures(
        "supplier sync problem",
        domain="finance",
        tenant_id="t1",
        limit=1,
    )

    assert len(similar) == 1
    assert similar[0].tenant_id == "t1"

    assert (
        memory.find_similar_failures(
            "employee import",
            domain="finance",
            tenant_id="t1",
        )
        == []
    )

    finance = memory.list_failures(
        domain="finance",
    )

    assert finance == [
        second,
        first,
    ]

    assert (
        memory.total_failure_cost()
        == 250.0
    )

    assert memory.lessons_learned(
        "finance"
    ) == [
        "Validate network before sync",
        "Use redundant supplier endpoint",
    ]


def test_next_wisdom_id_sequence():
    m = _m()

    engine = m.WisdomCrystallizationEngine()

    assert (
        engine._next_wisdom_id()
        == "wisdom-0001"
    )
    assert (
        engine._next_wisdom_id()
        == "wisdom-0002"
    )
