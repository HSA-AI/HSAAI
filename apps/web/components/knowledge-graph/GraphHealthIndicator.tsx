import type { GraphHealth } from "./types";

export function GraphHealthIndicator({ health }: { health: GraphHealth | null }) {
  const ok = health?.status === "ok";
  return (
    <div className="rounded-2xl border border-hsa-yellow/20 bg-white p-5 shadow-sm dark:bg-slate-950">
      <div className="flex items-center justify-between gap-3">
        <p className="font-black">Health Status</p>
        <span className={`rounded-full px-3 py-1 text-xs font-black ${ok ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"}`}>{health?.status || "loading"}</span>
      </div>
      <p className="mt-3 text-sm text-slate-600 dark:text-slate-300">Engine: {health?.engine || "checking"}</p>
      <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">Graph RAG Bridge: {health?.graph_rag_bridge_enabled ? "Enabled" : "Pending"}</p>
    </div>
  );
}
