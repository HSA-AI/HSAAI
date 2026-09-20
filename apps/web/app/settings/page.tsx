import { AppShell } from "@/components/layout/app-shell";
import { PageHeader } from "@/components/ui/page-header";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { KeyRound, ShieldCheck, UserCog } from "lucide-react";

/**
 * Settings — الأمان والإعدادات
 * أقسام نظيفة بعناوين hsa-section-title ومجموعات Card ونماذج موحدة.
 */
export default function SettingsPage() {
  return (
    <AppShell>
      <div className="space-y-6">
        <PageHeader
          eyebrow="Settings"
          title="الأمان والإعدادات"
          description="إدارة هوية الدخول، الصلاحيات، وتفضيلات الحساب داخل بيئة HSAAI الداخلية."
          actions={
            <Button aria-label="حفظ إعدادات HSAAI">
              حفظ التغييرات
            </Button>
          }
        />

        {/* SSO / Keycloak */}
        <section>
          <h2 className="hsa-section-title mb-4">
            الهوية والدخول — SSO / Keycloak
            <span className="text-xs font-bold text-hsa-secondary">Identity</span>
          </h2>
          <div className="grid gap-4 md:grid-cols-2">
            <Card hoverable>
              <div className="flex items-start justify-between gap-3">
                <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-hsa-soft text-hsa-gold">
                  <KeyRound size={20} />
                </span>
                <Badge tone="ok">جاهز للربط</Badge>
              </div>
              <h3 className="mt-4 text-lg font-bold text-hsa-black">SSO / Keycloak</h3>
              <p className="mt-2 text-sm leading-7 text-hsa-secondary">
                جاهز للربط مع Keycloak، LDAP، MFA، وJWT.
              </p>
              <div className="mt-4 grid gap-3">
                <div>
                  <label htmlFor="sso-issuer" className="mb-1.5 block text-xs font-bold text-hsa-secondary">
                    Issuer URL
                  </label>
                  <Input id="sso-issuer" defaultValue="https://keycloak.internal/realms/hsaai" dir="ltr" />
                </div>
                <div>
                  <label htmlFor="sso-client" className="mb-1.5 block text-xs font-bold text-hsa-secondary">
                    Client ID
                  </label>
                  <Input id="sso-client" defaultValue="hsaai-web" dir="ltr" />
                </div>
              </div>
            </Card>

            <Card hoverable>
              <div className="flex items-start justify-between gap-3">
                <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-hsa-soft text-hsa-gold">
                  <ShieldCheck size={20} />
                </span>
                <Badge tone="gold">RBAC نشط</Badge>
              </div>
              <h3 className="mt-4 text-lg font-bold text-hsa-black">RBAC</h3>
              <p className="mt-2 text-sm leading-7 text-hsa-secondary">
                أدوار وصلاحيات حسب المؤسسة ومساحة العمل.
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                {["Admin", "Supervisor", "Manager", "Employee"].map((role) => (
                  <span key={role} className="hsa-badge-neutral">
                    {role}
                  </span>
                ))}
              </div>
              <p className="mt-4 text-xs leading-6 text-hsa-secondary">
                تُطبَّق الصلاحيات على مستوى الوثائق والبحث والوكلاء، ويُسجَّل كل إجراء حساس في سجل التدقيق.
              </p>
            </Card>
          </div>
        </section>

        {/* Account preferences */}
        <section>
          <h2 className="hsa-section-title mb-4">
            تفضيلات الحساب
            <span className="text-xs font-bold text-hsa-secondary">Preferences</span>
          </h2>
          <Card>
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <label htmlFor="pref-name" className="mb-1.5 block text-xs font-bold text-hsa-secondary">
                  الاسم المعروض
                </label>
                <Input id="pref-name" defaultValue="موظف HSA" placeholder="اكتب اسمك المعروض" />
              </div>
              <div>
                <label htmlFor="pref-email" className="mb-1.5 block text-xs font-bold text-hsa-secondary">
                  البريد المؤسسي
                </label>
                <Input id="pref-email" type="email" defaultValue="employee@hsa.local" dir="ltr" />
              </div>
              <div className="md:col-span-2">
                <label htmlFor="pref-bio" className="mb-1.5 block text-xs font-bold text-hsa-secondary">
                  نبذة / توقيع المساعد
                </label>
                <Textarea
                  id="pref-bio"
                  rows={3}
                  defaultValue="أستخدم HSAAI للبحث في السياسات وصياغة التقارير التنفيذية."
                  placeholder="اكتب نبذة قصيرة أو تعليمات مخصصة للمساعد..."
                />
              </div>
            </div>
            <div className="mt-5 flex flex-wrap items-center gap-3">
              <Button aria-label="حفظ تفضيلات الحساب">حفظ التفضيلات</Button>
              <Button variant="secondary" aria-label="استعادة القيم الافتراضية للتفضيلات">
                استعادة الافتراضي
              </Button>
              <span className="flex items-center gap-1.5 text-xs text-hsa-secondary">
                <UserCog size={14} className="text-hsa-gold" />
                تُحفظ التفضيلات داخل مساحة العمل النشطة فقط.
              </span>
            </div>
          </Card>
        </section>
      </div>
    </AppShell>
  );
}
