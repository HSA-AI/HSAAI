import type { ModelProvider } from "./runtime.types";
import { RuntimeProviderAdapter, simulationHealth } from "./provider.adapter";

export class GpuServerAdapter implements RuntimeProviderAdapter {
  async healthCheck(provider: ModelProvider) { return simulationHealth(provider, "GPU Server"); }
  async listModels(provider: ModelProvider) { return [provider.modelName, "gpu-hosted-model-placeholder"]; }
}
