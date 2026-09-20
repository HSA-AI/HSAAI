
from __future__ import annotations
import csv, subprocess
from typing import Any

NVIDIA_QUERY = [
    "nvidia-smi",
    "--query-gpu=index,name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw",
    "--format=csv,noheader,nounits",
]

def read_gpu_metrics() -> list[dict[str, Any]]:
    try:
        result = subprocess.run(NVIDIA_QUERY, capture_output=True, text=True, check=True, timeout=5)
    except Exception:
        return []
    rows = csv.reader(result.stdout.strip().splitlines())
    metrics: list[dict[str, Any]] = []
    for row in rows:
        if len(row) < 7:
            continue
        metrics.append({
            "gpu_index": int(row[0].strip()),
            "gpu_name": row[1].strip(),
            "gpu_usage": float(row[2].strip() or 0),
            "vram_usage": float(row[3].strip() or 0),
            "vram_total": float(row[4].strip() or 0),
            "temperature": float(row[5].strip() or 0),
            "power_usage": float(row[6].strip() or 0),
        })
    return metrics
