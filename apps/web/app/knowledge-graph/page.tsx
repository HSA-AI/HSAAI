import Link from "next/link";
import { AppShell } from "@/components/layout/app-shell";
import { PageHeader } from "@/components/ui/page-header";
import { Badge } from "@/components/ui/badge";
import { KnowledgeGraphDashboard } from "@/components/knowledge-graph";

const goldLink =
  "inline-flex items-center justify-center rounded-xl bg-hsa-yellow px-4 py-2.5 text-sm font-bold text-hsa-black transition hover:bg-hsa-gold-dark hover:text-white";
const ghostLink =
  "inline-flex items-center justify-center rounded-xl border border-hsa-border bg-white px-4 py-2.5 text-sm font-bold text-hsa-black transition hover:border-hsa-gold/50 hover:bg-hsa-soft";

export default function Page() {
  return (
    <AppShell>
      <div className="space-y-6">
        <PageHeader
          eyebrow="HSAAI Enterprise AI Operating System"
          title="الرسم المعرفي المؤسسي"
          description="Knowledge Graph فعلي يربط المستندات، الكيانات، العلاقات، الوكلاء، المخاطر، السياسات، الصلاحيات، ونتائج RAG داخل طبقة واحدة قابلة للتوسع."
          actions={
            <>
              {/* FIX-MEDIUM-LOW-FINAL: pointed hrefs to existing routes */}
              <Link href="/enterprise-agents-center" className={goldLink}>
                الوكلاء
              </Link>
              <Link href="/knowledge-hub" className={ghostLink}>
                البحث المؤسسي
              </Link>
              <Link href="/enterprise-governance-center" className={ghostLink}>
                الحوكمة
              </Link>
            </>
          }
        />

        <KnowledgeGraphDashboard />

        <div className="flex justify-center">
          <Badge tone="neutral">Knowledge Graph · Entities · Relationships · Impact</Badge>
        </div>
      </div>
    </AppShell>
  );
}
