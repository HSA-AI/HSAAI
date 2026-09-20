import { FastApiTrainingAdapter, MockTrainingAdapter, type TrainingAdapter } from "./training.adapter";
import type { TrainingJob, TrainingJobInput } from "./training.types";

const seedJobs: TrainingJob[] = [
  {
    id: "train_demo_arabic_policy",
    modelName: "hsaai-qwen-enterprise-v1",
    baseModel: "/data/models/qwen2.5-7b-instruct",
    dataset: "/data/training/datasets/internal-policy-sample.jsonl",
    trainingMethod: "LoRA",
    gpuTarget: "0",
    epochs: 3,
    batchSize: 4,
    learningRate: 0.0002,
    maxSeqLength: 2048,
    outputDir: "/data/training/outputs/train_demo_arabic_policy",
    status: "simulation",
    progress: 10,
    createdAt: "2026-06-05T22:00:00.000Z",
    updatedAt: "2026-06-05T22:30:00.000Z",
    executionMode: "simulation",
    logs: ["Demo job created.", "FastAPI real-training adapter is available when MODEL_TRAINING_SERVICE_URL is configured."],
    note: "Demo job for the enterprise model training dashboard.",
  },
];

const fallback = new MockTrainingAdapter();
for (const job of seedJobs) {
  void fallback.createJob(job);
}

function adapter(): TrainingAdapter {
  const serviceUrl = process.env.MODEL_TRAINING_SERVICE_URL;
  if (serviceUrl) return new FastApiTrainingAdapter(serviceUrl.replace(/\/$/, ""));
  return fallback;
}

export class TrainingService {
  static async capabilities() { return adapter().capabilities(); }
  static async listJobs(): Promise<TrainingJob[]> { return adapter().listJobs(); }
  static async getJob(jobId: string): Promise<TrainingJob | null> { return adapter().getJob(jobId); }
  static async createJob(input: TrainingJobInput): Promise<TrainingJob> { return adapter().createJob(input); }
  static async cancelJob(jobId: string): Promise<TrainingJob | null> { return adapter().cancelJob(jobId); }
  static async logs(jobId: string): Promise<string[]> { return adapter().readLogs(jobId); }
}

export function normalizeTrainingInput(body: Partial<TrainingJobInput>): TrainingJobInput {
  return {
    modelName: body.modelName || "hsaai-local-model-draft",
    baseModel: body.baseModel || "/data/models/qwen2.5-7b-instruct",
    dataset: body.dataset || "/data/training/datasets/dataset-placeholder.jsonl",
    trainingMethod: body.trainingMethod || "LoRA",
    gpuTarget: body.gpuTarget || "auto",
    epochs: Number(body.epochs || 3),
    batchSize: Number(body.batchSize || 4),
    learningRate: Number(body.learningRate || 0.0002),
    maxSeqLength: Number(body.maxSeqLength || 2048),
    outputDir: body.outputDir,
  };
}
