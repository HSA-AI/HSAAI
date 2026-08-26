from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

CONFIG_PATH = Path(__file__).with_name("models.local.json")


def load_model_config() -> dict[str, Any]:
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def normalize(text: str | None) -> str:
    return (text or "").strip().lower()


def _external_allowed(sensitivity: str | None) -> bool:
    if os.getenv("INTERNAL_ONLY_MODE", "true").lower() == "true":
        return False
    if os.getenv("ALLOW_EXTERNAL_AI", "false").lower() != "true":
        return False
    return normalize(sensitivity) in {"public", "low", "non_sensitive", "non-sensitive"}


def route_model(prompt: str, task: str | None = None, sensitivity: str | None = None, requested_model: str | None = None) -> dict[str, Any]:
    """Hybrid enterprise model router.

    Default route is always local Ollama. External providers are returned only when:
    - INTERNAL_ONLY_MODE=false
    - ALLOW_EXTERNAL_AI=true
    - sensitivity is public/low/non_sensitive
    - the routing rule explicitly permits external usage
    """
    cfg = load_model_config()
    models = cfg.get("models", {})
    external_models = cfg.get("external_models", {})

    if requested_model:
        for key, meta in models.items():
            if requested_model in {key, meta.get("name")}:
                return {"provider": "ollama", "model_key": key, "model": meta["name"], "reason": "manual-local-override", "local_only": True}
        for key, meta in external_models.items():
            if requested_model in {key, meta.get("name")} and _external_allowed(sensitivity):
                return {"provider": meta.get("provider", key), "model_key": key, "model": meta["name"], "reason": "manual-external-override", "local_only": False}
        return {"provider": "ollama", "model_key": "manual", "model": requested_model, "reason": "manual-local-override", "local_only": True}

    searchable = f"{normalize(task)} {normalize(prompt)}"
    sensitivity_value = normalize(sensitivity)

    for rule in cfg.get("routing_rules", []):
        when = rule.get("when", {})
        contains_any = [normalize(x) for x in when.get("contains_any", [])]
        sensitivity_any = [normalize(x) for x in when.get("sensitivity_any", [])]
        matched = (contains_any and any(token in searchable for token in contains_any)) or (sensitivity_any and sensitivity_value in sensitivity_any)
        if matched:
            key = rule["model_key"]
            return {"provider": "ollama", "model_key": key, "model": models[key]["name"], "reason": "local-routing-rule", "local_only": True}

    for rule in cfg.get("external_routing_rules", []):
        when = rule.get("when", {})
        contains_any = [normalize(x) for x in when.get("contains_any", [])]
        matched = contains_any and any(token in searchable for token in contains_any)
        if matched and _external_allowed(sensitivity):
            key = rule["model_key"]
            meta = external_models[key]
            return {"provider": meta.get("provider", key), "model_key": key, "model": meta["name"], "reason": "optional-external-routing-rule", "local_only": False}

    key = cfg.get("default_key") or ("arabic" if "arabic" in models else "general" if "general" in models else next(iter(models.keys())))
    return {"provider": "ollama", "model_key": key, "model": models[key]["name"], "reason": "default-local-route", "local_only": True}
