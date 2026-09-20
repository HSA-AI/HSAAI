
from __future__ import annotations
from datetime import datetime
from pathlib import Path
from services.model_training.config import settings
from services.model_training.db.database import SessionLocal
from services.model_training.db.models import TrainingJob, TrainingLog, GPUMetric
from services.model_training.monitoring.gpu_monitor import read_gpu_metrics
from services.model_training.services.experiment_service import ExperimentService
from services.model_training.services.model_registry_service import ModelRegistryService
from services.model_training.trainers.lora_trainer import LoraTrainer
from services.model_training.trainers.qlora_trainer import QLoraTrainer
from services.model_training.trainers.sft_trainer import SFTEnterpriseTrainer

TRAINERS = {'LoRA': LoraTrainer, 'QLoRA': QLoraTrainer, 'SFT': SFTEnterpriseTrainer}

def run_training_job(job_id: int):
    db = SessionLocal()
    try:
        job = db.get(TrainingJob, job_id)
        if not job: raise ValueError(f'Job {job_id} not found')
        job.status = 'Training'
        out = Path(settings.artifacts_root) / 'trained_models' / f'job_{job.id}'
        out.mkdir(parents=True, exist_ok=True)
        job.output_dir = str(out)
        db.add(TrainingLog(job_id=job.id, level='INFO', message='Starting real training', payload={'method': job.method}))
        db.commit()
        exp = ExperimentService(db)
        def emit(payload: dict):
            for g in read_gpu_metrics():
                db.add(GPUMetric(job_id=job.id, **g))
                payload.setdefault('gpu', []).append(g)
            exp.log_metric(job.id, payload)
        trainer_cls = TRAINERS.get(job.method)
        if not trainer_cls: raise ValueError(f'Unsupported method: {job.method}')
        config = dict(job.config or {})
        if not config.get('dataset_path'):
            raise ValueError('dataset_path is required for real training')
        result = trainer_cls(job.id, config, str(out), emit).run()
        job.status = 'Saving'; db.commit()
        model = ModelRegistryService(db).register_from_job(job, result['artifact_path'], metrics=exp.metrics(job.id))
        job.status = 'Completed'; job.finished_at = datetime.utcnow()
        db.add(TrainingLog(job_id=job.id, level='INFO', message='Training completed', payload={'model_id': model.id, **result}))
        db.commit()
        return {'job_id': job.id, 'model_id': model.id, **result}
    except Exception as exc:
        job = db.get(TrainingJob, job_id)
        if job:
            job.status = 'Failed'; job.finished_at = datetime.utcnow()
            db.add(TrainingLog(job_id=job_id, level='ERROR', message=str(exc), payload={'type': type(exc).__name__}))
            db.commit()
        raise
    finally:
        db.close()
