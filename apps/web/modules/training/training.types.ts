export type TrainingMethod = "LoRA" | "QLoRA" | "Fine-tuning Placeholder";
export type TrainingStatus = "draft" | "queued" | "validating" | "running" | "simulation" | "completed" | "cancelled" | "failed";
export type TrainingExecutionMode = "simulation" | "real";

export interface TrainingJobInput {
  modelName: string;
  baseModel: string;
  dataset: string;
  trainingMethod: TrainingMethod;
  gpuTarget: string;
  epochs: number;
  batchSize: number;
  learningRate: number;
  maxSeqLength?: number;
  outputDir?: string;
}

export interface TrainingJob extends TrainingJobInput {
  id: string;
  status: TrainingStatus;
  createdAt: string;
  updatedAt: string;
  progress: number;
  logs: string[];
  note: string;
  pid?: number | null;
  executionMode: TrainingExecutionMode;
}

export interface TrainingCapability {
  executionMode: TrainingExecutionMode;
  supportsRealLora: boolean;
  supportsRealQlora: boolean;
  requiresGpu: boolean;
  backend: string;
  safeInternalOnly: boolean;
}
