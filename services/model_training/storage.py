from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable
from schemas import TrainingJob


class TrainingJobStore:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def job_dir(self, job_id: str) -> Path:
        return self.root / job_id

    def job_path(self, job_id: str) -> Path:
        return self.job_dir(job_id) / "job.json"

    def log_path(self, job_id: str) -> Path:
        return self.job_dir(job_id) / "train.log"

    def save(self, job: TrainingJob) -> TrainingJob:
        directory = self.job_dir(job.id)
        directory.mkdir(parents=True, exist_ok=True)
        self.job_path(job.id).write_text(job.model_dump_json(indent=2), encoding="utf-8")
        return job

    def get(self, job_id: str) -> TrainingJob | None:
        path = self.job_path(job_id)
        if not path.exists():
            return None
        return TrainingJob.model_validate(json.loads(path.read_text(encoding="utf-8")))

    def list(self) -> list[TrainingJob]:
        jobs: list[TrainingJob] = []
        for path in self.root.glob("*/job.json"):
            try:
                jobs.append(TrainingJob.model_validate(json.loads(path.read_text(encoding="utf-8"))))
            except Exception:
                continue
        return sorted(jobs, key=lambda item: item.created_at, reverse=True)

    def append_log(self, job_id: str, line: str) -> None:
        directory = self.job_dir(job_id)
        directory.mkdir(parents=True, exist_ok=True)
        with self.log_path(job_id).open("a", encoding="utf-8") as fh:
            fh.write(line.rstrip() + "\n")

    def logs(self, job_id: str) -> list[str]:
        path = self.log_path(job_id)
        if not path.exists():
            return []
        return path.read_text(encoding="utf-8", errors="replace").splitlines()[-500:]
