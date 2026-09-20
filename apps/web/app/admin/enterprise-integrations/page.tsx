import { AppShell } from "@/components/layout/app-shell";
import { PageHeader } from "@/components/ui/page-header";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { KpiCard } from "@/components/ui/kpi-card";
import { Bot, Network, ScrollText, ShieldCheck } from "lucide-react";

const systems = [
  { key: "sap_s4hana", name: "SAP S/4HANA", category: "ERP", sources: "Purchases, Inventory, Sales, Finance" },
  { key: "successfactors", name: "SAP SuccessFactors", category: "HR", sources: "Employees, Leaves, Org Structure" },
  { key: "active_directory", name: "Active Directory", category: "Identity", sources: "Users, Groups, Keycloak Mapping" },
  { key: "outlook_exchange", name: "Exchange / Outlook", category: "Collaboration", sources: "Mail, Calendar, Meetings" },
  { key: "sharepoint", name: "SharePoint", category: "Knowledge", sources: "Word, Excel, PDF, PowerPoint" },
  { key: "powerbi", name: "Power BI", category: "Analytics", sources: "Dashboards, Reports, Datasets" },
  { key: "jira", name: "Jira", category: "Projects", sources: "Issues, Epics, Sprints" },
  { key: "service_desk", name: "Service Desk", category: "ITSM", sources: "Tickets, SLA, Escalation" },
  { key: "dms", name: "DMS", category: "Documents", sources: "Search, Versions, Approvals" },
  { key: "data_warehouse", name: "Data Warehouse", category: "Analytics", sources: "Read-only SQL Analytics" },
];

const agentMap = [
  ["HR Agent", "SuccessFactors, SharePoint, DMS"],
  ["Finance Agent", "SAP S/4HANA, Power BI, Data Warehouse"],
  ["IT Agent", "Active Directory, Jira, Service Desk, Outlook"],
  ["Knowledge Agent", "SharePoint, DMS, Knowledge Base"],
  ["Executive Agent", "SAP, Power BI, Data Warehouse"],
];

const securityControls = [
  "Keycloak RBAC وربط الصلاحيات حسب الدور.",
  "Data Classification وField Masking وRow-Level Security.",
  "Encrypted Secrets عبر credentials_ref بدل حفظ الأسرار كنص.",
  "Human Approval للإجراءات الحساسة.",
  "منع UPDATE / DELETE / DROP / ALTER في Data Warehouse.",
];

export default function EnterpriseIntegrationsAdminPage() {
  return (
    <AppShell>
      <main className="space-y-6">
        <PageHeader
          eyebrow="Admin Center → Enterprise Integrations"
          title="Enterprise Integrations Center"
          description="مركز موحد لإدارة تكامل HSAAI مع أنظمة SAP وSuccessFactors وActive Directory وOutlook وSharePoint وPower BI وJira وService Desk وDMS وData Warehouse مع صلاحيات، تدقيق، Read Only افتراضيًا، وإظهار مصدر البيانات داخل إجابات الذكاء الاصطناعي."
        />

        <section className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <KpiCard label="Supported Systems" value="10" icon={<Network size={20} />} hint="جاهزة للربط" />
          <KpiCard label="Security Mode" value="Read Only Default" icon={<ShieldCheck size={20} />} />
          <KpiCard label="Audit" value="Full Access Logs" icon={<ScrollText size={20} />} />
          <KpiCard label="Agents" value="Source-Aware" icon={<Bot size={20} />} />
        </section>

        <section className="grid gap-4 lg:grid-cols-2">
          {systems.map((item) => (
            <Card key={item.key} hoverable>
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <p className="text-xs font-bold uppercase tracking-widest text-hsa-gold">{item.category}</p>
                  <h2 className="mt-1 text-xl font-bold text-hsa-black">{item.name}</h2>
                  <p className="mt-2 text-sm text-hsa-secondary">{item.sources}</p>
                </div>
                <Badge tone="warn">Config Required</Badge>
              </div>
              <div className="mt-4 grid grid-cols-3 gap-2 text-xs">
                <Badge tone="ok" className="justify-center">RBAC</Badge>
                <Badge tone="info" className="justify-center">Audit Log</Badge>
                <Badge tone="warn" className="justify-center">Read Only</Badge>
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <Button className="px-4 py-2 text-xs">Configure</Button>
                <Button variant="secondary" className="px-4 py-2 text-xs">Test Connection</Button>
                <Button variant="secondary" className="px-4 py-2 text-xs">View Logs</Button>
              </div>
            </Card>
          ))}
        </section>

        <section className="grid gap-4 lg:grid-cols-2">
          <Card>
            <h2 className="text-lg font-bold text-hsa-black">Agent Data Sources</h2>
            <div className="mt-4 space-y-3">
              {agentMap.map(([agent, sources]) => (
                <div key={agent} className="rounded-xl border border-hsa-border bg-hsa-bg p-4">
                  <p className="font-bold text-hsa-black">{agent}</p>
                  <p className="mt-1 text-sm text-hsa-secondary">{sources}</p>
                </div>
              ))}
            </div>
          </Card>
          <Card>
            <h2 className="text-lg font-bold text-hsa-black">Enterprise Security Controls</h2>
            <ul className="mt-4 space-y-3 text-sm leading-7 text-hsa-secondary">
              {securityControls.map((control) => (
                <li key={control} className="rounded-xl border border-hsa-border bg-hsa-bg p-3">
                  <span aria-hidden className="me-2 font-bold text-hsa-gold">•</span>
                  {control}
                </li>
              ))}
            </ul>
          </Card>
        </section>
      </main>
    </AppShell>
  );
}
