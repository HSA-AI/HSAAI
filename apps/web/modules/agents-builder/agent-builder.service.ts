import type { AgentDefinition, AgentDefinitionInput, AgentRunResult } from "./agent-builder.types";

const agents = new Map<string, AgentDefinition>();
const templates: AgentDefinition[] = [
  { id: "tpl_hr", template: "HR Assistant", name: "HR Assistant", description: "يساعد الموارد البشرية في السياسات والإجازات واللوائح.", systemPrompt: "You are an internal HR assistant. Answer only from approved HR knowledge.", tools: ["knowledge_search", "policy_lookup"], knowledgeBase: "hr-kb", modelSelection: "qwen2.5:7b-instruct", permissions: ["HR_READ"], createdAt: "2026-06-05T22:00:00.000Z", updatedAt: "2026-06-05T22:00:00.000Z" },
  { id: "tpl_finance", template: "Finance Assistant", name: "Finance Assistant", description: "مساعد مالي للاستفسارات والتحليلات الداخلية.", systemPrompt: "You are an internal finance assistant. Do not expose sensitive financial data without permission.", tools: ["knowledge_search", "spreadsheet_reader"], knowledgeBase: "finance-kb", modelSelection: "llama3.1:8b-instruct", permissions: ["FINANCE_READ"], createdAt: "2026-06-05T22:00:00.000Z", updatedAt: "2026-06-05T22:00:00.000Z" },
  { id: "tpl_it", template: "IT Support Agent", name: "IT Support Agent", description: "يدعم تقنية المعلومات وطلبات الدعم الداخلي.", systemPrompt: "You are an internal IT support agent. Create safe troubleshooting steps.", tools: ["ticket_lookup", "knowledge_search"], knowledgeBase: "it-kb", modelSelection: "mistral:7b-instruct", permissions: ["IT_READ"], createdAt: "2026-06-05T22:00:00.000Z", updatedAt: "2026-06-05T22:00:00.000Z" },
  { id: "tpl_legal", template: "Legal Document Assistant", name: "Legal Document Assistant", description: "يساعد في مراجعة العقود والمستندات القانونية داخلياً.", systemPrompt: "You are an internal legal document assistant. Provide analysis, not legal advice.", tools: ["document_ai", "citation_viewer"], knowledgeBase: "legal-kb", modelSelection: "qwen2.5:7b-instruct", permissions: ["LEGAL_READ"], createdAt: "2026-06-05T22:00:00.000Z", updatedAt: "2026-06-05T22:00:00.000Z" },
];
for (const agent of templates) agents.set(agent.id, agent);

export class AgentBuilderService {
  static list() { return Array.from(agents.values()); }
  static get(id: string) { return agents.get(id) ?? null; }
  static create(input: AgentDefinitionInput): AgentDefinition {
    const now = new Date().toISOString();
    const agent = { id: `agent_${Date.now()}`, createdAt: now, updatedAt: now, ...input };
    agents.set(agent.id, agent);
    return agent;
  }
  static update(id: string, input: Partial<AgentDefinitionInput>): AgentDefinition | null {
    const current = agents.get(id);
    if (!current) return null;
    const updated = { ...current, ...input, updatedAt: new Date().toISOString() };
    agents.set(id, updated);
    return updated;
  }
  static delete(id: string): boolean { return agents.delete(id); }
  static run(id: string, input: string): AgentRunResult | null {
    const agent = agents.get(id);
    if (!agent) return null;
    return {
      agentId: id,
      input,
      output: `Mock preview from ${agent.name}: سأستخدم ${agent.knowledgeBase} والأدوات المحددة للإجابة عند ربط الأدوات الحقيقية لاحقاً.`,
      citations: ["placeholder://knowledge-base/source-1"],
      mode: "mock-preview",
    };
  }
}

export function normalizeAgentInput(body: Partial<AgentDefinitionInput>): AgentDefinitionInput {
  return {
    name: body.name || "New Internal Agent",
    description: body.description || "Enterprise internal agent placeholder.",
    systemPrompt: body.systemPrompt || "You are a secure internal HSAAI enterprise agent.",
    tools: Array.isArray(body.tools) ? body.tools : ["knowledge_search"],
    knowledgeBase: body.knowledgeBase || "default-kb",
    modelSelection: body.modelSelection || "qwen2.5:7b-instruct",
    permissions: Array.isArray(body.permissions) ? body.permissions : ["INTERNAL_USER"],
  };
}
