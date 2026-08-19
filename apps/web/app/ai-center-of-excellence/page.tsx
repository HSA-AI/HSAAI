import Link from "next/link";

const modules = ['AI Strategy', 'Use Case Portfolio', 'AI Maturity', 'AI Adoption', 'AI Training', 'AI Value Realization'];

export default function Page() {
  return (
    <main className="min-h-dvh bg-slate-50 p-6 text-slate-900 dark:bg-hsa-black dark:text-white" dir="rtl">
      <section className="mx-auto max-w-7xl space-y-6">
        <div className="rounded-[2rem] border border-hsa-yellow/30 bg-white p-8 shadow-sm dark:bg-slate-950">
          <p className="text-sm font-bold text-hsa-gold">HSAAI Enterprise AI Operating System</p>
          <h1 className="mt-3 text-3xl font-black">AI Center of Excellence</h1>
          <p className="mt-2 text-lg text-slate-600 dark:text-slate-300">مركز تميز الذكاء الاصطناعي المؤسسي</p>
          <div className="mt-5 flex flex-wrap gap-3">
            {/* FIX-MEDIUM-LOW-FINAL: pointed hrefs to existing routes */}
            <Link href="/executive-dashboard" className="rounded-xl bg-hsa-yellow px-4 py-2 font-black text-hsa-black">Executive Command</Link>
            <Link href="/knowledge-hub" className="rounded-xl border border-hsa-yellow/30 px-4 py-2 font-bold">Enterprise Search</Link>
            <Link href="/enterprise-governance-center" className="rounded-xl border border-hsa-yellow/30 px-4 py-2 font-bold">Governance</Link>
          </div>
        </div>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {modules.map((item) => (
            <div key={item} className="rounded-2xl border border-hsa-yellow/20 bg-white p-5 shadow-sm dark:bg-slate-950">
              <p className="font-black text-hsa-black dark:text-hsa-yellow">{item}</p>
              <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">وحدة مرتبطة بالـ API والصلاحيات والسجلات ضمن بنية HSAAI العالمية.</p>
            </div>
          ))}
        </div>
        <div className="rounded-2xl border border-hsa-yellow/20 bg-hsa-soft/60 p-5 text-sm dark:bg-slate-900">
          <p className="font-black">API Contract</p>
          <code className="mt-2 block rounded-xl bg-black/80 p-3 text-left text-white" dir="ltr">/api/ai-coe/operating-model</code>
          <p className="mt-3 text-slate-600 dark:text-slate-300">هذه الصفحة مصممة كواجهة مركز تشغيل مؤسسي، وليست صفحة شكلية فقط. يتم ربطها بعقود API جاهزة للتشغيل والتوسع.</p>
        </div>
      </section>
    </main>
  );
}
