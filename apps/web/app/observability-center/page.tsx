import { AppShell } from "@/components/layout/app-shell";
import { PageHeader } from "@/components/ui/page-header";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Activity, BarChart3, Bot, Database, Gauge, LineChart, Server, Users, Workflow } from "lucide-react";

const metrics = [
  { name: "Model Usage", icon: Server },
  { name: "Token Usage", icon: Activity },
  { name: "Agent Performance", icon: Bot },
  { name: "Workflow Performance", icon: Workflow },
  { name: "API Usage", icon: BarChart3 },
  { name: "Latency", icon: Gauge },
  { name: "Errors", icon: LineChart },
  { name: "User Activity", icon: Users },
  { name: "Knowledge Usage", icon: Database },
] as const;

const services = [
  { name: "Prometheus", detail: "Metrics scraping", tone: "ok", status: "Online" },
  { name: "Grafana", detail: "Executive dashboards", tone: "ok", status: "Online" },
  { name: "OpenTelemetry", detail: "Traces & spans", tone: "info", status: "Compatible" },
] as const;

export default function ObservabilityCenterPage() {
  return (
    <AppShell>
      <div className="space-y-6">
        <PageHeader
          eyebrow="Observability Platform"
          title="Observability Center"
          description="لوحات متابعة تنفيذية وتشغيلية للنماذج والوكلاء ومسارات العمل والبنية التحتية."
        />

        <section className="grid gap-4 md:grid-cols-3">
          {services.map((s) => (
            <Card key={s.name} hoverable>
              <div className="flex items-center justify-between gap-3">
                <h2 className="font-bold text-hsa-black">{s.name}</h2>
                <Badge tone={s.tone as "ok" | "info"}>{s.status}</Badge>
              </div>
              <p className="mt-2 text-sm text-hsa-secondary">{s.detail}</p>
            </Card>
          ))}
        </section>

        <section>
          <h2 className="hsa-section-title mb-4">
            لوحات المقاييس
            <span className="text-xs font-bold text-hsa-secondary">Metric Dashboards</span>
          </h2>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {metrics.map((m) => {
              const Icon = m.icon;
              return (
                <Card key={m.name} hoverable>
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <h3 className="truncate text-sm font-bold uppercase tracking-wide text-hsa-secondary">{m.name}</h3>
                      <p className="mt-3 text-2xl font-bold text-hsa-gold">Ready</p>
                      <p className="mt-2 text-xs text-hsa-secondary">Prometheus / Grafana / OpenTelemetry compatible</p>
                    </div>
                    <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-hsa-soft text-hsa-gold">
                      <Icon size={20} />
                    </span>
                  </div>
                  <Badge tone="ok" className="mt-3">Healthy</Badge>
                </Card>
              );
            })}
          </div>
        </section>
      </div>
    </AppShell>
  );
}
