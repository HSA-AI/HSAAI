export type ProviderType = "Ollama" | "vLLM" | "GPU Server" | "Local";
export type ProviderStatus = "active" | "inactive" | "degraded" | "unknown";

export interface ModelProviderInput {
  providerType: ProviderType;
  endpointUrl: string;
  apiKey?: string;
  modelName: string;
  contextLength: number;
}

export interface ModelProvider extends ModelProviderInput {
  id: string;
  status: ProviderStatus;
  createdAt: string;
  updatedAt: string;
  lastHealthCheck?: string;
}

export interface ProviderHealthResult {
  ok: boolean;
  status: ProviderStatus;
  message: string;
  checkedAt: string;
}
