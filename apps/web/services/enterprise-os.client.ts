export type ApiEnvelope<T> = T & { error?: string };

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

// FIX V3: Use enterprise safeFetch for JSON validation + structured errors
import { safeFetch } from "@/lib/safe-fetch";

async function request<T>(path: string, init?: RequestInit): Promise<ApiEnvelope<T>> {
  const result = await safeFetch<T>(`${API_BASE}${path}`, {
    ...init,
    cache: "no-store",
  });
  if (result.error) {
    return { error: result.error.message } as ApiEnvelope<T>;
  }
  return result.data as ApiEnvelope<T>;
}

export type PlatformModule = {
  key: string;
  name: string;
  route: string;
  status: "ready" | "partial" | "requires_configuration";
  capabilities: string[];
};

export type ReadinessControl = {
  area: string;
  score: number;
  status: "ready" | "needs_configuration" | "needs_runtime_validation";
  evidence: string[];
};

export const enterpriseOSClient = {
  modules: () => request<{ items: PlatformModule[] }>("/api/platform/modules"),
  readiness: () => request<{ score: number; controls: ReadinessControl[] }>("/api/platform/readiness"),
  securityPosture: () => request<{ zero_trust_ready: boolean; controls: string[] }>("/api/security/posture"),
  searchFacets: () => request<{ facets: Record<string, string[]> }>("/api/enterprise-search/facets"),
};
