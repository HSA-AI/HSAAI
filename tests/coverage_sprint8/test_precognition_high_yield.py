import pytest


def _m():
    import common.precognition as module
    return module


@pytest.mark.asyncio
async def test_ingest_unknown_signal_does_not_predict(
    monkeypatch,
):
    m = _m()

    engine = m.EnterprisePrecognitionEngine()

    monkeypatch.setattr(
        m.time,
        "time",
        lambda: 1000.0,
    )

    signal = await engine.ingest_signal(
        "unknown_signal",
        "Something changed",
        0.8,
        source="monitor",
    )

    assert signal.signal_id == "signal-0001"
    assert signal.lead_time_hours == 72
    assert signal.confidence == pytest.approx(
        0.08
    )
    assert signal.detected_at == 1000.0
    assert engine._precognitions == []


@pytest.mark.asyncio
async def test_ingest_known_weak_signal_no_prediction():
    m = _m()

    engine = m.EnterprisePrecognitionEngine()

    signal = await engine.ingest_signal(
        "supplier_response_time_slowing",
        "Supplier responses are slowing",
        0.4,
    )

    assert signal.lead_time_hours == 168
    assert signal.confidence == pytest.approx(
        0.10
    )
    assert len(engine._signals) == 1
    assert engine._precognitions == []


@pytest.mark.asyncio
async def test_ingest_known_strong_signal_generates_prediction():
    m = _m()

    engine = m.EnterprisePrecognitionEngine()

    signal = await engine.ingest_signal(
        "supplier_response_time_slowing",
        "Supplier response degraded",
        0.8,
    )

    assert len(engine._precognitions) == 1

    precog = engine._precognitions[0]

    assert (
        precog.precognition_id
        == "precog-0001"
    )
    assert (
        precog.predicted_event
        == "Supply Disruption"
    )
    assert precog.event_type == "risk"
    assert precog.lead_signals == [signal]
    assert "Pre-position" in (
        precog.recommended_preparation
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "lead_hours,expected_window",
    [
        (48, "2-3 days"),
        (120, "5-8 days"),
        (336, "2-3 weeks"),
        (720, "1-2 months"),
    ],
)
async def test_generate_precognition_time_windows(
    lead_hours,
    expected_window,
):
    m = _m()

    engine = m.EnterprisePrecognitionEngine()

    signal = m.WeakSignal(
        signal_type="test",
        strength=0.8,
        confidence=0.7,
    )

    precog = await engine._generate_precognition(
        signal,
        {
            "leads_to": "custom_event",
            "lead_time_hours": lead_hours,
            "probability_boost": 0.2,
        },
    )

    assert (
        precog.time_window
        == expected_window
    )

    assert (
        precog.recommended_preparation
        == "Monitor situation closely."
    )

    assert precog.event_type == "opportunity"
    assert precog.probability == pytest.approx(
        0.46
    )
    assert "minor" in precog.potential_impact


@pytest.mark.asyncio
async def test_generate_prediction_probability_cap_and_risk():
    m = _m()

    engine = m.EnterprisePrecognitionEngine()

    signal = m.WeakSignal(
        strength=10.0,
        confidence=0.9,
    )

    precog = await engine._generate_precognition(
        signal,
        {
            "leads_to": "supply_disruption",
            "lead_time_hours": 168,
            "probability_boost": 0.5,
        },
    )

    assert precog.probability == 0.95
    assert precog.event_type == "risk"
    assert "negative" in (
        precog.potential_impact
    )


@pytest.mark.asyncio
async def test_scan_signal_cluster_and_ignore_stale(
    monkeypatch,
):
    m = _m()

    engine = m.EnterprisePrecognitionEngine()

    now = 1_000_000.0

    monkeypatch.setattr(
        m.time,
        "time",
        lambda: now,
    )

    engine._signals = [
        m.WeakSignal(
            signal_id="s1",
            signal_type=(
                "supplier_response_time_slowing"
            ),
            strength=0.6,
            detected_at=now - 100,
        ),
        m.WeakSignal(
            signal_id="s2",
            signal_type=(
                "supplier_response_time_slowing"
            ),
            strength=0.8,
            detected_at=now - 200,
        ),
        m.WeakSignal(
            signal_id="old",
            signal_type=(
                "supplier_response_time_slowing"
            ),
            strength=1.0,
            detected_at=(
                now - (86400 * 8)
            ),
        ),
        m.WeakSignal(
            signal_id="unknown",
            signal_type="not_known",
            strength=0.9,
            detected_at=now,
        ),
    ]

    result = await engine.scan_all_signals()

    assert len(result) == 1

    precog = result[0]

    assert len(
        precog.lead_signals
    ) == 2

    assert {
        s.signal_id
        for s in precog.lead_signals
    } == {"s1", "s2"}

    assert precog.confidence <= 0.9
    assert precog in engine._precognitions


@pytest.mark.asyncio
async def test_scan_single_signal_no_cluster(
    monkeypatch,
):
    m = _m()

    engine = m.EnterprisePrecognitionEngine()

    now = 5000.0

    monkeypatch.setattr(
        m.time,
        "time",
        lambda: now,
    )

    engine._signals = [
        m.WeakSignal(
            signal_id="s1",
            signal_type=(
                "quality_metrics_drifting"
            ),
            strength=0.8,
            detected_at=now,
        )
    ]

    assert (
        await engine.scan_all_signals()
        == []
    )


@pytest.mark.asyncio
async def test_verify_confirmed_and_falsified():
    m = _m()

    engine = m.EnterprisePrecognitionEngine()

    p1 = m.Precognition(
        precognition_id="p1",
    )
    p2 = m.Precognition(
        precognition_id="p2",
    )

    engine._precognitions = [
        p1,
        p2,
    ]

    await engine.verify(
        "p1",
        True,
        True,
        False,
    )

    await engine.verify(
        "p2",
        False,
        False,
        False,
    )

    assert (
        p1.verification_status
        == "confirmed"
    )
    assert (
        p2.verification_status
        == "falsified"
    )

    assert len(
        engine._verifications
    ) == 2

    assert engine._accuracy_history[
        0
    ] == pytest.approx(2 / 3)

    assert engine._accuracy_history[
        1
    ] == 0.0


@pytest.mark.asyncio
async def test_verify_unknown_prediction_still_records():
    m = _m()

    engine = m.EnterprisePrecognitionEngine()

    await engine.verify(
        "does-not-exist",
        True,
        False,
        True,
    )

    assert len(
        engine._verifications
    ) == 1

    assert engine._accuracy_history[
        0
    ] == pytest.approx(2 / 3)


def test_get_precognitions_status_and_limit():
    m = _m()

    engine = m.EnterprisePrecognitionEngine()

    signal = m.WeakSignal(
        signal_id="s1",
        description="lead signal",
    )

    engine._precognitions = [
        m.Precognition(
            precognition_id="p1",
            verification_status="pending",
            lead_signals=[signal],
        ),
        m.Precognition(
            precognition_id="p2",
            verification_status="confirmed",
            lead_signals=[signal],
        ),
        m.Precognition(
            precognition_id="p3",
            verification_status="confirmed",
            lead_signals=[signal],
        ),
    ]

    all_items = (
        engine.get_precognitions(
            limit=2
        )
    )

    assert [
        x["precognition_id"]
        for x in all_items
    ] == ["p2", "p3"]

    confirmed = (
        engine.get_precognitions(
            status="confirmed",
            limit=10,
        )
    )

    assert len(confirmed) == 2
    assert (
        confirmed[0][
            "lead_signals"
        ][0]["signal_id"]
        == "s1"
    )


def test_stats_empty_and_populated():
    m = _m()

    engine = m.EnterprisePrecognitionEngine()

    empty = engine.stats()

    assert empty[
        "signals_detected"
    ] == 0
    assert empty[
        "prediction_accuracy"
    ] == 0

    engine._signals.append(
        m.WeakSignal()
    )

    engine._precognitions.extend(
        [
            m.Precognition(
                verification_status=(
                    "confirmed"
                )
            ),
            m.Precognition(
                verification_status=(
                    "falsified"
                )
            ),
            m.Precognition(
                verification_status=(
                    "pending"
                )
            ),
        ]
    )

    engine._accuracy_history = [
        1.0,
        0.5,
    ]

    stats = engine.stats()

    assert stats[
        "signals_detected"
    ] == 1

    assert stats[
        "precognitions_generated"
    ] == 3

    assert stats[
        "precognitions_confirmed"
    ] == 1

    assert stats[
        "precognitions_falsified"
    ] == 1

    assert stats[
        "prediction_accuracy"
    ] == pytest.approx(0.75)

    assert stats[
        "known_patterns"
    ] == len(
        engine._signal_patterns
    )
