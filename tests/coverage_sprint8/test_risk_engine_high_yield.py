import importlib
import json
from types import SimpleNamespace

import pytest


def _module():
    return importlib.import_module(
        "common.governance.risk_engine"
    )


class FakeRedis:
    def __init__(self, *, last_hash=None, rows=None, fail_write=False):
        self.last_hash = last_hash
        self.rows = rows or {}
        self.fail_write = fail_write
        self.set_calls = []
        self.lpush_calls = []
        self.expire_calls = []
        self.ltrim_calls = []

    def ping(self):
        return True

    def get(self, key):
        if key == "risk:audit:last_hash":
            return self.last_hash
        return None

    def set(self, key, value):
        if self.fail_write:
            raise RuntimeError("redis write failed")
        self.set_calls.append((key, value))

    def lpush(self, key, value):
        if self.fail_write:
            raise RuntimeError("redis write failed")
        self.lpush_calls.append((key, value))

    def ltrim(self, key, start, end):
        if self.fail_write:
            raise RuntimeError("redis write failed")
        self.ltrim_calls.append((key, start, end))

    def expire(self, key, ttl):
        if self.fail_write:
            raise RuntimeError("redis write failed")
        self.expire_calls.append((key, ttl))

    def lrange(self, key, start, end):
        return list(self.rows.get(key, []))


class ConnectContext:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self.conn

    def __exit__(self, *args):
        return False


class FakeConn:
    def __init__(self, *, fail=False, error_type=RuntimeError):
        self.fail = fail
        self.error_type = error_type
        self.calls = []

    def execute(self, statement, params=None):
        self.calls.append((str(statement), params))
        if self.fail:
            raise self.error_type("database failed")
        return SimpleNamespace()


class FakeEngine:
    def __init__(self, conn):
        self.conn = conn

    def connect(self):
        return ConnectContext(self.conn)

    def begin(self):
        return ConnectContext(self.conn)


def _bare_engine(m):
    engine = object.__new__(m.RiskEngine)
    engine.approved_geographies = {"YE"}
    engine.medium_requires_approval = False
    engine.redis = None
    engine.pg_engine = None
    engine._last_hash = "genesis"
    return engine


def test_risk_engine_init_success_loads_redis_hash_and_postgres(monkeypatch):
    m = _module()

    redis_client = FakeRedis(
        last_hash="persisted-hash"
    )

    monkeypatch.setattr(
        m,
        "_REDIS_AVAILABLE",
        True,
    )
    monkeypatch.setattr(
        m.redis,
        "from_url",
        lambda *args, **kwargs: redis_client,
    )

    conn = FakeConn()
    pg = FakeEngine(conn)

    monkeypatch.setattr(
        m,
        "_SQLALCHEMY_AVAILABLE",
        True,
    )
    monkeypatch.setattr(
        m,
        "create_engine",
        lambda *args, **kwargs: pg,
    )

    engine = m.RiskEngine(
        redis_url="redis://unit",
        postgres_url="postgresql://unit",
    )

    assert engine.redis is redis_client
    assert engine._last_hash == "persisted-hash"
    assert engine.pg_engine is pg
    assert len(conn.calls) == 1
    assert "SELECT 1" in conn.calls[0][0]


def test_risk_engine_init_handles_redis_and_postgres_failures(monkeypatch):
    m = _module()

    monkeypatch.setattr(
        m,
        "_REDIS_AVAILABLE",
        True,
    )
    monkeypatch.setattr(
        m.redis,
        "from_url",
        lambda *a, **k: (_ for _ in ()).throw(
            RuntimeError("redis unavailable")
        ),
    )

    monkeypatch.setattr(
        m,
        "_SQLALCHEMY_AVAILABLE",
        True,
    )
    monkeypatch.setattr(
        m,
        "create_engine",
        lambda *a, **k: (_ for _ in ()).throw(
            RuntimeError("postgres unavailable")
        ),
    )

    engine = m.RiskEngine(
        postgres_url="postgresql://broken",
    )

    assert engine.redis is None
    assert engine._last_hash == "genesis"
    assert engine.pg_engine is None


@pytest.mark.parametrize(
    "factor_value,medium_requires,expected_level,auto,human,two_person",
    [
        (0, False, "low", True, False, False),
        (50, False, "medium", True, False, False),
        (50, True, "medium", False, False, False),
        (70, False, "high", False, True, False),
        (100, False, "critical", False, True, True),
    ],
)
def test_score_decision_flags(
    monkeypatch,
    factor_value,
    medium_requires,
    expected_level,
    auto,
    human,
    two_person,
):
    m = _module()

    engine = _bare_engine(m)
    engine.medium_requires_approval = medium_requires

    # Make the score deterministic: only action contributes.
    engine._factor_action_type = lambda value: factor_value
    engine._factor_data_sensitivity = lambda value: 0
    engine._factor_user_role = lambda value: 0
    engine._factor_tenant = lambda value: 0
    engine._factor_time_of_day = lambda value: 0
    engine._factor_geography = lambda value: 0

    audited = []
    engine._audit = lambda result: audited.append(result)

    monkeypatch.setattr(
        m,
        "asdict",
        lambda obj: dict(vars(obj)),
    )

    ctx = SimpleNamespace(
        action_type="test:resource",
        data_sensitivity="public",
        user_role="employee",
        tenant_trust_tier="trusted",
        timestamp="2026-09-27T12:00:00+00:00",
        geography="YE",
        request_id="request-1",
        tenant_id="tenant-a",
    )

    result = engine.score(ctx)

    assert result.level.value == expected_level
    assert result.auto_approve is auto
    assert result.requires_human_approval is human
    assert result.requires_two_person_rule is two_person
    assert result.requires_committee_notify is two_person
    assert audited == [result]


def test_query_audit_filters_tenant_score_level_and_bad_json():
    m = _module()

    high = {
        "event_id": "h",
        "score": 80,
        "level": m.RiskLevel.HIGH.value,
    }
    low = {
        "event_id": "l",
        "score": 20,
        "level": m.RiskLevel.LOW.value,
    }

    redis_client = FakeRedis(
        rows={
            "risk:audit:tenant:t1": [
                json.dumps(high),
                "{bad json",
                json.dumps(low),
            ],
            "risk:audit:events": [
                json.dumps(low),
                json.dumps(high),
            ],
        }
    )

    engine = _bare_engine(m)
    engine.redis = redis_client

    rows = engine.query_audit(
        tenant_id="t1",
        min_score=50,
        level=m.RiskLevel.HIGH,
        limit=10,
    )

    assert [x["event_id"] for x in rows] == ["h"]

    all_rows = engine.query_audit(limit=10)
    assert len(all_rows) == 2


def test_verify_integrity_valid_broken_and_malformed():
    m = _module()

    oldest = {
        "previous_hash": "genesis",
        "entry_hash": "h1",
    }
    newest = {
        "previous_hash": "h1",
        "entry_hash": "h2",
    }

    engine = _bare_engine(m)

    # Redis order is newest first; method reverses it.
    engine.redis = FakeRedis(
        rows={
            "risk:audit:events": [
                json.dumps(newest),
                json.dumps(oldest),
            ]
        }
    )

    assert engine.verify_integrity() is True

    broken = dict(newest)
    broken["previous_hash"] = "wrong"

    engine.redis = FakeRedis(
        rows={
            "risk:audit:events": [
                json.dumps(broken),
                json.dumps(oldest),
            ]
        }
    )

    assert engine.verify_integrity() is False

    engine.redis = FakeRedis(
        rows={
            "risk:audit:events": [
                "{not-json",
            ]
        }
    )

    assert engine.verify_integrity() is False


def test_audit_writes_postgres_and_redis():
    m = _module()

    redis_client = FakeRedis()
    conn = FakeConn()

    engine = _bare_engine(m)
    engine.redis = redis_client
    engine.pg_engine = FakeEngine(conn)

    result = SimpleNamespace(
        timestamp="2026-09-27T00:00:00+00:00",
        request_id="r1",
        score=72,
        level=m.RiskLevel.HIGH,
        factors={"action_type": 70},
        auto_approve=False,
        requires_human_approval=True,
        context_snapshot={
            "user_role": "employee",
            "action_type": "delete:document",
            "tenant_id": "tenant-a",
        },
    )

    engine._audit(result)

    assert engine._last_hash != "genesis"
    assert conn.calls
    assert "INSERT INTO audit_logs" in conn.calls[0][0]
    assert redis_client.set_calls
    assert len(redis_client.lpush_calls) == 2
    assert redis_client.expire_calls


def test_audit_storage_failures_are_nonfatal():
    m = _module()

    redis_client = FakeRedis(
        fail_write=True
    )

    conn = FakeConn(
        fail=True,
        error_type=m.SQLAlchemyError,
    )

    engine = _bare_engine(m)
    engine.redis = redis_client
    engine.pg_engine = FakeEngine(conn)

    result = SimpleNamespace(
        timestamp="2026-09-27T00:00:00+00:00",
        request_id="r-fail",
        score=90,
        level=m.RiskLevel.CRITICAL,
        factors={},
        auto_approve=False,
        requires_human_approval=True,
        context_snapshot={
            "user_role": "admin",
            "action_type": "delete:all",
            "tenant_id": "tenant-x",
        },
    )

    # Both durable stores fail, but risk scoring/audit must not crash.
    engine._audit(result)

    assert engine._last_hash != "genesis"
