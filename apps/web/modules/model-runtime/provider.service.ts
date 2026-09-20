import { GpuServerAdapter } from "./gpu-server.adapter";
import { LocalModelAdapter } from "./local-model.adapter";
import { OllamaAdapter } from "./ollama.adapter";
import type { RuntimeProviderAdapter } from "./provider.adapter";
import type { ModelProvider, ModelProviderInput, ProviderType } from "./runtime.types";
import { VllmAdapter } from "./vllm.adapter";

const providers = new Map<string, ModelProvider>();

const seed: ModelProvider[] = [
  { id: "provider_ollama_internal", providerType: "Ollama", endpointUrl: "http://local_llm:11434", modelName: "qwen2.5:7b-instruct", contextLength: 8192, status: "active", createdAt: "2026-06-05T22:00:00.000Z", updatedAt: "2026-06-05T22:00:00.000Z" },
  { id: "provider_vllm_placeholder", providerType: "vLLM", endpointUrl: "http://vllm:8000", modelName: "hsaai-qwen-enterprise-v1", contextLength: 32768, status: "inactive", createdAt: "2026-06-05T22:00:00.000Z", updatedAt: "2026-06-05T22:00:00.000Z" },
];
for (const provider of seed) providers.set(provider.id, provider);

function adapterFor(type: ProviderType): RuntimeProviderAdapter {
  if (type === "Ollama") return new OllamaAdapter();
  if (type === "vLLM") return new VllmAdapter();
  if (type === "GPU Server") return new GpuServerAdapter();
  return new LocalModelAdapter();
}

export class ProviderService {
  static listProviders(): ModelProvider[] { return Array.from(providers.values()); }
  static getProvider(id: string): ModelProvider | null { return providers.get(id) ?? null; }
  static createProvider(input: ModelProviderInput): ModelProvider {
    const now = new Date().toISOString();
    const provider: ModelProvider = { id: `provider_${Date.now()}`, status: "unknown", createdAt: now, updatedAt: now, ...input };
    providers.set(provider.id, provider);
    return provider;
  }
  static async testProvider(id: string) {
    const provider = providers.get(id);
    if (!provider) return null;
    const result = await adapterFor(provider.providerType).healthCheck(provider);
    providers.set(id, { ...provider, status: result.status, lastHealthCheck: result.checkedAt, updatedAt: result.checkedAt });
    return result;
  }
  static async registry() {
    const entries = await Promise.all(Array.from(providers.values()).map(async (provider) => ({ provider, models: await adapterFor(provider.providerType).listModels(provider) })));
    return entries;
  }
}

export function normalizeProviderInput(body: Partial<ModelProviderInput>): ModelProviderInput {
  return {
    providerType: body.providerType || "Ollama",
    endpointUrl: body.endpointUrl || "http://local_llm:11434",
    apiKey: body.apiKey || undefined,
    modelName: body.modelName || "qwen2.5:7b-instruct",
    contextLength: Number(body.contextLength || 8192),
  };
}
