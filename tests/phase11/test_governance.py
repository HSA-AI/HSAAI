"""
HSAAI Phase 11 Tests — Governance Service
==========================================
Tests RBAC, ABAC, Audit Logging, Data Governance, and Compliance.
Coverage target: 95% for governance module.
"""
import pytest
import asyncio
from services.governance.main import (
    Role, RBACEngine, ABACEngine, AccessDecisionEngine,
    Subject, Resource, Action, Environment,
    AuditLogger, DataClassification, DataGovernanceEngine,
    ComplianceFramework, ComplianceEngine,
)


# ═══════════════════════════════════════════════════════════════════
# RBAC TESTS
# ═══════════════════════════════════════════════════════════════════
class TestRBAC:
    def setup_method(self):
        self.rbac = RBACEngine()

    def test_super_admin_has_all_permissions(self):
        assert self.rbac.has_permission(Role.SUPER_ADMIN, "anything:anything")

    def test_employee_can_read_chat(self):
        assert self.rbac.has_permission(Role.EMPLOYEE, "read:chat")

    def test_employee_cannot_manage_users(self):
        assert not self.rbac.has_permission(Role.EMPLOYEE, "manage:users")

    def test_admin_can_manage_agents(self):
        assert self.rbac.has_permission(Role.ADMIN, "manage:agents")

    def test_admin_cannot_activate_kill_switch(self):
        """Kill switch is governance-only — admins can't halt AI."""
        assert not self.rbac.has_permission(Role.ADMIN, "activate:kill_switch")

    def test_governance_can_activate_kill_switch(self):
        assert self.rbac.has_permission(Role.GOVERNANCE, "activate:kill_switch")

    def test_builder_can_create_agents(self):
        assert self.rbac.has_permission(Role.BUILDER, "write:agents")

    def test_builder_cannot_read_audit_logs(self):
        assert not self.rbac.has_permission(Role.BUILDER, "read:audit_logs")

    def test_analyst_can_read_metrics(self):
        assert self.rbac.has_permission(Role.ANALYST, "read:metrics")

    def test_analyst_cannot_write_agents(self):
        assert not self.rbac.has_permission(Role.ANALYST, "write:agents")

    def test_wildcard_resource_matching(self):
        """read:* should match read:anything"""
        assert self.rbac.has_permission(Role.ADMIN, "read:any_new_resource")

    def test_get_permissions_returns_set(self):
        perms = self.rbac.get_permissions(Role.EMPLOYEE)
        assert isinstance(perms, set)
        assert "read:chat" in perms

    def test_get_roles_for_permission(self):
        roles = self.rbac.get_roles_for_permission("read:audit_logs")
        assert Role.GOVERNANCE in roles
        assert Role.EXTERNAL_AUDITOR in roles
        assert Role.EMPLOYEE not in roles


# ═══════════════════════════════════════════════════════════════════
# ABAC TESTS
# ═══════════════════════════════════════════════════════════════════
class TestABAC:
    def setup_method(self):
        self.abac = ABACEngine()

    def test_tenant_isolation_passes_same_tenant(self):
        s = Subject(user_id="u1", tenant_id="t1", role=Role.EMPLOYEE, clearance_level=1)
        r = Resource(resource_type="doc", resource_id="d1", tenant_id="t1",
                    classification="public")
        a = Action(verb="read", resource="documents")
        e = Environment()
        decision = self.abac.evaluate(s, r, a, e)
        assert decision.allowed

    def test_tenant_isolation_blocks_cross_tenant(self):
        s = Subject(user_id="u1", tenant_id="t1", role=Role.EMPLOYEE)
        r = Resource(resource_type="doc", resource_id="d1", tenant_id="t2")
        a = Action(verb="read", resource="documents")
        e = Environment()
        decision = self.abac.evaluate(s, r, a, e)
        assert not decision.allowed
        assert "P001" in decision.evaluated_policies[0]

    def test_clearance_blocks_low_clearance_subject(self):
        s = Subject(user_id="u1", tenant_id="t1", role=Role.EMPLOYEE, clearance_level=0)
        r = Resource(resource_type="doc", resource_id="d1", tenant_id="t1",
                    classification="confidential")
        a = Action(verb="read", resource="documents")
        e = Environment()
        decision = self.abac.evaluate(s, r, a, e)
        assert not decision.allowed

    def test_clearance_allows_sufficient_clearance(self):
        s = Subject(user_id="u1", tenant_id="t1", role=Role.EMPLOYEE, clearance_level=2)
        r = Resource(resource_type="doc", resource_id="d1", tenant_id="t1",
                    classification="confidential")
        a = Action(verb="read", resource="documents")
        e = Environment()
        decision = self.abac.evaluate(s, r, a, e)
        assert decision.allowed

    def test_department_restriction_blocks_other_department(self):
        s = Subject(user_id="u1", tenant_id="t1", role=Role.EMPLOYEE, department="finance")
        r = Resource(resource_type="doc", resource_id="d1", tenant_id="t1",
                    classification="restricted", department="hr")
        a = Action(verb="read", resource="documents")
        e = Environment()
        decision = self.abac.evaluate(s, r, a, e)
        assert not decision.allowed

    def test_critical_action_blocked_outside_business_hours(self):
        s = Subject(user_id="u1", tenant_id="t1", role=Role.ADMIN)
        r = Resource(resource_type="data", resource_id="d1", tenant_id="t1")
        a = Action(verb="delete", resource="data", risk_level="critical")
        e = Environment(is_business_hours=False)
        decision = self.abac.evaluate(s, r, a, e)
        assert not decision.allowed


# ═══════════════════════════════════════════════════════════════════
# UNIFIED DECISION ENGINE TESTS
# ═══════════════════════════════════════════════════════════════════
class TestAccessDecisionEngine:
    def setup_method(self):
        self.engine = AccessDecisionEngine()

    def test_rbac_blocks_first(self):
        """If RBAC denies, ABAC is not evaluated."""
        s = Subject(user_id="u1", tenant_id="t1", role=Role.EMPLOYEE)
        r = Resource(resource_type="user", resource_id="u2", tenant_id="t1")
        a = Action(verb="manage", resource="users")
        e = Environment()
        decision = self.engine.decide(s, r, a, e)
        assert not decision.allowed
        assert "RBAC" in decision.reason

    def test_rbac_passes_then_abac_evaluates(self):
        s = Subject(user_id="u1", tenant_id="t1", role=Role.ADMIN, clearance_level=3)
        r = Resource(resource_type="user", resource_id="u2", tenant_id="t1",
                    classification="public")
        a = Action(verb="manage", resource="users")
        e = Environment()
        decision = self.engine.decide(s, r, a, e)
        assert decision.allowed


# ═══════════════════════════════════════════════════════════════════
# AUDIT LOGGER TESTS
# ═══════════════════════════════════════════════════════════════════
class TestAuditLogger:
    def setup_method(self):
        # Use in-memory mode (no Redis)
        self.audit = AuditLogger(redis_url="redis://localhost:1")  # will fail → None
        self.audit._last_hash = "genesis"

    def test_log_returns_event_id(self):
        event = {"tenant_id": "t1", "user_id": "u1", "action": "read:doc"}
        event_id = self.audit.log(event)
        assert event_id is not None
        assert len(event_id) == 36  # UUID format

    def test_log_creates_hash_chain(self):
        e1 = self.audit.log({"action": "test1"})
        e2 = self.audit.log({"action": "test2"})
        # Hash chain: each entry references previous hash
        assert self.audit._last_hash != "genesis"


# ═══════════════════════════════════════════════════════════════════
# DATA GOVERNANCE TESTS
# ═══════════════════════════════════════════════════════════════════
class TestDataGovernance:
    def setup_method(self):
        self.gov = DataGovernanceEngine(redis_url="redis://localhost:1")

    def test_classify_pii_content(self):
        """Content with national ID should be classified as PII."""
        content = "Customer national ID is 1234567890"
        assert self.gov.classify(content) == DataClassification.PII

    def test_classify_email_as_pii(self):
        content = "Contact: ahmed@hsagroup.com"
        assert self.gov.classify(content) == DataClassification.PII

    def test_classify_financial_content(self):
        content = "The salary for this position is 50000"
        assert self.gov.classify(content) == DataClassification.FINANCIAL

    def test_classify_restricted_content(self):
        content = "This document is confidential and secret"
        assert self.gov.classify(content) == DataClassification.RESTRICTED

    def test_classify_internal_content(self):
        content = "Hello world, this is a normal message"
        assert self.gov.classify(content) == DataClassification.INTERNAL

    def test_retention_policy(self):
        """PII should have 3-year retention (Saudi PDPL)."""
        retention = self.gov.get_retention(DataClassification.PII)
        assert retention == 1095  # 3 years

    def test_financial_retention_7_years(self):
        retention = self.gov.get_retention(DataClassification.FINANCIAL)
        assert retention == 2555  # 7 years


# ═══════════════════════════════════════════════════════════════════
# COMPLIANCE TESTS
# ═══════════════════════════════════════════════════════════════════
class TestCompliance:
    def setup_method(self):
        self.engine = ComplianceEngine()

    def test_nist_ai_rmf_policies_loaded(self):
        policies = self.engine.get_policies_by_framework(ComplianceFramework.NIST_AI_RMF)
        assert len(policies) >= 4  # GOVERN, MAP, MEASURE, MANAGE

    def test_iso_42001_policies_loaded(self):
        policies = self.engine.get_policies_by_framework(ComplianceFramework.ISO_42001)
        assert len(policies) >= 3

    def test_gdpr_policies_loaded(self):
        policies = self.engine.get_policies_by_framework(ComplianceFramework.GDPR)
        assert any(p.policy_id == "GDPR-ART-17" for p in policies)  # right to erasure

    def test_saudi_pdpl_policies_loaded(self):
        policies = self.engine.get_policies_by_framework(ComplianceFramework.SAUDI_PDPL)
        assert any(p.policy_id == "PDPL-ART-33" for p in policies)  # breach notification

    def test_owasp_llm_top_10_policies_loaded(self):
        policies = self.engine.get_policies_by_framework(ComplianceFramework.OWASP_LLM_TOP_10)
        assert any(p.policy_id == "OWASP-LLM01" for p in policies)

    def test_assess_compliance_returns_report(self):
        report = self.engine.assess_compliance()
        assert "frameworks" in report
        assert "nist_ai_rmf" in report["frameworks"]
        assert report["frameworks"]["nist_ai_rmf"]["total_policies"] >= 4


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=services.governance", "--cov-report=term-missing"])
