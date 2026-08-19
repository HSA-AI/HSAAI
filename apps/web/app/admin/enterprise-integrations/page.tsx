import { AppShell } from "@/components/layout/app-shell";
import { Card } from "@/components/ui/card";

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

export default function EnterpriseIntegrationsAdminPage() {
  return (
    <AppShell>
      <main className="space-y-6">
        <section className="rounded-3xl border border-slate-200 bg-gradient-to-br from-slate-950 to-slate-800 p-6 text-white shadow-sm">
          <p className="text-sm font-bold text-hsa-yellow">Admin Center → Enterprise Integrations</p>
          <h1 className="mt-2 text-3xl font-black">Enterprise Integrations Center</h1>
          <p className="mt-3 max-w-5xl text-sm leading-7 text-slate-200">
            مركز موحد لإدارة تكامل HSAAI مع أنظمة SAP وSuccessFactors وActive Directory وOutlook وSharePoint وPower BI وJira وService Desk وDMS وData Warehouse مع صلاحيات، تدقيق، Read Only افتراضيًا، وإظهار مصدر البيانات داخل إجابات الذكاء الاصطناعي.
          </p>
        </section>

        <section className="grid gap-4 md:grid-cols-4">
          <Card className="p-5"><p className="text-xs text-slate-500">Supported Systems</p><h2 className="mt-2 text-3xl font-black">10</h2></Card>
          <Card className="p-5"><p className="text-xs text-slate-500">Security Mode</p><h2 className="mt-2 text-xl font-black">Read Only Default</h2></Card>
          <Card className="p-5"><p className="text-xs text-slate-500">Audit</p><h2 className="mt-2 text-xl font-black">Full Access Logs</h2></Card>
          <Card className="p-5"><p className="text-xs text-slate-500">Agents</p><h2 className="mt-2 text-xl font-black">Source-Aware</h2></Card>
        </section>

        <section className="grid gap-4 lg:grid-cols-2">
          {systems.map((item) => (
            <Card key={item.key} className="p-5">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-xs font-bold uppercase tracking-wide text-hsa-yellow">{item.category}</p>
                  <h2 className="mt-1 text-xl font-black text-slate-900">{item.name}</h2>
                  <p className="mt-2 text-sm text-slate-500">{item.sources}</p>
                </div>
                <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-600">Config Required</span>
              </div>
              <div className="mt-4 grid grid-cols-3 gap-2 text-xs">
                <span className="rounded-xl bg-emerald-50 px-3 py-2 font-bold text-emerald-700">RBAC</span>
                <span className="rounded-xl bg-blue-50 px-3 py-2 font-bold text-blue-700">Audit Log</span>
                <span className="rounded-xl bg-amber-50 px-3 py-2 font-bold text-amber-700">Read Only</span>
              </div>
              <div className="mt-4 flex gap-2">
                <button className="rounded-xl bg-slate-900 px-4 py-2 text-xs font-black text-white">Configure</button>
                <button className="rounded-xl border border-slate-200 px-4 py-2 text-xs font-black text-slate-700">Test Connection</button>
                <button className="rounded-xl border border-slate-200 px-4 py-2 text-xs font-black text-slate-700">View Logs</button>
              </div>
            </Card>
          ))}
        </section>

        <section className="grid gap-4 lg:grid-cols-2">
          <Card className="p-5">
            <h2 className="text-xl font-black">Agent Data Sources</h2>
            <div className="mt-4 space-y-3">
              {agentMap.map(([agent, sources]) => (
                <div key={agent} className="rounded-2xl border border-slate-100 p-4">
                  <p className="font-bold text-slate-900">{agent}</p>
                  <p className="mt-1 text-sm text-slate-500">{sources}</p>
                </div>
              ))}
            </div>
          </Card>
          <Card className="p-5">
            <h2 className="text-xl font-black">Enterprise Security Controls</h2>
            <ul className="mt-4 space-y-3 text-sm text-slate-600">
              <li>• Keycloak RBAC وربط الصلاحيات حسب الدور.</li>
              <li>• Data Classification وField Masking وRow-Level Security.</li>
              <li>• Encrypted Secrets عبر credentials_ref بدل حفظ الأسرار كنص.</li>
              <li>• Human Approval للإجراءات الحساسة.</li>
              <li>• منع UPDATE / DELETE / DROP / ALTER في Data Warehouse.</li>
            </ul>
          </Card>
        </section>
      </main>
    </AppShell>
  );
}
