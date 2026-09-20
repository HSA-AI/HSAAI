
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from services.model_training.db.database import get_db
from services.model_training.db.models import TrainedModel, Checkpoint, Deployment
from services.model_training.schemas import SUPPORTED_MODEL_FAMILIES

router = APIRouter(prefix='/api/training/models', tags=['model-registry'])

@router.get('/supported')
def supported_models(): return {'families': SUPPORTED_MODEL_FAMILIES}

@router.get('')
def list_trained_models(db: Session = Depends(get_db)):
    return db.query(TrainedModel).order_by(TrainedModel.created_at.desc()).all()

@router.get('/{model_id}')
def get_model(model_id: int, db: Session = Depends(get_db)):
    model = db.get(TrainedModel, model_id)
    if not model: raise HTTPException(status_code=404, detail='Model not found')
    return model

@router.get('/{model_id}/deployments')
def model_deployments(model_id: int, db: Session = Depends(get_db)):
    return db.query(Deployment).filter(Deployment.model_id == model_id).order_by(Deployment.created_at.desc()).all()

@router.get('/checkpoints/{job_id}')
def checkpoints(job_id: int, db: Session = Depends(get_db)):
    return db.query(Checkpoint).filter(Checkpoint.job_id == job_id).order_by(Checkpoint.created_at.desc()).all()

@router.delete('/checkpoints/{checkpoint_id}')
def delete_checkpoint(checkpoint_id: int, db: Session = Depends(get_db)):
    ckpt = db.get(Checkpoint, checkpoint_id)
    if not ckpt: raise HTTPException(status_code=404, detail='Checkpoint not found')
    db.delete(ckpt); db.commit(); return {'deleted': True}
