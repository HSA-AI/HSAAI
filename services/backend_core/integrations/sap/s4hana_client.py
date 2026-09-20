"""SAP S/4HANA read-only connector contract for HSAAI."""
from __future__ import annotations
import os
import httpx

class SAPS4HANAClient:
    def __init__(self, base_url: str | None = None, token: str | None = None):
        self.base_url = (base_url or os.getenv("SAP_S4HANA_BASE_URL", "")).rstrip("/")
        self.token = token or os.getenv("SAP_S4HANA_TOKEN", "")

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.token)

    async def get(self, path: str, params: dict | None = None) -> dict:
        if not self.configured:
            return {"configured": False, "message": "SAP S/4HANA connector requires SAP_S4HANA_BASE_URL and SAP_S4HANA_TOKEN."}
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}
        async with httpx.AsyncClient(timeout=30, verify=True) as client:
            response = await client.get(f"{self.base_url}/{path.lstrip('/')}", params=params, headers=headers)
            response.raise_for_status()
            return response.json()
