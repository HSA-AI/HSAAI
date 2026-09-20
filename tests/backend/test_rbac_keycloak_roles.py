from backend_core.security.rbac import has_permission

def test_keycloak_realm_roles_are_authorized():
    claims = {"realm_access": {"roles": ["knowledge_admin"]}}
    assert has_permission(claims, "knowledge:admin")
    assert has_permission(claims, "knowledge:review")

def test_ai_user_cannot_review_documents():
    claims = {"realm_access": {"roles": ["ai_user"]}}
    assert has_permission(claims, "chat:write")
    assert not has_permission(claims, "knowledge:review")
