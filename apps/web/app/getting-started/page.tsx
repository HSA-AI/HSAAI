import Link from "next/link";
import { AppShell } from "@/components/layout/app-shell";
import { Card } from "@/components/ui/card";
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
  return <AppShell><div className="space-y-6"><section className="rounded-[2rem] border border-hsa-yellow/25 bg-gradient-to-br from-hsa-black to-slate-950 p-7 text-white"><p className="text-sm font-black text-hsa-yellow">HSAAI Enterprise AI Operating System</p><h1 className="mt-2 text-3xl font-black">دليل البداية السريع</h1><p className="mt-3 max-w-3xl text-sm leading-7 text-slate-300">هذه الصفحة تجعل الوصول للمنصة واضحًا: ابدأ من الهوية، المعرفة، الوكلاء، البحث، ثم المراقبة والتكلفة. لا يتم إظهار أو تنفيذ أي إجراء حساس إلا من خلال الصلاحيات والموافقات.</p></section><ReadinessScorecard /><section className="grid gap-4 md:grid-cols-5">{onboarding.map(([step, title, text]) => <Card key={step} className="border-hsa-yellow/20"><span className="flex h-9 w-9 items-center justify-center rounded-full bg-hsa-yellow font-black text-hsa-black">{step}</span><h2 className="mt-4 font-black">{title}</h2><p className="mt-2 text-sm text-slate-500">{text}</p></Card>)}</section><section className="grid gap-4 md:grid-cols-5">{enterpriseQuickActions.map((action) => <Link key={action.href} href={action.href} className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm transition hover:-translate-y-1 hover:border-hsa-yellow dark:border-slate-800 dark:bg-slate-950"><b>{action.label}</b><p className="mt-2 text-sm text-slate-500">{action.description}</p><span className="mt-4 inline-block rounded-full bg-hsa-yellow/10 px-3 py-1 text-xs font-black text-hsa-gold">Shortcut {action.shortcut}</span></Link>)}</section></div></AppShell>;
}
