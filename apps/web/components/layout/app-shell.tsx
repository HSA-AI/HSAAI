"use client";
import type React from "react";

import { useEffect, useState, useRef } from "react";
import { Menu, X } from "lucide-react";
import { Sidebar } from "./sidebar";
import { Topbar } from "./topbar";
import { MobileBottomNav } from "./mobile-bottom-nav";
import { PlatformFooter } from "./platform-footer";
import { CommandPalette } from "@/components/enterprise/command-palette";
import { Breadcrumbs } from "@/components/enterprise/breadcrumbs";

export function AppShell({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const drawer = useRef<HTMLElement>(null);

  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement as HTMLElement | null;
    drawer.current?.querySelector<HTMLElement>("button, a, input")?.focus();
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
      if (event.key !== "Tab") return;
      const items = Array.from(drawer.current?.querySelectorAll<HTMLElement>("button:not([disabled]), a[href], input, [tabindex='0']") || []);
      if (!items.length) return;
      const first = items[0], last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener("keydown", handleKey);
    return () => { document.removeEventListener("keydown", handleKey); previous?.focus(); };
  }, [open]);

  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  return (
    <div className="flex min-h-dvh overflow-x-hidden bg-hsa-bg text-hsa-black dark:bg-[#080808] dark:text-white">
      <a href="#main-content" className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:start-3 focus:z-[100] focus:rounded-lg focus:bg-hsa-yellow focus:p-3 focus:text-black">تجاوز إلى المحتوى</a>
      {open && <button className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm md:hidden" onClick={() => setOpen(false)} aria-label="إغلاق القائمة" />}

      <aside className="hidden md:block">
        <Sidebar />
      </aside>

      <aside ref={drawer} id="mobile-navigation" role="dialog" aria-modal={open || undefined} aria-label="القائمة الرئيسية" inert={!open} aria-hidden={!open} className={`fixed inset-y-0 start-0 z-50 w-[min(86vw,22rem)] transition-transform duration-300 md:hidden ${open ? "translate-x-0" : "ltr:-translate-x-full rtl:translate-x-full"}`}>
        <Sidebar onNavigate={() => setOpen(false)} mobile />
        <button className="absolute end-3 top-3 rounded-xl border border-hsa-border bg-white p-2 text-hsa-black shadow-hsa-card" onClick={() => setOpen(false)} aria-label="إغلاق القائمة">
          <X size={18} />
        </button>
      </aside>

      <main className="flex min-w-0 flex-1 flex-col">
        <Topbar menuButton={
          <button onClick={() => setOpen(true)} aria-expanded={open} aria-controls="mobile-navigation" className="flex h-11 w-11 items-center justify-center rounded-xl border border-hsa-border bg-white text-hsa-black md:hidden" aria-label="فتح القائمة">
            <Menu size={20} />
          </button>
        } />
        <div id="main-content" tabIndex={-1} className="flex-1 min-w-0 overflow-x-hidden p-3 pb-24 sm:p-4 sm:pb-24 lg:p-6 md:pb-6"><Breadcrumbs />{children}</div>
        <PlatformFooter />
        <CommandPalette />
        <MobileBottomNav />
      </main>
    </div>
  );
}
