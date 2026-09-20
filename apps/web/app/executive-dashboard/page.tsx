import { BarChart3, Bot, Briefcase, FileSearch, Gauge, ShieldCheck, TrendingUp, Zap } from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { PageHeader } from "@/components/ui/page-header";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { KpiCard } from "@/components/ui/kpi-card";

const kpis = [
  { label: "العائد على الاستثمار ROI", value: "×4.6", delta: "+18%", hint: "قيمة موفرة مقابل كلفة التشغيل", icon: <TrendingUp size={20} /> },
  { label: "الأثر على الأعمال", value: "4,280", hint: "ساعة عمل موفرة تقديرياً", icon: <Briefcase size={20} /> },
  { label: "تبنّي الذكاء الاصطناعي", value: "84%", delta: "+9%", hint: "أعلى الإدارات استخداماً", icon: <Bot size={20} /> },
  { label: "الكفاءة التشغيلية", value: "1,366", hint: "إجراء مؤتمت خلال الفترة", icon: <Zap size={20} /> },
  { label: "المخاطر والحوكمة", value: "98%", hint: "وثائق مصنفة ومراجعة", icon: <ShieldCheck size={20} /> },
  { label: "الأداء العام", value: "97%", hint: "صحة تشغيلية مستقرة", icon: <Gauge size={20} /> },
] as const;

const impact = [
  { value: "68K", label: "طلب AI", hint: "إجمالي الاستخدام" },
  { value: "3,240", label: "مستخدم نشط", hint: "داخل المؤسسة" },
  { value: "18,720", label: "وثيقة مفهرسة", hint: "معرفة معتمدة" },
] as const;

const headers = ["المؤشر", "القيمة", "الدلالة"];
const rows = [
  ["نسبة إجابات من المعرفة", "91%", "اعتماد أعلى على مصادر المؤسسة"],
  ["حوكمة الوثائق", "98%", "وثائق مصنفة ومراجعة"],
  ["الصحة التشغيلية", "97%", "استقرار عام"],
  ["إجراءات مؤتمتة", "1,366", "تحسن الكفاءة"],
  ["تبنّي تقنية المعلومات", "84%", "أعلى الإدارات استخداماً"],
];

export default function Page() {
  return (
    <AppShell>
      <div className="mx-auto max-w-7xl space-y-8">
        <PageHeader
          eyebrow="HSAAI Enterprise Operations"
          title="لوحة القيادة التنفيذية"
          description="لوحة تنفيذية للإدارة العليا تعرض أثر HSAAI على الاستخدام، المعرفة، الأتمتة، الكفاءة، وتبنّي الإدارات للذكاء الاصطناعي."
          actions={<Badge tone="ok" className="px-3 py-1.5 text-xs">Operational Ready</Badge>}
        />

        <section aria-label="مؤشرات تنفيذية" className="grid grid-cols-2 gap-4 lg:grid-cols-3">
          {kpis.map((k) => (
            <KpiCard key={k.label} label={k.label} value={<span dir="ltr">{k.value}</span>} delta={"delta" in k ? k.delta : undefined} hint={k.hint} icon={k.icon} />
          ))}
        </section>

        <section>
          <h2 className="hsa-section-title mb-4">
            الأثر على الأعمال
            <span className="text-xs font-bold text-hsa-secondary">Business Impact</span>
          </h2>
          <Card hoverable>
            <div className="grid gap-6 sm:grid-cols-3">
              {impact.map((item) => (
                <div key={item.label} className="flex flex-col items-center gap-1 rounded-xl border border-hsa-border bg-hsa-bg px-4 py-6 text-center">
                  <strong className="text-4xl font-bold leading-none text-hsa-gold"><span dir="ltr">{item.value}</span></strong>
                  <span className="mt-2 text-sm font-bold text-hsa-black">{item.label}</span>
                  <span className="text-xs text-hsa-secondary">{item.hint}</span>
                </div>
              ))}
            </div>
            <p className="mt-5 flex items-center gap-2 text-sm leading-7 text-hsa-secondary">
              <BarChart3 size={16} className="shrink-0 text-hsa-gold" aria-hidden />
              أرقام تشغيلية تراكمية تعكس حجم الاعتماد على HSAAI داخل بيئة HSA الداخلية.
            </p>
          </Card>
        </section>

        <section>
          <Card>
            <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
              <h2 className="hsa-section-title">تفاصيل التشغيل</h2>
              <Badge tone="gold"><FileSearch size={12} aria-hidden /> مؤشرات معتمدة داخلياً</Badge>
            </div>
            <div className="overflow-x-auto">
              <table className="hsa-table min-w-[640px]">
                <thead>
                  <tr>{headers.map((h) => <th key={h}>{h}</th>)}</tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r[0]}>
                      <td className="font-bold">{r[0]}</td>
                      <td><span dir="ltr" className="text-lg font-bold text-hsa-gold">{r[1]}</span></td>
                      <td className="text-hsa-secondary">{r[2]}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </section>
      </div>
    </AppShell>
  );
}
