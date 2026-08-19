from fastapi import APIRouter, Depends
from backend_core.db.database import get_db
from backend_core.security.rbac import require_permission, get_current_claims
from .service import summary

router = APIRouter(prefix="/v1/finops", tags=["FinOps"])

@router.get("/summary", dependencies=[Depends(require_permission("analytics:read"))])
def finops_summary(claims: dict = Depends(get_current_claims), db=Depends(get_db)):
    return summary(db, tenant_id=claims.get("tenant_id", "default"), workspace_id=claims.get("workspace_id"))
