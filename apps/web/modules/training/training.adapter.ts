import type { TrainingCapability, TrainingJob, TrainingJobInput } from "./training.types";

export interface TrainingAdapter {
  capabilities(): Promise<TrainingCapability>;
  listJobs(): Promise<TrainingJob[]>;
  createJob(input: TrainingJobInput): Promise<TrainingJob>;
  getJob(jobId: string): Promise<TrainingJob | null>;
  cancelJob(jobId: string): Promise<TrainingJob | null>;
  readLogs(jobId: string): Promise<string[]>;
}

function nowIso() { return new Date().toISOString(); }

export class MockTrainingAdapter implements TrainingAdapter {
  private jobs = new Map<string, TrainingJob>();

  async capabilities(): Promise<TrainingCapability> {
    return { executionMode: "simulation", supportsRealLora: false, supportsRealQlora: false, requiresGpu: true, backend: "nextjs-memory-simulation", safeInternalOnly: true };
  }

  async listJobs(): Promise<TrainingJob[]> { return Array.from(this.jobs.values()); }

  async createJob(input: TrainingJobInput): Promise<TrainingJob> {
    const timestamp = nowIso();
    const job: TrainingJob = {
      id: `train_${Date.now()}`,
      ...input,
      maxSeqLength: input.maxSeqLength ?? 2048,
      status: "simulation",
      progress: 10,
      createdAt: timestamp,
      updatedAt: timestamp,
      executionMode: "simulation",
      logs: [
        "Created in Next.js simulation mode.",
        "No GPU workload was executed from the web process.",
        "Connect MODEL_TRAINING_SERVICE_URL to the FastAPI model_training service for real LoRA/QLoRA execution.",
      ],
      note: "Fallback simulation adapter. Real training runs through services/model_training.",
    };
    this.jobs.set(job.id, job);
    return job;
  }

  async getJob(jobId: string): Promise<TrainingJob | null> { return this.jobs.get(jobId) ?? null; }

  async cancelJob(jobId: string): Promise<TrainingJob | null> {
    const job = this.jobs.get(jobId);
    if (!job) return null;
    const updated = { ...job, status: "cancelled" as const, updatedAt: nowIso(), logs: [...job.logs, "Cancelled simulation job."] };
    this.jobs.set(jobId, updated);
    return updated;
  }

  async readLogs(jobId: string): Promise<string[]> {
    return this.jobs.get(jobId)?.logs ?? ["Job not found in fallback simulation adapter."];
  }
}

interface PythonTrainingJob {
  id: string;
  model_name: string;
  base_model: string;
  dataset: string;
  training_method: "LoRA" | "QLoRA" | "Fine-tuning Placeholder";
  gpu_target: string;
  epochs: number;
  batch_size: number;
  learning_rate: number;
  max_seq_length: number;
  output_dir: string;
  status: TrainingJob["status"];
  progress: number;
  created_at: string;
  updated_at: string;
  pid?: number | null;
  execution_mode: "simulation" | "real";
}

function fromPython(job: PythonTrainingJob, logs: string[] = []): TrainingJob {
  return {
    id: job.id,
    modelName: job.model_name,
    baseModel: job.base_model,
    dataset: job.dataset,
    trainingMethod: job.training_method,
    gpuTarget: job.gpu_target,
    epochs: job.epochs,
    batchSize: job.batch_size,
    learningRate: job.learning_rate,
    maxSeqLength: job.max_seq_length,
    outputDir: job.output_dir,
    status: job.status,
    progress: job.progress,
    createdAt: job.created_at,
    updatedAt: job.updated_at,
    pid: job.pid,
    executionMode: job.execution_mode,
    logs,
    note: job.execution_mode === "real" ? "Real local training job managed by FastAPI model_training service." : "Simulation job managed by FastAPI model_training service.",
  };
}

function toPython(input: TrainingJobInput) {
  return {
    model_name: input.modelName,
    base_model: input.baseModel,
    dataset: input.dataset,
    training_method: input.trainingMethod,
    gpu_target: input.gpuTarget,
    epochs: input.epochs,
    batch_size: input.batchSize,
    learning_rate: input.learningRate,
    max_seq_length: input.maxSeqLength ?? 2048,
    output_dir: input.outputDir,
  };
}

export class FastApiTrainingAdapter implements TrainingAdapter {
  constructor(private readonly baseUrl: string) {}

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, { ...init, cache: "no-store", headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) } });
    if (!response.ok) throw new Error(`model_training service error ${response.status}: ${await response.text()}`);
    return response.json() as Promise<T>;
  }

  async capabilities(): Promise<TrainingCapability> {
    const raw = await this.request<{ execution_mode: "simulation" | "real"; supports_real_lora: boolean; supports_real_qlora: boolean; requires_gpu: boolean; backend: string; safe_internal_only: boolean }>("/v1/capabilities");
    return { executionMode: raw.execution_mode, supportsRealLora: raw.supports_real_lora, supportsRealQlora: raw.supports_real_qlora, requiresGpu: raw.requires_gpu, backend: raw.backend, safeInternalOnly: raw.safe_internal_only };
  }

  async listJobs(): Promise<TrainingJob[]> {
    const jobs = await this.request<PythonTrainingJob[]>("/v1/training/jobs");
    return jobs.map((job) => fromPython(job));
  }

  async createJob(input: TrainingJobInput): Promise<TrainingJob> {
    const job = await this.request<PythonTrainingJob>("/v1/training/jobs", { method: "POST", body: JSON.stringify(toPython(input)) });
    return fromPython(job, await this.readLogs(job.id).catch(() => []));
  }

  async getJob(jobId: string): Promise<TrainingJob | null> {
    try { return fromPython(await this.request<PythonTrainingJob>(`/v1/training/jobs/${jobId}`), await this.readLogs(jobId).catch(() => [])); }
    catch { return null; }
  }

  async cancelJob(jobId: string): Promise<TrainingJob | null> {
    try { return fromPython(await this.request<PythonTrainingJob>(`/v1/training/jobs/${jobId}/cancel`, { method: "POST" }), await this.readLogs(jobId).catch(() => [])); }
    catch { return null; }
  }

  async readLogs(jobId: string): Promise<string[]> {
    const result = await this.request<{ job_id: string; logs: string[] }>(`/v1/training/jobs/${jobId}/logs`);
    return result.logs;
  }
}
