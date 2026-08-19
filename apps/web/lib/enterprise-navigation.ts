import {
  AlertTriangle,
  BarChart3,
  Bot,
  Crown,
  BookOpenText,
  Building2,
  CircleDollarSign,
  Compass,
  Database,
  FileQuestion,
  GitBranch,
  GraduationCap,
  HelpCircle,
  LayoutDashboard,
  Network,
  PlugZap,
  Search,
  Settings,
  ShieldCheck,
  ShieldAlert,
  Sparkles,
  Workflow,
} from "lucide-react";

export type EnterpriseNavItem = {
  href: string;
  label: string;
  labelEn: string;
  hint: string;
  keywords: string[];
  permission?: string;
  section: "core" | "operate" | "build" | "govern" | "admin" | "help";
  icon: typeof LayoutDashboard;
  primary?: boolean;
};

export const enterpriseNavSections: Array<{ key: EnterpriseNavItem["section"]; title: string; titleEn: string }> = [
  { key: "core", title: "التشغيل اليومي", titleEn: "Daily Work" },
  { key: "operate", title: "مراكز التشغيل", titleEn: "Operations" },
  { key: "build", title: "البناء والأتمتة", titleEn: "Build" },
  { key: "govern", title: "الحوكمة والأمان", titleEn: "Governance" },
  { key: "admin", title: "الإدارة", titleEn: "Administration" },
  { key: "help", title: "المساعدة", titleEn: "Help" },
];

export const enterpriseNavItems: EnterpriseNavItem[] = [

  { href: "/executive-dashboard", label: "Executive Command", labelEn: "Executive Command", hint: "مؤشرات الإدارة العليا والقيمة والمخاطر", keywords: ["executive", "ceo", "cio", "command", "roi"], section: "core", icon: Crown },
  { href: "/enterprise-agents-center", label: "Agent Mesh Center", labelEn: "Agent Mesh Center", hint: "شبكة وكلاء متقدمة بإشراف مركزي", keywords: ["agent mesh", "supervisor", "delegation", "وكلاء"], section: "operate", icon: Network },
  { href: "/ai-center-of-excellence", label: "AI Center of Excellence", labelEn: "AI CoE", hint: "استراتيجية، محفظة، تدريب، تبني", keywords: ["coe", "center of excellence", "strategy", "training"], section: "govern", icon: GraduationCap },
  { href: "/enterprise-governance-center", label: "AI Risk Center", labelEn: "AI Risk", hint: "سجل المخاطر والتخفيف وخرائط الحرارة", keywords: ["risk", "مخاطر", "hallucination", "bias"], section: "govern", icon: AlertTriangle },
  { href: "/enterprise-governance-center", label: "AI Security Center", labelEn: "AI Security", hint: "Prompt Firewall وDLP وAI SOC", keywords: ["security", "prompt injection", "dlp", "soc"], section: "govern", icon: ShieldAlert },
  { href: "/admin/knowledge-governance", label: "Data Governance", labelEn: "Data Governance", hint: "كتالوج البيانات والجودة والملكية", keywords: ["data governance", "catalog", "lineage", "quality"], section: "govern", icon: Database },
  { href: "/admin", label: "Audit Logs", labelEn: "Audit Logs", hint: "سجل تدقيق لكل إجراء حساس", keywords: ["audit", "logs", "trace"], section: "admin", icon: FileQuestion },
  { href: "/dashboard", label: "لوحة القيادة", labelEn: "Dashboard", hint: "مؤشرات تنفيذية وصحة المنصة", keywords: ["dashboard", "executive", "kpi", "لوحة"], section: "core", icon: LayoutDashboard },
  { href: "/chat?new=1", label: "AI Chat", labelEn: "AI Chat", hint: "مساعد مؤسسي موحد", keywords: ["chat", "assistant", "محادثة", "مساعد"], section: "core", icon: Bot, primary: true },
  { href: "/knowledge-hub", label: "Enterprise Search", labelEn: "Enterprise Search", hint: "بحث موحد بصلاحيات", keywords: ["search", "بحث", "documents", "citations"], section: "core", icon: Search },
  { href: "/knowledge-hub", label: "Knowledge Hub", labelEn: "Knowledge Hub", hint: "وثائق، RAG، مصادر، صلاحيات", keywords: ["knowledge", "rag", "qdrant", "معرفة"], section: "core", icon: BookOpenText },
  { href: "/enterprise-agents-center", label: "Agent Mesh", labelEn: "Agent Mesh", hint: "Supervisor والوكلاء المتخصصون", keywords: ["agents", "supervisor", "mesh", "وكلاء"], section: "operate", icon: Network },
  { href: "/workflow-studio", label: "Approvals", labelEn: "Approvals", hint: "موافقات بشرية للإجراءات الحساسة", keywords: ["approval", "human", "موافقة"], section: "operate", icon: ShieldCheck },
  { href: "/workflow-studio", label: "Workflow Studio", labelEn: "Workflow Studio", hint: "تصميم وتشغيل سير العمل", keywords: ["workflow", "automation", "سير"], section: "build", icon: Workflow },
  { href: "/no-code-agent-studio", label: "No-Code Agent Studio", labelEn: "Agent Studio", hint: "بناء وكلاء بدون كود", keywords: ["agent studio", "builder", "no code"], section: "build", icon: Sparkles },
  { href: "/knowledge-graph", label: "Knowledge Graph", labelEn: "Knowledge Graph", hint: "كيانات وعلاقات وتأثيرات", keywords: ["graph", "entities", "relationships"], section: "operate", icon: GitBranch },
  { href: "/ai-center-of-excellence", label: "AI CoE", labelEn: "AI CoE", hint: "محفظة، سياسات، مخاطر، تدريب", keywords: ["coe", "center of excellence", "training"], section: "govern", icon: GraduationCap },
  { href: "/finops", label: "AI FinOps", labelEn: "AI FinOps", hint: "تكلفة النماذج والوكلاء", keywords: ["finops", "cost", "tokens", "تكلفة"], section: "govern", icon: CircleDollarSign },
  { href: "/enterprise-governance-center", label: "Governance Center", labelEn: "Governance Center", hint: "سياسات وتصنيف وامتثال", keywords: ["governance", "policy", "risk", "حوكمة"], section: "govern", icon: ShieldCheck },
  { href: "/admin/enterprise-integrations", label: "Integrations", labelEn: "Integrations", hint: "SAP وAD وSharePoint وغيرها", keywords: ["sap", "sharepoint", "active directory", "jira", "integrations"], section: "admin", icon: PlugZap },
  { href: "/observability-center", label: "Observability", labelEn: "Observability", hint: "أداء، سجلات، تنبيهات", keywords: ["monitoring", "grafana", "prometheus", "logs"], section: "admin", icon: BarChart3 },
  { href: "/settings", label: "Settings", labelEn: "Settings", hint: "إعدادات المستخدم والمنصة", keywords: ["settings", "preferences"], section: "admin", icon: Settings },
  { href: "/admin", label: "Admin", labelEn: "Admin", hint: "مستخدمون وصلاحيات وتشغيل", keywords: ["admin", "rbac", "roles"], section: "admin", icon: Building2 },
  { href: "/getting-started", label: "Getting Started", labelEn: "Getting Started", hint: "دليل البداية السريع", keywords: ["start", "onboarding", "guide"], section: "help", icon: Compass },
  { href: "/help-center", label: "Help Center", labelEn: "Help Center", hint: "مساعدة داخلية وتوثيق", keywords: ["help", "docs", "documentation"], section: "help", icon: HelpCircle },
  { href: "/documentation", label: "Documentation", labelEn: "Documentation", hint: "توثيق المستخدم والمطور", keywords: ["documentation", "api", "developer"], section: "help", icon: FileQuestion },
];

export const enterpriseQuickActions = [
  { label: "محادثة جديدة", href: "/chat?new=1", shortcut: "N", description: "ابدأ محادثة مدعومة بالمعرفة والصلاحيات" },
  { label: "رفع وثيقة", href: "/knowledge-hub", shortcut: "U", description: "أضف وثيقة إلى قاعدة المعرفة المؤسسية" },
  { label: "إنشاء وكيل", href: "/no-code-agent-studio", shortcut: "A", description: "صمم وكيلًا جديدًا بدون كود" },
  { label: "إنشاء Workflow", href: "/workflow-studio", shortcut: "W", description: "صمم أتمتة مؤسسية بموافقة بشرية" },
  { label: "فتح الموافقات", href: "/workflow-studio", shortcut: "P", description: "راجع الطلبات الحساسة قبل التنفيذ" },
];

export function searchEnterpriseNavigation(query: string) {
  const q = query.trim().toLowerCase();
  if (!q) return enterpriseNavItems;
  return enterpriseNavItems.filter((item) =>
    [item.label, item.labelEn, item.hint, ...item.keywords].some((value) => value.toLowerCase().includes(q)),
  );
}
