import type React from "react";
import { AlertTriangle, Inbox, Loader2 } from "lucide-react";

export function EmptyState({ title, description, action }: { title: string; description: string; action?: React.ReactNode }) {
  return <div className="rounded-3xl border border-dashed border-hsa-yellow/40 bg-white/70 p-8 text-center dark:bg-slate-950/70"><Inbox className="mx-auto mb-3 text-hsa-gold" /><h2 className="text-lg font-black">{title}</h2><p className="mx-auto mt-2 max-w-xl text-sm text-slate-500">{description}</p>{action ? <div className="mt-5">{action}</div> : null}</div>;
}

export function LoadingState({ label = "جاري تحميل بيانات HSAAI..." }: { label?: string }) {
  return <div className="flex min-h-40 items-center justify-center rounded-3xl border border-slate-200 bg-white/70 text-sm font-bold text-slate-500 dark:border-slate-800 dark:bg-slate-950/70"><Loader2 className="ml-2 animate-spin" size={18} />{label}</div>;
}

export function ErrorState({ title = "تعذر تحميل البيانات", description }: { title?: string; description: string }) {
  return <div role="alert" className="rounded-3xl border border-red-200 bg-red-50 p-5 text-red-900 dark:border-red-900/40 dark:bg-red-950/30 dark:text-red-200"><div className="flex items-center gap-2 font-black"><AlertTriangle size={18} />{title}</div><p className="mt-2 text-sm">{description}</p></div>;
}
