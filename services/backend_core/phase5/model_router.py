
from __future__ import annotations
import os, re, time
from .schemas import ModelRouteRequest

LOCAL_MODELS = [m.strip() for m in os.getenv("LOCAL_LLM_MODELS", "qwen2.5:7b-instruct,llama3,mistral").split(",") if m.strip()]
DEFAULT_MODEL = os.getenv("LOCAL_LLM_MODEL", LOCAL_MODELS[0] if LOCAL_MODELS else "qwen2.5:7b-instruct")

RULES = [
    ("restricted", "qwen2.5:7b-instruct", "restricted data must remain on the approved local instruction model"),
    ("high", "qwen2.5:7b-instruct", "high-sensitivity enterprise reasoning"),
    ("medium", DEFAULT_MODEL, "balanced enterprise workload"),
    ("low", "llama3", "general low-risk assistant task"),
]

def route_model(req: ModelRouteRequest) -> dict:
    started = time.time()
    task = req.task.lower()
    chosen = DEFAULT_MODEL
    reason = "default local model"
    for sensitivity, model, why in RULES:
        if req.sensitivity == sensitivity:
            chosen, reason = model, why
            break
    if re.search(r"excel|جدول|xlsx|تحليل مالي|finance|sap", task):
        chosen, reason = "qwen2.5:7b-instruct", "structured/Arabic enterprise analysis"
    if re.search(r"تلخيص|summary|policy|سياسة", task) and req.sensitivity in {"low", "medium"}:
        chosen, reason = DEFAULT_MODEL, "summarization with local model"
    if req.require_local_only and chosen not in LOCAL_MODELS and chosen != DEFAULT_MODEL:
        chosen, reason = DEFAULT_MODEL, "fallback because only approved local models are allowed"
    return {
        "model": chosen,
        "provider": "ollama",
        "local_only": True,
        "reason": reason,
        "policy": "no external model routing in HSAAI internal-only mode",
        "available_models": LOCAL_MODELS,
        "elapsed_ms": int((time.time() - started) * 1000),
    }
