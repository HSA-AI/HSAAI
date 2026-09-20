import type {
  WorkflowAnalytics,
  WorkflowApproval,
  WorkflowDefinitionEnterprise,
  WorkflowExecution,
  WorkflowSchedule,
  WorkflowVersion,
} from "./workflow-studio.types";

const now = "2026-06-06T00:00:00.000Z";

const workflows: WorkflowDefinitionEnterprise[] = [
  {
    id: "wf_contract_approval_enterprise",
    name: "Contract Review & Approval",
    description: "OCR, knowledge search, local LLM analysis, legal approval, and archive workflow.",
    owner: "Legal Operations",
    department: "Legal",
    status: "active",
    currentVersion: "v3",
    tags: ["legal", "approval", "documents"],
    createdAt: now,
    updatedAt: now,
    nodes: [
      { id: "start", type: "start", label: "Contract Uploaded", position: { x: 50, y: 160 }, config: {} },
      { id: "search", type: "knowledge_search", label: "Search Legal KB", position: { x: 270, y: 160 }, config: { collection: "legal" } },
      { id: "llm", type: "llm", label: "Local LLM Risk Summary", position: { x: 520, y: 160 }, config: { model: "qwen2.5-local" } },
      { id: "approval", type: "human_approval", label: "Legal Manager Approval", position: { x: 790, y: 160 }, config: { role: "Legal Manager" } },
      { id: "end", type: "end", label: "Archive", position: { x: 1060, y: 160 }, config: {} },
    ],
    edges: [
      { id: "e1", source: "start", target: "search" },
      { id: "e2", source: "search", target: "llm" },
      { id: "e3", source: "llm", target: "approval" },
      { id: "e4", source: "approval", target: "end" },
    ],
  },
  {
    id: "wf_daily_executive_brief",
    name: "Daily Executive AI Brief",
    description: "Scheduled workflow to summarize enterprise AI usage, risks, and operations for executives.",
    owner: "AI Office",
    department: "Executive",
    status: "active",
    currentVersion: "v2",
    tags: ["executive", "analytics", "schedule"],
    createdAt: now,
    updatedAt: now,
    nodes: [
      { id: "start", type: "start", label: "Daily Schedule", position: { x: 50, y: 160 }, config: { time: "08:00" } },
      { id: "tool", type: "tool", label: "Collect Metrics", position: { x: 300, y: 160 }, config: { source: "executive_analytics" } },
      { id: "llm", type: "llm", label: "Summarize Locally", position: { x: 560, y: 160 }, config: { model: "llama-local" } },
      { id: "end", type: "end", label: "Publish Brief", position: { x: 820, y: 160 }, config: {} },
    ],
    edges: [
      { id: "e1", source: "start", target: "tool" },
      { id: "e2", source: "tool", target: "llm" },
      { id: "e3", source: "llm", target: "end" },
    ],
  },
];

const versions: WorkflowVersion[] = [
  { id: "wv_001", workflowId: "wf_contract_approval_enterprise", version: "v3", changeSummary: "Added legal manager approval node and risk summary output.", author: "AI Admin", createdAt: now, isPublished: true },
  { id: "wv_002", workflowId: "wf_daily_executive_brief", version: "v2", changeSummary: "Added governance risk summary into the daily brief.", author: "Executive Office", createdAt: now, isPublished: true },
];

const executions: WorkflowExecution[] = [
  { id: "run_1001", workflowId: "wf_contract_approval_enterprise", workflowName: "Contract Review & Approval", version: "v3", status: "completed", triggeredBy: "legal.user", startedAt: now, finishedAt: now, durationMs: 142000, stepsTotal: 5, stepsCompleted: 5, logs: ["Started", "Knowledge search completed", "Local LLM completed", "Approval approved", "Archived"] },
  { id: "run_1002", workflowId: "wf_daily_executive_brief", workflowName: "Daily Executive AI Brief", version: "v2", status: "running", triggeredBy: "scheduler", startedAt: now, stepsTotal: 4, stepsCompleted: 2, logs: ["Scheduled run started", "Metrics collected"] },
  { id: "run_1003", workflowId: "wf_contract_approval_enterprise", workflowName: "Contract Review & Approval", version: "v3", status: "waiting_approval", triggeredBy: "procurement.user", startedAt: now, stepsTotal: 5, stepsCompleted: 3, logs: ["Started", "Knowledge search completed", "Waiting for human approval"] },
];

const schedules: WorkflowSchedule[] = [
  { id: "sch_001", workflowId: "wf_daily_executive_brief", workflowName: "Daily Executive AI Brief", frequency: "daily", timezone: "Asia/Aden", enabled: true, nextRunAt: "2026-06-07T08:00:00.000+03:00", createdBy: "Executive Office" },
  { id: "sch_002", workflowId: "wf_contract_approval_enterprise", workflowName: "Contract Review & Approval", frequency: "manual", timezone: "Asia/Aden", enabled: false, createdBy: "Legal Operations" },
];

const approvals: WorkflowApproval[] = [
  { id: "apv_001", executionId: "run_1003", workflowName: "Contract Review & Approval", nodeLabel: "Legal Manager Approval", requestedRole: "Legal Manager", requestedBy: "procurement.user", status: "pending", createdAt: now },
  { id: "apv_002", executionId: "run_1001", workflowName: "Contract Review & Approval", nodeLabel: "Legal Manager Approval", requestedRole: "Legal Manager", requestedBy: "legal.user", status: "approved", createdAt: now, decidedAt: now, comment: "Approved after local AI risk summary." },
];

export class WorkflowStudioService {
  static overview() {
    const analytics = this.analytics();
    return { module: "Workflow Studio Enterprise", mode: "internal-only", analytics, latestExecutions: executions.slice(0, 5), pendingApprovals: approvals.filter((item) => item.status === "pending") };
  }
  static definitions() { return workflows; }
  static versions() { return versions; }
  static executions() { return executions; }
  static schedules() { return schedules; }
  static approvals() { return approvals; }
  static analytics(): WorkflowAnalytics {
    return {
      totalWorkflows: workflows.length,
      activeWorkflows: workflows.filter((workflow) => workflow.status === "active").length,
      totalExecutions: 1284,
      successRate: 94.2,
      failureRate: 3.1,
      averageRuntimeSeconds: 82,
      pendingApprovals: approvals.filter((item) => item.status === "pending").length,
      scheduledWorkflows: schedules.filter((item) => item.enabled).length,
      topWorkflows: [
        { name: "Contract Review & Approval", executions: 420, successRate: 95.1 },
        { name: "Daily Executive AI Brief", executions: 186, successRate: 98.4 },
        { name: "Invoice OCR Approval", executions: 154, successRate: 92.7 },
      ],
      trend: [
        { day: "Sat", executions: 142, failures: 3 },
        { day: "Sun", executions: 168, failures: 6 },
        { day: "Mon", executions: 211, failures: 8 },
        { day: "Tue", executions: 194, failures: 5 },
        { day: "Wed", executions: 231, failures: 7 },
        { day: "Thu", executions: 207, failures: 4 },
        { day: "Fri", executions: 131, failures: 2 },
      ],
    };
  }
}
