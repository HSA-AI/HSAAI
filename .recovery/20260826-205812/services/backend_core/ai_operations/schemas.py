
from pydantic import BaseModel
from typing import Literal

class RuntimeProvider(BaseModel):
    id: str
    name: str
    type: Literal['ollama','vllm','gpu_server','local']
    endpoint: str
    status: Literal['healthy','degraded','offline'] = 'healthy'
    active_models: int = 0

class ModelDeployment(BaseModel):
    id: str
    model_name: str
    version: str
    provider: str
    status: Literal['running','deploying','failed','stopped']
    latency_ms: int
    requests_per_minute: int

class GpuNode(BaseModel):
    id: str
    name: str
    usage_percent: float
    vram_percent: float
    temperature_c: float
    power_watts: float
