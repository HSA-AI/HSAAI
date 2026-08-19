import { AppShell } from "@/components/layout/app-shell";
import { Card } from "@/components/ui/card";

const agents = [
  ["Supervisor Agent", "يوجه الطلبات للوكلاء المتخصصين ويراقب الصلاحيات والأداء"],
  ["HR Agent", "سياسات الموارد البشرية، الإجازات، معرفة الموظفين"],
  ["Finance Agent", "الإجراءات المالية، الموازنات، المشتريات، المصروفات"],
  ["IT Agent", "الدعم الفني، البنية التحتية، الحوادث التقنية"],
  ["Legal Agent", "العقود، الامتثال، الحوكمة، الوثائق القانونية"],
];

export default function EnterpriseAgentsCenterPage() {
  return <AppShell><main className="space-y-6">
    <section><p className="text-sm font-bold text-hsa-yellow">Enterprise Agent Orchestration</p><h1 className="text-3xl font-black">Agents Center</h1><p className="mt-2 max-w-4xl text-slate-500">مركز إدارة الوكلاء: Supervisor Agent ينسق HR وFinance وIT وLegal مع RBAC وAudit Logs ومراقبة الأداء.</p></section>
    <section className="grid gap-4 lg:grid-cols-5">{agents.map(([name, desc]) => <Card key={name} className="border-hsa-yellow/20"><div className="text-xs font-bold text-hsa-gold">Active</div><h2 className="mt-2 text-lg font-black">{name}</h2><p className="mt-2 text-sm leading-7 text-slate-500">{desc}</p><div className="mt-4 rounded-xl bg-slate-100 p-3 text-xs dark:bg-slate-950">Health: healthy · SLA monitored</div></Card>)}</section>
    <section className="grid gap-4 lg:grid-cols-3"><Card><h2 className="font-bold">Routing Engine</h2><p className="mt-2 text-sm text-slate-500">Intent + Department + Roles → specialist agent.</p></Card><Card><h2 className="font-bold">Agent Memory</h2><p className="mt-2 text-sm text-slate-500">Session and workspace-scoped memory with tenant isolation.</p></Card><Card><h2 className="font-bold">Audit Logs</h2><p className="mt-2 text-sm text-slate-500">Every routing decision is logged for governance.</p></Card></section>
  </main></AppShell>;
}
