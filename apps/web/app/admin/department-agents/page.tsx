'use client';

import { useEffect, useMemo, useState } from 'react';

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
    <main className="min-h-screen bg-slate-950 text-slate-100" dir="rtl">
      <section className="mx-auto max-w-7xl px-6 py-8">
        <div className="mb-8 rounded-3xl border border-amber-300/20 bg-gradient-to-l from-slate-900 to-slate-800 p-8 shadow-2xl">
          <p className="text-sm font-semibold text-amber-300">HSAAI Enterprise Admin</p>
          <h1 className="mt-2 text-3xl font-bold text-white">Department AI Agents</h1>
          <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-300">
            إدارة الوكلاء المتخصصين لكل قسم وربط كل وكيل بصلاحياته ومجالات المعرفة المسموح له بالبحث فيها. هذه الطبقة تجعل HSAAI يعمل كفريق خبراء مؤسسيين بدل مساعد واحد عام.
          </p>
        </div>

        <div className="mb-6 grid gap-4 md:grid-cols-4">
          <Card label="إجمالي الوكلاء" value={stats.total} />
          <Card label="الوكلاء النشطون" value={stats.active} />
          <Card label="وكلاء بصلاحيات مقيدة" value={stats.restricted} />
          <Card label="نطاقات المعرفة" value={stats.scopes} />
        </div>

        <div className="mb-5 flex flex-col gap-3 rounded-2xl border border-slate-800 bg-slate-900/80 p-4 md:flex-row md:items-center md:justify-between">
          <input
            className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-white outline-none ring-amber-300/30 focus:ring-4 md:max-w-md"
            placeholder="ابحث باسم الوكيل أو القسم..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <div className="text-sm text-slate-400">{loading ? 'جاري التحميل...' : `${filtered.length} وكيل معروض`}</div>
        </div>

        {error && <div className="mb-4 rounded-xl border border-amber-400/30 bg-amber-400/10 p-4 text-sm text-amber-100">{error}</div>}

        <div className="overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/90 shadow-xl">
          <table className="w-full min-w-[900px] text-right text-sm">
            <thead className="bg-slate-800/80 text-slate-300">
              <tr>
                <th className="px-5 py-4">الوكيل</th>
                <th className="px-5 py-4">القسم</th>
                <th className="px-5 py-4">الصلاحيات</th>
                <th className="px-5 py-4">نطاقات المعرفة</th>
                <th className="px-5 py-4">الأولوية</th>
                <th className="px-5 py-4">الحالة</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {filtered.map((agent) => (
                <tr key={agent.key} className="hover:bg-slate-800/40">
                  <td className="px-5 py-4">
                    <div className="font-semibold text-white">{agent.name}</div>
                    <div className="mt-1 text-xs leading-6 text-slate-400">{agent.description}</div>
                    <div className="mt-2 text-xs text-amber-300">Escalation: {agent.escalation_target || 'غير محدد'}</div>
                  </td>
                  <td className="px-5 py-4 text-slate-300">{agent.department}</td>
                  <td className="px-5 py-4"><BadgeList items={agent.allowed_roles} /></td>
                  <td className="px-5 py-4"><BadgeList items={agent.knowledge_scopes} tone="gold" /></td>
                  <td className="px-5 py-4 text-slate-300">{agent.priority}</td>
                  <td className="px-5 py-4">
                    <span className={`rounded-full px-3 py-1 text-xs ${agent.enabled ? 'bg-emerald-400/10 text-emerald-300' : 'bg-slate-700 text-slate-300'}`}>
                      {agent.enabled ? 'نشط' : 'معطل'}
                    </span>
                  </td>
                </tr>
              ))}
              {!filtered.length && (
                <tr><td colSpan={6} className="px-5 py-16 text-center text-slate-400">لا توجد وكلاء مطابقة لبحثك.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}

function Card({ label, value }: { label: string; value: number }) {
  return <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5 shadow-lg"><div className="text-sm text-slate-400">{label}</div><div className="mt-2 text-3xl font-bold text-white">{value}</div></div>;
}

function BadgeList({ items, tone = 'slate' }: { items: string[]; tone?: 'slate' | 'gold' }) {
  return <div className="flex flex-wrap gap-2">{items.map((item) => <span key={item} className={`rounded-full px-2.5 py-1 text-xs ${tone === 'gold' ? 'bg-amber-300/10 text-amber-200' : 'bg-slate-800 text-slate-300'}`}>{item}</span>)}</div>;
}
