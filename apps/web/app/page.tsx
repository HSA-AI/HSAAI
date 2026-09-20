"use client";
import Image from "next/image";

import Link from "next/link";
import {
  ArrowLeft,
  BarChart3,
  Bot,
  BookOpenText,
  FileUp,
  MessageSquarePlus,
  Search,
  Settings,
  ShieldCheck,
  Sparkles,
  UsersRound,
} from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { Card } from "@/components/ui/card";
import { KpiCard } from "@/components/ui/kpi-card";
import { OfficialBadge } from "@/components/branding/official-badge";
import { brand } from "@/lib/brand";

const quickActions = [
  { title: "محادثة جديدة", desc: "ابدأ بسؤال مباشر للمساعد", href: "/chat?new=1", icon: MessageSquarePlus, primary: true },
  { title: "رفع ملف", desc: "أضف مستنداً للمعرفة", href: "/knowledge-hub", icon: FileUp },
  { title: "تلخيص مستند", desc: "احصل على ملخص تنفيذي", href: "/chat?new=1&template=summarize", icon: Sparkles },
  { title: "البحث في المعرفة", desc: "ابحث في ملفات المؤسسة", href: "/knowledge-hub", icon: Search },
  { title: "إنشاء تقرير", desc: "صياغة تقرير للإدارة", href: "/chat?new=1&template=report", icon: BarChart3 },
  { title: "إدارة الصلاحيات", desc: "للمشرفين فقط", href: "/admin", icon: ShieldCheck },
];

const mainSections = [
  { title: "المساعد", desc: "المحادثة، القوالب، والوكلاء الذكيون في نقطة دخول واحدة.", href: "/chat?new=1", icon: Bot },
  { title: "المعرفة", desc: "ملفات المؤسسة، قواعد المعرفة، الفهرسة، والمصادر.", href: "/knowledge-hub", icon: BookOpenText },
  { title: "البحث", desc: "بحث موحد وسهل عبر المستندات والمحادثات والمصادر.", href: "/knowledge-hub", icon: Search },
  { title: "لوحة القيادة", desc: "مؤشرات الاستخدام والتبني والتقارير التنفيذية.", href: "/dashboard", icon: BarChart3 },
  { title: "الإعدادات", desc: "اللغة، المظهر، الخصوصية، وتفضيلات الحساب.", href: "/settings", icon: Settings },
  { title: "الإدارة", desc: "المستخدمون، الأدوار، السياسات، المراقبة، والسجلات.", href: "/admin", icon: UsersRound },
];

const recent = [
  "تلخيص سياسة الموارد البشرية",
  "بحث عن إجراءات المشتريات",
  "تقرير تنفيذي عن استخدام الذكاء الاصطناعي",
];

export default function Page() {
  return (
    <AppShell>
      <div className="mx-auto max-w-7xl space-y-8">
        {/* Hero — light enterprise panel with gold accent */}
        <section className="relative overflow-hidden rounded-2xl border border-hsa-border bg-white p-6 shadow-hsa-card sm:p-10">
          <span aria-hidden className="absolute inset-x-0 top-0 h-1 bg-gradient-to-l from-hsa-yellow via-hsa-gold to-hsa-yellow" />
          <div className="flex flex-col items-center gap-6 text-center">
            <div className="flex h-24 w-24 items-center justify-center overflow-hidden rounded-full border-4 border-hsa-yellow bg-white shadow-hsa-gold sm:h-28 sm:w-28">
              <Image unoptimized width={512} height={512} src={brand.assistant.iconPath} alt="HSAAI Assistant" className="h-full w-full object-cover" />
            </div>
            <div className="max-w-3xl space-y-3">
              <OfficialBadge />
              <p className="text-sm font-semibold text-hsa-gold" dir="ltr">HSAAI Assistant First Experience</p>
              <h1 className="text-display font-bold text-hsa-black">كيف يمكنني مساعدتك اليوم؟</h1>
              <p className="mx-auto max-w-2xl text-sm leading-8 text-hsa-secondary sm:text-base">
                ابدأ بالمحادثة مباشرة، أو ارفع ملفاً، أو ابحث في معرفة المؤسسة — كل شيء من نقطة دخول واحدة سهلة للموظف والمدير والمشرف.
              </p>
            </div>

            <div className="grid w-full max-w-3xl gap-3 sm:grid-cols-[1fr_auto]">
              <Link
                href="/chat?new=1"
                className="group flex items-center justify-between gap-4 rounded-xl border border-hsa-border bg-white px-5 py-4 text-start shadow-hsa-card transition hover:-translate-y-0.5 hover:border-hsa-gold/50 hover:shadow-hsa-card-hover"
                aria-label="بدء محادثة جديدة مع المساعد الذكي"
              >
                <span className="min-w-0">
                  <span className="block text-xs font-bold text-hsa-secondary">اسأل HSAAI</span>
                  <span className="mt-1 block truncate text-lg font-bold text-hsa-black sm:text-xl">اكتب سؤالك أو افتح محادثة جديدة...</span>
                </span>
                <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-hsa-yellow text-hsa-black transition group-hover:bg-hsa-gold-dark group-hover:text-white">
                  <ArrowLeft size={22} />
                </span>
              </Link>

              <Link
                href="/chat?new=1"
                className="group flex min-w-[12rem] items-center justify-center gap-3 rounded-xl bg-hsa-yellow px-6 py-4 text-base font-bold text-hsa-black transition hover:-translate-y-0.5 hover:bg-hsa-gold-dark hover:text-white"
                aria-label="فتح المساعد الذكي"
              >
                <Image unoptimized width={512} height={512} src={brand.assistant.iconPath} alt="HSAAI Assistant" className="h-9 w-9 rounded-full object-cover" />
                المساعد الذكي
              </Link>
            </div>
          </div>
        </section>

        {/* Platform stats — official figures from the design reference */}
        <section aria-label="مؤشرات المنصة" className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {brand.stats.map((s) => (
            <KpiCard key={s.labelAr} label={s.labelAr} value={s.value} hint={s.labelEn} />
          ))}
        </section>

        {/* Quick actions */}
        <section>
          <div className="hsa-section-title mb-4">
            أسرع المهام استخداماً
            <span className="text-xs font-bold text-hsa-secondary">Quick Actions</span>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {quickActions.map((item) => {
              const Icon = item.icon;
              return (
                <Link
                  key={item.title}
                  href={item.href}
                  className={`group rounded-xl border p-5 shadow-hsa-card transition hover:-translate-y-1 hover:shadow-hsa-card-hover ${
                    item.primary ? "border-hsa-yellow/45 bg-hsa-soft/70" : "border-hsa-border bg-white hover:border-hsa-gold/40"
                  }`}
                >
                  <span className={`mb-3 flex h-11 w-11 items-center justify-center rounded-xl ${item.primary ? "bg-hsa-yellow text-hsa-black" : "bg-hsa-soft text-hsa-gold"}`}>
                    {item.primary ? <Image unoptimized width={512} height={512} src={brand.assistant.iconPath} alt="HSAAI Assistant" className="h-full w-full rounded-xl object-cover" /> : <Icon size={20} />}
                  </span>
                  <strong className={`block text-base font-bold ${item.primary ? "text-hsa-gold" : "text-hsa-black"}`}>{item.title}</strong>
                  <span className="mt-1 block text-sm leading-6 text-hsa-secondary">{item.desc}</span>
                </Link>
              );
            })}
          </div>
        </section>

        {/* Main sections */}
        <section>
          <div className="hsa-section-title mb-4">
            هيكل مبسط من منظور المستخدم
            <span className="text-xs font-bold text-hsa-secondary">Main Navigation</span>
          </div>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {mainSections.map((item) => {
              const Icon = item.icon;
              return (
                <Link key={item.title} href={item.href} className="group rounded-xl border border-hsa-border bg-white p-5 shadow-hsa-card transition hover:-translate-y-1 hover:border-hsa-gold/40 hover:shadow-hsa-card-hover">
                  <div className="flex items-start justify-between gap-4">
                    <span className="flex h-11 w-11 shrink-0 items-center justify-center overflow-hidden rounded-xl bg-hsa-soft text-hsa-gold">
                      {item.title === "المساعد" ? <Image unoptimized width={512} height={512} src={brand.assistant.iconPath} alt="HSAAI Assistant" className="h-full w-full rounded-xl object-cover" /> : <Icon size={20} />}
                    </span>
                    <ArrowLeft size={18} className="mt-2 text-hsa-border transition group-hover:-translate-x-1 group-hover:text-hsa-gold" />
                  </div>
                  <h3 className="mt-4 text-lg font-bold text-hsa-black">{item.title}</h3>
                  <p className="mt-2 text-sm leading-7 text-hsa-secondary">{item.desc}</p>
                </Link>
              );
            })}
          </div>
        </section>

        {/* Recent activity */}
        <section>
          <div className="hsa-section-title mb-4">النشاط الأخير</div>
          <Card>
            <div className="grid gap-3 sm:grid-cols-3">
              {recent.map((item) => (
                <Link key={item} href="/chat" className="rounded-xl border border-hsa-border bg-hsa-bg p-4 text-sm font-semibold text-hsa-black transition hover:border-hsa-gold/50 hover:bg-hsa-soft">
                  {item}
                </Link>
              ))}
            </div>
          </Card>
        </section>
      </div>
    </AppShell>
  );
}
