import { ArrowDown } from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { PageHeader } from "@/components/ui/page-header";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

type LayerStatus = "ok" | "warn";

const layers: { title: string; status: LayerStatus; statusLabel: string; items: string[] }[] = [
  { title: "User Experience", status: "ok", statusLabel: "مستقرة", items: ["Next.js Web", "HSAAI Chat", "Executive Dashboard", "HTML Preview"] },
  { title: "Access & Security", status: "ok", statusLabel: "مستقرة", items: ["Keycloak", "RBAC", "JWT", "Audit Logs"] },
  { title: "AI Control Plane", status: "ok", statusLabel: "مستقرة", items: ["API Gateway", "Backend Core", "AI Orchestrator", "Agent Router"] },
  { title: "Knowledge & RAG", status: "ok", statusLabel: "مستقرة", items: ["Document Loaders", "Chunking", "Embeddings", "Qdrant", "Citations"] },
  { title: "Local LLM", status: "ok", statusLabel: "مستقرة", items: ["Ollama", "Model Registry", "Prompt Templates", "Streaming"] },
  { title: "Enterprise Integrations", status: "warn", statusLabel: "تحت المراجعة", items: ["SAP", "Active Directory", "HR Systems", "Workflow Engine"] },
  { title: "Infrastructure", status: "ok", statusLabel: "مستقرة", items: ["Docker Compose", "Kubernetes", "Helm", "Monitoring"] },
];

const flow = [
  { step: "Edge", title: "طبقة الوصول", items: ["User", "Next.js Web", "HSAAI Chat", "Executive Dashboard"] },
  { step: "Gateway", title: "البوابة والحماية", items: ["API Gateway", "Keycloak OIDC + PKCE", "RBAC / JWT", "Audit Logs"] },
  { step: "Services", title: "خدمات المنصة", items: ["Backend Core", "AI Orchestrator", "Agent Router", "RAG / Agents", "Ollama Local LLM", "Workflow Engine"] },
  { step: "Data", title: "طبقة البيانات", items: ["Qdrant Vector DB", "Model Registry", "Document Store", "Monitoring & Logs"] },
];

function StatusDot({ status }: { status: LayerStatus }) {
  return <span aria-hidden className={`h-2.5 w-2.5 shrink-0 rounded-full ${status === "ok" ? "bg-emerald-500" : "bg-amber-500"}`} />;
}

export default function ArchitecturePage() {
  return (
    <AppShell>
      <div className="space-y-6">
        <PageHeader
          eyebrow="Architecture Center"
          title="خريطة معمارية لمنصة HSAAI"
          description="تعرض هذه الصفحة الطبقات الفعلية للمشروع حتى لا تظهر المنصة كلوحة بسيطة، بل كنظام ذكاء اصطناعي مؤسسي كامل."
        />

        <section>
          <h2 className="hsa-section-title mb-4">
            طبقات المنصة وحالة الخدمات
            <span className="text-xs font-bold text-hsa-secondary">Service Layers</span>
          </h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {layers.map((layer) => (
              <Card key={layer.title} hoverable className="flex flex-col">
                <div className="flex items-center justify-between gap-3">
                  <h3 className="text-base font-bold text-hsa-black">{layer.title}</h3>
                  <span className="flex items-center gap-1.5 text-xs font-bold text-hsa-secondary">
                    <StatusDot status={layer.status} />
                    {layer.statusLabel}
                  </span>
                </div>
                <ul className="mt-4 flex flex-wrap gap-2">
                  {layer.items.map((item) => (
                    <li key={item} className="rounded-lg border border-hsa-border bg-hsa-bg px-2.5 py-1.5 text-xs font-bold text-hsa-black">{item}</li>
                  ))}
                </ul>
              </Card>
            ))}
          </div>
        </section>

        <section>
          <Card>
            <h2 className="hsa-section-title">مسار الطلب من الطرف إلى الطرف</h2>
            <p className="mt-3 text-sm text-hsa-secondary">اتصال مباشر عبر أربع مراحل محددة بحدود واضحة — كل مرحلة تعتمد على ما قبلها فقط.</p>
            <div className="mt-5 space-y-3">
              {flow.map((stage, i) => (
                <div key={stage.step}>
                  <div className="rounded-xl border border-hsa-border bg-hsa-bg p-5 transition hover:border-hsa-gold/40">
                    <div className="flex flex-wrap items-center gap-3">
                      <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-hsa-yellow font-bold text-hsa-black">{i + 1}</span>
                      <h3 className="text-lg font-bold text-hsa-black">{stage.title}</h3>
                      <Badge tone="gold">{stage.step}</Badge>
                    </div>
                    <ul className="mt-4 flex flex-wrap gap-2">
                      {stage.items.map((item) => (
                        <li key={item} className="rounded-lg border border-hsa-border bg-white px-2.5 py-1.5 text-xs font-bold text-hsa-black shadow-hsa-card">{item}</li>
                      ))}
                    </ul>
                  </div>
                  {i < flow.length - 1 && (
                    <div className="flex justify-center py-1" aria-hidden>
                      <ArrowDown size={18} className="text-hsa-gold" />
                    </div>
                  )}
                </div>
              ))}
            </div>
          </Card>
        </section>
      </div>
    </AppShell>
  );
}
