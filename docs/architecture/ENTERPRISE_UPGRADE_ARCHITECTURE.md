# HSAAI Enterprise Upgrade Architecture

```text
User / Department
  -> Smart Responses Engine
  -> Arabic Intent Detection
  -> Supervisor Agent
      ├── HR Agent
      ├── Finance Agent
      ├── IT Agent
      └── Legal Agent
  -> RBAC + Tenant Isolation
  -> RAG / Qdrant / Knowledge Governance
  -> Workflow Automation Engine
  -> Human-in-the-Loop Approval
  -> Observability / Audit Logs
```

## Added Domains
- Agent Orchestration
- Workflow Automation
- Enterprise Data Connectors
- Observability Platform
- Human-in-the-Loop Governance

## Production Notes
- New tables are tenant/workspace scoped.
- Sensitive actions require Keycloak roles and audit logging.
- Connectors store secret references only, never raw secrets.
