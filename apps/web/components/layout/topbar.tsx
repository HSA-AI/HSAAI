"use client";

import type React from "react";
import Link from "next/link";
import { useTheme } from "next-themes";
import { Bell, Moon, Sun, UserCircle, Search, ShieldCheck, MessageSquarePlus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { BrandMark } from "@/components/branding/brand-mark";
import { LanguageSwitcher } from "@/components/i18n/language-switcher";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/lib/auth-provider";

export function Topbar({ menuButton }: { menuButton?: React.ReactNode }) {
  const { theme, setTheme } = useTheme();
  const { i18n, t } = useTranslation();
  const isArabic = (i18n.language || "ar").startsWith("ar");
  const { user } = useAuth();

  return (
    <header className="sticky top-0 z-30 flex min-h-16 items-center justify-between gap-3 border-b border-hsa-border bg-white/90 px-3 py-2 pt-[max(.5rem,env(safe-area-inset-top))] backdrop-blur sm:px-4 lg:px-6">
      <div className="flex min-w-0 items-center gap-3 sm:gap-4">
        {menuButton}
        <div className="hidden sm:block"><BrandMark compact /></div>
        <div className="min-w-0">
          <p className="truncate text-sm font-bold text-hsa-black">
            {isArabic ? "HSAAI — منصة التشغيل الذكي المؤسسية" : "HSAAI — Enterprise AI Platform"}
          </p>
          <p className="line-clamp-1 hidden text-xs text-hsa-secondary sm:block">
            {isArabic
              ? "محادثة، معرفة، بحث، تقارير، وإدارة في تجربة واحدة موحدة"
              : "Chat, knowledge, search, reports and admin in one unified experience"}
          </p>
        </div>
      </div>

      <Link
        href="/knowledge-hub"
        className="hidden min-w-[260px] items-center gap-2 rounded-xl border border-hsa-border bg-hsa-bg px-3 py-2 text-sm text-hsa-secondary transition hover:border-hsa-gold/50 hover:text-hsa-black lg:flex"
      >
        <Search size={16} /> {isArabic ? "ابحث في المعرفة المؤسسية..." : "Search enterprise knowledge..."}
      </Link>

      <div className="flex shrink-0 items-center gap-1 sm:gap-2">
        <Link
          href="/chat?new=1"
          className="hidden items-center gap-2 rounded-xl bg-hsa-yellow px-3 py-2 text-xs font-bold text-hsa-black transition hover:bg-hsa-gold-dark hover:text-white sm:flex"
        >
          <MessageSquarePlus size={15} /> {isArabic ? "محادثة جديدة" : "New Chat"}
        </Link>

        <div className="hidden items-center gap-1.5 rounded-full bg-hsa-soft px-3 py-1 text-xs font-bold text-hsa-gold md:flex">
          <ShieldCheck size={14} /> Internal
        </div>

        <LanguageSwitcher />

        <Button
          variant="ghost"
          className="h-10 w-10 p-0"
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          aria-label={isArabic ? "تبديل الوضع الداكن" : "Toggle dark mode"}
        >
          {theme === "dark" ? <Sun size={19} /> : <Moon size={19} />}
        </Button>

        <button
          type="button"
          className="relative flex h-10 w-10 items-center justify-center rounded-xl text-hsa-black transition hover:bg-hsa-soft"
          aria-label={t("common.notifications", "الإشعارات")}
        >
          <Bell size={19} />
          <span aria-hidden className="absolute end-2.5 top-2.5 h-1.5 w-1.5 rounded-full bg-hsa-gold" />
        </button>

        <button
          type="button"
          className="flex min-h-10 items-center gap-2 rounded-xl px-1.5 transition hover:bg-hsa-soft"
          aria-label={isArabic ? "الملف الشخصي" : "User profile"}
        >
          <UserCircle size={24} className="text-hsa-secondary" />
          {user?.username || user?.preferred_username ? (
            <span className="hidden max-w-[8rem] truncate text-xs font-bold text-hsa-black xl:block">
              {user.username || user.preferred_username}
            </span>
          ) : null}
        </button>
      </div>
    </header>
  );
}
