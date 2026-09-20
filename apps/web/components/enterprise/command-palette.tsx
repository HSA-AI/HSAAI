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
  return (
    <div className="fixed inset-0 z-[80] bg-black/50 p-3 backdrop-blur-sm" role="dialog" aria-modal="true" aria-label="Command Palette">
      <div className="mx-auto mt-20 max-w-2xl overflow-hidden rounded-2xl border border-hsa-border bg-white shadow-hsa-card-hover">
        <div className="flex items-center gap-3 border-b border-hsa-border p-4">
          <Search className="text-hsa-gold" size={18} />
          <input autoFocus value={query} onChange={(e) => setQuery(e.target.value)} placeholder="ابحث عن صفحة، وكيل، Workflow، أو إجراء سريع..." className="w-full bg-transparent text-sm outline-none" aria-label="بحث سريع" />
          <kbd className="rounded-lg border border-hsa-border px-2 py-1 text-xs text-hsa-secondary">Esc</kbd>
        </div>
        <div className="max-h-[60vh] overflow-y-auto p-3">
          <p className="mb-2 text-xs font-bold text-hsa-secondary">Quick Actions</p>
          <div className="grid gap-2 sm:grid-cols-2">
            {enterpriseQuickActions.map((action) => (
              <Link key={action.href} href={action.href} onClick={() => setOpen(false)} className="rounded-xl border border-hsa-border bg-white p-3 text-sm transition hover:border-hsa-gold/50 hover:bg-hsa-soft">
                <span className="flex items-center gap-2 font-bold text-hsa-black"><Zap size={15} className="text-hsa-gold" />{action.label}<kbd className="ms-auto rounded-md border border-hsa-border px-1.5 text-nano text-hsa-secondary">{action.shortcut}</kbd></span>
                <span className="mt-1 block text-xs text-hsa-secondary">{action.description}</span>
              </Link>
            ))}
          </div>
          <p className="mb-2 mt-5 text-xs font-bold text-hsa-secondary">Navigation</p>
          <div className="space-y-2">
            {results.map((item) => {
              const Icon = item.icon;
              return (
                <Link key={`${item.href}-${item.label}`} href={item.href} onClick={() => setOpen(false)} className="flex items-center gap-3 rounded-xl p-3 text-sm transition hover:bg-hsa-soft/60">
                  <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-hsa-soft text-hsa-gold"><Icon size={16} /></span>
                  <span className="min-w-0"><b className="block truncate text-hsa-black">{item.label}</b><span className="block truncate text-xs text-hsa-secondary">{item.hint}</span></span>
                </Link>
              );
            })}
          </div>
        </div>
        <div className="border-t border-hsa-border px-4 py-3 text-xs text-hsa-secondary">اضغط Ctrl/⌘ + K للفتح السريع. النتائج تخضع للصلاحيات عند ربط Keycloak.</div>
      </div>
    </div>
  );
}
