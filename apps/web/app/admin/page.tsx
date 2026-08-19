import { AppShell } from "@/components/layout/app-shell";

export default function AdminPage() {
  const cards = ["Organizations", "Workspaces", "Users", "Roles", "Audit Logs", "Data Policies", "Local AI Models", "Smart Responses", "Knowledge Governance", "Department AI Agents"];
  return (
    <AppShell>
      <main className="space-y-6 overflow-x-hidden">
        <section className="rounded-3xl bg-white p-5 text-slate-950 shadow-xl dark:bg-slate-950 dark:text-white sm:p-8">
          <p className="text-sm text-hsa-gold">Administration Center</p>
          <h1 className="text-2xl font-bold sm:text-3xl">Enterprise Control Plane</h1>
          <p className="mt-2 text-sm leading-7 text-slate-500 sm:text-base">Manage tenants, permissions, governance policies, and workspace isolation.</p>
        </section>
        <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {cards.map((c) => (
            <div key={c} className="rounded-2xl border border-slate-800 bg-slate-950 p-5 text-white">
              <h2 className="font-semibold">{c}</h2>
              <p className="mt-2 text-sm leading-7 text-slate-400">Production-ready module scaffold with API integration points.</p>
            </div>
          ))}
        </section>
      </main>
    </AppShell>
  );
}
