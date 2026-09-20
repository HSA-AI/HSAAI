import type React from "react";
import { AlertTriangle, Inbox, Loader2 } from "lucide-react";

/** HSAAI Empty / Loading / Error states — unified Design System states */

export function EmptyState({ title, description, action }: { title: string; description: string; action?: React.ReactNode }) {
  return (
    <div className="rounded-2xl border-2 border-dashed border-hsa-border bg-white p-10 text-center">
      <span className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-hsa-soft text-hsa-gold"><Inbox size={26} /></span>
      <h2 className="text-lg font-bold text-hsa-black">{title}</h2>
      <p className="mx-auto mt-2 max-w-xl text-sm leading-7 text-hsa-secondary">{description}</p>
      {action ? <div className="mt-5 flex justify-center">{action}</div> : null}
    </div>
  );
}

export function LoadingState({ label = "جارٍ تحميل بيانات HSAAI..." }: { label?: string }) {
  return (
    <div role="status" aria-live="polite" className="flex min-h-40 items-center justify-center rounded-2xl border border-hsa-border bg-white text-sm font-bold text-hsa-secondary">
      <Loader2 className="me-2 animate-spin text-hsa-gold" size={18} />
      {label}
    </div>
  );
}

export function ErrorState({ title = "تعذر تحميل البيانات", description, action }: { title?: string; description: string; action?: React.ReactNode }) {
  return (
    <div role="alert" className="rounded-2xl border border-red-200 bg-red-50 p-5 text-red-900">
      <div className="flex items-center gap-2 font-bold"><AlertTriangle size={18} />{title}</div>
      <p className="mt-2 text-sm leading-7">{description}</p>
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}
