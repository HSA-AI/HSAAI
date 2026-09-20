import { AppShell } from "@/components/layout/app-shell";
import { PageHeader } from "@/components/ui/page-header";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { HelpCircle, Search } from "lucide-react";

const faqs = [
  ["كيف أبدأ؟", "استخدم صفحة Getting Started ثم فعّل الهوية والصلاحيات والمعرفة قبل فتح الاستخدام الواسع."],
  ["هل يمكن ربط SAP وSharePoint؟", "نعم، مركز التكاملات يحتوي Mock Mode وطبقة إعداد جاهزة، أما الربط الإنتاجي فيحتاج بيانات اتصال وصلاحيات المؤسسة."],
  ["هل الوكلاء ينفذون قرارات حساسة مباشرة؟", "لا. الإجراءات الحساسة تمر عبر Human-in-the-Loop Approval Engine وسجل تدقيق."],
  ["كيف يتم التحكم في الوصول للوثائق؟", "يعتمد البحث والاسترجاع على Keycloak/RBAC وتصنيف الوثيقة والقسم والـ tenant/workspace."],
] as const;

const topics = ["البداية السريعة", "الصلاحيات والوصول", "المعرفة والبحث", "الوكلاء والموافقات", "التكاملات"];

export default function HelpCenterPage() {
  return (
    <AppShell>
      <div className="space-y-6">
        <PageHeader
          eyebrow="Internal Help Center"
          title="مركز المساعدة داخل HSAAI"
          description="إجابات مختصرة تساعد المستخدمين والمدراء والمشرفين على استخدام المنصة بأمان ووضوح."
        />

        {/* Search-style header */}
        <div
          aria-hidden="true"
          className="flex items-center gap-3 rounded-2xl border border-hsa-border bg-white px-4 py-3.5 shadow-hsa-card"
        >
          <Search size={18} className="shrink-0 text-hsa-gold" />
          <span className="truncate text-sm text-hsa-secondary">ابحث في مركز المساعدة: السياسات، الصلاحيات، الوكلاء، التكاملات...</span>
          <Badge tone="gold" className="ms-auto hidden shrink-0 sm:inline-flex">Ctrl + K</Badge>
        </div>

        {/* Topic chips */}
        <div className="flex flex-wrap gap-2">
          {topics.map((topic) => (
            <span key={topic} className="hsa-badge">
              <HelpCircle size={13} />
              {topic}
            </span>
          ))}
        </div>

        <section>
          <h2 className="hsa-section-title mb-4">
            الأسئلة الشائعة
            <span className="text-xs font-bold text-hsa-secondary">FAQ</span>
          </h2>
          <div className="grid gap-4 md:grid-cols-2">
            {faqs.map(([q, a]) => (
              <Card key={q} hoverable>
                <div className="flex items-start justify-between gap-3">
                  <h3 className="font-bold text-hsa-black">{q}</h3>
                  <Badge tone="gold" className="shrink-0">سؤال شائع</Badge>
                </div>
                <p className="mt-2 text-sm leading-7 text-hsa-secondary">{a}</p>
              </Card>
            ))}
          </div>
        </section>
      </div>
    </AppShell>
  );
}
