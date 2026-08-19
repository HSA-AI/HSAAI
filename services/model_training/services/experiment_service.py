
from sqlalchemy.orm import Session
from services.model_training.db.models import Experiment, TrainingLog, GPUMetric

class ExperimentService:
    def __init__(self, db: Session): self.db = db
    def log_metric(self, job_id: int, payload: dict):
        exp = self.db.query(Experiment).filter(Experiment.job_id == job_id).first()
        if not exp:
            exp = Experiment(job_id=job_id, hyperparameters={}, metrics={}); self.db.add(exp)
        metrics = dict(exp.metrics or {}); metrics.setdefault('points', []).append(payload); exp.metrics = metrics
        self.db.add(TrainingLog(job_id=job_id, level='METRIC', message='training_metric', payload=payload))
        self.db.commit()
    def logs(self, job_id: int):
        return self.db.query(TrainingLog).filter(TrainingLog.job_id == job_id).order_by(TrainingLog.created_at.asc()).all()
    def metrics(self, job_id: int):
        exp = self.db.query(Experiment).filter(Experiment.job_id == job_id).first(); return (exp.metrics if exp else {'points': []})
