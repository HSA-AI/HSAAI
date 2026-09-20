from fastapi import APIRouter
from backend_core.branding.config import branding

router = APIRouter(prefix="/branding", tags=["branding"])

@router.get("/official")
def official_branding():
    return branding.model_dump()
