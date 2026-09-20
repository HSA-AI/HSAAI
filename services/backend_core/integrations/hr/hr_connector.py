import os

def hr_status() -> dict:
    return {"configured": bool(os.getenv("HR_SYSTEM_BASE_URL")), "mode": "read-only HR policy and permitted employee data"}
