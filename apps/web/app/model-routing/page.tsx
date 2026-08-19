
    import { AppShell } from "@/components/layout/app-shell";
    import { Card } from "@/components/ui/card";

    export default function Page() {
      return (
        <AppShell>
          <div className="space-y-6">
            <section className="rounded-[2rem] border border-hsa-yellow/20 bg-gradient-to-br from-black via-slate-950 to-black p-8 text-white shadow-hsa-glow">
              <p className="text-sm font-black uppercase tracking-[0.35em] text-hsa-yellow">Enterprise AI Operations Platform</p>
              <h1 className="mt-4 text-3xl font-black md:text-5xl">Model Routing Center</h1>
              <p className="mt-4 max-w-4xl text-sm leading-8 text-slate-300 md:text-base">طبقة اختيار نموذج محلي حسب نوع المهمة وحساسيتها مع منع أي توجيه خارجي في نمط HSAAI الداخلي.</p>
            </section>
            <section className="grid gap-4 md:grid-cols-3">
                  <div className="rounded-3xl border border-hsa-yellow/20 bg-hsa-yellow/5 p-5"><h3 className="font-black text-hsa-yellow">Local-Only Policy</h3><p className="mt-2 text-sm leading-7 text-slate-500 dark:text-slate-300">كل التوجيه يتم نحو Ollama المحلي فقط، بدون OpenAI أو Anthropic أو أي مزود خارجي.</p></div>
              <div className="rounded-3xl border border-hsa-yellow/20 bg-hsa-yellow/5 p-5"><h3 className="font-black text-hsa-yellow">Sensitivity Rules</h3><p className="mt-2 text-sm leading-7 text-slate-500 dark:text-slate-300">restricted/high → qwen2.5، low/general → llama3 أو النموذج الافتراضي المحلي.</p></div>
              <div className="rounded-3xl border border-hsa-yellow/20 bg-hsa-yellow/5 p-5"><h3 className="font-black text-hsa-yellow">Task-Aware Routing</h3><p className="mt-2 text-sm leading-7 text-slate-500 dark:text-slate-300">مهام Excel/SAP/Finance والسياسات العربية توجه للنموذج الأنسب محليًا.</p></div>
            </section>
            <Card><h2 className="text-xl font-black">Routing Endpoint</h2><pre className="mt-4 overflow-auto rounded-2xl bg-black p-5 text-xs text-hsa-yellow">{`POST /v1/ops/models/route
{ task, sensitivity, require_local_only }`}</pre></Card>
          </div>
        </AppShell>
      );
    }
