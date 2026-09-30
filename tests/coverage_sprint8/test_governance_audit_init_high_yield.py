import importlib
from types import SimpleNamespace


def _module():
    return importlib.import_module(
        "services.governance.main"
    )


class RedisClient:
    def __init__(self, last_hash=None):
        self.last_hash = last_hash

    def ping(self):
        return True

    def get(self, key):
        if key == "audit:last_hash":
            return self.last_hash
        return None


class Conn:
    def __init__(self, *, missing_table=False):
        self.missing_table = missing_table
        self.calls = []
        self.commits = 0
        self._first_select = True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, statement, params=None):
        sql = str(statement)
        self.calls.append((sql, params))

        if (
            self.missing_table
            and self._first_select
            and "SELECT 1 FROM audit_logs" in sql
        ):
            self._first_select = False
            raise RuntimeError("table missing")

        return SimpleNamespace()

    def commit(self):
        self.commits += 1


class Engine:
    def __init__(self, conn):
        self.conn = conn

    def connect(self):
        return self.conn


class S3Client:
    def __init__(
        self,
        *,
        head_fail=False,
        create_fail=False,
    ):
        self.head_fail = head_fail
        self.create_fail = create_fail
        self.created = []

    def head_bucket(self, **kwargs):
        if self.head_fail:
            raise RuntimeError("bucket absent")

    def create_bucket(self, **kwargs):
        if self.create_fail:
            raise RuntimeError("cannot create bucket")
        self.created.append(kwargs)


def test_audit_init_existing_table_existing_bucket(monkeypatch):
    m = _module()

    redis_client = RedisClient(
        last_hash="persisted-audit-hash"
    )

    monkeypatch.setattr(
        m.redis,
        "from_url",
        lambda *a, **k: redis_client,
    )

    conn = Conn()
    engine = Engine(conn)

    monkeypatch.setattr(
        m,
        "_SQLALCHEMY_AVAILABLE",
        True,
    )
    monkeypatch.setattr(
        m,
        "create_engine",
        lambda *a, **k: engine,
    )

    s3 = S3Client()

    monkeypatch.setattr(
        m,
        "_BOTO3_AVAILABLE",
        True,
    )
    monkeypatch.setattr(
        m,
        "boto3",
        SimpleNamespace(
            client=lambda *a, **k: s3
        ),
        raising=False,
    )

    audit = m.AuditLogger(
        redis_url="redis://unit",
        postgres_url="postgresql://unit",
    )

    assert audit.redis is redis_client
    assert audit._last_hash == "persisted-audit-hash"
    assert audit.pg_engine is engine
    assert audit.s3 is s3
    assert any(
        "SELECT 1 FROM audit_logs" in sql
        for sql, _ in conn.calls
    )


def test_audit_init_creates_missing_sqlite_table_and_bucket(monkeypatch):
    m = _module()

    monkeypatch.setattr(
        m.redis,
        "from_url",
        lambda *a, **k: RedisClient(),
    )

    conn = Conn(
        missing_table=True
    )
    engine = Engine(conn)

    monkeypatch.setattr(
        m,
        "_SQLALCHEMY_AVAILABLE",
        True,
    )
    monkeypatch.setattr(
        m,
        "create_engine",
        lambda *a, **k: engine,
    )

    s3 = S3Client(
        head_fail=True
    )

    monkeypatch.setattr(
        m,
        "_BOTO3_AVAILABLE",
        True,
    )
    monkeypatch.setattr(
        m,
        "boto3",
        SimpleNamespace(
            client=lambda *a, **k: s3
        ),
        raising=False,
    )

    audit = m.AuditLogger(
        postgres_url="sqlite:///audit-test.db",
    )

    sql = "\n".join(
        statement
        for statement, _ in conn.calls
    )

    assert "CREATE TABLE IF NOT EXISTS audit_logs" in sql
    assert "AUTOINCREMENT" in sql
    assert conn.commits >= 1
    assert s3.created
    assert audit.s3 is s3


def test_audit_init_storage_failures_degrade_safely(monkeypatch):
    m = _module()

    monkeypatch.setattr(
        m.redis,
        "from_url",
        lambda *a, **k: (_ for _ in ()).throw(
            RuntimeError("redis down")
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
            RuntimeError("postgres down")
        ),
    )

    s3 = S3Client(
        head_fail=True,
        create_fail=True,
    )

    monkeypatch.setattr(
        m,
        "_BOTO3_AVAILABLE",
        True,
    )
    monkeypatch.setattr(
        m,
        "boto3",
        SimpleNamespace(
            client=lambda *a, **k: s3
        ),
        raising=False,
    )

    audit = m.AuditLogger(
        postgres_url="postgresql://broken",
    )

    assert audit.redis is None
    assert audit._last_hash == "genesis"
    assert audit.pg_engine is None
    assert audit.s3 is None
