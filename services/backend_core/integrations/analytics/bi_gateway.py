import os

def bi_status() -> dict:
    return {"configured": bool(os.getenv("BI_GATEWAY_URL")), "mode": "read-only KPI query gateway"}
