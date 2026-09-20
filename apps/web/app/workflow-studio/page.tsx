"use client";

import { Activity, CalendarClock, GitBranch, History, ShieldCheck, TimerReset, Workflow } from "lucide-react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AppShell } from "@/components/layout/app-shell";
import { PageHeader } from "@/components/ui/page-header";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { WorkflowStudioService } from "@/modules/workflow-studio/workflow-studio.service";

const overview = WorkflowStudioService.overview();
const definitions = WorkflowStudioService.definitions();
const versions = WorkflowStudioService.versions();
const executions = WorkflowStudioService.executions();
const schedules = WorkflowStudioService.schedules();
const approvals = WorkflowStudioService.approvals();
const analytics = WorkflowStudioService.analytics();

function MetricCard({ title, value, hint, icon: Icon }: { title: string; value: string | number; hint: string; icon: any }) {
  return (
    <Card hoverable className="relative overflow-hidden">
      <span aria-hidden className="absolute inset-y-0 start-0 w-1 bg-hsa-yellow" />
      <div className="flex items-center gap-4">
        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-hsa-soft text-hsa-gold"><Icon size={22} /></div>
        <div className="min-w-0">
          <p className="truncate text-xs font-bold uppercase tracking-wide text-hsa-secondary">{title}</p>
          <p className="mt-1 text-2xl font-bold text-hsa-gold">{value}</p>
          <p className="truncate text-xs text-hsa-secondary">{hint}</p>
        </div>
      </div>
    </Card>
  );
}

function statusTone(status: string): "ok" | "warn" | "info" | "neutral" {
  if (status === "completed" || status === "active" || status === "approved" || status === "enabled") return "ok";
  if (status === "waiting_approval" || status === "pending" || status === "disabled") return "warn";
  if (status === "running") return "info";
  return "neutral";
}

export default function WorkflowStudioEnterprisePage() {
  return (
    <AppShell>
      <div className="space-y-6">
        <PageHeader
          eyebrow="Phase 17.4 · Workflow Studio Enterprise"
          title="استوديو سير العمل المؤسسي"
          description="مركز متقدم لإدارة سير العمل الداخلي: Versioning، Scheduling، Execution History، Human Approval، Analytics، وربط جاهز مع محرك التنفيذ الداخلي بدون أي اعتماد على خدمات AI خارجية."
          actions={
            <>
              <Button>New Workflow</Button>
              <Button variant="secondary">Schedule Workflow</Button>
              <Button variant="secondary">Review Approvals</Button>
            </>
          }
        />

        <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <MetricCard title="Workflows" value={analytics.totalWorkflows} hint="Enterprise definitions" icon={Workflow} />
          <MetricCard title="Executions" value={analytics.totalExecutions.toLocaleString()} hint={`${analytics.successRate}% success rate`} icon={Activity} />
          <MetricCard title="Pending Approvals" value={analytics.pendingApprovals} hint="Human-in-the-loop" icon={ShieldCheck} />
          <MetricCard title="Avg Runtime" value={`${analytics.averageRuntimeSeconds}s`} hint="Across latest runs" icon={TimerReset} />
        </section>

        <section className="grid gap-6 xl:grid-cols-[1.35fr_.65fr]">
          <Card>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="hsa-section-title">Execution Trend</h2>
                <p className="mt-2 text-sm text-hsa-secondary">Workflow executions and failures by day.</p>
              </div>
              <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-hsa-soft text-hsa-gold"><History size={20} /></span>
            </div>
            <div className="mt-4 flex items-center gap-4 text-xs font-bold text-hsa-secondary">
              <span className="flex items-center gap-1.5"><span aria-hidden className="h-2 w-2 rounded-full bg-hsa-gold" />تشغيلات</span>
              <span className="flex items-center gap-1.5"><span aria-hidden className="h-2 w-2 rounded-full bg-hsa-secondary" />إخفاقات</span>
            </div>
            <div className="mt-2 h-72" dir="ltr">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={analytics.trend} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="hsaExecFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#F4C430" stopOpacity={0.35} />
                      <stop offset="100%" stopColor="#F4C430" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E7E5E4" />
                  <XAxis dataKey="day" tick={{ fill: "#64748B", fontSize: 12 }} axisLine={{ stroke: "#E7E5E4" }} tickLine={false} />
                  <YAxis tick={{ fill: "#64748B", fontSize: 12 }} axisLine={false} tickLine={false} width={36} />
                  <Tooltip
                    contentStyle={{ borderRadius: 12, border: "1px solid #E7E5E4", boxShadow: "0 8px 25px rgba(17,17,17,.10)", fontFamily: "inherit" }}
                    labelStyle={{ fontWeight: 700, color: "#111111" }}
                  />
                  <Area type="monotone" dataKey="executions" name="Executions" stroke="#A67C00" strokeWidth={2.5} fill="url(#hsaExecFill)" activeDot={{ r: 5, fill: "#F4C430", stroke: "#A67C00" }} />
                  <Area type="monotone" dataKey="failures" name="Failures" stroke="#64748B" strokeWidth={2} fill="#64748B" fillOpacity={0.05} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </Card>

          <Card>
            <h2 className="hsa-section-title">Top Workflows</h2>
            <div className="mt-5 space-y-4">
              {analytics.topWorkflows.map((workflow) => (
                <div key={workflow.name} className="rounded-xl border border-hsa-border bg-hsa-bg p-4 transition hover:border-hsa-gold/40">
                  <p className="font-bold text-hsa-black">{workflow.name}</p>
                  <p className="mt-1 text-sm text-hsa-secondary">{workflow.executions} executions · {workflow.successRate}% success</p>
                </div>
              ))}
            </div>
          </Card>
        </section>

        <section className="grid gap-6 xl:grid-cols-2">
          <Card>
            <h2 className="hsa-section-title"><GitBranch size={18} className="text-hsa-gold" /> Workflow Definitions</h2>
            <div className="mt-5 overflow-x-auto">
              <table className="hsa-table min-w-[640px]">
                <thead><tr><th>Name</th><th>Department</th><th>Version</th><th>Status</th><th>Nodes</th></tr></thead>
                <tbody>{definitions.map((workflow) => <tr key={workflow.id}><td className="font-bold">{workflow.name}</td><td>{workflow.department}</td><td dir="ltr">{workflow.currentVersion}</td><td><Badge tone={statusTone(workflow.status)}>{workflow.status}</Badge></td><td>{workflow.nodes.length}</td></tr>)}</tbody>
              </table>
            </div>
          </Card>

          <Card>
            <h2 className="hsa-section-title">Execution History</h2>
            <div className="mt-5 space-y-3">
              {executions.map((execution) => (
                <div key={execution.id} className="rounded-xl border border-hsa-border bg-hsa-bg p-4 transition hover:border-hsa-gold/40">
                  <div className="flex items-center justify-between gap-3"><p className="font-bold text-hsa-black">{execution.workflowName}</p><Badge tone={statusTone(execution.status)}>{execution.status}</Badge></div>
                  <p className="mt-1 text-sm text-hsa-secondary" dir="ltr">{execution.id} · {execution.stepsCompleted}/{execution.stepsTotal} steps · {execution.triggeredBy}</p>
                </div>
              ))}
            </div>
          </Card>
        </section>

        <section className="grid gap-6 xl:grid-cols-3">
          <Card>
            <h2 className="hsa-section-title"><CalendarClock size={18} className="text-hsa-gold" /> Schedules</h2>
            <div className="mt-5 space-y-3">{schedules.map((schedule) => <div key={schedule.id} className="rounded-xl border border-hsa-border bg-hsa-bg p-4 transition hover:border-hsa-gold/40"><p className="font-bold text-hsa-black">{schedule.workflowName}</p><p className="mt-1 text-sm text-hsa-secondary">{schedule.frequency} · {schedule.enabled ? "enabled" : "disabled"}</p><p className="mt-1 text-xs text-hsa-secondary">Next: {schedule.nextRunAt || "Manual only"}</p></div>)}</div>
          </Card>
          <Card>
            <h2 className="hsa-section-title">Human Approvals</h2>
            <div className="mt-5 space-y-3">{approvals.map((approval) => <div key={approval.id} className="rounded-xl border border-hsa-border bg-hsa-bg p-4 transition hover:border-hsa-gold/40"><p className="font-bold text-hsa-black">{approval.nodeLabel}</p><p className="mt-1 text-sm text-hsa-secondary">{approval.workflowName} · {approval.requestedRole}</p><Badge tone={statusTone(approval.status)} className="mt-2">{approval.status}</Badge></div>)}</div>
          </Card>
          <Card>
            <h2 className="hsa-section-title">Versioning</h2>
            <div className="mt-5 space-y-3">{versions.map((version) => <div key={version.id} className="rounded-xl border border-hsa-border bg-hsa-bg p-4 transition hover:border-hsa-gold/40"><p className="font-bold text-hsa-black"><span dir="ltr">{version.version}</span> · {version.author}</p><p className="mt-1 text-sm leading-6 text-hsa-secondary">{version.changeSummary}</p><Badge tone={version.isPublished ? "ok" : "neutral"} className="mt-2">{version.isPublished ? "Published" : "Draft"}</Badge></div>)}</div>
          </Card>
        </section>

        <Card>
          <h2 className="hsa-section-title">Enterprise Control Notes</h2>
          <p className="mt-3 leading-8 text-hsa-secondary">هذه الوحدة تضيف طبقة إدارة مؤسسية فوق Workflow Builder الحالي. التنفيذ الحالي داخلي ومهيأ للتوسع، ويمكن ربطه لاحقًا بمحرك workflow_engine لتنفيذ فعلي كامل للعقد، الموافقات، الجدولة، والسجلات الإنتاجية.</p>
          <pre dir="ltr" className="mt-4 overflow-x-auto rounded-xl border border-hsa-border bg-hsa-bg p-4 text-start text-xs leading-6 text-hsa-black">{JSON.stringify(overview, null, 2)}</pre>
        </Card>
      </div>
    </AppShell>
  );
}
