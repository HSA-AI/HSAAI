import { ShieldCheck } from "lucide-react";

/** Official environment badge — Soft Gold chip (reference .badge) */
export function OfficialBadge() {
  return (
    <div className="inline-flex items-center gap-2 rounded-full bg-hsa-soft px-3 py-1 text-micro font-bold text-hsa-gold">
      <ShieldCheck className="h-3.5 w-3.5" />
      بيئة داخلية رسمية — HSA Group · Information Technology
    </div>
  );
}
