export type AgentLifecycleStatus = "draft" | "active" | "paused" | "deprecated";
export type AgentRiskLevel = "low" | "medium" | "high" | "critical";

export type EnterpriseAgentTemplate = {
  id: string;
  name: string;
  department: string;
  description: string;
  defaultModel: string;
  tools: string[];
  knowledgeSpaces: string[];
  requiredPermissions: string[];
  riskLevel: AgentRiskLevel;
};

export type AgentVersion = {
  id: string;
  agentId: string;
  version: string;
  changelog: string;
  systemPrompt: string;
  model: string;
  tools: string[];
  status: AgentLifecycleStatus;
  createdBy: string;
  createdAt: string;
};

export type AgentRuntimeMetric = {
  agentId: string;
  agentName: string;
  requests: number;
  successRate: number;
  avgLatencyMs: number;
  failures: number;
  knowledgeHits: number;
  tokenUsage: number;
  lastRunAt: string;
};

export type AgentPermissionPolicy = {
  id: string;
  agentId: string;
  role: string;
  department: string;
  knowledgeScope: string;
  canRun: boolean;
  canEdit: boolean;
  canDeploy: boolean;
};
