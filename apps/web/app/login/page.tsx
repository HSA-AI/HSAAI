"use client";

import { useState, useEffect, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { BrandMark } from "@/components/branding/brand-mark";
import { Button, Card, CardBody, CardFooter, CardHeader, CardTitle, CardDescription, Eyebrow, BodySmall } from "@/lib/design-system";
import { useAuth } from "@/lib/auth-provider";

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
    <main className="min-h-dvh flex items-center justify-center bg-bg p-6">
      <div className="w-full max-w-md space-y-6">
        {/* Brand Header */}
        <header className="text-center space-y-4">
          <div className="flex justify-center">
            <BrandMark size={64} />
          </div>
          <div className="space-y-2">
            <Eyebrow>Enterprise AI Platform</Eyebrow>
            <h1 className="font-display text-h1 font-bold text-text-primary">HSAAI</h1>
            <p className="font-sans text-body text-text-secondary">
              منصة التشغيل الذكي المؤسسية — HSA Group
            </p>
          </div>
        </header>

        {/* Login Card */}
        <Card variant="elevated" padding="xl">
          <CardHeader>
            <CardTitle>تسجيل الدخول</CardTitle>
            <CardDescription>المصادقة عبر Keycloak OIDC + PKCE</CardDescription>
          </CardHeader>

          <CardBody className="space-y-4">
            {reason && (
              <div
                role="alert"
                className="rounded-lg bg-warning-soft border border-warning-border p-3 text-body-sm text-warning"
              >
                {REASONS[reason] || REASONS.error}
              </div>
            )}

            <Button
              onClick={handleLogin}
              loading={redirecting || isLoading}
              className="w-full"
              size="lg"
            >
              {redirecting ? "جارٍ التحويل إلى Keycloak..." : "تسجيل الدخول عبر Keycloak"}
            </Button>
          </CardBody>

          <CardFooter className="flex-col gap-2">
            <BodySmall className="text-center">الدخول مطلوب لجميع المستخدمين.</BodySmall>
            <BodySmall className="text-center">الحسابات تُدار مركزياً من قبل إدارة تقنية المعلومات.</BodySmall>
          </CardFooter>
        </Card>

        <footer className="text-center">
          <BodySmall>© HSA Group · Internal Use Only · v4.0</BodySmall>
        </footer>
      </div>
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="min-h-dvh flex items-center justify-center">جارٍ التحميل...</div>}>
      <LoginForm />
    </Suspense>
  );
}
