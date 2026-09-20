"use client";
import Image from "next/image";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BookOpenText, LayoutDashboard, BarChart3, Settings } from "lucide-react";
import { brand } from "@/lib/brand";

/* FIX: previous links pointed to /knowledge and /enterprise-search which do
   not exist as routes (404). Now mapped to real pages. */
const items = [
  { href: "/chat?new=1", base: "/chat", label: "المساعد", assistant: true, Icon: null },
  { href: "/knowledge-hub", base: "/knowledge-hub", label: "المعرفة", assistant: false, Icon: BookOpenText },
  { href: "/dashboard", base: "/dashboard", label: "القيادة", assistant: false, Icon: LayoutDashboard },
  { href: "/executive-dashboard", base: "/executive-dashboard", label: "التنفيذية", assistant: false, Icon: BarChart3 },
  { href: "/settings", base: "/settings", label: "الإعدادات", assistant: false, Icon: Settings },
] as const;

export function MobileBottomNav() {
  const pathname = usePathname();
  return (
    <nav className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-5 border-t border-hsa-border bg-white/95 px-2 pb-[max(.5rem,env(safe-area-inset-bottom))] pt-2 text-micro font-bold text-hsa-secondary backdrop-blur md:hidden" aria-label="تنقل الهاتف">
      {items.map(({ href, base, label, assistant, Icon }) => {
        const active = pathname === base || pathname.startsWith(`${base}/`);
        return (
          <Link
            key={base}
            href={href}
            aria-current={active ? "page" : undefined}
            className={`flex flex-col items-center gap-1 rounded-xl px-1 py-1.5 transition ${
              active ? "bg-hsa-soft text-hsa-gold" : "hover:bg-hsa-soft/60 hover:text-hsa-gold"
            }`}
          >
            {assistant ? (
              <Image unoptimized width={512} height={512} src={brand.assistant.iconPath} alt="HSAAI Assistant" className="h-6 w-6 rounded-full object-cover" />
            ) : Icon ? (
              <Icon size={18} />
            ) : null}
            <span>{label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
