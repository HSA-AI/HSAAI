import { Card } from "@/components/ui/card";

const controls = [
  ["Architecture", 96, "Unified modules, services, docs"],
  ["Security", 91, "RBAC, Keycloak, audit, sensitive approvals"],
  ["AI Operations", 89, "Agent Mesh, RAG, monitoring, quality hooks"],
  ["UX", 92, "RTL/LTR, command palette, guided access"],
  ["Production", 86, "Docker/K8s/Helm ready; real connectors require credentials"],
] as const;

export function ReadinessScorecard() {
  const score = Math.round(controls.reduce((sum, [, value]) => sum + value, 0) / controls.length);
  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-widest text-hsa-gold">Enterprise Readiness</p>
          <h2 className="mt-1 text-2xl font-bold text-hsa-black">{score}% جاهزية مؤسسية</h2>
          <p className="mt-1 text-sm text-hsa-secondary">التقييم يعتمد على البنية، الأمان، التشغيل، UX، وقابلية الإنتاج.</p>
        </div>
        <div className="rounded-2xl bg-hsa-yellow px-6 py-4 text-3xl font-bold text-hsa-black shadow-hsa-gold">{score}</div>
      </div>
      <div className="mt-5 grid gap-3 md:grid-cols-5">
        {controls.map(([area, value, detail]) => (
          <div key={area} className="rounded-xl border border-hsa-border bg-white p-3">
            <div className="flex items-center justify-between text-xs font-bold text-hsa-black">
              <span>{area}</span>
              <span className="text-hsa-gold">{value}%</span>
            </div>
            <div className="mt-2 h-2 rounded-full bg-hsa-bg">
              <div className="h-full rounded-full bg-hsa-yellow" style={{ width: `${value}%` }} />
            </div>
            <p className="mt-2 text-micro leading-5 text-hsa-secondary">{detail}</p>
          </div>
        ))}
      </div>
    </Card>
  );
}
