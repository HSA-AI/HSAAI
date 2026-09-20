# HSAAI Unified Information Architecture (Phase 4 Redesign)

## Design Principles
Inspired by: OpenAI, Microsoft, Anthropic, Google Cloud, SAP Fiori, IBM Watson, Material Design 3

1. **One canonical page per function** — no duplicates, no "_center" / "_studio" splits
2. **Three primary navigation zones**: Work / Build / Govern
3. **Progressive disclosure** — simple on top, advanced in tabs
4. **Role-based entry points** — different homepages for different roles

## Final Page Count: 22 (down from 55)

### WORK ZONE (employee-facing)
- `/chat` — AI chat assistant (primary surface)
- `/workspace` — Personal workspace (files, recent activity)
- `/dashboard` — Role-based dashboard
- `/executive-dashboard` — Executive KPI view (C-suite only)
- `/finops` — Cost & usage analytics

### BUILD ZONE (creator-facing)
- `/no-code-agent-studio` — Visual agent builder (replaces 4 prior studios)
- `/workflow-studio` — Workflow builder + runtime + monitoring (replaces 6 prior pages)
- `/knowledge-hub` — Knowledge base + documents (replaces 4 prior pages)
- `/knowledge-graph` — Graph visualization & query
- `/model-routing` — LLM model routing configuration

### GOVERN ZONE (admin-facing)
- `/enterprise-governance-center` — Unified governance: policies, compliance, audit, risk, security
- `/observability-center` — Unified observability: metrics, logs, traces, SLOs, maturity
- `/enterprise-agents-center` — Agent management & monitoring
- `/ai-center-of-excellence` — CoE dashboard, training resources
- `/admin/*` — Sub-pages for: models, providers, training, integrations, knowledge-governance, department-agents, local-models, smart-responses

### SHARED ZONE
- `/getting-started` — Onboarding for new users
- `/architecture` — System architecture documentation
- `/documentation` — API & user docs
- `/help-center` — Self-service support
- `/settings` — User preferences & API keys

## Removed Duplicates (33 pages deleted in Phase 4)

| Removed | Merged Into | Reason |
|--------|-------------|--------|
| governance-center | enterprise-governance-center | Duplicate |
| ai-risk | enterprise-governance-center | Sub-page of governance |
| ai-security | enterprise-governance-center | Sub-page of governance |
| knowledge | knowledge-hub | Duplicate |
| monitoring-enterprise | observability-center | Duplicate |
| maturity-center | observability-center | Sub-page of observability |
| ai-operations-center | observability-center | Consolidated ops view |
| data-governance | enterprise-governance-center | Sub-page of governance |
| agent-runtime | enterprise-agents-center | Sub-page of agents |
| audit-logs | enterprise-governance-center | Sub-page of governance |
| approvals | workflow-studio | Sub-page of workflow |
| integrations-center | admin/enterprise-integrations | Sub-page of admin |
| api | (dev only, removed) | Dev artifact |
| enterprise-search-2 | (renamed to enterprise-search, then merged into knowledge-hub) | Duplicate |
| workflow-center | workflow-studio | Duplicate |
| workflow-builder | workflow-studio | Duplicate |
| workflow-runtime | workflow-studio | Duplicate |
| workflow-execution-center | workflow-studio | Duplicate |
| workflows | workflow-studio | Duplicate |
| agent-studio | no-code-agent-studio | Duplicate |
| agent-builder | no-code-agent-studio | Duplicate |
| agent-control-center | enterprise-agents-center | Duplicate |
| agent-mesh | enterprise-agents-center | Duplicate |
| ai-operations | observability-center | Duplicate |
| ai-operations-analytics | observability-center | Duplicate |
| agents | enterprise-agents-center | Duplicate |
| integrations-monitoring | observability-center | Sub-page of observability |
| enterprise-search | knowledge-hub | Consolidated search |
| coe | ai-center-of-excellence | Duplicate |
| governance | enterprise-governance-center | Duplicate |
| integrations | admin/enterprise-integrations | Sub-page of admin |
| observability | observability-center | Duplicate |
| executive | executive-dashboard | Duplicate |

## Navigation Pattern (Top Bar)

```
[HSAAI Logo]    Work ▾   Build ▾   Govern ▾       [🔍 Search]  [👤 User]
                ├ Chat    ├ Agent Studio  ├ Governance
                ├ Workspace├ Workflow      ├ Observability
                ├ Dashboard├ Knowledge     ├ Agents Center
                └ FinOps  └ Model Routing └ CoE
```

## Role-Based Default Landing

| Role | Default Page |
|------|-------------|
| Employee | /chat |
| Manager | /dashboard |
| Executive | /executive-dashboard |
| Builder | /no-code-agent-studio |
| Admin | /enterprise-governance-center |
| Governance | /enterprise-governance-center |
| SRE | /observability-center |
| Finance | /finops |
