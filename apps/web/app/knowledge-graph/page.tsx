import Link from "next/link";
import { KnowledgeGraphDashboard } from "@/components/knowledge-graph";

export default function Page() {
  return (
    <main className="min-h-dvh bg-slate-50 p-6 text-slate-900 dark:bg-hsa-black dark:text-white" dir="rtl">
      <section className="mx-auto max-w-7xl space-y-6">
        <div className="rounded-[2rem] border border-hsa-yellow/30 bg-white p-8 shadow-sm dark:bg-slate-950">
          <p className="text-sm font-bold text-hsa-gold">HSAAI Enterprise AI Operating System</p>
          <h1 className="mt-3 text-3xl font-black">الرسم المعرفي المؤسسي</h1>
          <p className="mt-2 max-w-3xl text-lg text-slate-600 dark:text-slate-300">Knowledge Graph فعلي يربط المستندات، الكيانات، العلاقات، الوكلاء، المخاطر، السياسات، الصلاحيات، ونتائج RAG داخل طبقة واحدة قابلة للتوسع.</p>
          <div className="mt-5 flex flex-wrap gap-3">
            {/* FIX-MEDIUM-LOW-FINAL: pointed hrefs to existing routes */}
            <Link href="/enterprise-agents-center" className="rounded-xl bg-hsa-yellow px-4 py-2 font-black text-hsa-black">الوكلاء</Link>
            <Link href="/knowledge-hub" className="rounded-xl border border-hsa-yellow/30 px-4 py-2 font-bold">البحث المؤسسي</Link>
            <Link href="/enterprise-governance-center" className="rounded-xl border border-hsa-yellow/30 px-4 py-2 font-bold">الحوكمة</Link>
          </div>
        </div>
        <KnowledgeGraphDashboard />
      </section>
    </main>
  );
}
