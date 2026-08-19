import type { LocalModel, LocalModelInput } from "./local-model.types";

const models = new Map<string, LocalModel>();
const seed: LocalModel[] = [
  { id: "model_qwen_internal", name: "hsaai-qwen-enterprise-v1", version: "0.1-placeholder", size: "7B", format: "HF", location: "/storage/local_models/qwen-enterprise", provider: "provider_vllm_placeholder", status: "registered", createdAt: "2026-06-05T22:00:00.000Z", updatedAt: "2026-06-05T22:00:00.000Z" },
  { id: "model_gguf_fast", name: "mistral-fast-gguf", version: "0.1-placeholder", size: "7B-Q4", format: "GGUF", location: "/storage/local_models/mistral-q4.gguf", provider: "provider_ollama_internal", status: "disabled", createdAt: "2026-06-05T22:00:00.000Z", updatedAt: "2026-06-05T22:00:00.000Z" },
];
for (const model of seed) models.set(model.id, model);

export class LocalModelService {
  static list(): LocalModel[] { return Array.from(models.values()); }
  static get(id: string): LocalModel | null { return models.get(id) ?? null; }
  static register(input: LocalModelInput): LocalModel {
    const now = new Date().toISOString();
    const model: LocalModel = { id: `model_${Date.now()}`, status: "registered", createdAt: now, updatedAt: now, ...input };
    models.set(model.id, model);
    return model;
  }
  /**
   * Toggle the status of a local model between "active" and "disabled".
   *
   * FIX: Added optional `enabled` parameter to allow explicit enable/disable.
   * Previously the method only accepted one argument (id) and toggled.
   * Now it supports both toggle mode (1 arg) and explicit mode (2 args).
   */
  static toggle(id: string, enabled?: boolean): LocalModel | null {
    const model = models.get(id);
    if (!model) return null;
    const next: LocalModel["status"] = enabled !== undefined
      ? (enabled ? "active" : "disabled")
      : (model.status === "active" ? "disabled" : "active");
    const updated = { ...model, status: next, updatedAt: new Date().toISOString() };
    models.set(id, updated);
    return updated;
  }
  /**
   * Remove a local model from the registry.
   *
   * FIX: This method was missing, causing a TypeScript error in the
   * [modelId]/route.ts DELETE handler.
   */
  static remove(id: string): boolean {
    return models.delete(id);
  }
}

export function normalizeLocalModelInput(body: Partial<LocalModelInput>): LocalModelInput {
  return {
    name: body.name || "hsaai-local-model-placeholder",
    version: body.version || "0.1",
    size: body.size || "unknown",
    format: body.format || "Other",
    location: body.location || "/storage/local_models/model-placeholder",
    provider: body.provider || "provider_ollama_internal",
  };
}
