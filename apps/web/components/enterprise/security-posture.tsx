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
    <div className="rounded-2xl border p-6 shadow-sm">
      <h2 className="text-2xl font-bold">Security Posture</h2>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        {checks.map((check) => (
          <div key={check} className="rounded-xl border px-4 py-3 text-sm">✓ {check}</div>
        ))}
      </div>
    </div>
  );
}
