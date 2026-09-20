import { AppShell } from "@/components/layout/app-shell";
import { PageHeader } from "@/components/ui/page-header";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { KpiCard } from "@/components/ui/kpi-card";
import { Ban, GraduationCap, Server, ShieldCheck } from "lucide-react";

const models = [
  { key: "arabic", name: "qwen2.5:7b-instruct", use: "المعرفة العربية والسياسات والإجراءات", status: "Local Only" },
  { key: "general", name: "llama3.1:8b-instruct", use: "المهام العامة داخل الشركة", status: "Local Only" },
  { key: "coding", name: "codellama:7b-instruct", use: "الكود و DevOps و SQL", status: "Local Only" },
  { key: "fast", name: "mistral:7b-instruct", use: "التلخيص والردود السريعة", status: "Local Only" },
];

const policyStats = [
  { label: "Policy", value: "Internal Only", icon: <ShieldCheck size={20} />, hint: "لا مزودين خارجيين" },
  { label: "Runtime", value: "Ollama", icon: <Server size={20} />, hint: "تشغيل محلي بالكامل" },
  { label: "Egress", value: "Denied", icon: <Ban size={20} />, hint: "لا خروج للبيانات" },
  { label: "Training", value: "Local LoRA", icon: <GraduationCap size={20} />, hint: "تدريب داخل البيئة" },
];

export default function AdminModelsPage() {
  return (
    <AppShell>
      <main className="space-y-6">
        <PageHeader
          eyebrow="HSAAI Local Model Control Plane"
          title="إدارة النماذج المحلية"
          description="هذه الشاشة مخصصة لإدارة نماذج الذكاء الاصطناعي المحلية فقط. لا يوجد OpenAI أو Claude أو Gemini أو أي مزود خارجي."
        />

        <section className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {policyStats.map((s) => (
            <KpiCard key={s.label} label={s.label} value={s.value} icon={s.icon} hint={s.hint} />
          ))}
        </section>

        <section className="grid gap-4 md:grid-cols-2">
          {models.map((m) => (
            <Card key={m.key} hoverable>
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-xs font-bold uppercase tracking-widest text-hsa-gold">{m.key}</p>
                  <h2 className="mt-2 text-xl font-bold text-hsa-black">{m.name}</h2>
                </div>
                <Badge tone="gold">{m.status}</Badge>
              </div>
              <p className="mt-4 text-sm leading-7 text-hsa-secondary">{m.use}</p>
            </Card>
          ))}
        </section>

        <Card>
          <h2 className="text-lg font-bold text-hsa-black">Endpoints</h2>
          <pre dir="ltr" className="mt-4 overflow-x-auto rounded-2xl border border-hsa-border bg-hsa-bg p-5 text-start text-xs leading-6 text-hsa-black">
{`GET  /v1/models
POST /v1/models/route
POST /v1/generate
POST /v1/stream
POST /v1/datasets/prepare
POST /v1/fine-tune/jobs`}
          </pre>
        </Card>
      </main>
    </AppShell>
  );
}
