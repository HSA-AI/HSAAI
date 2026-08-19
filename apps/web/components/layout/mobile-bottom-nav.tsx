import Link from "next/link";
import { Bot, BookOpenText, Search, BarChart3, MoreHorizontal } from "lucide-react";
import { brand } from "@/lib/brand";

const items = [
  ["/chat?new=1", "المساعد", Bot],
  ["/knowledge", "المعرفة", BookOpenText],
  ["/enterprise-search", "البحث", Search],
  ["/dashboard", "القيادة", BarChart3],
  ["/settings", "المزيد", MoreHorizontal],
] as const;

export function MobileBottomNav() {
  return (
    <nav className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-5 border-t border-hsa-yellow/20 bg-white/95 px-2 pb-[max(.5rem,env(safe-area-inset-bottom))] pt-2 text-xs font-bold text-slate-600 backdrop-blur md:hidden dark:bg-hsa-black/95 dark:text-slate-300" aria-label="تنقل الهاتف">
      {items.map(([href, label, Icon]) => (
        <Link key={href} href={href} className="flex flex-col items-center gap-1 rounded-xl px-1 py-1.5 hover:bg-hsa-yellow/10 hover:text-hsa-yellow">
          {label === "المساعد" ? <img src={brand.assistant.iconPath} alt="HSAAI Enterprise Assistant" className="h-6 w-6 rounded-full object-cover" /> : <Icon size={18} />}
          <span>{label}</span>
        </Link>
      ))}
    </nav>
  );
}
