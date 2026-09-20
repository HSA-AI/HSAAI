"use client";

import { useState, useEffect, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Image from "next/image";
import { ShieldCheck, Loader2, KeyRound } from "lucide-react";
import { Button } from "@/components/ui/button";
import { LanguageSwitcher } from "@/components/i18n/language-switcher";
import { useAuth } from "@/lib/auth-provider";
import { brand } from "@/lib/brand";

const REASONS: Record<string, string> = {
  unauthenticated: "يجب تسجيل الدخول للوصول إلى هذه الصفحة.",
  session_expired: "انتهت جلستك. يرجى تسجيل الدخول مجدداً.",
  logout: "تم تسجيل الخروج بنجاح.",
  error: "حدث خطأ أثناء المصادقة. يرجى المحاولة مرة أخرى.",
};

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const reason = params.get("reason");
  const { login, isAuthenticated, isLoading } = useAuth();
  const [redirecting, setRedirecting] = useState(false);

  useEffect(() => {
    if (isAuthenticated && !isLoading) {
      router.replace("/");
    }
  }, [isAuthenticated, isLoading, router]);

  const handleLogin = async () => {
    setRedirecting(true);
    try {
      await login();
    } catch (e) {
      setRedirecting(false);
      console.error("Login failed:", e);
    }
  };

  return (
    <main className="flex min-h-dvh flex-col bg-hsa-bg">
      {/* Gold brand strip — reference header top border */}
      <div aria-hidden className="h-1 w-full bg-gradient-to-l from-hsa-yellow via-hsa-gold-dark to-hsa-yellow" />

      <div className="flex items-center justify-end p-4">
        <LanguageSwitcher />
      </div>

      <div className="flex flex-1 items-center justify-center px-4 pb-10 sm:px-6">
        <div className="w-full max-w-md space-y-6">
          {/* Official logo — protected proportions, gold ring */}
          <header className="space-y-4 text-center">
            <div className="flex justify-center">
              <span className="relative block h-20 w-20 overflow-hidden rounded-2xl border-[3px] border-hsa-yellow bg-white shadow-hsa-gold">
                <Image src={brand.logoPath} alt="HSAAI — الشعار الرسمي" fill sizes="80px" className="object-contain p-1" priority />
              </span>
            </div>
            <div className="space-y-1.5">
              <h1 className="text-3xl font-bold tracking-tight text-hsa-black" dir="ltr">{brand.platformName}</h1>
              <p className="text-micro font-semibold uppercase tracking-[0.3em] text-hsa-gold" dir="ltr">{brand.taglineEn}</p>
              <p className="text-sm font-semibold text-hsa-secondary">{brand.platformSubtitleAr}</p>
            </div>
          </header>

          {/* White card — unified card system */}
          <section className="rounded-2xl border border-hsa-border bg-white p-6 shadow-hsa-card-hover sm:p-8">
            <div className="space-y-2 text-center">
              <h2 className="text-xl font-bold text-hsa-black">تسجيل الدخول</h2>
              <p className="text-xs text-hsa-secondary">الدخول الآمن باستخدام حسابك المؤسسي</p>
            </div>

            {reason && (
              <div role="alert" className="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm leading-6 text-amber-800">
                {REASONS[reason] || REASONS.error}
              </div>
            )}

            <Button
              onClick={handleLogin}
              disabled={redirecting || isLoading}
              className="mt-6 min-h-12 w-full text-base"
              aria-label="تسجيل الدخول بحساب الشركة"
            >
              {redirecting ? (
                <>
                  <Loader2 className="animate-spin" size={18} />
                  جارٍ فتح صفحة تسجيل الدخول...
                </>
              ) : (
                <>
                  <KeyRound size={18} />
                  تسجيل الدخول بحساب الشركة
                </>
              )}
            </Button>

            <div className="mt-6 space-y-1.5 text-center text-xs leading-6 text-hsa-secondary">
              <p className="flex items-center justify-center gap-1.5">
                <ShieldCheck size={14} className="text-hsa-gold" />
                الدخول مطلوب لجميع المستخدمين.
              </p>
              <p>الحسابات تُدار مركزياً من قبل إدارة تقنية المعلومات.</p>
            </div>
          </section>

          <footer className="text-center text-xs text-hsa-secondary">
            © HSA Group · Information Technology · Internal Use Only
          </footer>
        </div>
      </div>
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={
      <div className="flex min-h-dvh items-center justify-center bg-hsa-bg">
        <div role="status" className="flex items-center gap-3 text-sm font-bold text-hsa-secondary">
          <Loader2 className="animate-spin text-hsa-gold" size={20} /> جارٍ التحميل...
        </div>
      </div>
    }>
      <LoginForm />
    </Suspense>
  );
}
