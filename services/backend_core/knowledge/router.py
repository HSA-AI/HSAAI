from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session
from backend_core.db.database import get_db
from backend_core.security.rbac import require_permission, verify_authorization, get_current_claims
from backend_core.knowledge.service import KnowledgeHubService
from backend_core.knowledge.schemas import KnowledgeSpaceCreate, KnowledgeCollectionCreate, KnowledgeDocumentRegister, KnowledgePermissionGrant, KnowledgeSearchRequest, DocumentWorkflowRequest

router = APIRouter(prefix="/v1/knowledge-hub", tags=["Enterprise Knowledge Hub"])

@router.get("/overview", dependencies=[Depends(require_permission("knowledge:read"))])
def overview(db: Session = Depends(get_db)):
    svc = KnowledgeHubService(db)
    spaces = svc.list_spaces()
    collections = svc.list_collections()
    analytics = svc.analytics()
    return {"spaces": spaces, "collections": collections, "analytics": analytics, "capabilities": ["spaces", "collections", "document_versioning", "approval_workflow", "qdrant_delete_sync", "metadata", "permissions", "analytics", "rag_bridge"]}

@router.post("/spaces", dependencies=[Depends(require_permission("knowledge:admin"))])
def create_space(payload: KnowledgeSpaceCreate, db: Session = Depends(get_db)):
    return KnowledgeHubService(db).create_space(payload)

@router.get("/spaces", dependencies=[Depends(require_permission("knowledge:read"))])
def list_spaces(db: Session = Depends(get_db)):
    return KnowledgeHubService(db).list_spaces()

@router.post("/collections", dependencies=[Depends(require_permission("knowledge:admin"))])
def create_collection(payload: KnowledgeCollectionCreate, db: Session = Depends(get_db)):
    return KnowledgeHubService(db).create_collection(payload)

@router.get("/collections", dependencies=[Depends(require_permission("knowledge:read"))])
def list_collections(space_key: str | None = None, db: Session = Depends(get_db)):
    return KnowledgeHubService(db).list_collections(space_key)

@router.post("/documents/register", dependencies=[Depends(require_permission("knowledge:upload"))])
async def register_document(payload: KnowledgeDocumentRegister, authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    # FIX v2.1 (P0): properly await verify_authorization
    claims = await verify_authorization(authorization)
    payload.uploaded_by = payload.uploaded_by or claims.get("sub", "system")
    payload.tenant_id = claims.get("tenant_id", payload.tenant_id)
    payload.workspace_id = claims.get("workspace_id", payload.workspace_id)
    return KnowledgeHubService(db).register_document(payload)

@router.get("/documents", dependencies=[Depends(require_permission("knowledge:read"))])
def list_documents(space_key: str | None = None, collection_key: str | None = None, claims: dict = Depends(get_current_claims), db: Session = Depends(get_db)):
    return KnowledgeHubService(db).list_documents(space_key, collection_key, claims)

@router.get("/documents/pending", dependencies=[Depends(require_permission("knowledge:review"))])
def list_pending_documents(db: Session = Depends(get_db)):
    return KnowledgeHubService(db).list_pending_documents()

@router.get("/documents/{document_id}", dependencies=[Depends(require_permission("knowledge:read"))])
def get_document(document_id: str, db: Session = Depends(get_db)):
    return KnowledgeHubService(db).get_document(document_id)

@router.post("/documents/{document_id}/submit-for-review", dependencies=[Depends(require_permission("knowledge:upload"))])
def submit_for_review(document_id: str, payload: DocumentWorkflowRequest, claims: dict = Depends(get_current_claims), db: Session = Depends(get_db)):
    return KnowledgeHubService(db).submit_for_review(document_id, claims.get("sub", "system"), payload.reason)

@router.post("/documents/{document_id}/approve", dependencies=[Depends(require_permission("knowledge:review"))])
def approve_document(document_id: str, payload: DocumentWorkflowRequest, claims: dict = Depends(get_current_claims), db: Session = Depends(get_db)):
    return KnowledgeHubService(db).approve_document(document_id, claims.get("sub", "system"), payload.reason)

@router.post("/documents/{document_id}/reject", dependencies=[Depends(require_permission("knowledge:review"))])
def reject_document(document_id: str, payload: DocumentWorkflowRequest, claims: dict = Depends(get_current_claims), db: Session = Depends(get_db)):
    return KnowledgeHubService(db).reject_document(document_id, claims.get("sub", "system"), payload.reason)

@router.post("/documents/{document_id}/archive", dependencies=[Depends(require_permission("knowledge:review"))])
def archive_document(document_id: str, payload: DocumentWorkflowRequest, claims: dict = Depends(get_current_claims), db: Session = Depends(get_db)):
    return KnowledgeHubService(db).archive_document(document_id, claims.get("sub", "system"), payload.reason)

@router.delete("/documents/{document_id}", dependencies=[Depends(require_permission("knowledge:delete"))])
def delete_document(document_id: str, claims: dict = Depends(get_current_claims), db: Session = Depends(get_db)):
    return KnowledgeHubService(db).delete_document(document_id, claims.get("sub", "system"))

@router.get("/documents/{document_id}/audit", dependencies=[Depends(require_permission("audit:read"))])
def audit_trail(document_id: str, db: Session = Depends(get_db)):
    return KnowledgeHubService(db).audit_trail(document_id)

@router.post("/permissions", dependencies=[Depends(require_permission("knowledge:admin"))])
def grant_permission(payload: KnowledgePermissionGrant, db: Session = Depends(get_db)):
    return KnowledgeHubService(db).grant_permission(payload)

@router.get("/permissions", dependencies=[Depends(require_permission("knowledge:read"))])
def permissions(resource_key: str | None = None, db: Session = Depends(get_db)):
    return KnowledgeHubService(db).permissions(resource_key)

@router.post("/search", dependencies=[Depends(require_permission("knowledge:read"))])
def search(payload: KnowledgeSearchRequest, claims: dict = Depends(get_current_claims), db: Session = Depends(get_db)):
    return KnowledgeHubService(db).search_metadata(payload, claims)

@router.get("/analytics", dependencies=[Depends(require_permission("analytics:read"))])
def analytics(db: Session = Depends(get_db)):
    return KnowledgeHubService(db).analytics()
