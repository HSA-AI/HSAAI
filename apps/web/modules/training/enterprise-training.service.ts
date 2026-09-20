import type { Dataset, TrainingCreatePayload, TrainingJob } from "./enterprise-training.types";

// Default to the Next.js internal API proxy so browser code never depends on
// cross-origin FastAPI URLs. Set NEXT_PUBLIC_MODEL_TRAINING_API_URL only when
// you intentionally want direct browser-to-service calls.
const BASE = (process.env.NEXT_PUBLIC_MODEL_TRAINING_API_URL ?? "").replace(/\/$/, "");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    cache: "no-store",
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json() as Promise<T>;
}

export const enterpriseTrainingApi = {
  capabilities: () => request<{ execution_mode: string; supports: string[]; backend: string; production_guard: string }>("/api/training/capabilities"),
  jobs: () => request<TrainingJob[]>("/api/training/jobs"),
  createJob: (payload: TrainingCreatePayload) => request<TrainingJob>("/api/training/jobs", { method: "POST", body: JSON.stringify(payload) }),
  startJob: (id: number) => request<{ rq_job_id: string }>(`/api/training/jobs/${id}/start`, { method: "POST" }),
  cancelJob: (id: number) => request<TrainingJob>(`/api/training/jobs/${id}/cancel`, { method: "POST" }),
  pauseJob: (id: number) => request<TrainingJob>(`/api/training/jobs/${id}/pause`, { method: "POST" }),
  resumeJob: (id: number) => request<{ rq_job_id: string }>(`/api/training/jobs/${id}/resume`, { method: "POST" }),
  logs: (id: number) => request<unknown[]>(`/api/training/jobs/${id}/logs`),
  metrics: (id: number) => request<{ points: unknown[] }>(`/api/training/jobs/${id}/metrics`),
  datasets: () => request<Dataset[]>("/api/training/datasets"),
  supportedModels: () => request<{ families: string[] }>("/api/training/models/supported"),
  gpu: () => request<{ gpus: unknown[] }>("/api/training/monitoring/gpu"),
};
