from types import SimpleNamespace

import pytest


def _module():
    import services.governance.main as m
    return m


class FakeAudit:
    def __init__(self):
        self.entries = []

    def log(self, entry):
        self.entries.append(entry)


class FakeRequest:
    def __init__(self, state, authorization="Bearer test-token"):
        self.app = SimpleNamespace(state=state)
        self.headers = {"Authorization": authorization}


class FakeRiskResult:
    def __init__(
        self,
        *,
        score=20,
        level=None,
        requires_human_approval=False,
        requires_two_person_rule=False,
    ):
        self.score = score
        self.level = level
        self.requires_human_approval = requires_human_approval
        self.requires_two_person_rule = requires_two_person_rule

    def to_dict(self):
        return {
            "score": self.score,
            "level": self.level.value,
            "requires_human_approval": self.requires_human_approval,
            "requires_two_person_rule": self.requires_two_person_rule,
        }


class FakePolicyDecision:
    def __init__(
        self,
        allowed=True,
        reason="allowed",
        denied_by=None,
        allowed_by=None,
    ):
        self.allowed = allowed
        self.reason = reason
        self.denied_by = denied_by
        self.allowed_by = allowed_by


def _install_types(monkeypatch, m):
    high = SimpleNamespace(value="high")
    critical = SimpleNamespace(value="critical")
    low = SimpleNamespace(value="low")

    monkeypatch.setattr(
        m,
        "RiskLevel",
        SimpleNamespace(
            HIGH=high,
            CRITICAL=critical,
            LOW=low,
        ),
    )

    class RiskContext:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    class PolicyRequest:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    monkeypatch.setattr(m, "RiskContext", RiskContext)
    monkeypatch.setattr(m, "PolicyRequest", PolicyRequest)

    return high, critical, low


@pytest.mark.asyncio
async def test_governance_evaluate_requires_risk_engine(monkeypatch):
    m = _module()
    _install_types(monkeypatch, m)

    state = SimpleNamespace(
        risk_engine=None,
        policy_engine=None,
        audit=FakeAudit(),
    )

    request = FakeRequest(state)

    with pytest.raises(m.HTTPException) as exc:
        await m.governance_evaluate(
            {"action_type": "read"},
            request,
            {"sub": "user-a"},
        )

    assert exc.value.status_code == 503
    assert "Risk engine not initialised" in str(exc.value.detail)


@pytest.mark.asyncio
async def test_governance_evaluate_allow_without_policy(monkeypatch):
    m = _module()
    _, _, low = _install_types(monkeypatch, m)

    risk_result = FakeRiskResult(
        score=15,
        level=low,
        requires_human_approval=False,
    )

    risk_engine = SimpleNamespace(
        score=lambda ctx: risk_result
    )

    audit = FakeAudit()

    state = SimpleNamespace(
        risk_engine=risk_engine,
        policy_engine=None,
        audit=audit,
    )

    request = FakeRequest(state)

    payload = {
        "action_type": "read_document",
        "data_sensitivity": "internal",
        "resource": {
            "type": "document",
            "id": "doc-1",
        },
        "request_id": "req-1",
    }

    claims = {
        "sub": "user-a",
        "roles": ["employee"],
        "tenant_id": "tenant-a",
        "mfa_verified": True,
    }

    result = await m.governance_evaluate(
        payload,
        request,
        claims,
    )

    assert result["decision"] == "ALLOW"
    assert result["policy"] is None
    assert result["approval_request_id"] is None
    assert result["risk"]["score"] == 15

    assert len(audit.entries) == 1
    assert audit.entries[0]["tenant_id"] == "tenant-a"
    assert audit.entries[0]["user_id"] == "user-a"
    assert audit.entries[0]["decision"] == "ALLOW"
    assert audit.entries[0]["request_id"] == "req-1"


@pytest.mark.asyncio
async def test_governance_evaluate_policy_deny_wins(monkeypatch):
    m = _module()
    _, critical, _ = _install_types(monkeypatch, m)

    risk_result = FakeRiskResult(
        score=95,
        level=critical,
        requires_human_approval=True,
        requires_two_person_rule=True,
    )

    risk_engine = SimpleNamespace(
        score=lambda ctx: risk_result
    )

    policy_decision = FakePolicyDecision(
        allowed=False,
        reason="restricted action",
        denied_by="policy-1",
    )

    policy_engine = SimpleNamespace(
        evaluate=lambda req: policy_decision
    )

    audit = FakeAudit()

    request = FakeRequest(
        SimpleNamespace(
            risk_engine=risk_engine,
            policy_engine=policy_engine,
            audit=audit,
        )
    )

    result = await m.governance_evaluate(
        {
            "action_type": "delete_record",
            "tenant_id": "tenant-a",
            "resource": {
                "type": "record",
                "id": "record-1",
            },
        },
        request,
        {
            "sub": "admin-a",
            "roles": ["admin"],
            "tenant_id": "tenant-a",
        },
    )

    assert result["decision"] == "DENY"
    assert result["approval_request_id"] is None
    assert result["policy"]["allowed"] is False
    assert result["policy"]["denied_by"] == "policy-1"
    assert audit.entries[-1]["decision"] == "DENY"


@pytest.mark.asyncio
async def test_governance_evaluate_escalates_and_creates_approval(monkeypatch):
    m = _module()
    high, _, _ = _install_types(monkeypatch, m)

    risk_result = FakeRiskResult(
        score=80,
        level=high,
        requires_human_approval=True,
        requires_two_person_rule=True,
    )

    risk_engine = SimpleNamespace(
        score=lambda ctx: risk_result
    )

    policy_decision = FakePolicyDecision(
        allowed=True,
        reason="policy allows with governance approval",
        allowed_by="policy-allow-1",
    )

    policy_engine = SimpleNamespace(
        evaluate=lambda req: policy_decision
    )

    audit = FakeAudit()

    captured = {}

    class Response:
        status_code = 201

        def json(self):
            return {"request_id": "approval-123"}

    class Client:
        def __init__(self, *args, **kwargs):
            captured["client_kwargs"] = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, **kwargs):
            captured["url"] = url
            captured["post"] = kwargs
            return Response()

    monkeypatch.setattr(
        m.httpx,
        "AsyncClient",
        Client,
    )

    request = FakeRequest(
        SimpleNamespace(
            risk_engine=risk_engine,
            policy_engine=policy_engine,
            audit=audit,
        ),
        authorization="Bearer approval-token",
    )

    result = await m.governance_evaluate(
        {
            "action_type": "export_sensitive_data",
            "tenant_id": "tenant-a",
            "resource": {
                "type": "dataset",
                "id": "dataset-7",
            },
            "approval_payload": {
                "reason": "business need",
            },
        },
        request,
        {
            "sub": "user-a",
            "roles": ["analyst"],
            "tenant_id": "tenant-a",
        },
    )

    assert result["decision"] == "ESCALATE"
    assert result["approval_request_id"] == "approval-123"
    assert result["policy"]["allowed"] is True

    assert captured["url"].endswith("/v1/approvals")
    assert (
        captured["post"]["headers"]["Authorization"]
        == "Bearer approval-token"
    )

    approval_json = captured["post"]["json"]

    assert approval_json["risk_level"] == "high"
    assert approval_json["requires_two_person"] is True
    assert approval_json["sla_hours"] == 24
    assert approval_json["resource_id"] == "dataset-7"

    assert audit.entries[-1]["decision"] == "ESCALATE"


@pytest.mark.asyncio
async def test_governance_evaluate_escalate_survives_approval_failure(
    monkeypatch,
):
    m = _module()
    _, critical, _ = _install_types(monkeypatch, m)

    risk_result = FakeRiskResult(
        score=99,
        level=critical,
        requires_human_approval=True,
        requires_two_person_rule=True,
    )

    state = SimpleNamespace(
        risk_engine=SimpleNamespace(
            score=lambda ctx: risk_result
        ),
        policy_engine=None,
        audit=FakeAudit(),
    )

    class BrokenClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            raise RuntimeError("backend unavailable")

    monkeypatch.setattr(
        m.httpx,
        "AsyncClient",
        BrokenClient,
    )

    result = await m.governance_evaluate(
        {
            "action_type": "critical_change",
            "resource": {
                "type": "system",
                "id": "sys-1",
            },
        },
        FakeRequest(state),
        {
            "sub": "operator-a",
            "roles": [],
            "tenant_id": "tenant-a",
        },
    )

    assert result["decision"] == "ESCALATE"
    assert result["approval_request_id"] is None
    assert result["policy"] is None

    # Critical risk uses the 4-hour SLA branch.
    assert state.audit.entries[-1]["decision"] == "ESCALATE"
