const DEFAULT_INTERNAL_MODEL_TRAINING_URL = "http://model-training:8090";

export function modelTrainingBaseUrl(): string {
  const url = process.env.MODEL_TRAINING_SERVICE_URL || process.env.INTERNAL_MODEL_TRAINING_API_URL || DEFAULT_INTERNAL_MODEL_TRAINING_URL;
  return url.replace(/\/$/, "");
}

export async function proxyModelTraining<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${modelTrainingBaseUrl()}${path}`, {
    ...init,
    cache: "no-store",
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!response.ok) {
    const body = await response.text().catch(() => "");
    throw new Error(`model_training ${response.status}: ${body}`);
  }
  return response.json() as Promise<T>;
}
