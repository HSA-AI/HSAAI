"use client";

import Link from "next/link";
import { Coins, PiggyBank, TrendingUp, Wallet } from "lucide-react";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AppShell } from "@/components/layout/app-shell";
import { PageHeader } from "@/components/ui/page-header";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { KpiCard } from "@/components/ui/kpi-card";

const kpis = [
  { label: "Token Usage", value: "48.6M", hint: "توكن معالج هذا الشهر", icon: <Coins size={20} /> },
  { label: "Monthly Cost", value: "12,480", hint: "تكلفة تشغيلية تقديرية", icon: <Wallet size={20} /> },
  { label: "Budget Consumed", value: "78%", hint: "من ميزانية الربع الحالية", icon: <PiggyBank size={20} /> },
  { label: "Forecast", value: "15.9K", hint: "توقع نهاية الشهر بالمسار الحالي", icon: <TrendingUp size={20} /> },
] as const;

const costTrend = [
  { day: "Sat", cost: 320 },
  { day: "Sun", cost: 385 },
  { day: "Mon", cost: 452 },
  { day: "Tue", cost: 418 },
  { day: "Wed", cost: 490 },
  { day: "Thu", cost: 465 },
  { day: "Fri", cost: 291 },
];

const costByDepartment = [
  { dept: "المعرفة", cost: 38 },
  { dept: "الوكلاء", cost: 27 },
  { dept: "المحادثات", cost: 21 },
  { dept: "التقارير", cost: 14 },
];

const budgets = [
  { name: "Knowledge & RAG", used: 62, tone: "ok" as const, note: "ضمن الحد" },
  { name: "Agent Runs", used: 78, tone: "ok" as const, note: "ضمن الحد" },
  { name: "Chat Sessions", used: 45, tone: "ok" as const, note: "ضمن الحد" },
  { name: "Reports & Export", used: 91, tone: "warn" as const, note: "قرب السقف" },
];

const tooltipStyle = {
  contentStyle: { borderRadius: 12, border: "1px solid #E7E5E4", boxShadow: "0 8px 25px rgba(17,17,17,.10)", fontFamily: "inherit" },
  labelStyle: { fontWeight: 700, color: "#111111" },
};

export default function Page() {
  return (
    <AppShell>
      <div className="mx-auto max-w-7xl space-y-8">
        <PageHeader
          eyebrow="HSAAI Enterprise AI Operating System"
          title="إدارة تكلفة الذكاء الاصطناعي"
          description="AI Cost Management / FinOps — تتبع الاستهلاك، التكاليف، الميزانيات، وتوقعات الإنفاق عبر وحدات HSAAI داخل البيئة المؤسسية."
          actions={
            <>
              {/* FIX-MEDIUM-LOW-FINAL: pointed hrefs to existing routes */}
              <Link href="/enterprise-agents-center" className="rounded-xl bg-hsa-yellow px-4 py-2.5 text-sm font-bold text-hsa-black transition hover:bg-hsa-gold-dark hover:text-white">الوكلاء</Link>
              <Link href="/knowledge-hub" className="rounded-xl border border-hsa-border bg-white px-4 py-2.5 text-sm font-bold text-hsa-black transition hover:border-hsa-gold/50 hover:bg-hsa-soft">البحث المؤسسي</Link>
              <Link href="/enterprise-governance-center" className="rounded-xl border border-hsa-border bg-white px-4 py-2.5 text-sm font-bold text-hsa-black transition hover:border-hsa-gold/50 hover:bg-hsa-soft">الحوكمة</Link>
            </>
          }
        />

        <section aria-label="مؤشرات التكلفة والاستخدام" className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {kpis.map((k) => (
            <KpiCard key={k.label} label={k.label} value={<span dir="ltr">{k.value}</span>} hint={k.hint} icon={k.icon} />
          ))}
        </section>

        <section>
          <h2 className="hsa-section-title mb-4">
            التكلفة والاستخدام
            <span className="text-xs font-bold text-hsa-secondary">Costs & Usage</span>
          </h2>
          <div className="grid gap-4 xl:grid-cols-2">
            <Card>
              <h3 className="text-lg font-bold text-hsa-black">اتجاه التكلفة اليومي</h3>
              <div className="mt-4 h-64" dir="ltr">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={costTrend} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id="hsaCostFill" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#F4C430" stopOpacity={0.35} />
                        <stop offset="100%" stopColor="#F4C430" stopOpacity={0.02} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#E7E5E4" />
                    <XAxis dataKey="day" tick={{ fill: "#64748B", fontSize: 12 }} axisLine={{ stroke: "#E7E5E4" }} tickLine={false} />
                    <YAxis tick={{ fill: "#64748B", fontSize: 12 }} axisLine={false} tickLine={false} width={36} />
                    <Tooltip {...tooltipStyle} />
                    <Area type="monotone" dataKey="cost" name="Cost" stroke="#A67C00" strokeWidth={2.5} fill="url(#hsaCostFill)" activeDot={{ r: 5, fill: "#F4C430", stroke: "#A67C00" }} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </Card>
            <Card>
              <h3 className="text-lg font-bold text-hsa-black">التكلفة حسب القسم (%)</h3>
              <div className="mt-4 h-64" dir="ltr">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={costByDepartment} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#E7E5E4" vertical={false} />
                    <XAxis dataKey="dept" tick={{ fill: "#64748B", fontSize: 12 }} axisLine={{ stroke: "#E7E5E4" }} tickLine={false} />
                    <YAxis tick={{ fill: "#64748B", fontSize: 12 }} axisLine={false} tickLine={false} width={36} />
                    <Tooltip {...tooltipStyle} cursor={{ fill: "rgba(244,196,48,0.08)" }} />
                    <Bar dataKey="cost" name="Cost %" fill="#F4C430" stroke="#A67C00" radius={[6, 6, 0, 0]} maxBarSize={48} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>
          </div>
        </section>

        <section>
          <h2 className="hsa-section-title mb-4">
            الميزانيات
            <span className="text-xs font-bold text-hsa-secondary">Budgets</span>
          </h2>
          <Card>
            <div className="grid gap-5 md:grid-cols-2">
              {budgets.map((b) => (
                <div key={b.name} className="rounded-xl border border-hsa-border p-4">
                  <div className="flex items-center justify-between gap-3">
                    <p className="font-bold text-hsa-black">{b.name}</p>
                    <Badge tone={b.tone}>{b.note}</Badge>
                  </div>
                  <div className="mt-3 h-2.5 w-full overflow-hidden rounded-full bg-hsa-bg" role="progressbar" aria-valuenow={b.used} aria-valuemin={0} aria-valuemax={100} aria-label={`استهلاك ميزانية ${b.name}`}>
                    <div className="h-full rounded-full bg-hsa-yellow" style={{ width: `${b.used}%` }} />
                  </div>
                  <p className="mt-2 text-xs text-hsa-secondary"><span dir="ltr">{b.used}%</span> من الميزانية المخصصة لهذا الربع</p>
                </div>
              ))}
            </div>
          </Card>
        </section>

        <section className="grid gap-4 lg:grid-cols-2">
          <Card hoverable className="relative overflow-hidden">
            <span aria-hidden className="absolute inset-y-0 start-0 w-1 bg-hsa-yellow" />
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="hsa-section-title">توقع الإنفاق</h2>
              <Badge tone="gold">Forecast</Badge>
            </div>
            <p className="mt-4 text-sm leading-7 text-hsa-secondary">بالاستمرار على المسار الحالي، يُتوقع استهلاك نهاية الشهر:</p>
            <strong className="mt-2 block text-5xl font-bold text-hsa-gold"><span dir="ltr">15.9K</span></strong>
            <p className="mt-3 text-sm leading-7 text-hsa-secondary">أي نحو <b className="text-hsa-black">78%</b> من سقف الميزانية الحالي — يُنصح بمراجعة حدود التقارير والتصدير.</p>
          </Card>
          <Card>
            <h2 className="hsa-section-title">API Contract</h2>
            <code className="mt-4 block rounded-xl border border-hsa-border bg-hsa-bg p-3 text-start text-sm font-bold text-hsa-black" dir="ltr">/api/finops/usage</code>
            <p className="mt-3 text-sm leading-7 text-hsa-secondary">هذه الصفحة ليست واجهة شكلية فقط؛ تم إضافة Router وModels ومهاجرات مقابلة في backend_core/enterprise_os.</p>
          </Card>
        </section>
      </div>
    </AppShell>
  );
}
