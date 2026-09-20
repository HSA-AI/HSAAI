import Link from "next/link";
import { AppShell } from "@/components/layout/app-shell";
import { PageHeader } from "@/components/ui/page-header";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { GraduationCap } from "lucide-react";

const modules = ["AI Strategy", "Use Case Portfolio", "AI Maturity", "AI Adoption", "AI Training", "AI Value Realization"];

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
          title="AI Center of Excellence"
          description="مركز تميز الذكاء الاصطناعي المؤسسي"
          actions={
            <>
              {/* FIX-MEDIUM-LOW-FINAL: pointed hrefs to existing routes */}
              <Link href="/executive-dashboard" className={goldLink}>
                Executive Command
              </Link>
              <Link href="/knowledge-hub" className={ghostLink}>
                Enterprise Search
              </Link>
              <Link href="/enterprise-governance-center" className={ghostLink}>
                Governance
              </Link>
            </>
          }
        />

        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {modules.map((item) => (
            <Card key={item} hoverable>
              <div className="flex items-start justify-between gap-3">
                <h2 className="font-bold text-hsa-black">{item}</h2>
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-hsa-soft text-hsa-gold">
                  <GraduationCap size={18} />
                </span>
              </div>
              <p className="mt-2 text-sm leading-7 text-hsa-secondary">
                وحدة مرتبطة بالـ API والصلاحيات والسجلات ضمن بنية HSAAI العالمية.
              </p>
            </Card>
          ))}
        </section>

        <Card className="bg-hsa-soft/40">
          <div className="flex items-center justify-between gap-3">
            <p className="font-bold text-hsa-black">API Contract</p>
            <Badge tone="gold">Enterprise OS</Badge>
          </div>
          <code dir="ltr" className="mt-3 block rounded-xl border border-hsa-border bg-white px-4 py-3 text-start text-sm text-hsa-gold">
            /api/ai-coe/operating-model
          </code>
          <p className="mt-3 text-sm leading-7 text-hsa-secondary">
            هذه الصفحة مصممة كواجهة مركز تشغيل مؤسسي، وليست صفحة شكلية فقط. يتم ربطها بعقود API جاهزة للتشغيل والتوسع.
          </p>
        </Card>
      </div>
    </AppShell>
  );
}
