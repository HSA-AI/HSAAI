"""Windows File Server / SMB connector contract."""
from __future__ import annotations
import os

class FileServerConnector:
    def __init__(self):
        self.server = os.getenv("SMB_SERVER", "")
        self.share = os.getenv("SMB_SHARE", "")
        self.domain = os.getenv("SMB_DOMAIN", "")

    @property
    def configured(self) -> bool:
        return bool(self.server and self.share and os.getenv("SMB_USERNAME") and os.getenv("SMB_PASSWORD"))

    def status(self) -> dict:
        return {"configured": self.configured, "server_present": bool(self.server), "share_present": bool(self.share), "acl_required": True}
