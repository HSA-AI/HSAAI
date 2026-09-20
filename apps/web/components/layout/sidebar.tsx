"use client";
import Image from "next/image";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTranslation } from "react-i18next";
import { BrandMark } from "@/components/branding/brand-mark";
import { OfficialBadge } from "@/components/branding/official-badge";
import { brand } from "@/lib/brand";
import { enterpriseNavItems, enterpriseNavSections } from "@/lib/enterprise-navigation";

const visibleSections = enterpriseNavSections.filter((section) => enterpriseNavItems.some((item) => item.section === section.key));

export function Sidebar({ onNavigate, mobile = false }: { onNavigate?: () => void; mobile?: boolean }) {
  const pathname = usePathname();
  const { i18n } = useTranslation();
  const isArabic = (i18n.language || "ar").startsWith("ar");

  const isActive = (href: string) => {
    const base = href.split("?")[0];
    return pathname === base || pathname.startsWith(`${base}/`);
  };

  return (
    <aside className={`${mobile ? "flex h-dvh w-full" : "flex h-dvh w-72"} shrink-0 flex-col overflow-hidden border-e border-hsa-border bg-white p-4 pb-[calc(1rem+env(safe-area-inset-bottom))]`}>
      {/* Brand header — official logo, untouchable proportions */}
      <div className="mb-5 rounded-2xl border border-hsa-border bg-white p-4 shadow-hsa-card">
        <BrandMark />
        <div className="mt-3"><OfficialBadge /></div>
      </div>

      <Link
        href="/chat?new=1"
        onClick={onNavigate}
        className="mb-4 flex items-center justify-center gap-2 rounded-xl bg-hsa-yellow px-4 py-3 text-sm font-semibold text-hsa-black transition hover:bg-hsa-gold-dark hover:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-hsa-gold/60 focus-visible:ring-offset-2"
      >
        <Image unoptimized width={512} height={512} src={brand.assistant.iconPath} alt="HSAAI Assistant" className="h-7 w-7 rounded-full object-cover" />
        {isArabic ? "محادثة جديدة" : "New Chat"}
      </Link>

      <nav className="min-h-0 flex-1 space-y-5 overflow-y-auto overscroll-contain pe-1" aria-label={isArabic ? "التنقل الرئيسي في HSAAI" : "HSAAI main navigation"}>
        {visibleSections.map((section) => (
          <div key={section.key}>
            <p className="mb-2 px-2 text-micro font-semibold uppercase tracking-wider text-hsa-secondary">
              {isArabic ? section.title : section.titleEn}
            </p>
            <div className="space-y-1">
              {enterpriseNavItems.filter((item) => item.section === section.key).map((item) => {
                const Icon = item.icon;
                const active = isActive(item.href);
                return (
                  <Link
                    key={`${item.href}-${item.label}`}
                    href={item.href}
                    onClick={onNavigate}
                    aria-current={active ? "page" : undefined}
                    className={`group flex min-h-11 items-center gap-3 rounded-xl px-3 py-2 text-sm font-semibold transition focus:outline-none focus-visible:ring-2 focus-visible:ring-hsa-gold/60 ${
                      active
                        ? "border border-hsa-yellow/40 bg-hsa-soft text-hsa-gold"
                        : item.primary
                          ? "border border-hsa-yellow/35 bg-hsa-soft/60 text-hsa-black hover:bg-hsa-soft hover:text-hsa-gold"
                          : "border border-transparent text-hsa-black hover:bg-hsa-soft/70 hover:text-hsa-gold"
                    }`}
                  >
                    <span className={`flex h-9 w-9 shrink-0 items-center justify-center overflow-hidden rounded-lg transition ${
                      active ? "bg-hsa-yellow text-hsa-black" : item.primary ? "bg-hsa-soft text-hsa-gold" : "bg-hsa-bg text-hsa-secondary group-hover:bg-hsa-soft group-hover:text-hsa-gold"
                    }`}>
                      {item.primary ? <Image unoptimized width={512} height={512} src={brand.assistant.iconPath} alt="HSAAI Assistant" className="h-full w-full rounded-lg object-cover" /> : <Icon size={17} />}
                    </span>
                    <span className="min-w-0">
                      <span className="block leading-5">{isArabic ? item.label : item.labelEn}</span>
                      <span className="block truncate text-micro font-medium text-hsa-secondary">{item.hint}</span>
                    </span>
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      <div className="mt-4 rounded-xl border border-hsa-border bg-hsa-bg p-3.5 text-xs">
        <p className="font-semibold text-hsa-black">HSAAI Enterprise OS</p>
        <p className="mt-1 leading-5 text-hsa-secondary">Agent Mesh · RAG · Governance · FinOps · Integrations</p>
      </div>
    </aside>
  );
}
