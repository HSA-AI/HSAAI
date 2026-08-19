import type { GraphHealth } from "./types";

export function GraphStatsCards({ health }: { health: GraphHealth | null }) {
  const cards = [
    ["Entities", health?.entities ?? 0],
    ["Relationships", health?.relationships ?? 0],
    ["Documents", health?.documents ?? 0],
    ["Neo4j", health?.neo4j_configured ? "Ready" : "SQL Layer"],
  ];
  return <div className="grid gap-4 md:grid-cols-4">{cards.map(([label, value]) => <div key={label} className="rounded-2xl border border-hsa-yellow/20 bg-white p-5 shadow-sm dark:bg-slate-950"><p className="text-xs font-bold text-slate-500 dark:text-slate-400">{label}</p><p className="mt-2 text-2xl font-black text-hsa-black dark:text-hsa-yellow">{value}</p></div>)}</div>;
}
