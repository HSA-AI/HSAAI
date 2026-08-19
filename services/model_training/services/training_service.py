
from __future__ import annotations
import os
from datetime import datetime
from pathlib import Path
from rq import Queue
from redis import Redis
from sqlalchemy.orm import Session
from services.model_training.config import settings
from services.model_training.db.models import TrainingJob, TrainingLog
from services.model_training.schemas import TrainingJobCreate, JobStatus

class TrainingService:
    def __init__(self, db: Session): self.db = db
    def create_job(self, payload: TrainingJobCreate, created_by: str = 'system') -> TrainingJob:
        config = payload.model_dump(mode='json')
        job = TrainingJob(training_name=payload.training_name, description=payload.description, base_model=payload.base_model,
                          dataset_id=payload.dataset_id, dataset_path=payload.dataset_path, method=payload.method.value,
                          status=JobStatus.pending.value, gpu_device=payload.compute.gpu_device, cpu_limit=payload.compute.cpu_limit,
                          ram_limit=payload.compute.ram_limit, vram_limit=payload.compute.vram_limit, created_by=created_by, config=config)
        self.db.add(job); self.db.commit(); self.db.refresh(job); return job
    def list_jobs(self):
        return self.db.query(TrainingJob).order_by(TrainingJob.created_at.desc()).all()
    def get_job(self, job_id: int):
        return self.db.get(TrainingJob, job_id)
    def enqueue(self, job_id: int):
        job = self.get_job(job_id)
        if not job: raise ValueError('Job not found')
        redis = Redis.from_url(settings.redis_url)
        q = Queue(settings.default_queue, connection=redis)
        rq_job = q.enqueue('services.model_training.workers.training_worker.run_training_job', job_id, job_timeout='7d')
        job.status = JobStatus.preparing.value; job.started_at = datetime.utcnow(); job.config = {**(job.config or {}), 'rq_job_id': rq_job.id}
        self.db.add(TrainingLog(job_id=job_id, level='INFO', message=f'Queued training job {rq_job.id}', payload={'rq_job_id': rq_job.id}))
        self.db.commit(); return rq_job.id
    def cancel(self, job_id: int):
        job = self.get_job(job_id)
        if not job: raise ValueError('Job not found')
        if job.output_dir:
            Path(job.output_dir).mkdir(parents=True, exist_ok=True); (Path(job.output_dir)/'.cancel').write_text('cancelled')
        job.status = JobStatus.cancelled.value; job.finished_at = datetime.utcnow()
        self.db.add(TrainingLog(job_id=job_id, level='WARN', message='Cancel requested', payload={}))
        self.db.commit(); return job
    def pause(self, job_id: int):
        job = self.get_job(job_id);
        if not job: raise ValueError('Job not found')
        job.status = JobStatus.paused.value; self.db.commit(); return job
    def resume(self, job_id: int):
        return self.enqueue(job_id)
    def retry(self, job_id: int):
        return self.enqueue(job_id)
