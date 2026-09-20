import { AppShell } from "@/components/layout/app-shell";
import { PageHeader } from "@/components/ui/page-header";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { AnalyticsCards } from "@/components/dashboard/analytics-cards";
import { AiUsageChart } from "@/components/dashboard/ai-usage-chart";
import { BrandHero } from "@/components/branding/brand-hero";
import { ReadinessScorecard } from "@/components/enterprise/readiness-scorecard";
import { KpiCard } from "@/components/ui/kpi-card";
import { Activity, Bot, FileSearch, Gauge } from "lucide-react";

const health = [
  ["API Gateway", "Online", "32 ms", "ok"],
  ["Backend Core", "Online", "45 ms", "ok"],
  ["RAG Engine", "Online", "71 ms", "ok"],
  ["Qdrant Vector DB", "Ready", "14 collections", "info"],
  ["Ollama LLM", "Ready", "llama3 / qwen", "info"],
  ["Keycloak Auth", "Protected", "RBAC active", "warn"],
] as const;

const kpis = [
  { label: "Indexed Documents", value: "128K", delta: "+4.8%", icon: <FileSearch size={20} />, hint: "وثائق مفهرسة" },
  { label: "RAG Answers", value: "42.6K", delta: "+18%", icon: <Activity size={20} />, hint: "إجابات مدعومة بالمصادر" },
  { label: "Agent Runs", value: "9,842", delta: "+11%", icon: <Bot size={20} />, hint: "تشغيلات الوكلاء" },
  { label: "Avg Latency", value: "1.8s", delta: "-9%", icon: <Gauge size={20} />, hint: "متوسط زمن الاستجابة" },
] as const;

const operations = [
  "رفع وثائق جديدة إلى Knowledge Brain",
  "تنفيذ محادثات مدعومة بالمصادر",
  "تشغيل وكلاء HR / Finance / IT بصلاحيات منفصلة",
  "مراقبة Ollama وQdrant وAPI Gateway من مركز Observability",
];

export default function Dashboard() {
  return (
    <AppShell>
      <div className="space-y-6">
        <BrandHero />

        <PageHeader
          eyebrow="Enterprise AI Command Center"
          title="لوحة تشغيل HSAAI المؤسسية"
          description="لوحة واحدة لقياس استخدام الذكاء الاصطناعي، صحة الخدمات، حالة RAG، نشاط الوكلاء، وحوكمة التشغيل داخل بيئة HSA الداخلية."
        />

        <AnalyticsCards />

        <ReadinessScorecard />

        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {kpis.map((k) => (
            <KpiCard key={k.label} label={k.label} value={k.value} delta={k.delta} icon={k.icon} hint={k.hint} />
          ))}
        </section>

        <section className="grid gap-6 xl:grid-cols-3">
          <div className="xl:col-span-2"><AiUsageChart /></div>
          <Card>
            <h2 className="text-lg font-bold text-hsa-black">Service Health Matrix</h2>
            <div className="mt-4 space-y-3">
              {health.map(([name, status, detail, tone]) => (
                <div key={name} className="flex items-center justify-between gap-3 rounded-xl border border-hsa-border bg-hsa-bg p-3 text-sm">
                  <div className="min-w-0">
                    <b className="block truncate text-hsa-black">{name}</b>
                    <p className="truncate text-xs text-hsa-secondary">{detail}</p>
                  </div>
                  <Badge tone={tone as "ok" | "info" | "warn"}>{status}</Badge>
                </div>
              ))}
            </div>
          </Card>
        </section>

        <section className="grid gap-6 lg:grid-cols-2">
          <Card>
            <h2 className="text-lg font-bold text-hsa-black">Active HSA Agents</h2>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              {["Supervisor", "HR", "Finance", "Executive", "Knowledge", "IT Support"].map((agent) => (
                <div key={agent} className="rounded-xl border border-hsa-border bg-hsa-soft/50 p-4 transition hover:border-hsa-gold/40">
                  <p className="font-bold text-hsa-black">{agent} Agent</p>
                  <p className="mt-1 text-xs text-hsa-secondary">Tools + RAG + RBAC + Audit Logs</p>
                </div>
              ))}
            </div>
          </Card>
          <Card>
            <h2 className="text-lg font-bold text-hsa-black">Operational Readiness</h2>
            <ul className="mt-4 space-y-3 text-sm">
              {operations.map((item) => (
                <li key={item} className="rounded-xl border border-hsa-border bg-hsa-bg p-3 leading-7 text-hsa-black">
                  <span aria-hidden className="me-2 font-bold text-hsa-gold">✓</span>
                  {item}
                </li>
              ))}
            </ul>
          </Card>
        </section>
      </div>
    </AppShell>
  );
}
