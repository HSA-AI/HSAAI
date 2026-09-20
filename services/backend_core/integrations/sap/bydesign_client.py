"""SAP Business ByDesign read-only connector contract for HSAAI."""
from __future__ import annotations
import os
import httpx

class SAPByDesignClient:
    def __init__(self, base_url: str | None = None, username: str | None = None, password: str | None = None):
        self.base_url = (base_url or os.getenv("SAP_BYDESIGN_BASE_URL", "")).rstrip("/")
        self.username = username or os.getenv("SAP_BYDESIGN_USERNAME", "")
        self.password = password or os.getenv("SAP_BYDESIGN_PASSWORD", "")

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.username and self.password)

    async def get(self, path: str, params: dict | None = None) -> dict:
        if not self.configured:
            return {"configured": False, "message": "SAP Business ByDesign connector credentials are not configured."}
        async with httpx.AsyncClient(timeout=30, verify=True, auth=(self.username, self.password)) as client:
            response = await client.get(f"{self.base_url}/{path.lstrip('/')}", params=params, headers={"Accept": "application/json"})
            response.raise_for_status()
            return response.json()
