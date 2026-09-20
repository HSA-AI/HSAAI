
from sqlalchemy.orm import Session
from services.model_training.db.models import TrainedModel, TrainingJob

class ModelRegistryService:
    def __init__(self, db: Session): self.db = db
    def register_from_job(self, job: TrainingJob, artifact_path: str, metrics: dict | None = None) -> TrainedModel:
        version = f"v{job.id}"
        model = TrainedModel(model_name=job.config.get('output_model_name') or job.training_name,
                             version=version, base_model=job.base_model, dataset_id=job.dataset_id,
                             method=job.method, metrics=metrics or {}, owner=job.created_by,
                             artifact_path=artifact_path)
        self.db.add(model); self.db.commit(); self.db.refresh(model); return model
    def list(self):
        return self.db.query(TrainedModel).order_by(TrainedModel.created_at.desc()).all()
