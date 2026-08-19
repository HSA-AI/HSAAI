"""Active Directory / LDAPS connector contract."""
from __future__ import annotations
import os

class ActiveDirectoryConnector:
    def __init__(self):
        self.server_url = os.getenv("LDAP_SERVER_URL", "")
        self.base_dn = os.getenv("LDAP_BASE_DN", "")
        self.bind_dn = os.getenv("LDAP_BIND_DN", "")

    @property
    def configured(self) -> bool:
        return bool(self.server_url and self.base_dn and self.bind_dn and os.getenv("LDAP_BIND_PASSWORD"))

    def status(self) -> dict:
        return {"configured": self.configured, "server_url_present": bool(self.server_url), "base_dn_present": bool(self.base_dn), "bind_dn_present": bool(self.bind_dn)}
