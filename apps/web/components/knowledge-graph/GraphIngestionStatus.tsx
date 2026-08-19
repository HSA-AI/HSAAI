import type { GraphHealth } from "./types";

export function GraphIngestionStatus({ health, onSeed }: { health: GraphHealth | null; onSeed: () => void }) {
  return (
    <div className="rounded-2xl border border-hsa-yellow/20 bg-hsa-soft/60 p-5 dark:bg-slate-900">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="font-black">Graph Ingestion Status</p>
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">Last ingestion: {health?.last_ingestion?.source_ref || "none"}</p>
        </div>
        <button onClick={onSeed} className="rounded-xl border border-hsa-yellow/40 px-4 py-2 font-bold">Seed مؤسسي تجريبي</button>
      </div>
    </div>
  );
}
