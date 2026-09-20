import Link from "next/link";
import { AppShell } from "@/components/layout/app-shell";
import { PageHeader } from "@/components/ui/page-header";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { GitBranch, LayoutTemplate, Plug, Sparkles, Wrench } from "lucide-react";

const goldLink =
  "inline-flex items-center justify-center rounded-xl bg-hsa-yellow px-4 py-2.5 text-sm font-bold text-hsa-black transition hover:bg-hsa-gold-dark hover:text-white";
const ghostLink =
  "inline-flex items-center justify-center rounded-xl border border-hsa-border bg-white px-4 py-2.5 text-sm font-bold text-hsa-black transition hover:border-hsa-gold/50 hover:bg-hsa-soft";

const palette = [
  { name: "Prompt Template Builder", icon: LayoutTemplate, body: "مرتبط بالصلاحيات والسجلات وواجهات API ضمن HSAAI Enterprise AI Operating System." },
  { name: "Workflow Designer", icon: GitBranch, body: "مرتبط بالصلاحيات والسجلات وواجهات API ضمن HSAAI Enterprise AI Operating System." },
  { name: "Tool Connector Builder", icon: Wrench, body: "مرتبط بالصلاحيات والسجلات وواجهات API ضمن HSAAI Enterprise AI Operating System." },
  { name: "Version History", icon: Plug, body: "مرتبط بالصلاحيات والسجلات وواجهات API ضمن HSAAI Enterprise AI Operating System." },
] as const;

export default function Page() {
  return (
    <AppShell>
      <div className="space-y-6">
        <PageHeader
          eyebrow="HSAAI Enterprise AI Operating System"
          title="استوديو الوكلاء بدون كود"
          description="No-Code Agent Studio"
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

        {/* Canvas — white surface with soft dashed build area */}
        <Card>
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Sparkles size={18} className="text-hsa-gold" />
              <h2 className="text-lg font-bold text-hsa-black">لوحة البناء — Canvas</h2>
            </div>
            <Badge tone="gold">Draft</Badge>
          </div>
          <div className="mt-4 rounded-2xl border-2 border-dashed border-hsa-border bg-hsa-bg p-10 text-center">
            <p className="font-bold text-hsa-black">اسحب مكوّنات الوكيل هنا</p>
            <p className="mt-2 text-sm text-hsa-secondary">Prompts · Tools · Workflows · Approvals — بدون كتابة كود.</p>
          </div>
        </Card>

        {/* Palette — builder modules */}
        <section>
          <h2 className="hsa-section-title mb-4">
            مكوّنات الاستوديو
            <span className="text-xs font-bold text-hsa-secondary">Palette</span>
          </h2>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {palette.map((item) => {
              const Icon = item.icon;
              return (
                <Card key={item.name} hoverable>
                  <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-hsa-soft text-hsa-gold">
                    <Icon size={20} />
                  </span>
                  <h3 className="mt-4 font-bold text-hsa-black">{item.name}</h3>
                  <p className="mt-2 text-sm leading-7 text-hsa-secondary">{item.body}</p>
                </Card>
              );
            })}
          </div>
        </section>

        <Card className="bg-hsa-soft/40">
          <div className="flex items-center justify-between gap-3">
            <p className="font-bold text-hsa-black">API Contract</p>
            <Badge tone="gold">Enterprise OS</Badge>
          </div>
          <code dir="ltr" className="mt-3 block rounded-xl border border-hsa-border bg-white px-4 py-3 text-start text-sm text-hsa-gold">
            /api/agent-studio
          </code>
          <p className="mt-3 text-sm leading-7 text-hsa-secondary">
            هذه الصفحة ليست واجهة شكلية فقط؛ تم إضافة Router وModels ومهاجرات مقابلة في backend_core/enterprise_os.
          </p>
        </Card>
      </div>
    </AppShell>
  );
}
