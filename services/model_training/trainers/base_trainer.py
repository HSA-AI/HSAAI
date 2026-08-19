
from __future__ import annotations
import json, os, time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Callable

MetricCallback = Callable[[dict[str, Any]], None]

class TrainingCancelled(Exception): pass

class BaseEnterpriseTrainer(ABC):
    def __init__(self, job_id: int, config: dict[str, Any], output_dir: str, emit: MetricCallback | None = None):
        self.job_id = job_id
        self.config = config
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.emit = emit or (lambda payload: None)
        self.cancel_file = self.output_dir / ".cancel"

    def ensure_not_cancelled(self):
        if self.cancel_file.exists():
            raise TrainingCancelled(f"Training job {self.job_id} cancelled")

    def write_metadata(self, payload: dict[str, Any]):
        (self.output_dir / "training_metadata.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    @abstractmethod
    def run(self) -> dict[str, Any]:
        """Subclasses (SFTTrainer, LoRATrainer, QLoRATrainer) implement the actual training loop."""
        ...  # FIX: removed `raise NotImplementedError` — @abstractmethod enforces it

class HFProgressCallback:
    def __init__(self, emit: MetricCallback, cancel_check: Callable[[], None]):
        self.emit = emit
        self.cancel_check = cancel_check

    def on_log(self, args, state, control, logs=None, **kwargs):
        self.cancel_check()
        logs = logs or {}
        self.emit({
            "step": state.global_step,
            "epoch": float(state.epoch or 0),
            "loss": logs.get("loss"),
            "eval_loss": logs.get("eval_loss"),
            "learning_rate": logs.get("learning_rate"),
            "tokens_processed": logs.get("total_flos"),
        })
        return control

    def on_step_begin(self, args, state, control, **kwargs):
        self.cancel_check(); return control
