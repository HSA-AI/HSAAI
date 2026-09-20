import { AppShell } from "@/components/layout/app-shell";
import { PageHeader } from "@/components/ui/page-header";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { CircleDollarSign, FilePenLine, KeyRound, Scale, ShieldCheck, UserCog } from "lucide-react";

const items = [
  { label: "Financial Decisions", icon: CircleDollarSign },
  { label: "Procurement Approval", icon: FilePenLine },
  { label: "Legal Recommendations", icon: Scale },
  { label: "Policy Changes", icon: ShieldCheck },
  { label: "User Access Changes", icon: KeyRound },
  { label: "Knowledge Publication", icon: UserCog },
] as const;

export default function EnterpriseGovernanceCenterPage() {
  return (
    <AppShell>
      <div className="space-y-6">
        <PageHeader
          eyebrow="Human-in-the-Loop Governance"
          title="Governance Center"
          description="أي إجراء حساس ينتقل من AI Recommendation إلى Human Review ثم Approval/Rejection قبل التنفيذ."
          actions={<Badge tone="gold">Approval Required</Badge>}
        />

        <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {items.map(({ label, icon: Icon }) => (
            <Card key={label} hoverable>
              <div className="flex items-start justify-between gap-3">
                <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-hsa-soft text-hsa-gold">
                  <Icon size={20} />
                </span>
                <Badge tone="warn">Human Review</Badge>
              </div>
              <h2 className="mt-4 font-bold text-hsa-black">{label}</h2>
              <p className="mt-2 text-sm leading-7 text-hsa-secondary">Multi-level approval · RBAC approvers · audit trail</p>
            </Card>
          ))}
        </section>

        <Card className="bg-hsa-soft/40">
          <div className="flex flex-wrap items-center gap-3 text-sm text-hsa-black">
            <ShieldCheck size={18} className="text-hsa-gold" />
            <span className="font-bold">مسار الموافقة:</span>
            <span className="text-hsa-secondary">AI Recommendation → Human Review → Approval / Rejection → Execution + Audit Log</span>
          </div>
        </Card>
      </div>
    </AppShell>
  );
}
