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
import { brand } from "@/lib/brand";

const quickActions = [
  { title: "محادثة جديدة", desc: "ابدأ بسؤال مباشر للمساعد", href: "/chat?new=1", icon: MessageSquarePlus, primary: true },
  { title: "رفع ملف", desc: "أضف مستندًا للمعرفة", href: "/knowledge", icon: FileUp },
  { title: "تلخيص مستند", desc: "احصل على ملخص تنفيذي", href: "/chat?new=1&template=summarize", icon: Sparkles },
  { title: "البحث في المعرفة", desc: "ابحث في ملفات المؤسسة", href: "/enterprise-search", icon: Search },
  { title: "إنشاء تقرير", desc: "صياغة تقرير للإدارة", href: "/chat?new=1&template=report", icon: BarChart3 },
  { title: "إدارة الصلاحيات", desc: "للمشرفين فقط", href: "/admin", icon: ShieldCheck },
];

const mainSections = [
  { title: "المساعد", desc: "المحادثة، القوالب، والوكلاء الذكيون في نقطة دخول واحدة.", href: "/chat?new=1", icon: Bot },
  { title: "المعرفة", desc: "ملفات المؤسسة، قواعد المعرفة، الفهرسة، والمصادر.", href: "/knowledge", icon: BookOpenText },
  { title: "البحث", desc: "بحث موحد وسهل عبر المستندات والمحادثات والمصادر.", href: "/enterprise-search", icon: Search },
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
    <main className="min-h-screen overflow-hidden bg-hsa-black text-white" dir="rtl">
      <div className="pointer-events-none fixed inset-0 opacity-80">
        <div className="absolute right-[-12rem] top-[-14rem] h-[36rem] w-[36rem] rounded-full bg-hsa-yellow/10 blur-3xl" />
        <div className="absolute bottom-[-16rem] left-[-14rem] h-[40rem] w-[40rem] rounded-full bg-hsa-gold/10 blur-3xl" />
      </div>

      <section className="relative mx-auto flex min-h-screen w-full max-w-7xl flex-col px-5 py-6 sm:px-8 lg:px-10">
        <header className="mb-8 flex flex-wrap items-center justify-between gap-5">
          <div className="flex items-center gap-4">
            <div className="flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-[1.25rem] border border-hsa-yellow/30 bg-hsa-yellow shadow-2xl shadow-hsa-yellow/20 sm:h-20 sm:w-20">
              <img src={brand.logoPath} alt="HSAAI Official Logo" className="h-full w-full object-cover" />
            </div>
            <div>
              <h1 className="text-3xl font-black tracking-tight sm:text-4xl">{brand.platformName}</h1>
              <p className="mt-1 text-sm font-semibold text-slate-300">{brand.platformSubtitleAr}</p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3 text-xs font-bold">
            <Link
              href="/chat?new=1"
              className="inline-flex items-center gap-2 rounded-full bg-hsa-yellow px-5 py-3 text-sm font-black text-hsa-black shadow-xl shadow-hsa-yellow/20 transition hover:-translate-y-0.5 hover:bg-hsa-gold"
              aria-label="فتح المساعد الذكي وبدء محادثة جديدة"
            >
              <img src={brand.assistant.iconPath} alt="HSAAI Enterprise Assistant" className="h-7 w-7 rounded-full object-cover ring-1 ring-black/10" />
              المساعد الذكي
            </Link>
            <span className="rounded-full border border-hsa-yellow/25 bg-hsa-yellow/10 px-4 py-2 text-hsa-yellow">Enterprise AI</span>
            <span className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-slate-300">Arabic RTL</span>
            <span className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-slate-300">Internal Only</span>
          </div>
        </header>

        <section className="grid flex-1 gap-8 lg:grid-cols-[1fr_23rem] lg:items-start">
          <div className="space-y-8">
            <div className="rounded-[2.25rem] border border-hsa-yellow/25 bg-white/[0.045] p-5 shadow-2xl shadow-black/40 backdrop-blur sm:p-8 lg:p-10">
              <div className="mx-auto max-w-4xl text-center">
                <div className="mx-auto mb-6 flex h-24 w-24 items-center justify-center overflow-hidden rounded-full border-4 border-hsa-yellow bg-black shadow-2xl shadow-hsa-yellow/20 sm:h-28 sm:w-28">
                  <img src={brand.assistant.iconPath} alt="HSAAI Enterprise Assistant" className="h-full w-full object-cover" />
                </div>
                <p className="text-sm font-black text-hsa-yellow">HSAAI Enterprise Assistant First Experience</p>
                <h2 className="mt-3 text-4xl font-black tracking-tight sm:text-5xl lg:text-6xl">كيف يمكنني مساعدتك اليوم؟</h2>
                <p className="mx-auto mt-4 max-w-2xl text-base leading-8 text-slate-300 sm:text-lg">
                  ابدأ بالمحادثة مباشرة، أو ارفع ملفًا، أو ابحث في معرفة المؤسسة — كل شيء من نقطة دخول واحدة سهلة للموظف والمدير والمشرف.
                </p>

                <div className="mx-auto mt-8 grid max-w-3xl gap-4 sm:grid-cols-[1fr_auto]">
                  <Link
                    href="/chat?new=1"
                    className="group flex items-center justify-between gap-4 rounded-[1.75rem] border border-hsa-yellow/40 bg-white px-5 py-4 text-right text-hsa-black shadow-2xl shadow-hsa-yellow/10 transition hover:-translate-y-0.5 hover:border-hsa-yellow sm:px-6 sm:py-5"
                    aria-label="بدء محادثة جديدة مع المساعد الذكي"
                  >
                    <span className="min-w-0">
                      <span className="block text-sm font-black text-slate-500">اسأل HSAAI</span>
                      <span className="mt-1 block truncate text-xl font-black sm:text-2xl">اكتب سؤالك أو افتح محادثة جديدة...</span>
                    </span>
                    <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-hsa-yellow text-hsa-black transition group-hover:bg-hsa-gold">
                      <ArrowLeft size={22} />
                    </span>
                  </Link>

                  <Link
                    href="/chat?new=1"
                    className="group flex min-w-[12rem] items-center justify-center gap-3 rounded-[1.75rem] border border-hsa-yellow bg-hsa-yellow px-6 py-4 text-base font-black text-hsa-black shadow-2xl shadow-hsa-yellow/20 transition hover:-translate-y-0.5 hover:bg-hsa-gold sm:py-5"
                    aria-label="فتح المساعد الذكي"
                  >
                    <img src={brand.assistant.iconPath} alt="HSAAI Enterprise Assistant" className="h-9 w-9 rounded-full object-cover ring-1 ring-black/10" />
                    المساعد الذكي
                  </Link>
                </div>
              </div>
            </div>

            <section>
              <div className="mb-4 flex items-end justify-between gap-4">
                <div>
                  <p className="text-sm font-black text-hsa-yellow">Quick Actions</p>
                  <h3 className="mt-1 text-2xl font-black">أسرع المهام استخدامًا</h3>
                </div>
                <Link href="/chat?new=1" className="hidden rounded-full bg-hsa-yellow px-4 py-2 text-sm font-black text-hsa-black hover:bg-hsa-gold sm:inline-flex">
                  محادثة جديدة
                </Link>
              </div>
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {quickActions.map((item) => {
                  const Icon = item.icon;
                  return (
                    <Link key={item.title} href={item.href} className={`group rounded-[1.5rem] border p-5 transition hover:-translate-y-0.5 ${item.primary ? "border-hsa-yellow/45 bg-hsa-yellow/15" : "border-white/10 bg-white/[0.035] hover:border-hsa-yellow/30 hover:bg-hsa-yellow/[0.06]"}`}>
                      <span className={`mb-4 flex h-11 w-11 items-center justify-center overflow-hidden rounded-2xl ${item.primary ? "bg-hsa-yellow text-hsa-black" : "bg-white/5 text-hsa-yellow"}`}>{item.primary ? <img src={brand.assistant.iconPath} alt="HSAAI Enterprise Assistant" className="h-full w-full rounded-2xl object-cover" /> : <Icon size={20} />}</span>
                      <strong className="block text-lg font-black">{item.title}</strong>
                      <span className="mt-1 block text-sm leading-6 text-slate-400">{item.desc}</span>
                    </Link>
                  );
                })}
              </div>
            </section>

            <section>
              <p className="text-sm font-black text-hsa-yellow">Main Navigation</p>
              <h3 className="mt-1 text-2xl font-black">هيكل مبسط من منظور المستخدم</h3>
              <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {mainSections.map((item) => {
                  const Icon = item.icon;
                  return (
                    <Link key={item.title} href={item.href} className="group rounded-[1.5rem] border border-white/10 bg-white/[0.035] p-5 transition hover:border-hsa-yellow/35 hover:bg-hsa-yellow/[0.055]">
                      <div className="flex items-start justify-between gap-4">
                        <span className="flex h-11 w-11 shrink-0 items-center justify-center overflow-hidden rounded-2xl bg-hsa-yellow/10 text-hsa-yellow">{item.title === "المساعد" ? <img src={brand.assistant.iconPath} alt="HSAAI Enterprise Assistant" className="h-full w-full rounded-2xl object-cover" /> : <Icon size={20} />}</span>
                        <ArrowLeft size={18} className="mt-2 text-slate-500 transition group-hover:-translate-x-1 group-hover:text-hsa-yellow" />
                      </div>
                      <h4 className="mt-4 text-xl font-black">{item.title}</h4>
                      <p className="mt-2 text-sm leading-7 text-slate-400">{item.desc}</p>
                    </Link>
                  );
                })}
              </div>
            </section>
          </div>

          <aside className="space-y-5 lg:sticky lg:top-6">
            <div className="rounded-[2rem] border border-hsa-yellow/30 bg-gradient-to-b from-hsa-yellow/15 to-white/[0.03] p-5 shadow-2xl shadow-black/40">
              <p className="text-sm font-black text-hsa-yellow">Recent Activity</p>
              <div className="mt-4 space-y-3">
                {recent.map((item) => (
                  <Link key={item} href="/chat" className="block rounded-2xl border border-white/10 bg-black/20 p-4 text-sm font-semibold text-slate-300 transition hover:border-hsa-yellow/30 hover:text-white">
                    {item}
                  </Link>
                ))}
              </div>
            </div>

            <div className="rounded-[2rem] border border-white/10 bg-white/[0.035] p-5">
              <p className="font-black text-white">User-first structure</p>
              <p className="mt-2 text-sm leading-7 text-slate-400">
                تم إخفاء المصطلحات التقنية عن المستخدم النهائي. تظهر الوظائف فقط: مساعد، معرفة، بحث، قيادة، إعدادات، إدارة.
              </p>
            </div>
          </aside>
        </section>
      </section>

      <Link
        href="/chat?new=1"
        className="fixed bottom-5 left-5 z-50 inline-flex items-center gap-3 rounded-full bg-hsa-yellow px-5 py-4 text-sm font-black text-hsa-black shadow-2xl shadow-hsa-yellow/25 transition hover:-translate-y-0.5 hover:bg-hsa-gold sm:hidden"
        aria-label="فتح المساعد الذكي من الزر العائم"
      >
        <img src={brand.assistant.iconPath} alt="HSAAI Enterprise Assistant" className="h-8 w-8 rounded-full object-cover" />
        المساعد الذكي
      </Link>
    </main>
  );
}
