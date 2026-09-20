import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { PageHeader } from "@/components/ui/page-header";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ReadinessScorecard } from "@/components/enterprise/readiness-scorecard";
import { enterpriseQuickActions } from "@/lib/enterprise-navigation";

const onboarding = [
  ["1", "اربط الهوية", "فعّل Keycloak/OIDC وحدد الأدوار والأقسام قبل إتاحة البيانات الحساسة."],
  ["2", "ابدأ بالمعرفة", "أنشئ Knowledge Space وارفع وثائق مصنفة ثم تحقق من الفهرسة في Qdrant."],
  ["3", "اختبر الوكلاء", "شغّل Supervisor Agent مع HR/Finance/IT وتأكد من Audit Logs والموافقات."],
  ["4", "فعّل البحث", "اختبر Enterprise Search مع الفلاتر والصلاحيات والمصادر والاستشهادات."],
  ["5", "راقب التشغيل", "راجع Observability وFinOps قبل توسيع الاستخدام داخل المؤسسة."],
] as const;

export default function GettingStartedPage() {
  return (
    <AppShell>
      <div className="space-y-6">
        <PageHeader
          eyebrow="HSAAI Enterprise AI Operating System"
          title="دليل البداية السريع"
          description="هذه الصفحة تجعل الوصول للمنصة واضحًا: ابدأ من الهوية، المعرفة، الوكلاء، البحث، ثم المراقبة والتكلفة. لا يتم إظهار أو تنفيذ أي إجراء حساس إلا من خلال الصلاحيات والموافقات."
          actions={<Badge tone="gold">Onboarding</Badge>}
        />

        <ReadinessScorecard />

        <section>
          <h2 className="hsa-section-title mb-4">
            خطوات التهيئة
            <span className="text-xs font-bold text-hsa-secondary">Onboarding Steps</span>
          </h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
            {onboarding.map(([step, title, text]) => (
              <Card key={step} hoverable>
                <span className="flex h-9 w-9 items-center justify-center rounded-full bg-hsa-yellow font-bold text-hsa-black">
                  {step}
                </span>
                <h3 className="mt-4 font-bold text-hsa-black">{title}</h3>
                <p className="mt-2 text-sm leading-7 text-hsa-secondary">{text}</p>
              </Card>
            ))}
          </div>
        </section>

        <section>
          <h2 className="hsa-section-title mb-4">
            اختصارات سريعة
            <span className="text-xs font-bold text-hsa-secondary">Quick Actions</span>
          </h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
            {enterpriseQuickActions.map((action) => (
              <Link
                key={action.href + action.label}
                href={action.href}
                className="group rounded-xl border border-hsa-border bg-white p-5 shadow-hsa-card transition-all duration-200 hover:-translate-y-1 hover:border-hsa-gold/40 hover:shadow-hsa-card-hover"
              >
                <div className="flex items-start justify-between gap-2">
                  <b className="font-bold text-hsa-black">{action.label}</b>
                  <ArrowLeft size={16} className="mt-1 shrink-0 text-hsa-border transition group-hover:-translate-x-1 group-hover:text-hsa-gold" />
                </div>
                <p className="mt-2 text-sm leading-7 text-hsa-secondary">{action.description}</p>
                <span className="mt-4 inline-flex items-center gap-1.5 rounded-full border border-hsa-yellow/30 bg-hsa-soft px-3 py-1 text-xs font-bold text-hsa-gold">
                  Shortcut {action.shortcut}
                </span>
              </Link>
            ))}
          </div>
        </section>
      </div>
    </AppShell>
  );
}
