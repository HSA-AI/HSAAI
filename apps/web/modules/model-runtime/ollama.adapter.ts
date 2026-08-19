import type { ModelProvider } from "./runtime.types";
import { RuntimeProviderAdapter, simulationHealth } from "./provider.adapter";

export class OllamaAdapter implements RuntimeProviderAdapter {
  async healthCheck(provider: ModelProvider) { return simulationHealth(provider, "Ollama"); }
  async listModels(provider: ModelProvider) { return [provider.modelName, "qwen2.5:7b-instruct", "llama3.1:8b-instruct", "mistral:7b-instruct"]; }
}
