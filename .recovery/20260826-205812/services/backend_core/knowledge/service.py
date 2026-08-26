import json, time, uuid, hashlib, os
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException
from backend_core.db.models import KnowledgeSpace, KnowledgeCollection, KnowledgeDocument, KnowledgeVersion, KnowledgePermission, KnowledgeAnalyticsEvent, DocumentApprovalEvent
from backend_core.knowledge.schemas import KnowledgeSpaceCreate, KnowledgeCollectionCreate, KnowledgeDocumentRegister, KnowledgePermissionGrant, KnowledgeSearchRequest
from backend_core.knowledge.qdrant_client import delete_document_vectors, QdrantDeleteError
# v9.1: Secure migration — use delete_document_vectors_secure for new code
# The original delete_document_vectors is preserved for backward compatibility
# but all NEW code should use the secure version.
# Migration in progress: archive_document and delete_document below
# still use the old function for backward compatibility with existing callers
# that pass only document_id (no claims). These will be migrated in v10.0
# when the API layer is updated to pass claims through.
try:
    from backend_core.knowledge.qdrant_client_secure import delete_document_vectors_secure
    _SECURE_DELETE_AVAILABLE = True
except ImportError:
    _SECURE_DELETE_AVAILABLE = False

SENSITIVE_CLASSIFICATIONS = {"sensitive", "confidential", "restricted"}
RAG_ENGINE_URL = os.getenv("RAG_ENGINE_URL", "http://rag_engine:8030")

class KnowledgeHubService:
    """Enterprise Knowledge Hub service with approval workflow and RAG governance."""
    def __init__(self, db: Session):
        self.db = db

    def ensure_defaults(self):
        if not self.db.query(KnowledgeSpace).first():
            self.create_space(KnowledgeSpaceCreate(key="corporate", name="Corporate Knowledge", description="Policies, procedures and enterprise documents", owner="AI Admin"))
            self.create_space(KnowledgeSpaceCreate(key="hr", name="Human Resources", description="HR policies and employee knowledge", owner="HR"))
            self.create_space(KnowledgeSpaceCreate(key="finance", name="Finance", description="Finance, procurement and accounting knowledge", owner="Finance"))
        if not self.db.query(KnowledgeCollection).first():
            self.create_collection(KnowledgeCollectionCreate(space_key="corporate", key="policies", name="Policies", description="Approved internal policies"))
            self.create_collection(KnowledgeCollectionCreate(space_key="corporate", key="procedures", name="Procedures", description="Operating procedures"))

    def create_space(self, payload: KnowledgeSpaceCreate):
        item = KnowledgeSpace(**payload.model_dump())
        self.db.add(item); self.db.commit(); self.db.refresh(item)
        self.log("space_created", "space", item.key, payload.owner)
        return item

    def list_spaces(self):
        self.ensure_defaults()
        return self.db.query(KnowledgeSpace).order_by(KnowledgeSpace.created_at.desc()).all()

    def create_collection(self, payload: KnowledgeCollectionCreate):
        item = KnowledgeCollection(**payload.model_dump())
        self.db.add(item); self.db.commit(); self.db.refresh(item)
        self.log("collection_created", "collection", item.key)
        return item

    def list_collections(self, space_key: str | None = None):
        self.ensure_defaults()
        q = self.db.query(KnowledgeCollection)
        if space_key: q = q.filter(KnowledgeCollection.space_key == space_key)
        return q.order_by(KnowledgeCollection.created_at.desc()).all()

    def register_document(self, payload: KnowledgeDocumentRegister):
        document_id = f"doc_{uuid.uuid4().hex[:16]}"
        metadata_json = json.dumps(payload.metadata or {}, ensure_ascii=False)
        tags_json = json.dumps(payload.tags or [], ensure_ascii=False)
        initial_status = payload.status or ("pending_review" if payload.sensitivity in SENSITIVE_CLASSIFICATIONS or payload.classification in SENSITIVE_CLASSIFICATIONS else "approved")
        item = KnowledgeDocument(
            document_id=document_id,
            metadata_json=metadata_json,
            tags_json=tags_json,
            status=initial_status,
            **payload.model_dump(exclude={"metadata", "tags", "status"})
        )
        self.db.add(item)
        checksum = hashlib.sha256(f"{payload.filename}:{time.time()}".encode()).hexdigest()
        self.db.add(KnowledgeVersion(document_id=document_id, version=1, checksum=checksum, change_note="Initial registration", created_by=payload.uploaded_by))
        col = self.db.query(KnowledgeCollection).filter(KnowledgeCollection.key == payload.collection_key).first()
        if col: col.document_count = (col.document_count or 0) + 1
        self.db.commit(); self.db.refresh(item)
        self.log("document_registered", "document", document_id, payload.uploaded_by)
        self.workflow_log(document_id, "register", payload.uploaded_by, "", initial_status, "Initial document registration", item.tenant_id, item.workspace_id)
        return item

    def _visible_document_query(self, claims: dict | None = None):
        q = self.db.query(KnowledgeDocument).filter(KnowledgeDocument.status != "archived")
        if not claims:
            return q
        tenant_id = claims.get("tenant_id", "default")
        workspace_id = claims.get("workspace_id", "default")
        roles = set(claims.get("roles") or [])
        q = q.filter(KnowledgeDocument.tenant_id == tenant_id, KnowledgeDocument.workspace_id == workspace_id)
        if "hsaai_admin" in roles or "knowledge_admin" in roles or "auditor" in roles:
            return q
        # Department managers see their department and public/internal approved docs.
        department = claims.get("department") or claims.get("workspace_id") or "general"
        return q.filter(KnowledgeDocument.status == "approved").filter(
            (KnowledgeDocument.department == department) | (KnowledgeDocument.classification.in_(["public", "internal"]))
        )

    def list_documents(self, space_key: str | None = None, collection_key: str | None = None, claims: dict | None = None):
        q = self._visible_document_query(claims)
        if space_key: q = q.filter(KnowledgeDocument.space_key == space_key)
        if collection_key: q = q.filter(KnowledgeDocument.collection_key == collection_key)
        return q.order_by(KnowledgeDocument.created_at.desc()).limit(300).all()

    def get_document(self, document_id: str):
        item = self.db.query(KnowledgeDocument).filter(KnowledgeDocument.document_id == document_id).first()
        if not item:
            raise HTTPException(status_code=404, detail="Document not found")
        return item

    def submit_for_review(self, document_id: str, actor: str, reason: str = ""):
        item = self.get_document(document_id)
        before = item.status
        if item.status not in {"draft", "rejected"}:
            raise HTTPException(status_code=409, detail="Only draft or rejected documents can be submitted for review")
        item.status = "pending_review"
        self.db.commit(); self.db.refresh(item)
        self.workflow_log(document_id, "submit_for_review", actor, before, item.status, reason, item.tenant_id, item.workspace_id)
        self.log("document_submitted_for_review", "document", document_id, actor)
        return item

    def approve_document(self, document_id: str, actor: str, reason: str = ""):
        item = self.get_document(document_id)
        before = item.status
        if item.status not in {"pending_review", "draft"}:
            raise HTTPException(status_code=409, detail="Only pending_review or draft documents can be approved")
        item.status = "approved"
        item.reviewed_by = actor
        item.review_reason = reason
        item.approved_at = func.now()
        item.qdrant_indexed = True  # Actual ingestion is performed by RAG engine in production upload flow.
        self.db.commit(); self.db.refresh(item)
        self.workflow_log(document_id, "approve", actor, before, item.status, reason, item.tenant_id, item.workspace_id)
        self.log("document_approved", "document", document_id, actor)
        return item

    def reject_document(self, document_id: str, actor: str, reason: str):
        item = self.get_document(document_id)
        before = item.status
        if item.status not in {"pending_review", "draft"}:
            raise HTTPException(status_code=409, detail="Only pending_review or draft documents can be rejected")
        item.status = "rejected"
        item.reviewed_by = actor
        item.review_reason = reason
        self.db.commit(); self.db.refresh(item)
        self.workflow_log(document_id, "reject", actor, before, item.status, reason, item.tenant_id, item.workspace_id)
        self.log("document_rejected", "document", document_id, actor)
        return item

    def archive_document(self, document_id: str, actor: str, reason: str = ""):
        item = self.get_document(document_id)
        before = item.status
        item.status = "archived"
        item.archived_at = func.now()
        self.db.commit(); self.db.refresh(item)
        try:
            # v10.1: Migrated to delete_document_vectors (original) for sync context
            # Note: The async secure version (delete_document_vectors_v91) should be
            # called from the API layer where claims are available. This sync method
            # is preserved for backward compatibility with existing callers.
            # Full migration to async secure version in v11.0.
            delete_document_vectors(document_id)
            item.qdrant_indexed = False
            self.db.commit()
            qdrant_result = "deleted"
        except QdrantDeleteError as exc:
            qdrant_result = f"delete_failed:{exc}"
        self.workflow_log(document_id, "archive", actor, before, item.status, f"{reason} | qdrant={qdrant_result}", item.tenant_id, item.workspace_id)
        self.log("document_archived", "document", document_id, actor)
        return {"document": item, "qdrant": qdrant_result}

    async def archive_document_secure(self, document_id: str, claims: dict, reason: str = ""):
        """v10.1: Secure archive using delete_document_vectors_v91.

        This is the production-recommended method that uses the secure
        delete function with full Zero Trust enforcement.
        """
        from backend_core.knowledge.qdrant_v91_upgrades import delete_document_vectors_v91
        item = self.get_document(document_id)
        before = item.status
        item.status = "archived"
        item.archived_at = func.now()
        self.db.commit(); self.db.refresh(item)
        try:
            qdrant_result = await delete_document_vectors_v91(document_id, claims)
            item.qdrant_indexed = False
            self.db.commit()
            qdrant_status = "deleted"
        except Exception as exc:
            qdrant_result = {"error": str(exc)}
            qdrant_status = "failed"
        actor = claims.get("sub", "system")
        self.workflow_log(document_id, "archive", actor, before, item.status,
                          f"{reason} | qdrant={qdrant_status}", item.tenant_id, item.workspace_id)
        self.log("document_archived", "document", document_id, actor)
        return {"document": item, "qdrant": qdrant_result}

    def delete_document(self, document_id: str, actor: str):
        item = self.get_document(document_id)
        tenant_id, workspace_id = item.tenant_id, item.workspace_id
        try:
            # v10.1: Migrated to delete_document_vectors (original) for sync context
            # See archive_document_secure for the async secure version.
            qdrant_result = delete_document_vectors(document_id)
            qdrant_status = "deleted"
        except QdrantDeleteError as exc:
            qdrant_result = {"error": str(exc)}
            qdrant_status = "failed"
        self.workflow_log(document_id, "delete", actor, item.status, "deleted", f"qdrant={qdrant_status}", tenant_id, workspace_id)
        self.log("document_deleted", "document", document_id, actor)
        self.db.delete(item); self.db.commit()
        return {"deleted": True, "document_id": document_id, "qdrant_status": qdrant_status, "qdrant_result": qdrant_result}

    def list_pending_documents(self):
        return self.db.query(KnowledgeDocument).filter(KnowledgeDocument.status == "pending_review").order_by(KnowledgeDocument.created_at.desc()).all()

    def grant_permission(self, payload: KnowledgePermissionGrant):
        item = KnowledgePermission(**payload.model_dump())
        self.db.add(item); self.db.commit(); self.db.refresh(item)
        self.log("permission_granted", payload.resource_type, payload.resource_key, payload.principal)
        return item

    def permissions(self, resource_key: str | None = None):
        q = self.db.query(KnowledgePermission)
        if resource_key: q = q.filter(KnowledgePermission.resource_key == resource_key)
        return q.order_by(KnowledgePermission.created_at.desc()).all()

    def workflow_log(self, document_id: str, action: str, actor: str, from_status: str, to_status: str, reason: str, tenant_id: str, workspace_id: str):
        self.db.add(DocumentApprovalEvent(document_id=document_id, action=action, actor=actor, from_status=from_status or "", to_status=to_status or "", reason=reason or "", tenant_id=tenant_id, workspace_id=workspace_id))
        self.db.commit()

    def audit_trail(self, document_id: str):
        return self.db.query(DocumentApprovalEvent).filter(DocumentApprovalEvent.document_id == document_id).order_by(DocumentApprovalEvent.created_at.desc()).all()

    def log(self, event_type: str, resource_type: str, resource_key: str, actor: str = "system", query: str = "", result_count: int = 0, latency_ms: int = 0):
        self.db.add(KnowledgeAnalyticsEvent(event_type=event_type, resource_type=resource_type, resource_key=resource_key, actor=actor, query=query, result_count=result_count, latency_ms=latency_ms))
        self.db.commit()

    def analytics(self):
        spaces = self.db.query(KnowledgeSpace).count()
        collections = self.db.query(KnowledgeCollection).count()
        documents = self.db.query(KnowledgeDocument).count()
        events = self.db.query(KnowledgeAnalyticsEvent).count()
        by_status = dict(self.db.query(KnowledgeDocument.status, func.count(KnowledgeDocument.id)).group_by(KnowledgeDocument.status).all())
        sensitive = self.db.query(KnowledgeDocument).filter(KnowledgeDocument.sensitivity.in_(list(SENSITIVE_CLASSIFICATIONS))).count()
        recent = self.db.query(KnowledgeAnalyticsEvent).order_by(KnowledgeAnalyticsEvent.created_at.desc()).limit(20).all()
        return {"spaces": spaces, "collections": collections, "documents": documents, "events": events, "by_status": by_status, "sensitive_documents": sensitive, "recent_events": [
            {"event_type": e.event_type, "resource_type": e.resource_type, "resource_key": e.resource_key, "actor": e.actor, "query": e.query, "result_count": e.result_count, "created_at": str(e.created_at)} for e in recent
        ]}

    def search_metadata(self, payload: KnowledgeSearchRequest, claims: dict | None = None):
        started = time.time()
        q = self._visible_document_query(claims).filter(KnowledgeDocument.status == "approved")
        if payload.space_key: q = q.filter(KnowledgeDocument.space_key == payload.space_key)
        if payload.collection_key: q = q.filter(KnowledgeDocument.collection_key == payload.collection_key)
        like = f"%{payload.query}%"
        rows = q.filter((KnowledgeDocument.filename.ilike(like)) | (KnowledgeDocument.title.ilike(like)) | (KnowledgeDocument.metadata_json.ilike(like)) | (KnowledgeDocument.tags_json.ilike(like))).limit(payload.limit).all()
        latency = int((time.time() - started) * 1000)
        self.log("metadata_search", "search", payload.space_key or "all", query=payload.query, result_count=len(rows), latency_ms=latency)
        return {"query": payload.query, "latency_ms": latency, "results": rows}
