import type { GraphEntity } from "./types";

export function EntityDetailsDrawer({ entity, onClose }: { entity: GraphEntity | null; onClose: () => void }) {
  if (!entity) return null;
  return (
    <aside className="fixed inset-y-0 left-0 z-50 w-full max-w-md border-r border-hsa-yellow/20 bg-white p-6 shadow-2xl dark:bg-slate-950" dir="rtl">
      <button onClick={onClose} className="rounded-xl border border-hsa-yellow/30 px-4 py-2 text-sm font-bold">إغلاق</button>
      <h2 className="mt-6 text-2xl font-black">{entity.name}</h2>
      <p className="mt-2 text-sm text-hsa-gold">{entity.entity_type}</p>
      <dl className="mt-6 space-y-4 text-sm">
        <div><dt className="font-black">Entity Key</dt><dd className="mt-1 break-all text-slate-600 dark:text-slate-300">{entity.entity_key}</dd></div>
        <div><dt className="font-black">Description</dt><dd className="mt-1 text-slate-600 dark:text-slate-300">{entity.description || "—"}</dd></div>
        <div><dt className="font-black">Source Citation</dt><dd className="mt-1 break-all text-slate-600 dark:text-slate-300">{entity.source_ref || "Manual / Seed"}</dd></div>
        <div><dt className="font-black">Permission Visibility</dt><dd className="mt-1 text-slate-600 dark:text-slate-300">{entity.visibility || "workspace"}</dd></div>
      </dl>
    </aside>
  );
}
