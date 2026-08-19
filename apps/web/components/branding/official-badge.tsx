import { ShieldCheck } from "lucide-react";

export function OfficialBadge() {
  return (
    <div className="inline-flex items-center gap-2 rounded-full border border-hsa-yellow/50 bg-hsa-soft px-3 py-1 text-xs font-semibold text-hsa-black shadow-sm dark:border-hsa-yellow/30 dark:bg-hsa-black dark:text-hsa-yellow">
      <ShieldCheck className="h-4 w-4" />
      بيئة داخلية رسمية — HSA Internal AI
    </div>
  );
}
