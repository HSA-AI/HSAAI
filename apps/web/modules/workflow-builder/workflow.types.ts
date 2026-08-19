export type WorkflowNodeType = "start" | "llm" | "knowledge_search" | "tool" | "condition" | "human_approval" | "end";

export interface WorkflowNode {
  id: string;
  type: WorkflowNodeType;
  label: string;
  config: Record<string, string | number | boolean>;
  x: number;
  y: number;
}

export interface WorkflowEdge { id: string; source: string; target: string; }

export interface WorkflowDefinitionInput {
  name: string;
  description: string;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
}

export interface WorkflowDefinition extends WorkflowDefinitionInput {
  id: string;
  createdAt: string;
  updatedAt: string;
}
