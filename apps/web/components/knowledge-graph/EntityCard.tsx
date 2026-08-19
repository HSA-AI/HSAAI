import type { GraphEntity } from "./types";

export function EntityCard({ entity, onSelect }: { entity: GraphEntity; onSelect: (entity: GraphEntity) => void }) {
  return (
    <button onClick={() => onSelect(entity)} className="w-full rounded-2xl border border-hsa-yellow/20 bg-white p-4 text-start shadow-sm transition hover:border-hsa-yellow dark:bg-slate-950">
      <div className="flex items-center justify-between gap-3">
        <p className="font-black">{entity.name}</p>
        <span className="rounded-full bg-hsa-yellow/20 px-2 py-1 text-xs font-bold text-hsa-black dark:text-hsa-yellow">{entity.entity_type}</span>
      </div>
      <p className="mt-2 line-clamp-2 text-sm text-slate-600 dark:text-slate-300">{entity.description || entity.entity_key}</p>
      <p className="mt-3 text-xs text-slate-500">{entity.classification || "internal"} · {entity.visibility || "workspace"}</p>
    </button>
  );
}
