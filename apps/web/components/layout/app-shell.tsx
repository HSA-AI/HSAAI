"use client";
import type React from "react";

import { useEffect, useState } from "react";
import { Menu, X } from "lucide-react";
import { Sidebar } from "./sidebar";
import { Topbar } from "./topbar";
import { MobileBottomNav } from "./mobile-bottom-nav";
import { CommandPalette } from "@/components/enterprise/command-palette";
import { Breadcrumbs } from "@/components/enterprise/breadcrumbs";

export function AppShell({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  return (
    <div className="flex min-h-dvh overflow-x-hidden bg-slate-50 text-slate-950 dark:bg-hsa-black dark:text-white" dir="rtl">
      {open && <button className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm md:hidden" onClick={() => setOpen(false)} aria-label="إغلاق القائمة" />}

      <aside className="hidden md:block">
        <Sidebar />
      </aside>

      <aside className={`fixed inset-y-0 right-0 z-50 w-[min(86vw,22rem)] transition-transform duration-300 md:hidden ${open ? "translate-x-0" : "translate-x-full"}`}>
        <Sidebar onNavigate={() => setOpen(false)} mobile />
        <button className="absolute left-3 top-3 rounded-xl border border-white/10 bg-black/30 p-2 text-white" onClick={() => setOpen(false)} aria-label="إغلاق القائمة">
          <X size={18} />
        </button>
      </aside>

      <main className="flex min-w-0 flex-1 flex-col">
        <Topbar menuButton={
          <button onClick={() => setOpen(true)} className="flex h-11 w-11 items-center justify-center rounded-xl border border-slate-200 bg-white text-slate-900 dark:border-white/10 dark:bg-white/5 dark:text-white md:hidden" aria-label="فتح القائمة">
            <Menu size={20} />
          </button>
        } />
        <div className="flex-1 overflow-x-hidden p-3 pb-24 sm:p-4 sm:pb-24 lg:p-6 md:pb-6"><Breadcrumbs />{children}</div>
        <CommandPalette />
        <MobileBottomNav />
      </main>
    </div>
  );
}
