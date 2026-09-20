import { AppShell } from "@/components/layout/app-shell";
import { PageHeader } from "@/components/ui/page-header";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Bot, BrainCircuit, FileClock, GitFork, Landmark, Scale, MonitorCog, Users } from "lucide-react";

const agents = [
  { name: "Supervisor Agent", icon: GitFork, desc: "يوجه الطلبات للوكلاء المتخصصين ويراقب الصلاحيات والأداء" },
  { name: "HR Agent", icon: Users, desc: "سياسات الموارد البشرية، الإجازات، معرفة الموظفين" },
  { name: "Finance Agent", icon: Landmark, desc: "الإجراءات المالية، الموازنات، المشتريات، المصروفات" },
  { name: "IT Agent", icon: MonitorCog, desc: "الدعم الفني، البنية التحتية، الحوادث التقنية" },
  { name: "Legal Agent", icon: Scale, desc: "العقود، الامتثال، الحوكمة، الوثائق القانونية" },
] as const;

const platform = [
  { title: "Routing Engine", icon: BrainCircuit, body: "Intent + Department + Roles → specialist agent." },
  { title: "Agent Memory", icon: Bot, body: "Session and workspace-scoped memory with tenant isolation." },
  { title: "Audit Logs", icon: FileClock, body: "Every routing decision is logged for governance." },
] as const;

export default function EnterpriseAgentsCenterPage() {
  return (
    <AppShell>
      <div className="space-y-6">
        <PageHeader
          eyebrow="Enterprise Agent Orchestration"
          title="Agents Center"
          description="مركز إدارة الوكلاء: Supervisor Agent ينسق HR وFinance وIT وLegal مع RBAC وAudit Logs ومراقبة الأداء."
          actions={<Badge tone="ok">All systems healthy</Badge>}
        />

        {/* Agent cards grid */}
        <section>
          <h2 className="hsa-section-title mb-4">
            الوكلاء النشطون
            <span className="text-xs font-bold text-hsa-secondary">Active Agents</span>
          </h2>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {agents.map((agent) => {
              const Icon = agent.icon;
              return (
                <Card key={agent.name} hoverable>
                  <div className="flex items-start justify-between gap-3">
                    <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-hsa-soft text-hsa-gold">
                      <Icon size={20} />
                    </span>
                    <Badge tone="ok">Active</Badge>
                  </div>
                  <h3 className="mt-4 text-lg font-bold text-hsa-black">{agent.name}</h3>
                  <p className="mt-2 text-sm leading-7 text-hsa-secondary">{agent.desc}</p>
                  <div className="mt-4 rounded-xl border border-hsa-border bg-hsa-bg p-3 text-xs text-hsa-secondary">
                    Health: <span className="font-bold text-hsa-gold">healthy</span> · SLA monitored
                  </div>
                </Card>
              );
            })}
          </div>
        </section>

        {/* Platform capabilities */}
        <section className="grid gap-4 lg:grid-cols-3">
          {platform.map((p) => {
            const Icon = p.icon;
            return (
              <Card key={p.title} hoverable>
                <div className="flex items-center gap-3">
                  <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-hsa-soft text-hsa-gold">
                    <Icon size={18} />
                  </span>
                  <h2 className="font-bold text-hsa-black">{p.title}</h2>
                </div>
                <p className="mt-3 text-sm leading-7 text-hsa-secondary">{p.body}</p>
              </Card>
            );
          })}
        </section>
      </div>
    </AppShell>
  );
}
