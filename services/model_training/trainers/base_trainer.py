from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Callable


MetricCallback = Callable[[dict[str, Any]], None]


class TrainingCancelled(Exception):
    """Raised when a training job receives a cancellation request."""


class BaseEnterpriseTrainer(ABC):
    """
    Common base class for SFT / LoRA / QLoRA trainers.

    Responsibilities:
    - Create the artifact directory.
    - Check cancellation requests.
    - Persist training metadata.
    - Emit metrics to the worker.
    """

    def __init__(
        self,
        job_id: int,
        config: dict[str, Any],
        output_dir: str,
        emit: MetricCallback | None = None,
    ) -> None:
        self.job_id = job_id
        self.config = config or {}

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.emit = emit or (lambda payload: None)

        self.cancel_file = self.output_dir / ".cancel"

    def ensure_not_cancelled(self) -> None:
        """
        Stop training when the worker detects a cancellation marker.
        """
        if self.cancel_file.exists():
            raise TrainingCancelled(
                f"Training job {self.job_id} cancelled"
            )

    def write_metadata(
        self,
        payload: dict[str, Any],
    ) -> None:
        """
        Persist metadata atomically enough for normal training usage.
        """
        metadata_path = self.output_dir / "training_metadata.json"
        temporary_path = self.output_dir / "training_metadata.json.tmp"

        temporary_path.write_text(
            json.dumps(
                payload,
                indent=2,
                ensure_ascii=False,
                default=str,
            ),
            encoding="utf-8",
        )

        temporary_path.replace(metadata_path)

    def emit_metric(
        self,
        payload: dict[str, Any],
    ) -> None:
        """
        Centralized metric emission.
        """
        self.ensure_not_cancelled()
        self.emit(payload)

    @abstractmethod
    def run(self) -> dict[str, Any]:
        """
        Concrete trainers must implement the real training loop.

        Expected result:

        {
            "artifact_path": "...",
            "metrics": {...}
        }
        """
        raise NotImplementedError


class HFProgressCallback:
    """
    HuggingFace Trainer callback.

    Sends training metrics to the model-training worker and
    checks cancellation before continuing.
    """

    def __init__(
        self,
        emit: MetricCallback,
        cancel_check: Callable[[], None],
    ) -> None:
        self.emit = emit
        self.cancel_check = cancel_check

    def on_log(
        self,
        args,
        state,
        control,
        logs=None,
        **kwargs,
    ):
        self.cancel_check()

        logs = logs or {}

        epoch = getattr(state, "epoch", None)
        global_step = getattr(state, "global_step", 0)

        payload = {
            "step": int(global_step or 0),
            "epoch": float(epoch or 0),
            "loss": logs.get("loss"),
            "eval_loss": logs.get("eval_loss"),
            "learning_rate": logs.get("learning_rate"),
            "tokens_processed": logs.get("total_flos"),
        }

        self.emit(payload)

        return control

    def on_step_begin(
        self,
        args,
        state,
        control,
        **kwargs,
    ):
        self.cancel_check()
        return control

    def on_epoch_begin(
        self,
        args,
        state,
        control,
        **kwargs,
    ):
        self.cancel_check()
        return control

    def on_train_begin(
        self,
        args,
        state,
        control,
        **kwargs,
    ):
        self.cancel_check()
        return control
