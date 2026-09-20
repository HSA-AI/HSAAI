"""Only configured OAuth clients can contribute HSAAI resource roles."""
import pytest
from common.auth.service_auth import _extract_roles
from backend_core.security.rbac import _roles_from_claims,has_permission

@pytest.mark.parametrize('extract',[_extract_roles,_roles_from_claims])
def test_other_client_cannot_grant_platform_admin(monkeypatch,extract):
    monkeypatch.setenv('HSAAI_ROLE_CLIENT_IDS','hsaai-api')
    claims={'roles':['ai_user'],'resource_access':{'unrelated-app':{'roles':['hsaai_admin']},'hsaai-api':{'roles':['auditor']}}}
    assert extract(claims)==['ai_user','auditor'] and not has_permission(claims,'approvals:decide')

@pytest.mark.parametrize('extract',[_extract_roles,_roles_from_claims])
def test_configured_client_and_realm_roles_remain_supported(monkeypatch,extract):
    monkeypatch.setenv('HSAAI_ROLE_CLIENT_IDS','hsaai-api,service-client')
    claims={'realm_access':{'roles':['department_manager']},'resource_access':{'service-client':{'roles':['hsaai_admin']}}}
    assert extract(claims)==['department_manager','hsaai_admin']
