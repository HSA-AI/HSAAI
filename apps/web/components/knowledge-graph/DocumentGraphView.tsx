import type { GraphEntity } from "./types";

export function DocumentGraphView({ entities }: { entities: GraphEntity[] }) {
  const docs = entities.filter((entity) => entity.entity_type === "Document").slice(0, 6);
  return (
    <div className="rounded-2xl border border-hsa-yellow/20 bg-white p-5 shadow-sm dark:bg-slate-950">
      <p className="font-black">Document Knowledge Map</p>
      <div className="mt-4 space-y-3">
        {docs.map((doc) => <div key={doc.entity_key} className="rounded-xl bg-slate-50 p-3 text-sm dark:bg-slate-900"><p className="font-bold">{doc.name}</p><p className="mt-1 text-slate-500">{doc.source_ref || doc.entity_key}</p></div>)}
        {docs.length === 0 && <p className="text-sm text-slate-500">لا توجد مستندات مفهرسة في Graph حتى الآن.</p>}
      </div>
    </div>
  );
}
