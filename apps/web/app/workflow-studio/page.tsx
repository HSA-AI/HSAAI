"use client";

import { Activity, CalendarClock, GitBranch, History, ShieldCheck, TimerReset, Workflow } from "lucide-react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AppShell } from "@/components/layout/app-shell";
import { Card } from "@/components/ui/card";
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
    <Card className="flex items-center gap-4">
      <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-hsa-yellow/20 text-hsa-black dark:text-hsa-yellow"><Icon size={22} /></div>
      <div>
        <p className="text-xs font-black uppercase tracking-[0.25em] text-slate-500">{title}</p>
        <p className="mt-1 text-2xl font-black">{value}</p>
        <p className="text-xs text-slate-500">{hint}</p>
      </div>
    </Card>
  );
}

export default function WorkflowStudioEnterprisePage() {
  return (
    <AppShell>
      <main className="space-y-6">
        <section className="rounded-[2rem] bg-slate-950 p-8 text-white shadow-hsa-glow">
          <p className="text-xs font-black uppercase tracking-[0.35em] text-hsa-yellow">Phase 17.4 · Workflow Studio Enterprise</p>
          <h1 className="mt-3 text-4xl font-black">استوديو سير العمل المؤسسي</h1>
          <p className="mt-4 max-w-5xl leading-8 text-slate-300">مركز متقدم لإدارة سير العمل الداخلي: Versioning، Scheduling، Execution History، Human Approval، Analytics، وربط جاهز مع محرك التنفيذ الداخلي بدون أي اعتماد على خدمات AI خارجية.</p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Button>New Workflow</Button>
            <Button className="bg-white/10 text-white ring-1 ring-white/20">Schedule Workflow</Button>
            <Button className="bg-white/10 text-white ring-1 ring-white/20">Review Approvals</Button>
          </div>
        </section>

        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <MetricCard title="Workflows" value={analytics.totalWorkflows} hint="Enterprise definitions" icon={Workflow} />
          <MetricCard title="Executions" value={analytics.totalExecutions.toLocaleString()} hint={`${analytics.successRate}% success rate`} icon={Activity} />
          <MetricCard title="Pending Approvals" value={analytics.pendingApprovals} hint="Human-in-the-loop" icon={ShieldCheck} />
          <MetricCard title="Avg Runtime" value={`${analytics.averageRuntimeSeconds}s`} hint="Across latest runs" icon={TimerReset} />
        </section>

        <section className="grid gap-6 xl:grid-cols-[1.35fr_.65fr]">
          <Card>
            <div className="flex items-center justify-between gap-3">
              <div><h2 className="text-xl font-black">Execution Trend</h2><p className="text-sm text-slate-500">Workflow executions and failures by day.</p></div>
              <History className="text-hsa-yellow" />
            </div>
            <div className="mt-6 h-72">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={analytics.trend}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="day" />
                  <YAxis />
                  <Tooltip />
                  <Area type="monotone" dataKey="executions" stroke="currentColor" fill="currentColor" fillOpacity={0.12} />
                  <Area type="monotone" dataKey="failures" stroke="currentColor" fill="currentColor" fillOpacity={0.05} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </Card>

          <Card>
            <h2 className="text-xl font-black">Top Workflows</h2>
            <div className="mt-5 space-y-4">
              {analytics.topWorkflows.map((workflow) => (
                <div key={workflow.name} className="rounded-2xl border p-4 dark:border-slate-800">
                  <p className="font-black">{workflow.name}</p>
                  <p className="mt-1 text-sm text-slate-500">{workflow.executions} executions · {workflow.successRate}% success</p>
                </div>
              ))}
            </div>
          </Card>
        </section>

        <section className="grid gap-6 xl:grid-cols-2">
          <Card>
            <div className="flex items-center gap-2"><GitBranch className="text-hsa-yellow" /><h2 className="text-xl font-black">Workflow Definitions</h2></div>
            <div className="mt-5 overflow-auto">
              <table className="w-full min-w-[780px] text-sm">
                <thead className="text-right text-xs uppercase tracking-wider text-slate-500"><tr><th className="p-3">Name</th><th className="p-3">Department</th><th className="p-3">Version</th><th className="p-3">Status</th><th className="p-3">Nodes</th></tr></thead>
                <tbody>{definitions.map((workflow) => <tr key={workflow.id} className="border-t dark:border-slate-800"><td className="p-3 font-bold">{workflow.name}</td><td className="p-3">{workflow.department}</td><td className="p-3">{workflow.currentVersion}</td><td className="p-3">{workflow.status}</td><td className="p-3">{workflow.nodes.length}</td></tr>)}</tbody>
              </table>
            </div>
          </Card>

          <Card>
            <h2 className="text-xl font-black">Execution History</h2>
            <div className="mt-5 space-y-3">
              {executions.map((execution) => (
                <div key={execution.id} className="rounded-2xl border p-4 dark:border-slate-800">
                  <div className="flex items-center justify-between gap-3"><p className="font-black">{execution.workflowName}</p><span className="rounded-full bg-hsa-yellow/20 px-3 py-1 text-xs font-black">{execution.status}</span></div>
                  <p className="mt-1 text-sm text-slate-500">{execution.id} · {execution.stepsCompleted}/{execution.stepsTotal} steps · {execution.triggeredBy}</p>
                </div>
              ))}
            </div>
          </Card>
        </section>

        <section className="grid gap-6 xl:grid-cols-3">
          <Card>
            <div className="flex items-center gap-2"><CalendarClock className="text-hsa-yellow" /><h2 className="text-xl font-black">Schedules</h2></div>
            <div className="mt-5 space-y-3">{schedules.map((schedule) => <div key={schedule.id} className="rounded-2xl border p-4 dark:border-slate-800"><p className="font-black">{schedule.workflowName}</p><p className="text-sm text-slate-500">{schedule.frequency} · {schedule.enabled ? "enabled" : "disabled"}</p><p className="text-xs text-slate-400">Next: {schedule.nextRunAt || "Manual only"}</p></div>)}</div>
          </Card>
          <Card>
            <h2 className="text-xl font-black">Human Approvals</h2>
            <div className="mt-5 space-y-3">{approvals.map((approval) => <div key={approval.id} className="rounded-2xl border p-4 dark:border-slate-800"><p className="font-black">{approval.nodeLabel}</p><p className="text-sm text-slate-500">{approval.workflowName} · {approval.requestedRole}</p><p className="text-xs font-bold text-hsa-yellow">{approval.status}</p></div>)}</div>
          </Card>
          <Card>
            <h2 className="text-xl font-black">Versioning</h2>
            <div className="mt-5 space-y-3">{versions.map((version) => <div key={version.id} className="rounded-2xl border p-4 dark:border-slate-800"><p className="font-black">{version.version} · {version.author}</p><p className="text-sm text-slate-500">{version.changeSummary}</p><p className="text-xs text-slate-400">{version.isPublished ? "Published" : "Draft"}</p></div>)}</div>
          </Card>
        </section>

        <Card>
          <h2 className="text-xl font-black">Enterprise Control Notes</h2>
          <p className="mt-3 leading-8 text-slate-600 dark:text-slate-300">هذه الوحدة تضيف طبقة إدارة مؤسسية فوق Workflow Builder الحالي. التنفيذ الحالي داخلي ومهيأ للتوسع، ويمكن ربطه لاحقًا بمحرك workflow_engine لتنفيذ فعلي كامل للعقد، الموافقات، الجدولة، والسجلات الإنتاجية.</p>
          <pre className="mt-4 overflow-auto rounded-2xl bg-black p-5 text-xs leading-6 text-hsa-yellow">{JSON.stringify(overview, null, 2)}</pre>
        </Card>
      </main>
    </AppShell>
  );
}
