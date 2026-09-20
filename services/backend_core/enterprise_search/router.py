
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from backend_core.security.rbac import require_permission
from .service import service

# FIX FIX-MEDIUM-QUALITY (Issue 5): import canonical SearchRequest base class.
import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), '..', '..', '..', '..', 'packages'))
try:
    from common.schemas.search import SearchRequest as _CanonicalSearchRequest
except ImportError:  # fallback: minimal base so the module still loads.
    class _CanonicalSearchRequest(BaseModel):  # type: ignore[no-redef]
        query: str

class SearchRequest(_CanonicalSearchRequest):
    """FIX FIX-MEDIUM-QUALITY (Issue 5): subclasses canonical SearchRequest
    and adds enterprise-search filter fields (department/classification/space_id)."""
    department: str | None = None
    classification: str | None = None
    space_id: str | None = None

router = APIRouter(prefix='/v1/enterprise-search', tags=['Enterprise Search 2.0'])

@router.post('/hybrid', dependencies=[Depends(require_permission('knowledge:read'))])
def hybrid_search(payload: SearchRequest):
    filters = {k:v for k,v in payload.model_dump().items() if k != 'query' and v}
    return service.search(payload.query, filters)

@router.get('/capabilities', dependencies=[Depends(require_permission('knowledge:read'))])
def capabilities():
    return {'capabilities':['bm25','semantic_vector','hybrid_merge','metadata_filters','department_filters','cross_space_search','reranking','search_analytics'], 'external_ai_required': False}
