export type LocalModelFormat = "GGUF" | "Safetensors" | "HF" | "Other";
export type LocalModelStatus = "registered" | "active" | "disabled" | "missing-file";

export interface LocalModelInput {
  name: string;
  version: string;
  size: string;
  format: LocalModelFormat;
  location: string;
  provider: string;
}

export interface LocalModel extends LocalModelInput {
  id: string;
  status: LocalModelStatus;
  createdAt: string;
  updatedAt: string;
}
