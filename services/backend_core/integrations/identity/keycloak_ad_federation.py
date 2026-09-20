def federation_plan() -> dict:
    return {"source": "Windows Server Active Directory", "federation": "Keycloak user federation via LDAPS", "required": ["LDAP_SERVER_URL", "LDAP_BASE_DN", "LDAP_BIND_DN", "LDAP_BIND_PASSWORD"]}
