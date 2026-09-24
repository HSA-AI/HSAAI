import json
import pytest

def test_governance_rbac_abac_allow_deny_and_fail_closed():
    import governance.main as g

    rbac = g.RBACEngine()
    assert rbac.has_permission(g.Role.SUPER_ADMIN, "anything:anything") is True
    assert rbac.has_permission(g.Role.ADMIN, "read:documents") is True
    assert rbac.has_permission(g.Role.EMPLOYEE, "delete:agents") is False
    assert g.Role.SUPER_ADMIN in rbac.get_roles_for_permission("read:knowledge")

    engine = g.AccessDecisionEngine()
    subject = g.Subject(
        user_id="u",
        tenant_id="t1",
        role=g.Role.EMPLOYEE,
        department="hr",
        clearance_level=2,
    )
    resource = g.Resource(
        resource_type="knowledge",
        resource_id="r1",
        tenant_id="t1",
        classification="internal",
        department="hr",
    )
    action = g.Action(verb="read", resource="knowledge", risk_level="low")
    env = g.Environment(is_business_hours=True, is_production=True)

    allowed = engine.decide(subject, resource, action, env)
    assert allowed.allowed is True

    cross_tenant = g.Resource(
        resource_type="knowledge", resource_id="r2",
        tenant_id="t2", classification="internal"
    )
    denied = engine.decide(subject, cross_tenant, action, env)
    assert denied.allowed is False
    assert "P001" in denied.reason

    denied_rbac = engine.decide(
        subject, resource, g.Action(verb="delete", resource="agents"), env
    )
    assert denied_rbac.allowed is False
    assert "RBAC denied" in denied_rbac.reason

    auditor = g.Subject(
        user_id="a", tenant_id="t1", role=g.Role.EXTERNAL_AUDITOR,
        clearance_level=3, attributes={}
    )
    audit_resource = g.Resource(
        resource_type="compliance_reports", resource_id="x",
        tenant_id="t1", classification="internal"
    )
    audit_action = g.Action(verb="read", resource="compliance_reports")
    expired = engine.decide(auditor, audit_resource, audit_action, env)
    assert expired.allowed is False


class FakeRedis:
    def __init__(self):
        self.data = {}
        self.lists = {}
        self.expired = []
    def get(self, key):
        return self.data.get(key)
    def set(self, key, value):
        self.data[key] = value
    def lpush(self, key, value):
        self.lists.setdefault(key, []).insert(0, value)
    def ltrim(self, key, start, end):
        self.lists[key] = self.lists.get(key, [])[start:end+1]
    def expire(self, key, ttl):
        self.expired.append((key, ttl))
    def lrange(self, key, start, end):
        return self.lists.get(key, [])[start:end+1]


def test_governance_audit_hash_chain_query(monkeypatch):
    import governance.main as g

    audit = g.AuditLogger.__new__(g.AuditLogger)
    audit.redis = FakeRedis()
    audit.pg_engine = None
    audit.s3 = None
    audit.s3_bucket = "bucket"
    audit._last_hash = "genesis"

    eid1 = audit.log({
        "tenant_id": "t1",
        "user_id": "u1",
        "action": "read:knowledge",
        "decision": "ALLOW",
    })
    first_hash = audit._last_hash
    eid2 = audit.log({
        "tenant_id": "t1",
        "user_id": "u2",
        "action": "write:knowledge",
        "decision": "DENY",
    })

    assert eid1 != eid2
    assert first_hash != audit._last_hash
    assert audit.redis.get("audit:last_hash") == audit._last_hash

    rows = audit.query(action="read:knowledge", limit=10)
    assert len(rows) == 1
    assert rows[0]["action"] == "read:knowledge"

    audit.redis.lpush("audit:events", "{bad json")
    rows = audit.query(limit=10)
    assert all(isinstance(x, dict) for x in rows)


@pytest.mark.asyncio
async def test_tool_registry_dispatch_unknown_success_and_failure(monkeypatch):
    import common.tool_registry as tr

    unknown = await tr.dispatch_tool("__missing__", {}, {"tenant_id": "t"})
    assert unknown["success"] is False
    assert "Unknown tool" in unknown["error"]

    async def ok_handler(value, _context=None):
        return {"success": True, "value": value, "tenant": _context["tenant_id"]}

    async def bad_handler(_context=None):
        raise RuntimeError("boom")

    tr.register_tool(tr.ToolDefinition(
        name="unit_ok", description="unit", parameters={},
        handler=ok_handler, category="test"
    ))
    tr.register_tool(tr.ToolDefinition(
        name="unit_bad", description="unit", parameters={},
        handler=bad_handler, category="test"
    ))

    assert tr.get_tool("unit_ok").name == "unit_ok"
    listed = {x["name"] for x in tr.list_tools()}
    assert "unit_ok" in listed

    good = await tr.dispatch_tool("unit_ok", {"value": 7}, {"tenant_id": "t1"})
    assert good == {"success": True, "value": 7, "tenant": "t1"}

    bad = await tr.dispatch_tool("unit_bad", {}, {"tenant_id": "t1"})
    assert bad["success"] is False
    assert "boom" in bad["error"]


@pytest.mark.asyncio
async def test_tool_registry_short_summarizer_path():
    import common.tool_registry as tr
    result = await tr._summarizer("short text", max_length=100)
    assert result["success"] is True
    assert result["summary"] == "short text"
