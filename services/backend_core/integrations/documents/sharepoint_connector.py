import os

def sharepoint_status() -> dict:
    return {"configured": bool(os.getenv("SHAREPOINT_SITE_URL") and os.getenv("SHAREPOINT_CLIENT_ID")), "mode": "Microsoft Graph read-only sync"}
