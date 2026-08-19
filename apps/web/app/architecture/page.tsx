import { AppShell } from "@/components/layout/app-shell";
import { Card } from "@/components/ui/card";

const layers = [
  { title: "User Experience", items: ["Next.js Web", "HSAAI Chat", "Executive Dashboard", "HTML Preview"] },
  { title: "Access & Security", items: ["Keycloak", "RBAC", "JWT", "Audit Logs"] },
  { title: "AI Control Plane", items: ["API Gateway", "Backend Core", "AI Orchestrator", "Agent Router"] },
  { title: "Knowledge & RAG", items: ["Document Loaders", "Chunking", "Embeddings", "Qdrant", "Citations"] },
  { title: "Local LLM", items: ["Ollama", "Model Registry", "Prompt Templates", "Streaming"] },
  { title: "Enterprise Integrations", items: ["SAP", "Active Directory", "HR Systems", "Workflow Engine"] },
  { title: "Infrastructure", items: ["Docker Compose", "Kubernetes", "Helm", "Monitoring"] },
];

export default function ArchitecturePage() {
  return (
    <AppShell>
      <main className="space-y-6">
        <section>
          <p className="text-sm font-bold text-hsa-yellow">Architecture Center</p>
          <h1 className="text-3xl font-black">خريطة معمارية لمنصة HSAAI</h1>
          <p className="mt-2 max-w-4xl text-slate-500">تعرض هذه الصفحة الطبقات الفعلية للمشروع حتى لا تظهر المنصة كلوحة بسيطة، بل كنظام ذكاء اصطناعي مؤسسي كامل.</p>
        </section>

        <section className="grid gap-4 lg:grid-cols-7">
          {layers.map((layer, index) => (
            <Card key={layer.title} className="relative border-hsa-yellow/20">
              <span className="grid h-9 w-9 place-items-center rounded-full bg-hsa-yellow font-black text-black">{index + 1}</span>
              <h2 className="mt-4 text-lg font-bold">{layer.title}</h2>
              <ul className="mt-3 space-y-2 text-xs text-slate-500">
                {layer.items.map((item) => <li key={item} className="rounded-xl bg-slate-100 p-2 dark:bg-slate-950">{item}</li>)}
              </ul>
            </Card>
          ))}
        </section>

        <Card>
          <h2 className="text-lg font-bold">End-to-End Request Flow</h2>
          <div className="mt-4 grid gap-3 md:grid-cols-6">
            {["User", "API Gateway", "Backend Core", "Orchestrator", "RAG / Agents", "Ollama / Response"].map((step, i) => (
              <div key={step} className="rounded-2xl border border-slate-200 p-4 text-center dark:border-slate-800">
                <div className="mx-auto mb-3 grid h-10 w-10 place-items-center rounded-full bg-hsa-yellow font-black text-black">{i + 1}</div>
                <b className="text-sm">{step}</b>
              </div>
            ))}
          </div>
        </Card>
      </main>
    </AppShell>
  );
}
