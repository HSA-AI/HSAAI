import client from './client';

export interface Approval {
  id: string;
  type: 'model_deployment' | 'data_access' | 'agent_creation' | 'workflow_change';
  title: string;
  description: string;
  requestedBy: string;
  requestedAt: string;
  status: 'pending' | 'approved' | 'rejected';
  riskLevel: 'low' | 'medium' | 'high' | 'critical';
  approvers: string[];
  decision?: 'approved' | 'rejected';
  decidedBy?: string;
  decidedAt?: string;
  reason?: string;
}

export async function getPendingApprovals(): Promise<Approval[]> {
  const { data } = await client.get('/v1/governance/approvals?status=pending');
  return data.approvals || [];
}

export async function getAllApprovals(): Promise<Approval[]> {
  const { data } = await client.get('/v1/governance/approvals');
  return data.approvals || [];
}

export async function approveRequest(
  approvalId: string,
  reason?: string,
): Promise<void> {
  await client.post(`/v1/governance/approvals/${approvalId}/approve`, { reason });
}

export async function rejectRequest(
  approvalId: string,
  reason: string,
): Promise<void> {
  await client.post(`/v1/governance/approvals/${approvalId}/reject`, { reason });
}

export async function getGovernanceOverview() {
  const { data } = await client.get('/v1/governance/overview');
  return data;
}
