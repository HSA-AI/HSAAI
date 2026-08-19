
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field

SUPPORTED_MODEL_FAMILIES = ["Llama 3", "Llama 3.1", "Llama 3.2", "Qwen", "Qwen2.5", "Mistral", "Gemma", "Phi", "DeepSeek"]

class TrainingMethod(str, Enum):
    lora = "LoRA"
    qlora = "QLoRA"
    sft = "SFT"

class JobStatus(str, Enum):
    pending = "Pending"
    preparing = "Preparing"
    training = "Training"
    validating = "Validating"
    saving = "Saving"
    deploying = "Deploying"
    completed = "Completed"
    failed = "Failed"
    cancelled = "Cancelled"
    paused = "Paused"

class HyperParameters(BaseModel):
    epochs: int = Field(default=3, ge=1)
    learning_rate: float = Field(default=2e-4, gt=0)
    batch_size: int = Field(default=1, ge=1)
    gradient_accumulation: int = Field(default=4, ge=1)
    warmup_steps: int = Field(default=50, ge=0)
    weight_decay: float = Field(default=0.0, ge=0)
    max_sequence_length: int = Field(default=2048, ge=128)
    lora_rank: int = Field(default=16, ge=1)
    lora_alpha: int = Field(default=32, ge=1)
    lora_dropout: float = Field(default=0.05, ge=0, le=1)

class ComputeResources(BaseModel):
    gpu_device: str = "auto"
    cpu_limit: Optional[str] = None
    ram_limit: Optional[str] = None
    vram_limit: Optional[str] = None
    multi_gpu: bool = False

class TrainingJobCreate(BaseModel):
    training_name: str
    description: Optional[str] = None
    base_model: str
    dataset_id: Optional[int] = None
    dataset_path: Optional[str] = None
    method: TrainingMethod
    hyperparameters: HyperParameters = Field(default_factory=HyperParameters)
    compute: ComputeResources = Field(default_factory=ComputeResources)
    output_model_name: Optional[str] = None

class TrainingJobOut(BaseModel):
    id: int
    training_name: str
    description: Optional[str] = None
    base_model: str
    dataset_id: Optional[int] = None
    dataset_path: Optional[str] = None
    method: str
    status: str
    gpu_device: Optional[str] = None
    created_by: str
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    config: dict[str, Any] = {}
    output_dir: Optional[str] = None
    class Config:
        from_attributes = True

class DatasetCreate(BaseModel):
    name: str
    version: str = "v1"
    format: str
    path: str
    created_by: str = "system"

class DatasetOut(BaseModel):
    id: int
    name: str
    version: str
    format: str
    path: str
    size_bytes: int
    records_count: int
    tokens_count: int
    validation_status: str
    statistics: dict[str, Any]
    created_by: str
    created_at: datetime
    class Config:
        from_attributes = True

class MetricPoint(BaseModel):
    step: int
    epoch: float | None = None
    loss: float | None = None
    eval_loss: float | None = None
    learning_rate: float | None = None
    eta_seconds: float | None = None
    tokens_processed: int | None = None
    gpu_usage: float | None = None
    vram_usage: float | None = None

class DeployRequest(BaseModel):
    target: str = Field(pattern="^(ollama|vllm)$")
    endpoint_url: Optional[str] = None
    model_name: Optional[str] = None
    config: dict[str, Any] = Field(default_factory=dict)
