import { AppShell } from "@/components/layout/app-shell";
import { PageHeader } from "@/components/ui/page-header";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { FileText, Search } from "lucide-react";

const docs = [
  ["Architecture", "ARCHITECTURE.md", "شرح طبقات المنصة والواجهات والخدمات وقواعد البيانات والتشغيل."],
  ["Enterprise Readiness", "ENTERPRISE_READINESS.md", "قائمة جاهزية المؤسسات ومعايير الإنتاج والحوكمة والأمان."],
  ["Operations", "docs/operations/RUNBOOK.md", "تشغيل، مراقبة، نسخ احتياطي، واستجابة للحوادث."],
  ["Security", "docs/security/SECURITY_GUIDE.md", "Zero Trust وRBAC وKeycloak ومراجعة الوصول."],
  ["Integrations", "docs/integrations/INTEGRATION_GUIDE.md", "إعداد SAP وAD وSharePoint وJira وREST APIs."],
] as const;

export default function DocumentationPage() {
  return (
    <AppShell>
      <div className="space-y-6">
        <PageHeader
          eyebrow="Documentation Workspace"
          title="توثيق HSAAI التشغيلي"
          description="روابط الوثائق الرئيسية داخل المشروع للمدير والمطور ومسؤول التشغيل والأمن."
        />

        {/* Search-style header */}
        <div
          aria-hidden="true"
          className="flex items-center gap-3 rounded-2xl border border-hsa-border bg-white px-4 py-3.5 shadow-hsa-card"
        >
          <Search size={18} className="shrink-0 text-hsa-gold" />
          <span className="truncate text-sm text-hsa-secondary">ابحث في التوثيق: Architecture، Security، Integrations، Runbook...</span>
          <Badge tone="gold" className="ms-auto hidden shrink-0 sm:inline-flex">5 Docs</Badge>
        </div>

        <section>
          <h2 className="hsa-section-title mb-4">
            الوثائق الرئيسية
            <span className="text-xs font-bold text-hsa-secondary">Core Documents</span>
          </h2>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {docs.map(([title, file, desc]) => (
              <Card key={file} hoverable>
                <div className="flex items-start justify-between gap-3">
                  <h2 className="font-bold text-hsa-black">{title}</h2>
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-hsa-soft text-hsa-gold">
                    <FileText size={16} />
                  </span>
                </div>
                <code dir="ltr" className="mt-3 block truncate rounded-xl border border-hsa-border bg-hsa-bg px-3 py-2 text-start text-xs text-hsa-gold">
                  {file}
                </code>
                <p className="mt-3 text-sm leading-7 text-hsa-secondary">{desc}</p>
                <Badge tone="neutral" className="mt-3">Markdown</Badge>
              </Card>
            ))}
          </div>
        </section>
      </div>
    </AppShell>
  );
}
