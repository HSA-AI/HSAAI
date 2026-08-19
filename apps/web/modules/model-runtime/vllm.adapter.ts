import type { ModelProvider } from "./runtime.types";
import { RuntimeProviderAdapter, simulationHealth } from "./provider.adapter";

export class VllmAdapter implements RuntimeProviderAdapter {
  async healthCheck(provider: ModelProvider) { return simulationHealth(provider, "vLLM"); }
  async listModels(provider: ModelProvider) { return [provider.modelName, "hsaai-qwen-enterprise-v1"]; }
}
