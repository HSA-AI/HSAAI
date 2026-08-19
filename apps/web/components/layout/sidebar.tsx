import Link from "next/link";
import { BrandMark } from "@/components/branding/brand-mark";
import { OfficialBadge } from "@/components/branding/official-badge";
import { brand } from "@/lib/brand";
import { enterpriseNavItems, enterpriseNavSections } from "@/lib/enterprise-navigation";

const visibleSections = enterpriseNavSections.filter((section) => enterpriseNavItems.some((item) => item.section === section.key));

export function Sidebar({ onNavigate, mobile = false }: { onNavigate?: () => void; mobile?: boolean }) {
  return (
    <aside className={`${mobile ? "flex h-dvh w-full" : "flex h-dvh w-80"} shrink-0 flex-col overflow-hidden border-l border-hsa-yellow/20 bg-white p-4 pb-[calc(1rem+env(safe-area-inset-bottom))] dark:border-hsa-yellow/20 dark:bg-hsa-black`}>
      <div className="mb-5 rounded-[1.75rem] border border-hsa-yellow/25 bg-gradient-to-br from-hsa-yellow to-hsa-soft p-4 shadow-hsa-glow dark:from-hsa-black dark:to-slate-950 dark:ring-1 dark:ring-hsa-yellow/25">
        <BrandMark />
        <div className="mt-4"><OfficialBadge /></div>
      </div>

      <Link
        href="/chat?new=1"
        onClick={onNavigate}
        className="mb-4 flex items-center justify-center gap-2 rounded-2xl bg-hsa-yellow px-4 py-3 text-sm font-black text-hsa-black shadow-lg shadow-hsa-yellow/20 transition hover:-translate-y-0.5 hover:bg-hsa-gold focus:outline-none focus:ring-2 focus:ring-hsa-yellow focus:ring-offset-2 dark:focus:ring-offset-hsa-black"
      >
        <img src={brand.assistant.iconPath} alt="HSAAI Enterprise Assistant" className="h-7 w-7 rounded-full object-cover" /> محادثة جديدة
      </Link>

      <nav className="min-h-0 flex-1 space-y-5 overflow-y-auto overscroll-contain pr-1" aria-label="التنقل الرئيسي في HSAAI">
        {visibleSections.map((section) => (
          <div key={section.key}>
            <p className="mb-2 px-2 text-[11px] font-black uppercase tracking-wider text-slate-400">{section.title}</p>
            <div className="space-y-1.5">
              {enterpriseNavItems.filter((item) => item.section === section.key).map((item) => {
                const Icon = item.icon;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={onNavigate}
                    className={`group flex min-h-12 items-center gap-3 rounded-2xl px-3 py-2.5 text-sm font-bold transition active:scale-[.99] focus:outline-none focus:ring-2 focus:ring-hsa-yellow/70 ${
                      item.primary
                        ? "border border-hsa-yellow/35 bg-hsa-yellow/10 text-hsa-black hover:bg-hsa-yellow dark:text-hsa-yellow dark:hover:text-hsa-black"
                        : "text-slate-700 hover:bg-hsa-soft hover:text-hsa-black dark:text-slate-200 dark:hover:bg-hsa-yellow/10 dark:hover:text-hsa-yellow"
                    }`}
                  >
                    <span className={`flex h-9 w-9 items-center justify-center overflow-hidden rounded-xl ${item.primary ? "bg-hsa-yellow text-hsa-black" : "bg-slate-100 text-slate-700 dark:bg-white/5 dark:text-hsa-yellow"}`}>
                      {item.primary ? <img src={brand.assistant.iconPath} alt="HSAAI Enterprise Assistant" className="h-full w-full rounded-xl object-cover" /> : <Icon size={17} />}
                    </span>
                    <span className="min-w-0">
                      <span className="block leading-5">{item.label}</span>
                      <span className="block truncate text-[11px] font-medium text-slate-500 dark:text-slate-400">{item.hint}</span>
                    </span>
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      <div className="mt-4 rounded-2xl border border-hsa-yellow/20 bg-hsa-soft/80 p-4 text-xs text-hsa-black dark:bg-slate-950 dark:text-slate-300">
        <p className="font-black text-hsa-black dark:text-hsa-yellow">Enterprise OS</p>
        <p className="mt-1 text-slate-600 dark:text-slate-400">Agent Mesh · RAG · Governance · FinOps · Integrations</p>
      </div>
    </aside>
  );
}
