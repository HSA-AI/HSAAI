export type WorkflowStatus = "draft" | "active" | "paused" | "archived";
export type WorkflowRunStatus = "pending" | "running" | "waiting_approval" | "completed" | "failed" | "cancelled";
export type ApprovalStatus = "pending" | "approved" | "rejected" | "expired";
export type ScheduleFrequency = "manual" | "hourly" | "daily" | "weekly" | "cron";

export interface WorkflowStudioNode {
  id: string;
  type: "start" | "llm" | "knowledge_search" | "tool" | "condition" | "human_approval" | "end";
  label: string;
  config: Record<string, string | number | boolean>;
  position: { x: number; y: number };
}

export interface WorkflowStudioEdge {
  id: string;
  source: string;
  target: string;
  condition?: string;
}

export interface WorkflowDefinitionEnterprise {
  id: string;
  name: string;
  description: string;
  owner: string;
  department: string;
  status: WorkflowStatus;
  currentVersion: string;
  nodes: WorkflowStudioNode[];
  edges: WorkflowStudioEdge[];
  tags: string[];
  createdAt: string;
  updatedAt: string;
}

export interface WorkflowVersion {
  id: string;
  workflowId: string;
  version: string;
  changeSummary: string;
  author: string;
  createdAt: string;
  isPublished: boolean;
}

export interface WorkflowExecution {
  id: string;
  workflowId: string;
  workflowName: string;
  version: string;
  status: WorkflowRunStatus;
  triggeredBy: string;
  startedAt: string;
  finishedAt?: string;
  durationMs?: number;
  stepsTotal: number;
  stepsCompleted: number;
  logs: string[];
}

export interface WorkflowSchedule {
  id: string;
  workflowId: string;
  workflowName: string;
  frequency: ScheduleFrequency;
  cron?: string;
  timezone: string;
  enabled: boolean;
  nextRunAt?: string;
  createdBy: string;
}

export interface WorkflowApproval {
  id: string;
  executionId: string;
  workflowName: string;
  nodeLabel: string;
  requestedRole: string;
  requestedBy: string;
  status: ApprovalStatus;
  createdAt: string;
  decidedAt?: string;
  comment?: string;
}

export interface WorkflowAnalytics {
  totalWorkflows: number;
  activeWorkflows: number;
  totalExecutions: number;
  successRate: number;
  failureRate: number;
  averageRuntimeSeconds: number;
  pendingApprovals: number;
  scheduledWorkflows: number;
  topWorkflows: Array<{ name: string; executions: number; successRate: number }>;
  trend: Array<{ day: string; executions: number; failures: number }>;
}
