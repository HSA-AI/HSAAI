import { ShieldCheck } from "lucide-react";

/** HSAAI Security Posture — light enterprise card with gold check list */
export function SecurityPosture() {
  const checks = [
    "Strict internal-only mode",
    "Zero Trust network policies",
    "Keycloak MFA ready",
    "LDAP/AD federation ready",
    "Encrypted local storage policy",
    "Tenant/workspace isolation",
    "Audit log trail",
    "Release gate checks",
  ];
  return (
    <div className="rounded-2xl border border-hsa-border bg-white p-6 shadow-hsa-card">
      <div className="flex items-center gap-2">
        <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-hsa-soft text-hsa-gold">
          <ShieldCheck size={18} />
        </span>
        <h2 className="hsa-section-title flex-1">Security Posture</h2>
      </div>
      <ul className="mt-5 grid gap-3 md:grid-cols-2">
        {checks.map((check) => (
          <li
            key={check}
            className="rounded-xl border border-hsa-border bg-hsa-bg px-4 py-3 text-sm text-hsa-black transition hover:border-hsa-gold/40"
          >
            <span aria-hidden className="me-2 font-bold text-hsa-gold">✓</span>
            {check}
          </li>
        ))}
      </ul>
    </div>
  );
}
