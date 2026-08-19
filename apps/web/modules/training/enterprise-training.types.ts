
export type TrainingStatus = "Pending" | "Preparing" | "Training" | "Validating" | "Saving" | "Deploying" | "Completed" | "Failed" | "Cancelled" | "Paused";
export type TrainingMethod = "LoRA" | "QLoRA" | "SFT";
export type TrainingJob = {
  id: number; training_name: string; description?: string | null; base_model: string; dataset_id?: number | null; dataset_path?: string | null;
  method: TrainingMethod | string; status: TrainingStatus | string; gpu_device?: string | null; created_by: string;
  created_at: string; started_at?: string | null; finished_at?: string | null; config: Record<string, unknown>; output_dir?: string | null;
};
export type Dataset = { id: number; name: string; version: string; format: string; path: string; size_bytes: number; records_count: number; tokens_count: number; validation_status: string; statistics: Record<string, unknown>; created_by: string; created_at: string; };
export type MetricPoint = { step: number; epoch?: number; loss?: number; eval_loss?: number; learning_rate?: number; eta_seconds?: number; tokens_processed?: number; gpu_usage?: number; vram_usage?: number; };
export type TrainingCreatePayload = {
  training_name: string; description?: string; base_model: string; dataset_id?: number; dataset_path?: string; method: TrainingMethod;
  hyperparameters: { epochs: number; learning_rate: number; batch_size: number; gradient_accumulation: number; warmup_steps: number; weight_decay: number; max_sequence_length: number; lora_rank: number; lora_alpha: number; lora_dropout: number; };
  compute: { gpu_device: string; cpu_limit?: string; ram_limit?: string; vram_limit?: string; multi_gpu: boolean; };
  output_model_name?: string;
};
