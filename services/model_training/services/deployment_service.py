
from sqlalchemy.orm import Session
from services.model_training.db.models import Deployment, TrainedModel

class DeploymentService:
    def __init__(self, db: Session): self.db = db
    def deploy(self, model_id: int, target: str, endpoint_url: str | None = None, config: dict | None = None) -> Deployment:
        model = self.db.get(TrainedModel, model_id)
        if not model: raise ValueError('Model not found')
        # Real integration point: call Ollama Modelfile import or vLLM reload endpoint.
        dep = Deployment(model_id=model_id, target=target, endpoint_url=endpoint_url, config=config or {}, status='Pending')
        self.db.add(dep); self.db.commit(); self.db.refresh(dep)
        return dep
