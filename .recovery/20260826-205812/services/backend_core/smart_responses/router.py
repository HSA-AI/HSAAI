import csv
import io
import json
from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session

from backend_core.db.database import get_db
from backend_core.security.rbac import require_permission
from backend_core.smart_responses import service
from backend_core.smart_responses.schemas import PriorityUpdate, SmartResponseCreate, SmartResponseUpdate

router = APIRouter(prefix="/v1/smart-responses", tags=["Smart Responses"])


def _ctx(claims: dict) -> tuple[str, str]:
    return claims.get("tenant_id", "default"), claims.get("sub", "system")


@router.get("")
def list_smart_responses(
    workspace_id: str | None = Query(default=None),
    include_disabled: bool = True,
    db: Session = Depends(get_db),
    claims: dict = Depends(require_permission("admin:read")),
):
    tenant_id, _ = _ctx(claims)
    service.seed_defaults(db, tenant_id=tenant_id, workspace_id=workspace_id or claims.get("workspace_id", "default"))
    return [service.to_dict(item) for item in service.list_templates(db, tenant_id, workspace_id, include_disabled)]


@router.post("")
def create_smart_response(payload: SmartResponseCreate, db: Session = Depends(get_db), claims: dict = Depends(require_permission("admin:read"))):
    tenant_id, actor = _ctx(claims)
    return service.to_dict(service.create_template(db, payload, tenant_id, actor))


@router.get("/analytics")
def smart_response_analytics(workspace_id: str | None = None, db: Session = Depends(get_db), claims: dict = Depends(require_permission("admin:read"))):
    tenant_id, _ = _ctx(claims)
    return service.analytics(db, tenant_id, workspace_id)


@router.post("/import/{fmt}")
async def import_smart_responses(fmt: str, file: UploadFile = File(...), db: Session = Depends(get_db), claims: dict = Depends(require_permission("admin:read"))):
    tenant_id, actor = _ctx(claims)
    items = await service.parse_upload(file, fmt)
    return service.import_items(db, items, tenant_id, actor)


@router.get("/export/json")
def export_json(workspace_id: str | None = None, db: Session = Depends(get_db), claims: dict = Depends(require_permission("admin:read"))):
    tenant_id, _ = _ctx(claims)
    payload = json.dumps(service.export_rows(db, tenant_id, workspace_id), ensure_ascii=False, default=str, indent=2)
    return Response(payload, media_type="application/json", headers={"Content-Disposition": "attachment; filename=smart_responses.json"})


@router.get("/export/csv")
def export_csv(workspace_id: str | None = None, db: Session = Depends(get_db), claims: dict = Depends(require_permission("admin:read"))):
    tenant_id, _ = _ctx(claims)
    rows = service.export_rows(db, tenant_id, workspace_id)
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()) if rows else ["rule_name", "intent", "keywords", "response_text"])
    writer.writeheader()
    writer.writerows(rows)
    return Response(output.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=smart_responses.csv"})


@router.get("/export/excel")
def export_excel(workspace_id: str | None = None, db: Session = Depends(get_db), claims: dict = Depends(require_permission("admin:read"))):
    try:
        from openpyxl import Workbook
    except Exception as exc:
        return Response(f"openpyxl is required for Excel export: {exc}", status_code=500)
    tenant_id, _ = _ctx(claims)
    rows = service.export_rows(db, tenant_id, workspace_id)
    wb = Workbook()
    ws = wb.active
    ws.title = "Smart Responses"
    headers = list(rows[0].keys()) if rows else ["rule_name", "intent", "keywords", "response_text"]
    ws.append(headers)
    for row in rows:
        ws.append([json.dumps(row.get(h), ensure_ascii=False, default=str) if isinstance(row.get(h), (list, dict)) else row.get(h) for h in headers])
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": "attachment; filename=smart_responses.xlsx"})


@router.get("/{template_id}")
def get_smart_response(template_id: int, db: Session = Depends(get_db), claims: dict = Depends(require_permission("admin:read"))):
    tenant_id, _ = _ctx(claims)
    return service.to_dict(service.get_template(db, template_id, tenant_id))


@router.put("/{template_id}")
def update_smart_response(template_id: int, payload: SmartResponseUpdate, db: Session = Depends(get_db), claims: dict = Depends(require_permission("admin:read"))):
    tenant_id, actor = _ctx(claims)
    return service.to_dict(service.update_template(db, template_id, payload, tenant_id, actor))


@router.delete("/{template_id}")
def delete_smart_response(template_id: int, db: Session = Depends(get_db), claims: dict = Depends(require_permission("admin:read"))):
    tenant_id, _ = _ctx(claims)
    service.delete_template(db, template_id, tenant_id)
    return {"deleted": True}


@router.patch("/{template_id}/toggle")
def toggle_smart_response(template_id: int, db: Session = Depends(get_db), claims: dict = Depends(require_permission("admin:read"))):
    tenant_id, actor = _ctx(claims)
    template = service.get_template(db, template_id, tenant_id)
    return service.to_dict(service.update_template(db, template_id, SmartResponseUpdate(enabled=not template.enabled), tenant_id, actor))


@router.patch("/{template_id}/priority")
def update_priority(template_id: int, payload: PriorityUpdate, db: Session = Depends(get_db), claims: dict = Depends(require_permission("admin:read"))):
    tenant_id, actor = _ctx(claims)
    return service.to_dict(service.update_template(db, template_id, SmartResponseUpdate(priority=payload.priority), tenant_id, actor))
