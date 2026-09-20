'use client';

import { useEffect, useMemo, useState } from 'react';
import { AppShell } from '@/components/layout/app-shell';
import { PageHeader } from '@/components/ui/page-header';
import { Badge } from '@/components/ui/badge';
import { KpiCard } from '@/components/ui/kpi-card';
import { Input } from '@/components/ui/input';
import { Activity, Bot, BookOpen, Search, ShieldCheck } from 'lucide-react';

type DepartmentAgent = {
  id: number | null;
  key: string;
  name: string;
  department: string;
  description: string;
  system_prompt: string;
  allowed_roles: string[];
  knowledge_scopes: string[];
  escalation_target: string;
  priority: number;
  enabled: boolean;
};

const fallbackAgents: DepartmentAgent[] = [
  { id: null, key: 'hr', name: 'HR Agent', department: 'human_resources', description: 'سياسات الموظفين والإجازات والتوظيف والتدريب.', system_prompt: '', allowed_roles: ['ai_user', 'department_manager'], knowledge_scopes: ['hr'], escalation_target: 'HR Service Desk', priority: 20, enabled: true },
  { id: null, key: 'finance', name: 'Finance Agent', department: 'finance', description: 'الميزانيات والمصروفات والفواتير والإجراءات المالية.', system_prompt: '', allowed_roles: ['department_manager', 'auditor'], knowledge_scopes: ['finance'], escalation_target: 'Finance Governance Team', priority: 15, enabled: true },
  { id: null, key: 'it', name: 'IT Support Agent', department: 'it', description: 'الدعم الفني والصلاحيات والأنظمة والشبكات.', system_prompt: '', allowed_roles: ['ai_user', 'department_manager'], knowledge_scopes: ['it', 'security'], escalation_target: 'IT Service Desk', priority: 25, enabled: true },
  { id: null, key: 'knowledge', name: 'Knowledge Agent', department: 'knowledge_management', description: 'البحث في الوثائق والمصادر والسياسات المعتمدة.', system_prompt: '', allowed_roles: ['knowledge_admin', 'ai_user'], knowledge_scopes: ['knowledge'], escalation_target: 'Knowledge Governance Team', priority: 5, enabled: true },
  { id: null, key: 'executive', name: 'Executive Agent', department: 'executive', description: 'التقارير والمؤشرات والملخصات التنفيذية.', system_prompt: '', allowed_roles: ['department_manager', 'auditor'], knowledge_scopes: ['executive', 'reports'], escalation_target: 'Executive Office', priority: 1, enabled: true },
];

export default function DepartmentAgentsPage() {
  const [agents, setAgents] = useState<DepartmentAgent[]>(fallbackAgents);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');

  useEffect(() => {
    // SECURITY FIX v2.1 (P0): Use httpOnly cookie-based auth via same-origin fetch.
    // Previously this read hsaai_access_token from localStorage, which violated
    // the v2.0 security model and exposed the token to XSS. The browser now
    // automatically attaches the httpOnly cookie when credentials: 'include' is set.
    fetch('/api/department-agents', { credentials: 'include' })
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error('تعذر تحميل الوكلاء من الخادم'))))
      .then((data) => Array.isArray(data) && setAgents(data))
      .catch((err) => setError(err.message || 'تعذر تحميل البيانات؛ يتم عرض كتالوج افتراضي.'))
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return agents;
    return agents.filter((a) => [a.name, a.key, a.department, a.description].join(' ').toLowerCase().includes(q));
  }, [agents, query]);

  const stats = useMemo(() => ({
    total: agents.length,
    active: agents.filter((a) => a.enabled).length,
    restricted: agents.filter((a) => a.allowed_roles.includes('auditor') || a.allowed_roles.includes('department_manager')).length,
    scopes: new Set(agents.flatMap((a) => a.knowledge_scopes)).size,
  }), [agents]);

  return (
    <AppShell>
      <main className="space-y-6">
        <PageHeader
          eyebrow="HSAAI Enterprise Admin"
          title="Department AI Agents"
          description="إدارة الوكلاء المتخصصين لكل قسم وربط كل وكيل بصلاحياته ومجالات المعرفة المسموح له بالبحث فيها. هذه الطبقة تجعل HSAAI يعمل كفريق خبراء مؤسسيين بدل مساعد واحد عام."
        />

        <section className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <KpiCard label="إجمالي الوكلاء" value={stats.total} icon={<Bot size={20} />} />
          <KpiCard label="الوكلاء النشطون" value={stats.active} icon={<Activity size={20} />} />
          <KpiCard label="وكلاء بصلاحيات مقيدة" value={stats.restricted} icon={<ShieldCheck size={20} />} />
          <KpiCard label="نطاقات المعرفة" value={stats.scopes} icon={<BookOpen size={20} />} />
        </section>

        <div className="flex flex-col gap-3 rounded-2xl border border-hsa-border bg-white p-4 shadow-hsa-card md:flex-row md:items-center md:justify-between">
          <div className="relative w-full md:max-w-md">
            <Search size={16} aria-hidden className="pointer-events-none absolute start-3 top-1/2 -translate-y-1/2 text-hsa-secondary" />
            <Input
              className="ps-9"
              placeholder="ابحث باسم الوكيل أو القسم..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              aria-label="بحث في وكلاء الأقسام"
            />
          </div>
          <div className="text-sm text-hsa-secondary" role="status">{loading ? 'جاري التحميل...' : `${filtered.length} وكيل معروض`}</div>
        </div>

        {error && <div role="alert" className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm leading-7 text-amber-800">{error}</div>}

        <div className="overflow-hidden rounded-2xl border border-hsa-border bg-white shadow-hsa-card">
          <div className="overflow-x-auto">
            <table className="hsa-table min-w-[900px]">
              <thead>
                <tr>
                  <th>الوكيل</th>
                  <th>القسم</th>
                  <th>الصلاحيات</th>
                  <th>نطاقات المعرفة</th>
                  <th>الأولوية</th>
                  <th>الحالة</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((agent) => (
                  <tr key={agent.key}>
                    <td>
                      <div className="font-bold text-hsa-black">{agent.name}</div>
                      <div className="mt-1 text-xs leading-6 text-hsa-secondary">{agent.description}</div>
                      <div className="mt-2 text-xs font-bold text-hsa-gold">Escalation: {agent.escalation_target || 'غير محدد'}</div>
                    </td>
                    <td className="text-hsa-secondary">{agent.department}</td>
                    <td><BadgeList items={agent.allowed_roles} /></td>
                    <td><BadgeList items={agent.knowledge_scopes} tone="gold" /></td>
                    <td>{agent.priority}</td>
                    <td>
                      <Badge tone={agent.enabled ? 'ok' : 'neutral'}>
                        {agent.enabled ? 'نشط' : 'معطل'}
                      </Badge>
                    </td>
                  </tr>
                ))}
                {!filtered.length && (
                  <tr><td colSpan={6} className="px-5 py-16 text-center text-hsa-secondary">لا توجد وكلاء مطابقة لبحثك.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </main>
    </AppShell>
  );
}

function BadgeList({ items, tone = 'neutral' }: { items: string[]; tone?: 'gold' | 'neutral' }) {
  return <div className="flex flex-wrap gap-2">{items.map((item) => <Badge key={item} tone={tone}>{item}</Badge>)}</div>;
}
