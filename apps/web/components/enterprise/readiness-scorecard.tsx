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
  return <Card className="border-hsa-yellow/25"><div className="flex flex-wrap items-center justify-between gap-4"><div><p className="text-xs font-black uppercase tracking-widest text-hsa-gold">Enterprise Readiness</p><h2 className="text-2xl font-black">{score}% جاهزية مؤسسية</h2><p className="mt-1 text-sm text-slate-500">التقييم يعتمد على البنية، الأمان، التشغيل، UX، وقابلية الإنتاج.</p></div><div className="rounded-3xl bg-hsa-yellow px-6 py-4 text-3xl font-black text-hsa-black">{score}</div></div><div className="mt-5 grid gap-3 md:grid-cols-5">{controls.map(([area, value, detail]) => <div key={area} className="rounded-2xl border border-slate-200 p-3 dark:border-slate-800"><div className="flex items-center justify-between text-xs font-black"><span>{area}</span><span>{value}%</span></div><div className="mt-2 h-2 rounded-full bg-slate-100 dark:bg-slate-800"><div className="h-full rounded-full bg-hsa-yellow" style={{ width: `${value}%` }} /></div><p className="mt-2 text-xs text-slate-500">{detail}</p></div>)}</div></Card>;
}
