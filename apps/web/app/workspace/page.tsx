"use client";
import { AppShell } from "@/components/layout/app-shell";
import { PageHeader } from "@/components/ui/page-header";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useWorkspaceStore } from "@/store/workspace.store";
import { Building2, CheckCircle2, Layers } from "lucide-react";

const spaces = ["default", "hr", "finance", "executive"];

const labels: Record<string, string> = {
  default: "مساحة العمل العامة",
  hr: "الموارد البشرية",
  finance: "المالية",
  executive: "الإدارة العليا",
};

export default function WorkspacePage() {
  const { workspaceId, setWorkspace } = useWorkspaceStore();

  return (
    <AppShell>
      <div className="space-y-6">
        <PageHeader
          eyebrow="Workspace"
          title="مساحات العمل"
          description="عزل الذاكرة والملفات والصلاحيات بين أقسام المؤسسة — كل مساحة تعمل ببيانات وصلاحيات مستقلة."
        />

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {spaces.map((s) => {
            const active = workspaceId === s;
            return (
              <Card key={s} hoverable className={active ? "border-hsa-gold/50 bg-hsa-soft/50" : undefined}>
                <div className="flex items-start justify-between gap-3">
                  <span className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ${active ? "bg-hsa-yellow text-hsa-black" : "bg-hsa-soft text-hsa-gold"}`}>
                    {s === "default" ? <Layers size={20} /> : <Building2 size={20} />}
                  </span>
                  {active ? <Badge tone="gold">مفعلة</Badge> : <Badge tone="neutral">غير مفعلة</Badge>}
                </div>
                <h2 className="mt-4 text-lg font-bold text-hsa-black">{labels[s] ?? s}</h2>
                <p className="mt-1 text-xs font-bold uppercase tracking-wide text-hsa-secondary" dir="ltr">
                  {s}
                </p>
                <p className="mt-2 text-sm leading-7 text-hsa-secondary">عزل الذاكرة والملفات والصلاحيات.</p>
                <Button
                  onClick={() => setWorkspace(s)}
                  variant={active ? "secondary" : "primary"}
                  className="mt-4 w-full"
                  aria-pressed={active}
                  aria-label={active ? `مساحة العمل ${labels[s] ?? s} مفعلة حالياً` : `تفعيل مساحة العمل ${labels[s] ?? s}`}
                >
                  {active ? (
                    <>
                      <CheckCircle2 size={16} />
                      {workspaceId === s ? "مفعلة" : "تفعيل"}
                    </>
                  ) : (
                    "تفعيل"
                  )}
                </Button>
              </Card>
            );
          })}
        </div>
      </div>
    </AppShell>
  );
}
