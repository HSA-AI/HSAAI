/**
 * HSAAI Enterprise Training API Service v3.0
 * ═══════════════════════════════════════════════════════════════════════
 *
 * CRITICAL FIX (V3): Replaced the broken request() helper that used
 * `throw new Error(await res.text())` — which captured entire HTML pages
 * as the error message and rendered them in the UI.
 *
 * Now uses the enterprise safeFetch utility with:
 *   1. JSON Content-Type validation
 *   2. Structured ApiError objects
 *   3. Arabic error messages
 *   4. Request-ID tracing
 *   5. Retry with exponential backoff
 *
 * ═══════════════════════════════════════════════════════════════════════
 */
import { apiGet, apiPost, type ApiError, type ApiResponse } from "@/lib/safe-fetch";
import type { Dataset, TrainingCreatePayload, TrainingJob } from "./enterprise-training.types";

// Note: BASE is now "" (empty) — all requests go through Next.js rewrites
// which proxy /api/training/* to the model-training service.
// This ensures cookies are forwarded and no CORS issues arise.
const BASE = "";

export const enterpriseTrainingApi = {
  capabilities: (): Promise<ApiResponse<{ execution_mode: string; supports: string[]; backend: string; production_guard: string }>> =>
    apiGet(`${BASE}/api/training/capabilities`),

  jobs: (): Promise<ApiResponse<TrainingJob[]>> =>
    apiGet(`${BASE}/api/training/jobs`),

  createJob: (payload: TrainingCreatePayload): Promise<ApiResponse<TrainingJob>> =>
    apiPost(`${BASE}/api/training/jobs`, payload),

  startJob: (id: number): Promise<ApiResponse<{ rq_job_id: string }>> =>
    apiPost(`${BASE}/api/training/jobs/${id}/start`),

  cancelJob: (id: number): Promise<ApiResponse<TrainingJob>> =>
    apiPost(`${BASE}/api/training/jobs/${id}/cancel`),

  pauseJob: (id: number): Promise<ApiResponse<TrainingJob>> =>
    apiPost(`${BASE}/api/training/jobs/${id}/pause`),

  resumeJob: (id: number): Promise<ApiResponse<{ rq_job_id: string }>> =>
    apiPost(`${BASE}/api/training/jobs/${id}/resume`),

  logs: (id: number): Promise<ApiResponse<unknown[]>> =>
    apiGet(`${BASE}/api/training/jobs/${id}/logs`),

  metrics: (id: number): Promise<ApiResponse<{ points: unknown[] }>> =>
    apiGet(`${BASE}/api/training/jobs/${id}/metrics`),

  datasets: (): Promise<ApiResponse<Dataset[]>> =>
    apiGet(`${BASE}/api/training/datasets`),

  supportedModels: (): Promise<ApiResponse<{ families: string[] }>> =>
    apiGet(`${BASE}/api/training/models/supported`),

  gpu: (): Promise<ApiResponse<{ gpus: unknown[] }>> =>
    apiGet(`${BASE}/api/training/monitoring/gpu`),
};

export type { ApiError, ApiResponse };
