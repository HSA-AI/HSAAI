import { AppShell } from "@/components/layout/app-shell";
import { PageHeader } from "@/components/ui/page-header";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Lock, Route, ShieldCheck, Target } from "lucide-react";

const policies = [
  {
    title: "Local-Only Policy",
    icon: Lock,
    body: "كل التوجيه يتم نحو Ollama المحلي فقط، بدون OpenAI أو Anthropic أو أي مزود خارجي.",
  },
  {
    title: "Sensitivity Rules",
    icon: ShieldCheck,
    body: "restricted/high → qwen2.5، low/general → llama3 أو النموذج الافتراضي المحلي.",
  },
  {
    title: "Task-Aware Routing",
    icon: Target,
    body: "مهام Excel/SAP/Finance والسياسات العربية توجه للنموذج الأنسب محليًا.",
  },
] as const;

export default function Page() {
  return (
    <AppShell>
      <div className="space-y-6">
        <PageHeader
          eyebrow="Enterprise AI Operations Platform"
          title="Model Routing Center"
          description="طبقة اختيار نموذج محلي حسب نوع المهمة وحساسيتها مع منع أي توجيه خارجي في نمط HSAAI الداخلي."
          actions={<Badge tone="gold">Internal Only</Badge>}
        />

        <section className="grid gap-4 md:grid-cols-3">
          {policies.map((p) => {
            const Icon = p.icon;
            return (
              <Card key={p.title} hoverable>
                <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-hsa-soft text-hsa-gold">
                  <Icon size={20} />
                </span>
                <h2 className="mt-4 font-bold text-hsa-black">{p.title}</h2>
                <p className="mt-2 text-sm leading-7 text-hsa-secondary">{p.body}</p>
              </Card>
            );
          })}
        </section>

        <Card>
          <div className="flex items-center gap-2">
            <Route size={18} className="text-hsa-gold" />
            <h2 className="text-lg font-bold text-hsa-black">Routing Endpoint</h2>
          </div>
          <pre
            dir="ltr"
            className="mt-4 overflow-x-auto rounded-xl border border-hsa-border bg-hsa-bg p-4 text-start text-xs leading-6 text-hsa-gold"
          >
            {`POST /v1/ops/models/route
{ task, sensitivity, require_local_only }`}
          </pre>
          <p className="mt-3 text-xs text-hsa-secondary">
            يُستقبل الطلب من بوابة التشغيل الداخلية فقط — لا يوجد مسار خارجي لهذه الواجهة.
          </p>
        </Card>
      </div>
    </AppShell>
  );
}
