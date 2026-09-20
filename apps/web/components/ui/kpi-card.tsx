import * as React from "react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";

/**
 * HSAAI KPI Card — large gold numerals (reference: index.html .stat-num)
 * Numbers use Dark Gold #A67C00 on white for WCAG-compliant contrast.
 */
export function KpiCard({
  label,
  value,
  delta,
  icon,
  hint,
  className,
}: {
  label: string;
  value: React.ReactNode;
  delta?: string;
  icon?: React.ReactNode;
  hint?: string;
  className?: string;
}) {
  return (
    <div className={cn("hsa-card hsa-card-hover relative overflow-hidden", className)}>
      <span aria-hidden className="absolute inset-y-0 start-0 w-1 bg-hsa-yellow" />
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          {/* typography-v2: labels wrap instead of truncating — a cut label
              ("…THLY COST") defeats dashboard scannability */}
          <p className="text-xs font-semibold uppercase tracking-wide text-hsa-secondary">{label}</p>
          <strong className="mt-2 block text-3xl font-bold leading-tight tabular-nums text-hsa-gold">{value}</strong>
          {hint ? <p className="mt-2 text-xs text-hsa-secondary">{hint}</p> : null}
        </div>
        {icon ? (
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-hsa-soft text-hsa-gold">{icon}</span>
        ) : null}
      </div>
      {delta ? <Badge tone={delta.startsWith("-") ? "warn" : "ok"} className="mt-3">{delta}</Badge> : null}
    </div>
  );
}
