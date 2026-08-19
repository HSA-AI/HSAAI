# HSAAI Agent Framework

## 1. Overview

The HSAAI Agent Framework provides 21 specialized AI agents, each tailored to a specific business department within HSA Group. Agents operate within a governed execution environment with tool calling, memory management, and policy enforcement.

## 2. Agent Architecture

```
User Query → HSAAI AI Orchestrator → Department Agent Selection →
Agent Execution (Tool Calling + RAG + LLM) → Response Verification →
Delivery
```

### Agent Components
- **System Instructions:** Department-specific behavioral rules
- **Knowledge Sources:** RAG-backed domain knowledge
- **Tools:** Department-specific API integrations
- **Permissions:** RBAC + ABAC scoped to department
- **Risk Level:** Low, Medium, High, Critical
- **Approval Requirements:** High-risk actions require AI Governance Officer approval

## 3. Department Agents

| Agent | Department | Risk Level | Key Tools |
|-------|-----------|------------|-----------|
| HR Assistant | Human Resources | Low | `hr.leave_balance`, `hr.submit_request` |
| Finance Assistant | Finance | High | `sap.invoice_read`, `fin.budget_check` |
| Supply Chain Assistant | Supply Chain | Medium | `wms.inventory_read`, `sc.forecast` |
| Legal Assistant | Legal | High | `legal.contract_search`, `legal.citation_check` |
| Customer Service Assistant | Customer Service | Low | `crm.ticket_create`, `wms.order_status` |
| Executive Assistant | Executive Office | Medium | `powerbi.embed`, `analytics.kpi_read` |
| Procurement Assistant | Procurement | Medium | `sap.po_read`, `procurement.vendor_search` |
| Manufacturing Assistant | Manufacturing | Medium | `mes.production_read`, `qa.report_anomaly` |
| Quality Assurance Assistant | QA | Low | `qa.manual_search`, `qa.report_issue` |
| IT Operations Assistant | IT | Medium | `it.ticket_create`, `monitoring.alerts` |
| Sales Assistant | Sales | Low | `crm.customer_read`, `sales.forecast` |
| Marketing Assistant | Marketing | Low | `marketing.campaign_read` |
| Logistics Assistant | Logistics | Medium | `wms.shipment_track`, `logistics.route_optimize` |
| Treasury Assistant | Treasury | High | `treasury.cashflow_read`, `fin.fx_rate` |
| Accounting Assistant | Accounting | Medium | `sap.gl_read`, `acc.reconciliation` |
| Compliance Assistant | Compliance | High | `compliance.policy_search`, `compliance.audit_log` |
| Cybersecurity Assistant | Cybersecurity | High | `security.scan_read`, `security.incident_log` |
| Audit Assistant | Internal Audit | Medium | `audit.log_search`, `audit.report_generate` |
| Research Assistant | R&D | Low | `research.literature_search` |
| Warehouse Assistant | Warehouses | Low | `wms.inventory_check`, `wms.picklist_generate` |
| Knowledge Assistant | Cross-department | Low | `rag.search`, `rag.retrieve_document` |

## 4. Tool Calling Protocol

```json
{
  "tool": "search_knowledge",
  "arguments": {
    "query": "procurement policy threshold",
    "top_k": 5,
    "filters": {"department": "Procurement"}
  }
}
```

### Available Tools
| Tool | Purpose | Permission |
|------|---------|------------|
| `search_knowledge` | Hybrid retrieval over enterprise knowledge | `analytics.view` |
| `retrieve_document` | Fetch full document with chunks | Per document ACL |
| `verify_answer` | Hallucination check on generated response | `evaluations.run` |
| `generate_citation` | Create verified citation for a chunk | `analytics.view` |

## 5. Memory Management

- **Session Memory:** Redis-backed, 24-hour TTL
- **Conversation History:** PostgreSQL with tenant isolation
- **Context Window:** Managed by LLM Gateway (8K tokens default)
- **Context Compression:** Top-5 most relevant sentences per chunk

## 6. Governance

- All agent actions logged to audit trail (HMAC-signed)
- High-risk actions require explicit approval
- Agent deployment requires AI Governance Officer sign-off
- Performance monitored: success rate, latency, hallucination rate
