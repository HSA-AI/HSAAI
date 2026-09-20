
from __future__ import annotations
import csv, json, os
from pathlib import Path
from sqlalchemy.orm import Session
from services.model_training.db.models import Dataset
from services.model_training.schemas import DatasetCreate

SUPPORTED_FORMATS = {"json", "jsonl", "csv", "txt"}

class DatasetService:
    def __init__(self, db: Session): self.db = db

    def create(self, payload: DatasetCreate) -> Dataset:
        fmt = payload.format.lower().lstrip('.')
        if fmt not in SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported dataset format: {payload.format}")
        stats = self.inspect(Path(payload.path), fmt)
        ds = Dataset(name=payload.name, version=payload.version, format=fmt, path=payload.path,
                     size_bytes=stats["size_bytes"], records_count=stats["records_count"],
                     tokens_count=stats["tokens_count"], validation_status=stats["validation_status"],
                     statistics=stats, created_by=payload.created_by)
        self.db.add(ds); self.db.commit(); self.db.refresh(ds); return ds

    def list(self) -> list[Dataset]:
        return self.db.query(Dataset).order_by(Dataset.created_at.desc()).all()

    def inspect(self, path: Path, fmt: str) -> dict:
        if not path.exists():
            raise FileNotFoundError(str(path))
        size = path.stat().st_size
        records = 0; tokens = 0; sample = []
        with path.open('r', encoding='utf-8', errors='ignore') as f:
            if fmt == 'jsonl':
                for line in f:
                    if line.strip():
                        records += 1; tokens += len(line.split())
                        if len(sample) < 3: sample.append(json.loads(line))
            elif fmt == 'json':
                obj = json.load(f); items = obj if isinstance(obj, list) else [obj]
                records = len(items); tokens = len(json.dumps(obj, ensure_ascii=False).split()); sample = items[:3]
            elif fmt == 'csv':
                reader = csv.DictReader(f)
                for row in reader:
                    records += 1; tokens += len(' '.join(row.values()).split())
                    if len(sample) < 3: sample.append(row)
            else:
                text = f.read(); lines = [x for x in text.splitlines() if x.strip()]
                records = len(lines); tokens = len(text.split()); sample = lines[:3]
        return {"size_bytes": size, "records_count": records, "tokens_count": tokens, "sample": sample,
                "validation_status": "valid" if records > 0 else "invalid"}
