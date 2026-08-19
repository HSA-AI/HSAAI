import { AppShell } from "@/components/layout/app-shell";
import { Card } from "@/components/ui/card";

const docs = [
  ["Architecture", "ARCHITECTURE.md", "شرح طبقات المنصة والواجهات والخدمات وقواعد البيانات والتشغيل."],
  ["Enterprise Readiness", "ENTERPRISE_READINESS.md", "قائمة جاهزية المؤسسات ومعايير الإنتاج والحوكمة والأمان."],
  ["Operations", "docs/operations/RUNBOOK.md", "تشغيل، مراقبة، نسخ احتياطي، واستجابة للحوادث."],
  ["Security", "docs/security/SECURITY_GUIDE.md", "Zero Trust وRBAC وKeycloak ومراجعة الوصول."],
  ["Integrations", "docs/integrations/INTEGRATION_GUIDE.md", "إعداد SAP وAD وSharePoint وJira وREST APIs."],
] as const;

export default function DocumentationPage() {
  return <AppShell><div className="space-y-6"><section><p className="text-sm font-black text-hsa-gold">Documentation Workspace</p><h1 className="text-3xl font-black">توثيق HSAAI التشغيلي</h1><p className="mt-2 max-w-3xl text-slate-500">روابط الوثائق الرئيسية داخل المشروع للمدير والمطور ومسؤول التشغيل والأمن.</p></section><div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{docs.map(([title, file, desc]) => <Card key={file} className="border-hsa-yellow/20"><h2 className="font-black">{title}</h2><code className="mt-3 block rounded-2xl bg-slate-100 p-3 text-xs dark:bg-slate-900">{file}</code><p className="mt-3 text-sm text-slate-500">{desc}</p></Card>)}</div></div></AppShell>;
}
