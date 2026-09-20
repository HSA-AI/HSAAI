import type { WorkflowDefinition, WorkflowDefinitionInput, WorkflowNodeType } from "./workflow.types";

const workflows = new Map<string, WorkflowDefinition>();
const demo: WorkflowDefinition = {
  id: "wf_contract_review_demo",
  name: "Contract Review Approval Flow",
  description: "Mock workflow: document upload, knowledge search, LLM summary, human approval.",
  nodes: [
    { id: "start", type: "start", label: "Start", x: 40, y: 160, config: {} },
    { id: "search", type: "knowledge_search", label: "Knowledge Search", x: 260, y: 160, config: { kb: "legal-kb" } },
    { id: "llm", type: "llm", label: "LLM Analysis", x: 500, y: 160, config: { model: "qwen2.5:7b-instruct" } },
    { id: "approval", type: "human_approval", label: "Human Approval", x: 740, y: 160, config: { role: "LEGAL_MANAGER" } },
    { id: "end", type: "end", label: "End", x: 980, y: 160, config: {} },
  ],
  edges: [
    { id: "e1", source: "start", target: "search" },
    { id: "e2", source: "search", target: "llm" },
    { id: "e3", source: "llm", target: "approval" },
    { id: "e4", source: "approval", target: "end" },
  ],
  createdAt: "2026-06-05T22:00:00.000Z",
  updatedAt: "2026-06-05T22:00:00.000Z",
};
workflows.set(demo.id, demo);

export const nodeTypes: WorkflowNodeType[] = ["start", "llm", "knowledge_search", "tool", "condition", "human_approval", "end"];

export class WorkflowBuilderService {
  static list() { return Array.from(workflows.values()); }
  static get(id: string) { return workflows.get(id) ?? null; }
  static save(input: WorkflowDefinitionInput): WorkflowDefinition {
    const now = new Date().toISOString();
    const workflow = { id: `wf_${Date.now()}`, createdAt: now, updatedAt: now, ...input };
    workflows.set(workflow.id, workflow);
    return workflow;
  }
  static run(id: string) {
    const workflow = workflows.get(id);
    if (!workflow) return null;
    return {
      workflowId: id,
      mode: "mock-run",
      logs: workflow.nodes.map((node, index) => `${index + 1}. ${node.label} [${node.type}] simulated successfully.`),
      note: "Execution is simulated. Bind this structure to workflow_engine for real execution later.",
    };
  }
}

export function normalizeWorkflowInput(body: Partial<WorkflowDefinitionInput>): WorkflowDefinitionInput {
  return {
    name: body.name || "New Enterprise Workflow",
    description: body.description || "Mock workflow ready for future workflow_engine binding.",
    nodes: Array.isArray(body.nodes) ? body.nodes : demo.nodes,
    edges: Array.isArray(body.edges) ? body.edges : demo.edges,
  };
}
