from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend_core.db.database import get_db
from backend_core.security.rbac import require_permission
from backend_core.executive.schemas import ExecutiveAlertCreate
from backend_core.executive.service import ExecutiveAnalyticsService

router = APIRouter(prefix="/v1/executive", tags=["Executive Dashboard Enterprise"])

@router.get("/overview", dependencies=[Depends(require_permission("executive:read"))])
def overview(db: Session = Depends(get_db)):
    return ExecutiveAnalyticsService(db).overview()

@router.get("/departments", dependencies=[Depends(require_permission("executive:read"))])
def departments(db: Session = Depends(get_db)):
    return ExecutiveAnalyticsService(db).departments()

@router.get("/knowledge", dependencies=[Depends(require_permission("executive:read"))])
def knowledge(db: Session = Depends(get_db)):
    return ExecutiveAnalyticsService(db).knowledge()

@router.get("/agents", dependencies=[Depends(require_permission("executive:read"))])
def agents(db: Session = Depends(get_db)):
    return ExecutiveAnalyticsService(db).agents()

@router.get("/workflows", dependencies=[Depends(require_permission("executive:read"))])
def workflows(db: Session = Depends(get_db)):
    return ExecutiveAnalyticsService(db).workflows()

@router.get("/infrastructure", dependencies=[Depends(require_permission("executive:read"))])
def infrastructure(db: Session = Depends(get_db)):
    return ExecutiveAnalyticsService(db).infrastructure()

@router.get("/alerts", dependencies=[Depends(require_permission("executive:read"))])
def alerts(db: Session = Depends(get_db)):
    return ExecutiveAnalyticsService(db).alerts()

@router.post("/alerts", dependencies=[Depends(require_permission("executive:write"))])
def create_alert(payload: ExecutiveAlertCreate, db: Session = Depends(get_db)):
    return ExecutiveAnalyticsService(db).create_alert(payload)
