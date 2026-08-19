import client from './client';

export interface DashboardKPI {
  label: string;
  value: string;
  change?: string;
  trend?: 'up' | 'down' | 'stable';
}

export interface ServiceStatus {
  name: string;
  port: string;
  status: 'healthy' | 'warning' | 'down';
  latencyMs: number;
  uptime: string;
}

export interface DashboardData {
  kpis: DashboardKPI[];
  services: ServiceStatus[];
  weeklyUsage: Array<{ day: string; value: number }>;
  departmentAdoption: Array<{ department: string; percentage: number }>;
}

export async function getDashboard(): Promise<DashboardData> {
  const { data } = await client.get('/v1/dashboard');
  return data;
}

export async function getServicesHealth(): Promise<ServiceStatus[]> {
  const { data } = await client.get('/v1/services/health');
  return data.services || [];
}

export async function getExecutiveMetrics() {
  const { data } = await client.get('/v1/executive/metrics');
  return data;
}
