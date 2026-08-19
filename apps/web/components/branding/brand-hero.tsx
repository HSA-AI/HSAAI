import { BrandMark } from "./brand-mark";
import { OfficialBadge } from "./official-badge";
import { brand } from "@/lib/brand";

export function BrandHero() {
  return (
    <section className="relative overflow-hidden rounded-[2rem] border border-hsa-yellow/30 bg-gradient-to-br from-hsa-yellow via-hsa-gold to-white p-8 text-hsa-black shadow-xl dark:from-hsa-black dark:via-slate-950 dark:to-slate-900 dark:text-white">
      <div className="absolute -left-20 -top-20 h-64 w-64 rounded-full bg-white/30 blur-3xl dark:bg-hsa-yellow/10" />
      <div className="absolute -bottom-24 right-20 h-72 w-72 rounded-full bg-hsa-black/10 blur-3xl dark:bg-hsa-yellow/10" />
      <div className="relative z-10 grid gap-8 lg:grid-cols-[1.1fr_.9fr] lg:items-center">
        <div className="space-y-5">
          <OfficialBadge />
          <div className="space-y-2">
            <h1 className="text-4xl font-black tracking-tight lg:text-5xl">{brand.platformName}</h1>
            <p className="max-w-2xl text-lg font-medium text-black/70 dark:text-white/70">{brand.platformSubtitleAr} التابعة لـ {brand.companyNameAr}، مصممة للعمل الداخلي الصارم، المعرفة المؤسسية، والوكلاء الذكيين.</p>
          </div>
          <div className="grid gap-3 text-sm font-semibold sm:grid-cols-3">
            <div className="rounded-2xl bg-white/70 p-4 dark:bg-white/10">Local LLM</div>
            <div className="rounded-2xl bg-white/70 p-4 dark:bg-white/10">Enterprise RAG</div>
            <div className="rounded-2xl bg-white/70 p-4 dark:bg-white/10">Zero Trust</div>
          </div>
        </div>
        <div className="rounded-[2rem] border border-black/10 bg-white/80 p-8 shadow-2xl backdrop-blur dark:border-white/10 dark:bg-black/40">
          <BrandMark />
          <div className="mt-6 space-y-3 text-sm text-black/70 dark:text-white/70">
            <p>نظام موحد للمحادثة الذكية، البحث في وثائق المؤسسة، إدارة الوكلاء، الحوكمة، والتشغيل الداخلي الآمن.</p>
            <p className="font-bold text-hsa-black dark:text-hsa-yellow">Official HSA Enterprise Experience</p>
          </div>
        </div>
      </div>
    </section>
  );
}
