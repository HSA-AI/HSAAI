import type { ReactNode } from "react";
import { AppShell } from "@/components/layout/app-shell";
import { PageHeader } from "@/components/ui/page-header";
import { Card } from "@/components/ui/card";
import {
  BookOpenCheck,
  Bot,
  Building2,
  Cpu,
  FileText,
  LayoutGrid,
  ScrollText,
  ShieldCheck,
  Users,
  Zap,
} from "lucide-react";

type AdminModule = { name: string; icon: ReactNode };

const cards: AdminModule[] = [
  { name: "Organizations", icon: <Building2 size={20} /> },
  { name: "Workspaces", icon: <LayoutGrid size={20} /> },
  { name: "Users", icon: <Users size={20} /> },
  { name: "Roles", icon: <ShieldCheck size={20} /> },
  { name: "Audit Logs", icon: <ScrollText size={20} /> },
  { name: "Data Policies", icon: <FileText size={20} /> },
  { name: "Local AI Models", icon: <Cpu size={20} /> },
  { name: "Smart Responses", icon: <Zap size={20} /> },
  { name: "Knowledge Governance", icon: <BookOpenCheck size={20} /> },
  { name: "Department AI Agents", icon: <Bot size={20} /> },
];

export default function AdminPage() {
  return (
    <AppShell>
      <main className="space-y-6">
        <PageHeader
          eyebrow="Administration Center"
          title="Enterprise Control Plane"
          description="Manage tenants, permissions, governance policies, and workspace isolation."
        />

        <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {cards.map((c) => (
            <Card key={c.name} hoverable>
              <div className="flex items-start gap-3">
                <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-hsa-soft text-hsa-gold" aria-hidden>
                  {c.icon}
                </span>
                <div className="min-w-0">
                  <h2 className="font-bold text-hsa-black">{c.name}</h2>
                  <p className="mt-2 text-sm leading-7 text-hsa-secondary">
                    Production-ready module scaffold with API integration points.
                  </p>
                </div>
              </div>
            </Card>
          ))}
        </section>
      </main>
    </AppShell>
  );
}
