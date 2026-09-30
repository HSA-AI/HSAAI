import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

import services.governance.main as g


class FakeRedis:
    def __init__(self, events=None, members=None):
        self.events = events or []
        self.members = members or set()
        self.set_calls = []
        self.sadd_calls = []

    def lrange(self, key, start, end):
        return list(self.events)

    def set(self, *args):
        self.set_calls.append(args)

    def sadd(self, *args):
        self.sadd_calls.append(args)

    def smembers(self, key):
        return set(self.members)


def test_data_governance_classification_paths():
    engine = g.DataGovernanceEngine.__new__(g.DataGovernanceEngine)
    engine.redis = None

    assert engine.classify("test@example.com") == g.DataClassification.PII
    assert engine.classify("invoice revenue report") == g.DataClassification.FINANCIAL
    assert engine.classify("confidential document") == g.DataClassification.RESTRICTED
    assert engine.classify("ordinary internal note") == g.DataClassification.INTERNAL


def test_register_asset_without_and_with_redis():
    engine = g.DataGovernanceEngine.__new__(g.DataGovernanceEngine)
    engine.redis = None

    asset = g.DataAsset(
        asset_id="asset-1",
        tenant_id="tenant-1",
        name="Test",
        classification=g.DataClassification.INTERNAL,
        owner_id="user-1",
        source="unit-test",
    )

    assert engine.register_asset(asset) is False

    redis = FakeRedis()
    engine.redis = redis

    assert engine.register_asset(asset) is True
    assert redis.set_calls
    assert redis.sadd_calls


def test_lineage_paths():
    engine = g.DataGovernanceEngine.__new__(g.DataGovernanceEngine)

    engine.redis = None
    assert engine.get_lineage("a") == []

    redis = FakeRedis(members={"up-1", "up-2"})
    engine.redis = redis

    engine.add_lineage("a", "up-1")
    assert len(redis.sadd_calls) == 2
    assert sorted(engine.get_lineage("a")) == ["up-1", "up-2"]


def test_compliance_report_has_frameworks():
    engine = g.ComplianceEngine()
    report = engine.assess_compliance()

    assert "generated_at" in report
    assert "frameworks" in report
    assert g.ComplianceFramework.NIST_AI_RMF.value in report["frameworks"]


def make_audit_logger(redis=None):
    obj = g.AuditLogger.__new__(g.AuditLogger)
    obj.redis = redis
    obj.pg_engine = None
    obj.s3 = None
    obj.s3_bucket = "test-bucket"
    return obj


def test_audit_query_filters_and_invalid_json():
    events = [
        json.dumps({
            "action": "read",
            "timestamp": "2026-09-25T10:00:00",
        }),
        json.dumps({
            "action": "write",
            "timestamp": "2026-09-25T11:00:00",
        }),
        "{invalid-json",
    ]

    logger = make_audit_logger(FakeRedis(events))

    results = logger.query(
        action="write",
        start_time="2026-09-25T10:30:00",
        end_time="2026-09-25T12:00:00",
    )

    assert len(results) == 1
    assert results[0]["action"] == "write"


def test_audit_query_without_redis():
    logger = make_audit_logger(None)
    assert logger.query() == []


def test_audit_integrity_success():
    oldest = {
        "previous_hash": "genesis",
        "entry_hash": "h1",
    }
    newest = {
        "previous_hash": "h1",
        "entry_hash": "h2",
    }

    redis = FakeRedis([
        json.dumps(newest),
        json.dumps(oldest),
    ])

    logger = make_audit_logger(redis)
    assert logger.verify_integrity() is True


def test_audit_integrity_broken_chain():
    redis = FakeRedis([
        json.dumps({
            "previous_hash": "wrong",
            "entry_hash": "h1",
        })
    ])

    logger = make_audit_logger(redis)
    assert logger.verify_integrity() is False


def test_audit_integrity_invalid_json():
    logger = make_audit_logger(FakeRedis(["not-json"]))
    assert logger.verify_integrity() is False


def test_archive_without_postgres():
    logger = make_audit_logger()
    result = logger.archive_old_logs()

    assert result["archived"] == 0
    assert "PostgreSQL unavailable" in result["error"]


def test_archive_without_s3():
    logger = make_audit_logger()
    logger.pg_engine = object()

    result = logger.archive_old_logs()

    assert result["archived"] == 0
    assert "S3/MinIO client unavailable" in result["error"]


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows


class FakeConn:
    def __init__(self, rows):
        self.rows = rows
        self.executions = []

    def execute(self, *args):
        self.executions.append(args)
        if len(self.executions) == 1:
            return FakeResult(self.rows)
        return FakeResult([])


class FakeBegin:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self.conn

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeEngine:
    def __init__(self, rows):
        self.conn = FakeConn(rows)

    def begin(self):
        return FakeBegin(self.conn)


class FakeS3:
    def __init__(self, fail=False):
        self.fail = fail
        self.calls = []

    def put_object(self, **kwargs):
        if self.fail:
            raise RuntimeError("s3 down")
        self.calls.append(kwargs)


def test_archive_no_rows():
    logger = make_audit_logger()
    logger.pg_engine = FakeEngine([])
    logger.s3 = FakeS3()

    result = logger.archive_old_logs(age_days=30)

    assert result["archived"] == 0
    assert result["deleted"] == 0
    assert result["error"] is None


def test_archive_success():
    row = (
        1,
        "actor",
        "read",
        "resource",
        "workspace",
        "tenant",
        True,
        '{"x":1}',
        datetime.now(timezone.utc),
    )

    logger = make_audit_logger()
    logger.pg_engine = FakeEngine([row])
    logger.s3 = FakeS3()

    result = logger.archive_old_logs(age_days=30)

    assert result["archived"] == 1
    assert result["deleted"] == 1
    assert result["error"] is None
    assert result["s3_key"].startswith("s3://test-bucket/")
    assert logger.s3.calls


def test_archive_s3_failure():
    row = (
        1,
        "actor",
        "read",
        "resource",
        "workspace",
        "tenant",
        True,
        "{}",
        datetime.now(timezone.utc),
    )

    logger = make_audit_logger()
    logger.pg_engine = FakeEngine([row])
    logger.s3 = FakeS3(fail=True)

    result = logger.archive_old_logs()

    assert result["archived"] == 0
    assert "S3 write failed" in result["error"]
