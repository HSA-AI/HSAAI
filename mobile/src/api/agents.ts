import client from './client';

export interface Agent {
  id: string;
  name: string;
  nameAr: string;
  description: string;
  icon: string;
  status: 'active' | 'idle' | 'error';
  tools: string[];
  totalRequests?: number;
  avgLatencyMs?: number;
  successRate?: number;
  department: string;
}

export async function getAgents(): Promise<Agent[]> {
  const { data } = await client.get('/v1/agents');
  return data.agents || [];
}

export async function getAgent(agentId: string): Promise<Agent> {
  const { data } = await client.get(`/v1/agents/${agentId}`);
  return data;
}

export async function runAgent(
  agentId: string,
  input: string,
  workspaceId: string = 'hsa-main-workspace',
): Promise<{ output: string; latency_ms: number; tools_used: string[] }> {
  const { data } = await client.post(`/v1/agents/${agentId}/run`, {
    input,
    workspace_id: workspaceId,
  });
  return data;
}
