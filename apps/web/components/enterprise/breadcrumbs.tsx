"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronLeft, Home } from "lucide-react";
import { enterpriseNavItems } from "@/lib/enterprise-navigation";

export function Breadcrumbs() {
  const pathname = usePathname();
  const active = enterpriseNavItems.find((item) => pathname === item.href || pathname.startsWith(`${item.href}/`));
  return <nav aria-label="مسار الصفحة" className="mb-4 flex flex-wrap items-center gap-2 text-xs text-slate-500"><Link href="/dashboard" className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white px-3 py-1 font-bold hover:border-hsa-yellow dark:border-slate-800 dark:bg-slate-950"><Home size={13} /> HSAAI</Link><ChevronLeft size={14} /> <span className="rounded-full bg-hsa-yellow/10 px-3 py-1 font-bold text-hsa-black dark:text-hsa-yellow">{active?.label ?? "Workspace"}</span></nav>;
}
