"use client";
import type React from "react";
import Link from "next/link";
import { useTheme } from "next-themes";
import { Bell, Moon, Sun, UserCircle, Search, ShieldCheck, MessageSquarePlus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { BrandMark } from "@/components/branding/brand-mark";

export function Topbar({ menuButton }: { menuButton?: React.ReactNode }) {
  const { theme, setTheme } = useTheme();
  return (
    <header className="sticky top-0 z-30 flex min-h-16 items-center justify-between gap-3 border-b border-hsa-yellow/20 bg-white/90 px-3 py-2 pt-[max(.5rem,env(safe-area-inset-top))] backdrop-blur dark:border-hsa-yellow/20 dark:bg-hsa-black/90 sm:px-4 lg:px-6">
      <div className="flex min-w-0 items-center gap-3 sm:gap-4">
        {menuButton}
        <div className="hidden sm:block md:hidden"><BrandMark compact /></div>
        <div className="min-w-0">
          <p className="truncate text-sm font-black text-slate-900 dark:text-white">HSAAI — المساعد الذكي المؤسسي</p>
          <p className="line-clamp-1 text-xs text-slate-500 dark:text-slate-400">محادثة، معرفة، بحث، تقارير، وإدارة في تجربة واحدة سهلة</p>
        </div>
      </div>
      {/* FIX-MEDIUM-LOW-FINAL: pointed href to existing route */}
      <Link href="/knowledge-hub" className="hidden min-w-[280px] items-center gap-2 rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-500 transition hover:border-hsa-yellow/40 hover:text-hsa-black lg:flex dark:border-slate-800 dark:bg-slate-900 dark:hover:text-hsa-yellow"><Search size={16} /> ابحث في المعرفة المؤسسية...</Link>
      <div className="flex shrink-0 items-center gap-1 sm:gap-2">
        <Link href="/chat?new=1" className="hidden items-center gap-2 rounded-full bg-hsa-yellow px-3 py-2 text-xs font-black text-hsa-black shadow-sm transition hover:bg-hsa-gold sm:flex"><MessageSquarePlus size={15} /> محادثة جديدة</Link>
        <div className="hidden items-center gap-2 rounded-full bg-hsa-soft px-3 py-1 text-xs font-bold text-hsa-black dark:bg-hsa-yellow/10 dark:text-hsa-yellow sm:flex"><ShieldCheck size={14} /> Internal</div>
        <Button className="h-10 w-10 bg-transparent p-0 text-slate-900 shadow-none dark:text-white" onClick={() => setTheme(theme === "dark" ? "light" : "dark")} aria-label="تبديل الوضع الداكن">
          {theme === "dark" ? <Sun size={19} /> : <Moon size={19} />}
        </Button>
        <Bell size={20} className="hidden sm:block" />
        <UserCircle size={24} />
      </div>
    </header>
  );
}
