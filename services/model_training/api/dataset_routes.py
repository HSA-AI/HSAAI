"""
HSAAI Model Training — Dataset Routes (v2.0 hardened)

SECURITY FIX v2.0:
  - Path traversal protection in upload_dataset (was Critical).
  - Validates name/version against strict allowlist.
  - Sanitizes filename via secure_filename().
  - Validates extension against allowlist.
  - Enforces max file size.
  - Final safety check via resolve().relative_to().
  - Optional: requires authentication (when auth_service is wired).
"""
import re
import os
import sys
from pathlib import Path
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'packages'))
try:
    from common.auth.service_auth import verify_service_auth as _auth_dep
    _AUTH_AVAILABLE = True
except ImportError as _e:
    _AUTH_AVAILABLE = False
    _AUTH_LOAD_ERROR = str(_e)
    async def _auth_dep():  # type: ignore
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Authentication module unavailable. Service cannot accept requests.")

from services.model_training.config import settings
from services.model_training.db.database import get_db
from services.model_training.schemas import DatasetCreate, DatasetOut
from services.model_training.services.dataset_service import DatasetService

router = APIRouter(prefix='/api/training/datasets', tags=['datasets'])

# Strict validation patterns
ALLOWED_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')
ALLOWED_EXTENSIONS = {'.jsonl', '.json', '.csv', '.txt', '.parquet'}
MAX_DATASET_SIZE = 500 * 1024 * 1024  # 500MB


def secure_filename(filename: str) -> str:
    """Sanitize filename: keep only alphanumeric, dash, underscore, dot."""
    if not filename:
        return "dataset.jsonl"
    # Take only the basename (strip any path components)
    name = Path(filename).name
    # Allow only safe characters
    safe = re.sub(r'[^a-zA-Z0-9._-]', '_', name)
    if safe != name or '..' in safe or safe.startswith('.'):
        # If anything changed, use a generic name (preserves extension)
        ext = Path(name).suffix.lower()
        if ext in ALLOWED_EXTENSIONS:
            safe = f"dataset{ext}"
        else:
            safe = "dataset.jsonl"
    return safe or "dataset.jsonl"


@router.post('', response_model=DatasetOut)
def register_dataset(payload: DatasetCreate, db: Session = Depends(get_db), claims: dict = Depends(_auth_dep)):
    try:
        return DatasetService(db).create(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post('/upload', response_model=DatasetOut)
def upload_dataset(
    name: str,
    version: str = 'v1',
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    claims: dict = Depends(_auth_dep),
):
    # SECURITY v2.0: Validate name and version against strict allowlist
    if not ALLOWED_NAME_PATTERN.match(name):
        raise HTTPException(
            status_code=400,
            detail="Invalid dataset name. Use alphanumeric, dash, underscore only (no slashes, dots, or special chars).",
        )
    if not ALLOWED_NAME_PATTERN.match(version):
        raise HTTPException(
            status_code=400,
            detail="Invalid version. Use alphanumeric, dash, underscore only.",
        )

    # Sanitize filename
    safe_filename = secure_filename(file.filename or 'dataset.jsonl')

    # Validate extension
    ext = Path(safe_filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Extension '{ext}' not allowed. Use one of: {sorted(ALLOWED_EXTENSIONS)}",
        )

    # Read content and validate size
    content = file.file.read()
    if len(content) > MAX_DATASET_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"Dataset too large. Max {MAX_DATASET_SIZE // 1024 // 1024}MB.",
        )

    # Safe path construction
    dest_dir = Path(settings.artifacts_root) / 'datasets' / name / version
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / safe_filename

    # FINAL SAFETY CHECK: ensure dest is within dest_dir (prevents path traversal)
    try:
        dest.resolve().relative_to(dest_dir.resolve())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Path traversal detected. Filename rejected.",
        )

    # Write the file
    with dest.open('wb') as f:
        f.write(content)

    return DatasetService(db).create(
        DatasetCreate(name=name, version=version, format=ext.lstrip('.'), path=str(dest))
    )


@router.get('', response_model=list[DatasetOut])
def list_datasets(db: Session = Depends(get_db), claims: dict = Depends(_auth_dep)):
    return DatasetService(db).list()


@router.get('/{dataset_id}/preview')
def preview_dataset(dataset_id: int, db: Session = Depends(get_db), claims: dict = Depends(_auth_dep)):
    from services.model_training.db.models import Dataset
    ds = db.get(Dataset, dataset_id)
    if not ds:
        raise HTTPException(status_code=404, detail='Dataset not found')
    return ds.statistics
