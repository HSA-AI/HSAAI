import type { ModelProvider, ProviderHealthResult } from "./runtime.types";

export interface RuntimeProviderAdapter {
  healthCheck(provider: ModelProvider): Promise<ProviderHealthResult>;
  listModels(provider: ModelProvider): Promise<string[]>;
}

export function simulationHealth(provider: ModelProvider, label: string): ProviderHealthResult {
  const hasEndpoint = provider.providerType === "Local" || provider.endpointUrl.length > 0;
  return {
    ok: hasEndpoint,
    status: hasEndpoint ? "active" : "unknown",
    message: `${label} adapter is configured in simulation mode. No external AI service is used.`,
    checkedAt: new Date().toISOString(),
  };
}
