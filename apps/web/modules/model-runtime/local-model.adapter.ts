import type { ModelProvider } from "./runtime.types";
import { RuntimeProviderAdapter, simulationHealth } from "./provider.adapter";

export class LocalModelAdapter implements RuntimeProviderAdapter {
  async healthCheck(provider: ModelProvider) { return simulationHealth(provider, "Local Model Files"); }
  async listModels(provider: ModelProvider) { return [provider.modelName, "/storage/local_models/*.gguf", "/storage/local_models/*.safetensors"]; }
}
