import type { GraphEntity, GraphRelationship } from "./types";

export function KnowledgeGraphCanvas({ entities, relationships }: { entities: GraphEntity[]; relationships: GraphRelationship[] }) {
  const visible = entities.slice(0, 12);
  return (
    <div className="rounded-2xl border border-hsa-yellow/20 bg-white p-5 shadow-sm dark:bg-slate-950">
      <div className="flex items-center justify-between gap-3">
        <p className="font-black">Graph Overview</p>
        <span className="text-xs text-slate-500">{visible.length} nodes · {relationships.length} edges</span>
      </div>
      <div className="mt-5 grid min-h-80 gap-3 md:grid-cols-3">
        {visible.map((entity, index) => (
          <div key={entity.entity_key} className="rounded-2xl border border-hsa-yellow/20 bg-slate-50 p-4 dark:bg-slate-900" style={{ transform: `translateY(${(index % 3) * 8}px)` }}>
            <p className="text-xs font-bold text-hsa-gold">{entity.entity_type}</p>
            <p className="mt-1 font-black">{entity.name}</p>
            <p className="mt-2 line-clamp-2 text-xs text-slate-500">{entity.entity_key}</p>
          </div>
        ))}
        {visible.length === 0 && <p className="text-sm text-slate-500">اضغط Seed أو ارفع مستندًا لبدء بناء الرسم المعرفي.</p>}
      </div>
    </div>
  );
}
