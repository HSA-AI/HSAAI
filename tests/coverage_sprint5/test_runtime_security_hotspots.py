import base64
import json
import sys
import types
from datetime import datetime, timezone
from types import SimpleNamespace

import httpx
import pytest


# ============================================================
# AGENT RUNTIME
# ============================================================

class _Response:
    def __init__(self, status_code=200, data=None, text=""):
        self.status_code = status_code
        self._data = data or {}
        self.text = text

    def json(self):
        return self._data


class _AsyncClient:
    queue = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, *args, **kwargs):
        item = self.queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    async def post(self, *args, **kwargs):
        item = self.queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.mark.asyncio
async def test_agent_orchestrator_success_and_metrics(monkeypatch):
    import backend_core.agent_runtime.service as m

    monkeypatch.setattr(m.httpx, "AsyncClient", _AsyncClient)

    monkeypatch.setattr(m.AgentOrchestrator, "_total_runs", 0)
    monkeypatch.setattr(m.AgentOrchestrator, "_successful_runs", 0)
    monkeypatch.setattr(m.AgentOrchestrator, "_total_latency_ms", 0)
    monkeypatch.setattr(m.AgentOrchestrator, "_tool_failures", 0)

    service = m.AgentOrchestrator()
    service.memory.get_context = lambda *a, **k: {
        "context_retrieved": True,
        "session_id": "session-1",
    }

    _AsyncClient.queue = [
        _Response(
            200,
            {
                "results": [
                    {"text": "Finance policy A"},
                    {"text": "Finance policy B"},
                ]
            },
        ),
        _Response(
            200,
            {"text": "Enterprise answer"},
        ),
    ]

    result = await service.run(
        "finance-agent",
        "What is the policy?",
        session_id="session-1",
        tenant_id="tenant-1",
        workspace_id="finance",
        user_id="user-1",
    )

    assert result["answer"] == "Enterprise answer"
    assert result["rag_results_count"] == 2
    assert result["llm_error"] is None
    assert result["external_ai_used"] is False
    assert result["memory"]["context_retrieved"] is True
    assert result["steps"][-1]["status"] == "completed"

    metrics = service.metrics()
    assert metrics["total_runs"] == 1
    assert metrics["successful_runs"] == 1
    assert metrics["success_rate"] == 1.0


@pytest.mark.asyncio
async def test_agent_orchestrator_no_rag_llm_error_fallback(monkeypatch):
    import backend_core.agent_runtime.service as m

    monkeypatch.setattr(m.httpx, "AsyncClient", _AsyncClient)

    service = m.AgentOrchestrator()
    service.memory.get_context = lambda *a, **k: {}

    _AsyncClient.queue = [
        RuntimeError("rag unavailable"),
        _Response(503, {}),
    ]

    result = await service.run(
        "agent",
        "hello",
        tenant_id="tenant",
        workspace_id="workspace",
    )

    assert result["rag_results_count"] == 0
    assert "LLM gateway returned 503" in result["llm_error"]
    assert "لم أتمكن" in result["answer"]
    assert result["steps"][-1]["status"] == "error"


@pytest.mark.asyncio
async def test_agent_orchestrator_rag_fallback_when_llm_raises(monkeypatch):
    import backend_core.agent_runtime.service as m

    monkeypatch.setattr(m.httpx, "AsyncClient", _AsyncClient)

    service = m.AgentOrchestrator()
    service.memory.get_context = lambda *a, **k: {}

    _AsyncClient.queue = [
        _Response(
            200,
            {"results": [{"text": "Internal knowledge"}]},
        ),
        RuntimeError("llm offline"),
    ]

    result = await service.run(
        "agent",
        "question",
        tenant_id="tenant",
        workspace_id="workspace",
    )

    assert result["rag_results_count"] == 1
    assert result["llm_error"] == "llm offline"
    assert "بناءً على المصادر الداخلية" in result["answer"]
    assert "Internal knowledge" in result["answer"]


@pytest.mark.asyncio
async def test_agent_tool_executor_paths(monkeypatch):
    import backend_core.agent_runtime.service as m

    monkeypatch.setattr(m.httpx, "AsyncClient", _AsyncClient)

    tool = m.ToolExecutor()

    assert tool.execute("missing", {})["status"] == "error"

    no_query = await tool._execute_rag({})
    assert no_query["status"] == "error"

    _AsyncClient.queue = [
        _Response(
            200,
            {"results": [{"text": "a"}, {"text": "b"}]},
        )
    ]
    result = await tool._execute_rag(
        {
            "query": "finance",
            "tenant_id": "t",
            "workspace_id": "w",
        }
    )
    assert result["status"] == "completed"
    assert result["result"]["hits"] == 2

    _AsyncClient.queue = [_Response(500)]
    assert (await tool._execute_rag({"query": "x"}))["status"] == "error"

    _AsyncClient.queue = [RuntimeError("rag down")]
    assert (await tool._execute_rag({"query": "x"}))["status"] == "error"

    _AsyncClient.queue = [_Response(200, {"ok": True})]
    result = await tool._execute_integration(
        "sap",
        "/sap",
        {"x": 1},
    )
    assert result["status"] == "completed"

    _AsyncClient.queue = [_Response(403)]
    result = await tool._execute_integration(
        "sap",
        "/sap",
        {},
    )
    assert result["status"] == "error"

    _AsyncClient.queue = [httpx.ConnectError("offline")]
    result = await tool._execute_integration(
        "sap",
        "/sap",
        {},
    )
    assert result["status"] == "unavailable"

    _AsyncClient.queue = [RuntimeError("other")]
    result = await tool._execute_integration(
        "sap",
        "/sap",
        {},
    )
    assert result["status"] == "error"


# ============================================================
# DATABASE MIGRATIONS
# ============================================================

def _install_fake_alembic(monkeypatch, expected="head123"):
    alembic_pkg = types.ModuleType("alembic")
    alembic_pkg.__path__ = []

    config_mod = types.ModuleType("alembic.config")
    script_mod = types.ModuleType("alembic.script")

    class Config:
        def __init__(self, path):
            self.path = path
            self.options = {}

        def set_main_option(self, name, value):
            self.options[name] = value

    class ScriptDirectory:
        @classmethod
        def from_config(cls, cfg):
            return cls()

        def get_current_head(self):
            return expected

    config_mod.Config = Config
    script_mod.ScriptDirectory = ScriptDirectory

    monkeypatch.setitem(sys.modules, "alembic", alembic_pkg)
    monkeypatch.setitem(sys.modules, "alembic.config", config_mod)
    monkeypatch.setitem(sys.modules, "alembic.script", script_mod)


class _ScalarResult:
    def __init__(self, values=None, scalar_value=None):
        self.values = values or []
        self.scalar_value = scalar_value

    def scalars(self):
        return iter(self.values)

    def scalar(self):
        return self.scalar_value


class _Connection:
    def __init__(self, revisions=None, unsafe=False, dialect="postgresql"):
        self.revisions = revisions or []
        self.unsafe = unsafe
        self.dialect = SimpleNamespace(name=dialect)

    def execute(self, statement, *args, **kwargs):
        sql = str(statement)
        if "alembic_version" in sql:
            return _ScalarResult(values=self.revisions)
        if "rolsuper" in sql:
            return _ScalarResult(scalar_value=self.unsafe)
        return _ScalarResult()


class _ConnectContext:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self.connection

    def __exit__(self, *args):
        return False


class _Engine:
    def __init__(self, connection):
        self.connection = connection

    def connect(self):
        return _ConnectContext(self.connection)


def test_run_migrations_fail_closed_production(monkeypatch):
    import backend_core.db.database as m

    monkeypatch.setenv("USE_ALEMBIC", "false")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("RUN_MIGRATIONS_ON_STARTUP", "true")

    with pytest.raises(RuntimeError, match="forbidden"):
        m.run_migrations()


def test_run_migrations_verification_requires_alembic(monkeypatch):
    import backend_core.db.database as m

    monkeypatch.setenv("USE_ALEMBIC", "false")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("RUN_MIGRATIONS_ON_STARTUP", "false")

    with pytest.raises(RuntimeError, match="Schema verification"):
        m.run_migrations()


def test_run_migrations_schema_verification_paths(monkeypatch):
    import backend_core.db.database as m

    _install_fake_alembic(monkeypatch, expected="head123")

    monkeypatch.setenv("USE_ALEMBIC", "true")
    monkeypatch.setenv("RUN_MIGRATIONS_ON_STARTUP", "false")
    monkeypatch.setenv("APP_ENV", "production")

    monkeypatch.setattr(
        m,
        "engine",
        _Engine(_Connection(["old-head"], False)),
    )

    with pytest.raises(RuntimeError, match="schema is not current"):
        m.run_migrations()

    monkeypatch.setattr(
        m,
        "engine",
        _Engine(_Connection(["head123"], True)),
    )

    with pytest.raises(RuntimeError, match="must not bypass RLS"):
        m.run_migrations()

    monkeypatch.setattr(
        m,
        "engine",
        _Engine(_Connection(["head123"], False)),
    )

    assert m.run_migrations() is None


def test_run_migrations_alembic_success_and_failures(monkeypatch, tmp_path):
    import backend_core.db.database as m

    monkeypatch.chdir(tmp_path)
    (tmp_path / "alembic.ini").write_text(
        "[alembic]\nscript_location = alembic\n"
    )

    monkeypatch.setenv("USE_ALEMBIC", "true")
    monkeypatch.setenv("RUN_MIGRATIONS_ON_STARTUP", "true")
    monkeypatch.setenv("APP_ENV", "development")

    calls = []

    def success(*args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(
            stdout="migration success",
            stderr="migration warning",
        )

    monkeypatch.setattr(m.subprocess, "run", success)
    assert m.run_migrations() is None
    assert calls

    def failed(*args, **kwargs):
        raise m.subprocess.CalledProcessError(
            2,
            ["alembic"],
            output="stdout-error",
            stderr="stderr-error",
        )

    monkeypatch.setattr(m.subprocess, "run", failed)

    with pytest.raises(m.subprocess.CalledProcessError):
        m.run_migrations()

    def missing(*args, **kwargs):
        raise FileNotFoundError("missing")

    monkeypatch.setattr(m.subprocess, "run", missing)

    with pytest.raises(FileNotFoundError):
        m.run_migrations()


def test_run_migrations_development_fallback(monkeypatch):
    import backend_core.db.database as m

    monkeypatch.setenv("USE_ALEMBIC", "false")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("RUN_MIGRATIONS_ON_STARTUP", "true")

    called = []
    monkeypatch.setattr(
        m,
        "init_db",
        lambda: called.append(True),
    )

    assert m.run_migrations() is None
    assert called == [True]


# ============================================================
# JWT VALIDATOR
# ============================================================

def _b64json(data):
    raw = json.dumps(data).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _token(header, payload):
    return f"{_b64json(header)}.{_b64json(payload)}.signature"


def _jwt_validator():
    from common.security.jwt_validator import JWTValidator

    return JWTValidator(
        jwks_url="https://jwks.example/certs",
        issuer="issuer-1",
        audience="api-1",
        clock_skew_seconds=30,
    )


@pytest.mark.asyncio
async def test_jwt_rejects_bad_format_algorithm_kid_and_unknown_key(monkeypatch):
    import common.security.jwt_validator as m

    validator = _jwt_validator()

    with pytest.raises(m.JWTValidationError, match="3 parts"):
        await validator.verify("invalid")

    forbidden = _token(
        {"alg": "HS256", "kid": "k1"},
        {},
    )
    with pytest.raises(m.JWTValidationError, match="Forbidden algorithm"):
        await validator.verify(forbidden)

    async def jwks():
        return {"keys": [{"kid": "k1"}]}

    monkeypatch.setattr(validator, "_fetch_jwks", jwks)

    missing_kid = _token(
        {"alg": "RS256"},
        {},
    )
    with pytest.raises(m.JWTValidationError, match="Missing 'kid'"):
        await validator.verify(missing_kid)

    unknown = _token(
        {"alg": "RS256", "kid": "missing"},
        {},
    )
    with pytest.raises(m.JWTValidationError, match="No JWKS key matches"):
        await validator.verify(unknown)


@pytest.mark.asyncio
async def test_jwt_success_roles_tenant_and_audience_list(monkeypatch):
    import jwt
    import common.security.jwt_validator as m

    validator = _jwt_validator()

    async def jwks():
        return {"keys": [{"kid": "k1", "kty": "RSA"}]}

    monkeypatch.setattr(validator, "_fetch_jwks", jwks)

    monkeypatch.setattr(
        jwt,
        "PyJWK",
        SimpleNamespace(
            from_dict=lambda _: SimpleNamespace(key="public-key")
        ),
    )

    now = int(m.time.time())

    verified = {
        "sub": "user-1",
        "iss": "issuer-1",
        "aud": ["api-1", "other"],
        "exp": now + 3600,
        "iat": now,
        "nbf": now - 1,
        "tenant": "tenant-1",
        "roles": "admin",
        "email": "user@example.com",
        "name": "User",
    }

    monkeypatch.setattr(
        jwt,
        "decode",
        lambda *a, **k: verified,
    )

    token = _token(
        {"alg": "RS256", "kid": "k1"},
        verified,
    )

    claims = await validator.verify(token)

    assert claims.sub == "user-1"
    assert claims.tenant_id == "tenant-1"
    assert claims.roles == ["admin"]
    assert claims.aud == "api-1"
    assert claims.email == "user@example.com"


@pytest.mark.asyncio
async def test_jwt_manual_claim_validation_paths(monkeypatch):
    import jwt
    import common.security.jwt_validator as m

    validator = _jwt_validator()

    async def jwks():
        return {"keys": [{"kid": "k1"}]}

    monkeypatch.setattr(validator, "_fetch_jwks", jwks)
    monkeypatch.setattr(
        jwt,
        "PyJWK",
        SimpleNamespace(
            from_dict=lambda _: SimpleNamespace(key="key")
        ),
    )

    now = int(m.time.time())

    base = {
        "sub": "u",
        "iss": "issuer-1",
        "aud": "api-1",
        "exp": now + 500,
        "iat": now,
    }

    token = _token(
        {"alg": "RS256", "kid": "k1"},
        base,
    )

    async def check(payload, text):
        monkeypatch.setattr(
            jwt,
            "decode",
            lambda *a, **k: payload,
        )
        with pytest.raises(m.JWTValidationError, match=text):
            await validator.verify(token)

    missing = dict(base)
    del missing["sub"]
    await check(missing, "Missing required claim")

    bad_issuer = dict(base, iss="wrong")
    await check(bad_issuer, "Invalid issuer")

    bad_aud = dict(base, aud="wrong")
    await check(bad_aud, "Invalid audience")

    bad_list = dict(base, aud=["other"])
    await check(bad_list, "not in")

    expired = dict(base, exp=now - 1000)
    await check(expired, "Token expired")

    future_iat = dict(base, iat=now + 1000)
    await check(future_iat, "issued in future")

    future_nbf = dict(base, nbf=now + 1000)
    await check(future_nbf, "not yet valid")


@pytest.mark.asyncio
async def test_jwt_jwks_http_error_and_decode_error(monkeypatch):
    import common.security.jwt_validator as m

    validator = _jwt_validator()

    async def bad_jwks():
        raise httpx.ConnectError("jwks down")

    monkeypatch.setattr(validator, "_fetch_jwks", bad_jwks)

    token = _token(
        {"alg": "RS256", "kid": "k1"},
        {},
    )

    with pytest.raises(m.JWTValidationError, match="JWKS fetch failed"):
        await validator.verify(token)

    with pytest.raises(m.JWTValidationError, match="Failed to decode"):
        validator._decode_base64json("***not-base64***")


# ============================================================
# GOVERNANCE AUDIT ARCHIVE
# ============================================================

class _FetchResult:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows


class _GovConnection:
    def __init__(self, rows=None, fail=False):
        self.rows = rows or []
        self.fail = fail
        self.calls = []

    def execute(self, statement, params=None):
        self.calls.append((str(statement), params))

        if self.fail:
            import services.governance.main as m
            raise m.SQLAlchemyError("database failure")

        if str(statement).lstrip().upper().startswith("SELECT"):
            return _FetchResult(self.rows)

        return _FetchResult([])


class _Begin:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self.conn

    def __exit__(self, *args):
        return False


class _GovEngine:
    def __init__(self, conns):
        self.conns = list(conns)

    def begin(self):
        return _Begin(self.conns.pop(0))


class _S3:
    def __init__(self, fail=False):
        self.fail = fail
        self.calls = []

    def put_object(self, **kwargs):
        if self.fail:
            raise RuntimeError("s3 down")
        self.calls.append(kwargs)


def _audit_logger():
    import services.governance.main as m

    obj = object.__new__(m.AuditLogger)
    obj.pg_engine = None
    obj.s3 = None
    obj.s3_bucket = "audit-test"
    return obj


def test_archive_old_logs_missing_services_and_empty():
    logger = _audit_logger()

    result = logger.archive_old_logs()
    assert result["archived"] == 0
    assert "PostgreSQL unavailable" in result["error"]

    logger.pg_engine = _GovEngine([])
    result = logger.archive_old_logs()
    assert "S3/MinIO client unavailable" in result["error"]

    logger.s3 = _S3()
    logger.pg_engine = _GovEngine([
        _GovConnection(rows=[]),
    ])

    result = logger.archive_old_logs(age_days=30)
    assert result["archived"] == 0
    assert result["deleted"] == 0
    assert result["error"] is None


def test_archive_old_logs_success():
    now = datetime.now(timezone.utc)

    rows = [
        (
            1,
            "user-1",
            "read",
            "document",
            "workspace-1",
            "tenant-1",
            True,
            '{"ok":true}',
            now,
        ),
        (
            2,
            "user-2",
            "write",
            "record",
            "workspace-1",
            "tenant-1",
            False,
            '{"ok":false}',
            now,
        ),
    ]

    select_conn = _GovConnection(rows=rows)
    delete_conn = _GovConnection()

    logger = _audit_logger()
    logger.pg_engine = _GovEngine([
        select_conn,
        delete_conn,
    ])
    logger.s3 = _S3()

    result = logger.archive_old_logs(age_days=90)

    assert result["archived"] == 2
    assert result["deleted"] == 2
    assert result["error"] is None
    assert result["s3_key"].startswith("s3://audit-test/audit/")
    assert len(logger.s3.calls) == 1

    call = logger.s3.calls[0]
    assert call["Bucket"] == "audit-test"
    assert call["ContentType"] == "application/x-ndjson"
    assert call["Metadata"]["row-count"] == "2"

    body = call["Body"].decode()
    assert '"id": 1' in body
    assert '"id": 2' in body

    assert delete_conn.calls
    assert delete_conn.calls[0][1] == {"ids": [1, 2]}


def test_archive_old_logs_read_s3_and_delete_failures():
    import services.governance.main as m

    logger = _audit_logger()
    logger.s3 = _S3()

    logger.pg_engine = _GovEngine([
        _GovConnection(fail=True),
    ])

    result = logger.archive_old_logs()
    assert "Postgres read failed" in result["error"]

    row = (
        5,
        "u",
        "a",
        "r",
        "w",
        "t",
        True,
        "{}",
        datetime.now(timezone.utc),
    )

    logger.pg_engine = _GovEngine([
        _GovConnection(rows=[row]),
    ])
    logger.s3 = _S3(fail=True)

    result = logger.archive_old_logs()
    assert result["archived"] == 0
    assert "S3 write failed" in result["error"]

    logger.pg_engine = _GovEngine([
        _GovConnection(rows=[row]),
        _GovConnection(fail=True),
    ])
    logger.s3 = _S3()

    result = logger.archive_old_logs()
    assert result["archived"] == 1
    assert result["deleted"] == 0
    assert "Postgres delete failed" in result["error"]


# ============================================================
# APPROVAL NOTIFICATIONS
# ============================================================

def _approval_row():
    return SimpleNamespace(
        action_type="deploy",
        resource_type="model",
        resource_id="model-1",
        request_id="approval-1",
        risk_level="high",
    )


@pytest.mark.asyncio
async def test_notify_approval_no_channels(monkeypatch):
    import backend_core.approvals.service as m

    monkeypatch.setattr(m.settings, "smtp_host", "", raising=False)
    monkeypatch.setattr(
        m.settings,
        "approval_email_from",
        "",
        raising=False,
    )
    monkeypatch.setattr(
        m.settings,
        "teams_webhook_url",
        "",
        raising=False,
    )
    monkeypatch.setattr(
        m.settings,
        "slack_webhook_url",
        "",
        raising=False,
    )
    monkeypatch.setattr(
        m.settings,
        "approval_webhook_url",
        "",
        raising=False,
    )

    assert await m.notify_approval(
        _approval_row(),
        stage="first",
    ) is None


@pytest.mark.asyncio
async def test_notify_approval_webhooks(monkeypatch):
    import backend_core.approvals.service as m

    monkeypatch.setattr(m.settings, "smtp_host", "", raising=False)
    monkeypatch.setattr(
        m.settings,
        "approval_email_from",
        "",
        raising=False,
    )
    monkeypatch.setattr(
        m.settings,
        "teams_webhook_url",
        "https://teams.example/hook",
        raising=False,
    )
    monkeypatch.setattr(
        m.settings,
        "slack_webhook_url",
        "https://slack.example/hook",
        raising=False,
    )
    monkeypatch.setattr(
        m.settings,
        "approval_webhook_url",
        "",
        raising=False,
    )

    posts = []

    class Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json):
            posts.append((url, json))
            return _Response(200)

    monkeypatch.setattr(m.httpx, "AsyncClient", Client)

    await m.notify_approval(
        _approval_row(),
        stage="second",
    )

    assert len(posts) == 2
    assert all(
        payload["stage"] == "second"
        for _, payload in posts
    )
    assert all(
        payload["request_id"] == "approval-1"
        for _, payload in posts
    )


@pytest.mark.asyncio
async def test_notify_approval_async_email(monkeypatch):
    import backend_core.approvals.service as m

    monkeypatch.setattr(
        m.settings,
        "smtp_host",
        "smtp.example",
        raising=False,
    )
    monkeypatch.setattr(
        m.settings,
        "smtp_port",
        587,
        raising=False,
    )
    monkeypatch.setattr(
        m.settings,
        "smtp_user",
        "user",
        raising=False,
    )
    monkeypatch.setattr(
        m.settings,
        "smtp_password",
        "password",
        raising=False,
    )
    monkeypatch.setattr(
        m.settings,
        "approval_email_from",
        "ai@example.com",
        raising=False,
    )

    for attr in (
        "teams_webhook_url",
        "slack_webhook_url",
        "approval_webhook_url",
    ):
        monkeypatch.setattr(
            m.settings,
            attr,
            "",
            raising=False,
        )

    sent = []

    fake = types.ModuleType("aiosmtplib")

    async def send(message, **kwargs):
        sent.append((message, kwargs))

    fake.send = send
    monkeypatch.setitem(sys.modules, "aiosmtplib", fake)

    await m.notify_approval(
        _approval_row(),
        stage="escalation",
    )

    assert len(sent) == 1
    message, kwargs = sent[0]
    assert message["From"] == "ai@example.com"
    assert "SLA BREACHED" in message["Subject"]
    assert kwargs["hostname"] == "smtp.example"
    assert kwargs["start_tls"] is True
