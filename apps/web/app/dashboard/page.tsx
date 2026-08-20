"use client";

import { Card, CardHeader, CardBody, Badge, Button, PageHero, H2, H3, BodyLarge, BodySmall, Eyebrow } from "@/lib/design-system";

const metrics = [
  { label: "متوسط زمن الاستجابة", value: "840ms", trend: "-12%", status: "success" as const },
  { label: "مساحات العمل", value: "3", trend: "+1", status: "info" as const },
  { label: "الوكلاء النشطون", value: "5", trend: "+2", status: "success" as const },
  { label: "الرموز اليوم", value: "125K", trend: "+18%", status: "success" as const },
];

const readinessMetrics = [
  { label: "الإنتاج", value: 92 },
  { label: "تجربة المستخدم", value: 89 },
  { label: "عمليات الذكاء الاصطناعي", value: 91 },
  { label: "الأمان", value: 96 },
  { label: "البنية المعمارية", value: 88 },
];

const features = [
  { title: "Zero Trust", description: "مصادقة OIDC + PKCE + MFA لكل طلب", icon: "🔐" },
  { title: "Enterprise RAG", description: "بحث دلالي في المستندات المؤسسية", icon: "📚" },
  { title: "Local LLM", description: "Qwen2.5-7B عبر Ollama + vLLM", icon: "🧠" },
];

export default function DashboardPage() {
  return (
    <div className="ds-page">
      {/* Hero */}
      <PageHero
        eyebrow="لوحة التحكم"
        title="منصة HSAAI الذكية"
        description="نظام تشغيل ذكاء اصطناعي مؤسسي موحّد — HSA Group"
        actions={
          <Button variant="primary" size="md">
            محادثة جديدة
          </Button>
        }
      />

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 gap-4 mb-8 lg:grid-cols-4">
        {metrics.map((m) => (
          <Card key={m.label} variant="elevated" padding="md">
            <CardBody>
              <div className="flex items-center justify-between mb-2">
                <span className="text-caption text-text-muted">{m.label}</span>
                <Badge variant={m.status} dot>{m.trend}</Badge>
              </div>
              <div className="text-h2 font-bold text-text-primary tabular-nums">
                {m.value}
              </div>
            </CardBody>
          </Card>
        ))}
      </div>

      {/* Readiness Score */}
      <Card variant="brand" padding="xl" className="mb-8">
        <CardHeader>
          <Eyebrow>Enterprise Readiness</Eyebrow>
          <H2 className="text-white">درجة الجاهزية المؤسسية</H2>
          <BodyLarge className="text-neutral-300">
            النسبة الإجمالية: <span className="text-primary-gold font-bold text-h2">91%</span>
          </BodyLarge>
        </CardHeader>
        <CardBody>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {readinessMetrics.map((m) => (
              <div key={m.label} className="text-center">
                <div className="text-h3 font-bold text-primary-gold mb-1">{m.value}%</div>
                <div className="text-caption text-neutral-400">{m.label}</div>
                <div className="mt-2 h-1.5 rounded-full bg-neutral-800 overflow-hidden">
                  <div
                    className="h-full bg-primary-gold rounded-full transition-all duration-slow"
                    style={{ width: `${m.value}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </CardBody>
      </Card>

      {/* Features */}
      <div className="grid gap-4 sm:grid-cols-3">
        {features.map((f) => (
          <Card key={f.title} variant="default" padding="lg">
            <CardBody>
              <div className="text-3xl mb-3">{f.icon}</div>
              <H3 className="mb-2">{f.title}</H3>
              <BodySmall className="text-text-secondary">{f.description}</BodySmall>
            </CardBody>
          </Card>
        ))}
      </div>
    </div>
  );
}
