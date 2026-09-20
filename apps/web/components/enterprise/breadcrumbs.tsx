"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronLeft, Home } from "lucide-react";
import { enterpriseNavItems } from "@/lib/enterprise-navigation";

export function Breadcrumbs() {
  const pathname = usePathname();
  const active = enterpriseNavItems.find((item) => {
    const base = item.href.split("?")[0];
    return pathname === base || pathname.startsWith(`${base}/`);
  });
  return (
    <nav aria-label="مسار الصفحة" className="mb-4 flex flex-wrap items-center gap-2 text-xs text-hsa-secondary">
      <Link href="/dashboard" className="inline-flex items-center gap-1 rounded-full border border-hsa-border bg-white px-3 py-1 font-bold text-hsa-black transition hover:border-hsa-gold/50 hover:bg-hsa-soft">
        <Home size={13} /> HSAAI
      </Link>
      <ChevronLeft size={14} className="text-hsa-border" />
      <span aria-current="page" className="rounded-full bg-hsa-soft px-3 py-1 font-bold text-hsa-gold">{active?.label ?? "Workspace"}</span>
    </nav>
  );
}
