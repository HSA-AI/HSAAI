import os

def itsm_status() -> dict:
    return {"configured": bool(os.getenv("ITSM_BASE_URL")), "mode": "ticket read/create subject to approval"}
