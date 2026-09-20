import { BrandMark } from "./brand-mark";
import { OfficialBadge } from "./official-badge";
import { brand } from "@/lib/brand";

/** Light enterprise hero — white card, gold top accent, official typography */
export function BrandHero() {
  return (
    <section className="relative overflow-hidden rounded-2xl border border-hsa-border bg-white shadow-hsa-card">
      <span aria-hidden className="absolute inset-x-0 top-0 h-1 bg-gradient-to-l from-hsa-yellow via-hsa-gold to-hsa-yellow" />
      <div className="grid gap-8 p-6 sm:p-8 lg:grid-cols-[1.1fr_.9fr] lg:items-center">
        <div className="space-y-4">
          <OfficialBadge />
          <div className="space-y-2">
            <h1 className="text-3xl font-bold tracking-tight text-hsa-black lg:text-4xl">{brand.platformName}</h1>
            <p className="max-w-2xl text-base font-semibold leading-8 text-hsa-secondary">
              {brand.platformFullNameAr} التابعة لـ{brand.companyNameAr} — مصممة للعمل الداخلي الصارم، المعرفة المؤسسية، والوكلاء الذكيين بأعلى معايير الأمان.
            </p>
          </div>
          <div className="grid gap-2 text-xs font-bold sm:grid-cols-3">
            <div className="rounded-xl border border-hsa-border bg-hsa-bg px-4 py-3 text-hsa-black">Local LLM</div>
            <div className="rounded-xl border border-hsa-border bg-hsa-bg px-4 py-3 text-hsa-black">Enterprise RAG</div>
            <div className="rounded-xl border border-hsa-border bg-hsa-bg px-4 py-3 text-hsa-black">Zero Trust</div>
          </div>
        </div>
        <div className="rounded-2xl border border-hsa-border bg-hsa-bg p-6">
          <BrandMark />
          <div className="mt-4 space-y-2 text-sm leading-7 text-hsa-secondary">
            <p>نظام موحد للمحادثة الذكية، البحث في وثائق المؤسسة، إدارة الوكلاء، الحوكمة، والتشغيل الداخلي الآمن.</p>
            <p className="font-bold text-hsa-gold">Official HSA Enterprise Experience</p>
          </div>
        </div>
      </div>
    </section>
  );
}
