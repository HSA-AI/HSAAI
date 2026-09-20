import type { AgentPermissionPolicy, AgentRuntimeMetric, AgentVersion, EnterpriseAgentTemplate } from "./agent-studio.types";

export const enterpriseAgentTemplates: EnterpriseAgentTemplate[] = [
  { id: "hr-assistant", name: "HR Assistant", department: "Human Resources", description: "مساعد موارد بشرية للسياسات والإجازات واللوائح الداخلية.", defaultModel: "qwen2.5:7b-instruct", tools: ["knowledge_search", "policy_lookup"], knowledgeSpaces: ["hr"], requiredPermissions: ["HR_READ"], riskLevel: "medium" },
  { id: "finance-assistant", name: "Finance Assistant", department: "Finance", description: "مساعد مالي للسياسات المالية والتقارير الداخلية.", defaultModel: "llama3.1:8b-instruct", tools: ["knowledge_search", "spreadsheet_analyzer"], knowledgeSpaces: ["finance"], requiredPermissions: ["FINANCE_READ"], riskLevel: "high" },
  { id: "legal-document-assistant", name: "Legal Document Assistant", department: "Legal", description: "تحليل العقود والمستندات القانونية داخلياً.", defaultModel: "qwen2.5:7b-instruct", tools: ["document_ai", "citation_viewer"], knowledgeSpaces: ["legal"], requiredPermissions: ["LEGAL_READ"], riskLevel: "high" },
  { id: "it-support-agent", name: "IT Support Agent", department: "IT", description: "مساعد دعم تقني لإجراءات تقنية المعلومات والخدمات الداخلية.", defaultModel: "mistral:7b-instruct", tools: ["ticket_lookup", "knowledge_search"], knowledgeSpaces: ["it"], requiredPermissions: ["IT_READ"], riskLevel: "low" },
  { id: "procurement-assistant", name: "Procurement Assistant", department: "Procurement", description: "مساعد مشتريات للطلبات والموردين والسياسات الشرائية.", defaultModel: "qwen2.5:7b-instruct", tools: ["supplier_lookup", "knowledge_search"], knowledgeSpaces: ["procurement"], requiredPermissions: ["PROCUREMENT_READ"], riskLevel: "medium" },
  { id: "executive-assistant", name: "Executive Assistant", department: "Executive", description: "مساعد تنفيذي للملخصات ومؤشرات الأداء والتنبيهات.", defaultModel: "llama3.1:8b-instruct", tools: ["executive_analytics", "knowledge_search"], knowledgeSpaces: ["executive"], requiredPermissions: ["EXECUTIVE_READ"], riskLevel: "critical" },
];

export const agentVersions: AgentVersion[] = [
  { id: "agv-hr-001", agentId: "hr-assistant", version: "1.0.0", changelog: "Initial HR policy assistant.", systemPrompt: "You are a secure HR assistant for internal policies only.", model: "qwen2.5:7b-instruct", tools: ["knowledge_search"], status: "active", createdBy: "AI Admin", createdAt: "2026-06-06T00:00:00Z" },
  { id: "agv-fin-001", agentId: "finance-assistant", version: "1.0.0", changelog: "Initial finance assistant with strict financial scope.", systemPrompt: "You are a finance assistant. Never expose data outside authorized scope.", model: "llama3.1:8b-instruct", tools: ["knowledge_search", "spreadsheet_analyzer"], status: "active", createdBy: "AI Admin", createdAt: "2026-06-06T00:00:00Z" },
];

export const agentMetrics: AgentRuntimeMetric[] = [
  { agentId: "hr-assistant", agentName: "HR Assistant", requests: 12450, successRate: 94.2, avgLatencyMs: 1180, failures: 37, knowledgeHits: 10790, tokenUsage: 4860000, lastRunAt: "2026-06-06T08:45:00Z" },
  { agentId: "finance-assistant", agentName: "Finance Assistant", requests: 5120, successRate: 91.4, avgLatencyMs: 1460, failures: 55, knowledgeHits: 4810, tokenUsage: 2920000, lastRunAt: "2026-06-06T08:41:00Z" },
  { agentId: "it-support-agent", agentName: "IT Support Agent", requests: 8730, successRate: 96.1, avgLatencyMs: 920, failures: 22, knowledgeHits: 6901, tokenUsage: 2010000, lastRunAt: "2026-06-06T08:48:00Z" },
];

export const agentPermissions: AgentPermissionPolicy[] = [
  { id: "ap-hr", agentId: "hr-assistant", role: "HR Manager", department: "Human Resources", knowledgeScope: "hr/*", canRun: true, canEdit: true, canDeploy: false },
  { id: "ap-fin", agentId: "finance-assistant", role: "Finance Manager", department: "Finance", knowledgeScope: "finance/*", canRun: true, canEdit: true, canDeploy: false },
  { id: "ap-ai-admin", agentId: "*", role: "AI Admin", department: "AI Office", knowledgeScope: "approved/*", canRun: true, canEdit: true, canDeploy: true },
];

export function getAgentStudioSummary() {
  const totalRequests = agentMetrics.reduce((sum, item) => sum + item.requests, 0);
  const avgSuccessRate = Number((agentMetrics.reduce((sum, item) => sum + item.successRate, 0) / agentMetrics.length).toFixed(1));
  const activeAgents = agentVersions.filter((item) => item.status === "active").length;
  const highRiskAgents = enterpriseAgentTemplates.filter((item) => item.riskLevel === "high" || item.riskLevel === "critical").length;
  return { totalTemplates: enterpriseAgentTemplates.length, activeAgents, totalRequests, avgSuccessRate, highRiskAgents, managedPermissions: agentPermissions.length };
}
