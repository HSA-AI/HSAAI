"""
HSAAI Model Training — Training Routes
SECURITY FIX v2.1 (P0): All mutating endpoints now require service auth.
Previously, anyone with network access could launch GPU training jobs,
pause/resume/cancel them, delete them, or deploy models — a critical
privilege escalation. See Discovery Report C-3.
"""
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
import os, sys

# Service auth
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'packages'))
try:
    from common.auth.service_auth import verify_service_auth as _auth_dep
    _AUTH_AVAILABLE = True
except ImportError as _e:
    _AUTH_AVAILABLE = False
    async def _auth_dep():  # type: ignore
        raise HTTPException(status_code=503, detail="Authentication module unavailable.")

from services.model_training.db.database import get_db
from services.model_training.schemas import TrainingJobCreate, TrainingJobOut, DeployRequest
from services.model_training.services.training_service import TrainingService
from services.model_training.services.experiment_service import ExperimentService
from services.model_training.services.deployment_service import DeploymentService

router = APIRouter(prefix='/api/training', tags=['training'])

@router.get('/capabilities')
def capabilities():
    # Public capability discovery — no auth needed
    return {
        'execution_mode': 'real',
        'supports': ['LoRA', 'QLoRA', 'SFT', 'datasets', 'experiments', 'model-registry', 'gpu-monitoring'],
        'backend': 'FastAPI + Redis/RQ + PostgreSQL + HuggingFace/PEFT/TRL',
        'production_guard': 'real-training-service-required',
        'auth_required': True,
    }


# ---- Job management (all require auth) ----

@router.post('/jobs', response_model=TrainingJobOut)
async def create_training_job(payload: TrainingJobCreate, db: Session = Depends(get_db), claims: dict = Depends(_auth_dep)):
    try: return TrainingService(db).create_job(payload)
    except Exception as exc: raise HTTPException(status_code=400, detail=str(exc))

@router.get('/jobs', response_model=list[TrainingJobOut])
async def list_training_jobs(db: Session = Depends(get_db), claims: dict = Depends(_auth_dep)):
    return TrainingService(db).list_jobs()

@router.get('/jobs/{job_id}', response_model=TrainingJobOut)
async def get_training_job(job_id: int, db: Session = Depends(get_db), claims: dict = Depends(_auth_dep)):
    job = TrainingService(db).get_job(job_id)
    if not job: raise HTTPException(status_code=404, detail='Job not found')
    return job

@router.delete('/jobs/{job_id}')
async def delete_training_job(job_id: int, db: Session = Depends(get_db), claims: dict = Depends(_auth_dep)):
    job = TrainingService(db).get_job(job_id)
    if not job: raise HTTPException(status_code=404, detail='Job not found')
    db.delete(job); db.commit(); return {'deleted': True}

@router.post('/jobs/{job_id}/start')
async def start_job(job_id: int, db: Session = Depends(get_db), claims: dict = Depends(_auth_dep)):
    try: return {'rq_job_id': TrainingService(db).enqueue(job_id)}
    except Exception as exc: raise HTTPException(status_code=400, detail=str(exc))

@router.post('/jobs/{job_id}/pause')
async def pause_job(job_id: int, db: Session = Depends(get_db), claims: dict = Depends(_auth_dep)):
    return TrainingService(db).pause(job_id)

@router.post('/jobs/{job_id}/resume')
async def resume_job(job_id: int, db: Session = Depends(get_db), claims: dict = Depends(_auth_dep)):
    return {'rq_job_id': TrainingService(db).resume(job_id)}

@router.post('/jobs/{job_id}/cancel')
async def cancel_job(job_id: int, db: Session = Depends(get_db), claims: dict = Depends(_auth_dep)):
    return TrainingService(db).cancel(job_id)

@router.post('/jobs/{job_id}/retry')
async def retry_job(job_id: int, db: Session = Depends(get_db), claims: dict = Depends(_auth_dep)):
    return {'rq_job_id': TrainingService(db).retry(job_id)}

@router.post('/jobs/{job_id}/deploy')
async def deploy_job(job_id: int, payload: DeployRequest, db: Session = Depends(get_db), claims: dict = Depends(_auth_dep)):
    from services.model_training.db.models import TrainedModel
    model = db.query(TrainedModel).filter(TrainedModel.version == f'v{job_id}').first()
    if not model: raise HTTPException(status_code=404, detail='Trained model not found for this job')
    return DeploymentService(db).deploy(model.id, payload.target, payload.endpoint_url, payload.config)

@router.get('/jobs/{job_id}/logs')
async def job_logs(job_id: int, db: Session = Depends(get_db), claims: dict = Depends(_auth_dep)):
    return ExperimentService(db).logs(job_id)

@router.get('/jobs/{job_id}/metrics')
async def job_metrics(job_id: int, db: Session = Depends(get_db), claims: dict = Depends(_auth_dep)):
    return ExperimentService(db).metrics(job_id)
