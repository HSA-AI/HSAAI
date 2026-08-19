"use client";
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Search, Zap } from "lucide-react";
import { enterpriseQuickActions, searchEnterpriseNavigation } from "@/lib/enterprise-navigation";

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const results = useMemo(() => searchEnterpriseNavigation(query).slice(0, 8), [query]);
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") { event.preventDefault(); setOpen((value) => !value); }
      if (event.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  if (!open) return null;
  return <div className="fixed inset-0 z-[80] bg-black/55 p-3 backdrop-blur-sm" role="dialog" aria-modal="true" aria-label="Command Palette"><div className="mx-auto mt-20 max-w-2xl overflow-hidden rounded-3xl border border-hsa-yellow/30 bg-white shadow-2xl dark:bg-slate-950"><div className="flex items-center gap-3 border-b border-slate-200 p-4 dark:border-slate-800"><Search className="text-hsa-gold" /><input autoFocus value={query} onChange={(e) => setQuery(e.target.value)} placeholder="ابحث عن صفحة، وكيل، Workflow، أو إجراء سريع..." className="w-full bg-transparent text-sm outline-none" aria-label="بحث سريع" /><kbd className="rounded-lg border px-2 py-1 text-xs text-slate-500">Esc</kbd></div><div className="max-h-[60vh] overflow-y-auto p-3"><p className="mb-2 text-xs font-black text-slate-500">Quick Actions</p><div className="grid gap-2 sm:grid-cols-2">{enterpriseQuickActions.map((action) => <Link key={action.href} href={action.href} onClick={() => setOpen(false)} className="rounded-2xl border border-slate-200 p-3 text-sm hover:border-hsa-yellow hover:bg-hsa-yellow/10 dark:border-slate-800"><span className="flex items-center gap-2 font-black"><Zap size={15} className="text-hsa-gold" />{action.label}<kbd className="mr-auto rounded-md border px-1.5 text-[10px]">{action.shortcut}</kbd></span><span className="mt-1 block text-xs text-slate-500">{action.description}</span></Link>)}</div><p className="mb-2 mt-5 text-xs font-black text-slate-500">Navigation</p><div className="space-y-2">{results.map((item) => { const Icon = item.icon; return <Link key={item.href} href={item.href} onClick={() => setOpen(false)} className="flex items-center gap-3 rounded-2xl p-3 text-sm hover:bg-slate-100 dark:hover:bg-white/5"><span className="flex h-9 w-9 items-center justify-center rounded-xl bg-hsa-yellow/15 text-hsa-gold"><Icon size={16} /></span><span><b>{item.label}</b><span className="block text-xs text-slate-500">{item.hint}</span></span></Link>; })}</div></div><div className="border-t border-slate-200 px-4 py-3 text-xs text-slate-500 dark:border-slate-800">اضغط Ctrl/⌘ + K للفتح السريع. النتائج تخضع للصلاحيات عند ربط Keycloak.</div></div></div>;
}
