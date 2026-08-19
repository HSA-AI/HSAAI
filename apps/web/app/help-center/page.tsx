import { AppShell } from "@/components/layout/app-shell";
import { Card } from "@/components/ui/card";

const faqs = [
  ["كيف أبدأ؟", "استخدم صفحة Getting Started ثم فعّل الهوية والصلاحيات والمعرفة قبل فتح الاستخدام الواسع."],
  ["هل يمكن ربط SAP وSharePoint؟", "نعم، مركز التكاملات يحتوي Mock Mode وطبقة إعداد جاهزة، أما الربط الإنتاجي فيحتاج بيانات اتصال وصلاحيات المؤسسة."],
  ["هل الوكلاء ينفذون قرارات حساسة مباشرة؟", "لا. الإجراءات الحساسة تمر عبر Human-in-the-Loop Approval Engine وسجل تدقيق."],
  ["كيف يتم التحكم في الوصول للوثائق؟", "يعتمد البحث والاسترجاع على Keycloak/RBAC وتصنيف الوثيقة والقسم والـ tenant/workspace."],
] as const;

export default function HelpCenterPage() {
  return <AppShell><div className="space-y-6"><section><p className="text-sm font-black text-hsa-gold">Internal Help Center</p><h1 className="text-3xl font-black">مركز المساعدة داخل HSAAI</h1><p className="mt-2 max-w-3xl text-slate-500">إجابات مختصرة تساعد المستخدمين والمدراء والمشرفين على استخدام المنصة بأمان ووضوح.</p></section><div className="grid gap-4 md:grid-cols-2">{faqs.map(([q, a]) => <Card key={q} className="border-hsa-yellow/20"><h2 className="font-black">{q}</h2><p className="mt-2 text-sm leading-7 text-slate-500">{a}</p></Card>)}</div></div></AppShell>;
}
