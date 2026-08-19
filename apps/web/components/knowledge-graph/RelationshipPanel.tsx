import type { GraphRelationship } from "./types";

export function RelationshipPanel({ relationships }: { relationships: GraphRelationship[] }) {
  return (
    <div className="rounded-2xl border border-hsa-yellow/20 bg-white p-5 shadow-sm dark:bg-slate-950">
      <p className="font-black">Relationship Explorer</p>
      <div className="mt-4 max-h-96 space-y-3 overflow-auto">
        {relationships.map((rel) => <div key={rel.relationship_key} className="rounded-xl bg-slate-50 p-3 text-sm dark:bg-slate-900"><p className="font-bold text-hsa-black dark:text-hsa-yellow">{rel.relationship_type}</p><p className="mt-1 break-all text-slate-600 dark:text-slate-300">{rel.source_key} → {rel.target_key}</p></div>)}
        {relationships.length === 0 && <p className="text-sm text-slate-500">لا توجد علاقات بعد.</p>}
      </div>
    </div>
  );
}
