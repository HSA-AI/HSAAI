export interface AgentDefinitionInput {
  name: string;
  description: string;
  systemPrompt: string;
  tools: string[];
  knowledgeBase: string;
  modelSelection: string;
  permissions: string[];
}

export interface AgentDefinition extends AgentDefinitionInput {
  id: string;
  template?: string;
  createdAt: string;
  updatedAt: string;
}

export interface AgentRunResult {
  agentId: string;
  input: string;
  output: string;
  citations: string[];
  mode: "mock-preview";
}
