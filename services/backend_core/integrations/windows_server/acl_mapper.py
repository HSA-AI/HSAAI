def map_windows_acl_to_hsaai_permissions(file_acl: list[dict]) -> dict:
    """Map Windows ACL entries into HSAAI permission scopes.

    Expected ACL item: {"principal": "DOMAIN\\Group", "rights": ["read"]}
    """
    readers = sorted({entry.get("principal", "") for entry in file_acl if "read" in [r.lower() for r in entry.get("rights", [])]})
    return {"allowed_principals": readers, "policy": "deny_by_default"}
