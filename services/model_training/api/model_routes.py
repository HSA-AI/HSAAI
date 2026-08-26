from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from services.model_training.db.database import get_db, set_tenant_id
from services.model_training.db.models import (
    Checkpoint,
    Deployment,
    TrainedModel,
    TrainingJob,
)
from services.model_training.schemas import SUPPORTED_MODEL_FAMILIES


router = APIRouter(
    prefix="/api/training/models",
    tags=["model-registry"],
)


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def get_auth_dependency():
    """
    Load the project's existing Keycloak authentication dependency lazily.
    """
    from services.auth_service.main import current_user

    return current_user


# ---------------------------------------------------------------------------
# Tenant handling
# ---------------------------------------------------------------------------

def _tenant_from_claims(claims: dict) -> str:
    """
    Get tenant_id only from authenticated claims.
    """
    if not isinstance(claims, dict):
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication claims",
        )

    tenant_id = claims.get("tenant_id")

    if not tenant_id:
        raise HTTPException(
            status_code=403,
            detail="Missing tenant_id in authentication claims",
        )

    return str(tenant_id)


def _set_db_tenant(db: Session, claims: dict) -> str:
    """
    Bind the SQLAlchemy session to the authenticated tenant.
    """
    tenant_id = _tenant_from_claims(claims)
    set_tenant_id(db, tenant_id)
    return tenant_id


# ---------------------------------------------------------------------------
# Supported model families
# ---------------------------------------------------------------------------

@router.get(
    "/supported",
    response_model=None,
)
def supported_models():
    return {
        "families": SUPPORTED_MODEL_FAMILIES,
    }


# ---------------------------------------------------------------------------
# List trained models
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=None,
)
def list_trained_models(
    db: Session = Depends(get_db),
    claims: dict = Depends(get_auth_dependency()),
):
    tenant_id = _set_db_tenant(db, claims)

    return (
        db.query(TrainedModel)
        .filter(
            TrainedModel.tenant_id == tenant_id,
        )
        .order_by(
            TrainedModel.created_at.desc(),
        )
        .all()
    )


# ---------------------------------------------------------------------------
# Get trained model
# ---------------------------------------------------------------------------

@router.get(
    "/{model_id}",
    response_model=None,
)
def get_model(
    model_id: int,
    db: Session = Depends(get_db),
    claims: dict = Depends(get_auth_dependency()),
):
    tenant_id = _set_db_tenant(db, claims)

    model = (
        db.query(TrainedModel)
        .filter(
            TrainedModel.id == model_id,
            TrainedModel.tenant_id == tenant_id,
        )
        .first()
    )

    if model is None:
        raise HTTPException(
            status_code=404,
            detail="Model not found",
        )

    return model


# ---------------------------------------------------------------------------
# Model deployments
# ---------------------------------------------------------------------------

@router.get(
    "/{model_id}/deployments",
    response_model=None,
)
def model_deployments(
    model_id: int,
    db: Session = Depends(get_db),
    claims: dict = Depends(get_auth_dependency()),
):
    tenant_id = _set_db_tenant(db, claims)

    model_exists = (
        db.query(TrainedModel.id)
        .filter(
            TrainedModel.id == model_id,
            TrainedModel.tenant_id == tenant_id,
        )
        .first()
    )

    if model_exists is None:
        raise HTTPException(
            status_code=404,
            detail="Model not found",
        )

    return (
        db.query(Deployment)
        .filter(
            Deployment.model_id == model_id,
            Deployment.tenant_id == tenant_id,
        )
        .order_by(
            Deployment.created_at.desc(),
        )
        .all()
    )


# ---------------------------------------------------------------------------
# Checkpoints for training job
# ---------------------------------------------------------------------------

@router.get(
    "/checkpoints/{job_id}",
    response_model=None,
)
def checkpoints(
    job_id: int,
    db: Session = Depends(get_db),
    claims: dict = Depends(get_auth_dependency()),
):
    tenant_id = _set_db_tenant(db, claims)

    job_exists = (
        db.query(TrainingJob.id)
        .filter(
            TrainingJob.id == job_id,
            TrainingJob.tenant_id == tenant_id,
        )
        .first()
    )

    if job_exists is None:
        raise HTTPException(
            status_code=404,
            detail="Training job not found",
        )

    return (
        db.query(Checkpoint)
        .filter(
            Checkpoint.job_id == job_id,
            Checkpoint.tenant_id == tenant_id,
        )
        .order_by(
            Checkpoint.created_at.desc(),
        )
        .all()
    )


# ---------------------------------------------------------------------------
# Delete checkpoint
# ---------------------------------------------------------------------------

@router.delete(
    "/checkpoints/{checkpoint_id}",
    response_model=None,
)
def delete_checkpoint(
    checkpoint_id: int,
    db: Session = Depends(get_db),
    claims: dict = Depends(get_auth_dependency()),
):
    tenant_id = _set_db_tenant(db, claims)

    checkpoint = (
        db.query(Checkpoint)
        .filter(
            Checkpoint.id == checkpoint_id,
            Checkpoint.tenant_id == tenant_id,
        )
        .first()
    )

    if checkpoint is None:
        raise HTTPException(
            status_code=404,
            detail="Checkpoint not found",
        )

    db.delete(checkpoint)
    db.commit()

    return {
        "deleted": True,
        "checkpoint_id": checkpoint_id,
        "tenant_id": tenant_id,
    }
