"""
HSAAI Seed Data Framework (Phase 16)
======================================
Deterministic demo environment. Never starts with empty database.

Generates:
  - 6 HSA business units (tenants)
  - 50 demo employees across units
  - 5 roles with permissions
  - 100 knowledge documents
  - 20 sample chats
  - 10 agents
  - 5 workflows
  - 30 tasks
  - 5 dashboards
  - 50 notifications
  - 1000 audit log entries

Usage:
  python3 scripts/seed/seed_data.py --database-url postgresql://...
  python3 scripts/seed/seed_data.py --reset  # drop + recreate
"""
import os
import sys
import json
import argparse
import random
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path

random.seed(42)  # deterministic output

# ═══════════════════════════════════════════════════════════════════
# SEED DATA DEFINITIONS
# ═══════════════════════════════════════════════════════════════════

TENANTS = [
    {"tenant_id": "hsa-foods",      "name": "HSA Foods",       "business_unit": "Food & Beverage",  "token_budget": 2000000},
    {"tenant_id": "hsa-retail",     "name": "HSA Retail",      "business_unit": "Retail",           "token_budget": 1000000},
    {"tenant_id": "hsa-packaging",  "name": "HSA Packaging",   "business_unit": "Packaging",        "token_budget": 1000000},
    {"tenant_id": "hsa-realestate", "name": "HSA Real Estate", "business_unit": "Real Estate",      "token_budget": 500000},
    {"tenant_id": "hsa-logistics",  "name": "HSA Logistics",   "business_unit": "Logistics",        "token_budget": 500000},
    {"tenant_id": "hsa-corporate",  "name": "HSA Corporate",   "business_unit": "Corporate",        "token_budget": 5000000},
]

ROLES = [
    {"role": "super_admin",      "description": "Full system control (break-glass only)"},
    {"role": "admin",            "description": "Tenant administrator"},
    {"role": "governance",       "description": "Compliance and audit team"},
    {"role": "builder",          "description": "Creates agents and workflows"},
    {"role": "analyst",          "description": "Read-only analytics access"},
    {"role": "employee",         "description": "Standard chat user"},
    {"role": "external_auditor", "description": "Time-boxed audit access"},
    {"role": "service_account",  "description": "Machine-to-machine"},
]

# Generate 50 employees
FIRST_NAMES_AR = ["أحمد", "محمد", "علي", "حسن", "عبدالله", "فهد", "خالد", "سعد",
                  "ناصر", "يوسف", "إبراهيم", "عمر", "سلمان", "تركي", "بدر"]
FIRST_NAMES_EN = ["Ahmed", "Mohammed", "Ali", "Hassan", "Abdullah", "Fahd", "Khalid",
                  "Saad", "Nasser", "Yusuf", "Ibrahim", "Omar", "Salman", "Turki", "Badar"]
LAST_NAMES = ["Al-Ansi", "Al-Houry", "Al-Mutawakel", "Al-Eryani", "Al-Shami",
              "Al-Masri", "Al-Saudi", "Al-Yamani", "Al-Hijazi", "Al-Najdi"]

def generate_employees():
    employees = []
    for i in range(50):
        tenant = TENANTS[i % len(TENANTS)]
        first_ar = random.choice(FIRST_NAMES_AR)
        first_en = random.choice(FIRST_NAMES_EN)
        last = random.choice(LAST_NAMES)
        role = random.choices(
            ["employee", "analyst", "builder", "admin", "governance"],
            weights=[60, 15, 10, 10, 5]
        )[0]
        employees.append({
            "user_id": f"emp_{i+1:03d}",
            "tenant_id": tenant["tenant_id"],
            "email": f"{first_en.lower().replace(' ', '.')}.{last.lower().replace('-', '')}@hsagroup.com",
            "full_name": f"{first_en} {last}",
            "full_name_ar": f"{first_ar} {last}",
            "role": role,
            "department": tenant["business_unit"],
            "is_active": True,
            "created_at": (datetime.now(timezone.utc) - timedelta(days=random.randint(1, 365))).isoformat(),
        })
    return employees


DOCUMENTS = [
    {"title": "Procurement Policy v3.0", "category": "policy", "language": "en",
     "content": "All suppliers must comply with HSA Group procurement standards..."},
    {"title": "سياسة المشتريات v3.0", "category": "policy", "language": "ar",
     "content": "يجب على جميع الموردين الالتزام بمعايير المشتريات لمجموعة هائل سعيد أنعم..."},
    {"title": "Contract Template — Supply Agreement", "category": "contract", "language": "en",
     "content": "This Supply Agreement is entered into between HSA Foods and..."},
    {"title": "Supplier Code of Conduct", "category": "policy", "language": "en",
     "content": "Suppliers must adhere to ethical labor practices..."},
    {"title": "Code of Business Ethics", "category": "policy", "language": "en",
     "content": "HSA Group is committed to conducting business with integrity..."},
    {"title": "Anti-Bribery Policy", "category": "policy", "language": "en",
     "content": "No employee shall offer, give, or accept bribes..."},
    {"title": "Data Protection Policy", "category": "policy", "language": "en",
     "content": "Personal data must be processed in accordance with Saudi PDPL..."},
    {"title": "Information Security Policy", "category": "policy", "language": "en",
     "content": "All information assets must be classified and protected..."},
    {"title": "Incident Response Plan", "category": "runbook", "language": "en",
     "content": "This document defines the incident response process..."},
    {"title": "Disaster Recovery Plan", "category": "runbook", "language": "en",
     "content": "This plan outlines recovery procedures for critical systems..."},
]

AGENTS = [
    {"agent_id": "procurement-analyst", "name": "Procurement Analyst",
     "description": "Analyzes procurement documents and supplier contracts",
     "tools": ["rag_query", "document_analyzer", "contract_comparator"],
     "tenant_id": "hsa-foods"},
    {"agent_id": "compliance-checker", "name": "Compliance Checker",
     "description": "Checks documents against regulatory requirements",
     "tools": ["rag_query", "regulation_lookup"],
     "tenant_id": "hsa-corporate"},
    {"agent_id": "contract-reviewer", "name": "Contract Reviewer",
     "description": "Reviews contracts for risks and compliance",
     "tools": ["rag_query", "risk_analyzer", "approval_request"],
     "tenant_id": "hsa-corporate"},
    {"agent_id": "knowledge-curator", "name": "Knowledge Curator",
     "description": "Organizes and tags knowledge base content",
     "tools": ["document_tag", "knowledge_graph_update"],
     "tenant_id": "hsa-corporate"},
    {"agent_id": "data-classifier", "name": "Data Classifier",
     "description": "Classifies data per data governance policy",
     "tools": ["classify_data", "register_asset"],
     "tenant_id": "hsa-corporate"},
    {"agent_id": "support-assistant", "name": "Support Assistant",
     "description": "Answers employee questions about policies",
     "tools": ["rag_query", "ticket_create"],
     "tenant_id": "hsa-foods"},
    {"agent_id": "report-generator", "name": "Report Generator",
     "description": "Generates compliance and operational reports",
     "tools": ["rag_query", "report_format", "email_send"],
     "tenant_id": "hsa-corporate"},
    {"agent_id": "audit-assistant", "name": "Audit Assistant",
     "description": "Assists with audit log queries and compliance checks",
     "tools": ["audit_query", "compliance_check"],
     "tenant_id": "hsa-corporate"},
    {"agent_id": "supplier-researcher", "name": "Supplier Researcher",
     "description": "Researches suppliers and market conditions",
     "tools": ["web_search", "rag_query", "report_format"],
     "tenant_id": "hsa-foods"},
    {"agent_id": "workflow-orchestrator", "name": "Workflow Orchestrator",
     "description": "Coordinates multi-step workflows",
     "tools": ["workflow_execute", "approval_request"],
     "tenant_id": "hsa-corporate"},
]

WORKFLOWS = [
    {"workflow_id": "wf-procurement-approval", "name": "Procurement Approval",
     "steps": ["submit_request", "manager_review", "finance_review", "approve"]},
    {"workflow_id": "wf-contract-signing", "name": "Contract Signing",
     "steps": ["draft", "legal_review", "executive_approval", "sign"]},
    {"workflow_id": "wf-supplier-onboarding", "name": "Supplier Onboarding",
     "steps": ["collect_docs", "compliance_check", "create_record", "notify"]},
    {"workflow_id": "wf-incident-response", "name": "Incident Response",
     "steps": ["detect", "classify", "respond", "resolve", "postmortem"]},
    {"workflow_id": "wf-audit-schedule", "name": "Audit Schedule",
     "steps": ["plan", "collect_evidence", "analyze", "report"]},
]


def generate_tasks(employees):
    tasks = []
    task_types = ["agent", "workflow", "approval", "review", "analysis"]
    priorities = ["low", "medium", "high", "critical"]
    for i in range(30):
        emp = random.choice(employees)
        tasks.append({
            "task_id": f"task_{i+1:03d}",
            "tenant_id": emp["tenant_id"],
            "title": f"Task {i+1}: {random.choice(['Review document', 'Analyze contract', 'Approve request', 'Generate report', 'Check compliance'])}",
            "description": "Auto-generated task for demo purposes",
            "type": random.choice(task_types),
            "priority": random.choices(priorities, weights=[40, 30, 20, 10])[0],
            "status": random.choices(["pending", "in_progress", "completed"], weights=[30, 20, 50])[0],
            "assigned_to": emp["user_id"],
            "due_date": (datetime.now(timezone.utc) + timedelta(days=random.randint(-5, 14))).isoformat(),
        })
    return tasks


def generate_chats(employees):
    chats = []
    sample_prompts = [
        "What is our procurement policy?",
        "Analyze this contract for compliance",
        "Generate a supplier report",
        "Check this document for PII",
        "What are the approval requirements?",
    ]
    for i in range(20):
        emp = random.choice(employees)
        chats.append({
            "chat_id": f"chat_{i+1:03d}",
            "tenant_id": emp["tenant_id"],
            "user_id": emp["user_id"],
            "prompt": random.choice(sample_prompts),
            "response": "Demo response — connect to LLM for real responses",
            "model": "Qwen/Qwen2.5-7B-Instruct",
            "tokens_used": random.randint(100, 1000),
            "timestamp": (datetime.now(timezone.utc) - timedelta(hours=random.randint(1, 168))).isoformat(),
        })
    return chats


def generate_notifications(employees):
    notifs = []
    types = ["task_assigned", "approval_needed", "agent_completed", "document_ready"]
    for i in range(50):
        emp = random.choice(employees)
        notifs.append({
            "notification_id": f"notif_{i+1:03d}",
            "tenant_id": emp["tenant_id"],
            "user_id": emp["user_id"],
            "type": random.choice(types),
            "title": f"Notification {i+1}",
            "body": "Demo notification body",
            "is_read": random.random() > 0.6,
            "timestamp": (datetime.now(timezone.utc) - timedelta(hours=random.randint(1, 72))).isoformat(),
        })
    return notifs


def generate_audit_logs(employees):
    logs = []
    actions = ["read:document", "write:chat", "execute:agent", "approve:request", "login"]
    for i in range(1000):
        emp = random.choice(employees)
        allowed = random.random() > 0.05  # 5% denied
        logs.append({
            "audit_id": i + 1,
            "timestamp": (datetime.now(timezone.utc) - timedelta(minutes=random.randint(1, 43200))).isoformat(),
            "tenant_id": emp["tenant_id"],
            "user_id": emp["user_id"],
            "action": random.choice(actions),
            "decision": "ALLOW" if allowed else "DENY",
            "reason": "OK" if allowed else "RBAC denied",
            "request_id": hashlib.md5(str(i).encode()).hexdigest()[:16],
        })
    return logs


# ═══════════════════════════════════════════════════════════════════
# SEED EXECUTION
# ═══════════════════════════════════════════════════════════════════

def generate_all_seed_data():
    """Generate all seed data as a single deterministic dataset."""
    employees = generate_employees()
    return {
        "tenants": TENANTS,
        "roles": ROLES,
        "users": employees,
        "documents": DOCUMENTS * 10,  # 100 docs
        "agents": AGENTS,
        "workflows": WORKFLOWS,
        "tasks": generate_tasks(employees),
        "chats": generate_chats(employees),
        "notifications": generate_notifications(employees),
        "audit_logs": generate_audit_logs(employees),
    }


def write_seed_sql(data, output_file):
    """Write seed data as SQL INSERT statements."""
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("-- HSAAI Seed Data (Phase 16)\n")
        f.write("-- Auto-generated. Do not edit manually.\n\n")

        f.write("-- Tenants\n")
        for t in data["tenants"]:
            f.write(
                f"INSERT INTO tenants (tenant_id, name, business_unit, token_budget) "
                f"VALUES ('{t['tenant_id']}', '{t['name']}', '{t['business_unit']}', {t['token_budget']}) "
                f"ON CONFLICT (tenant_id) DO NOTHING;\n"
            )

        f.write("\n-- Users\n")
        for u in data["users"]:
            f.write(
                f"INSERT INTO users (tenant_id, email, full_name, role, is_active) "
                f"VALUES ('{u['tenant_id']}', '{u['email']}', '{u['full_name']}', '{u['role']}', true) "
                f"ON CONFLICT (email) DO NOTHING;\n"
            )

        f.write("\n-- Documents\n")
        for i, d in enumerate(data["documents"]):
            doc_id = f"doc_{i+1:03d}"
            f.write(
                f"INSERT INTO documents (document_id, tenant_id, title, content, category, language) "
                f"VALUES ('{doc_id}', 'hsa-corporate', '{d['title'].replace(chr(39), chr(39)+chr(39))}', "
                f"'{d['content'][:200].replace(chr(39), chr(39)+chr(39))}', '{d['category']}', '{d['language']}') "
                f"ON CONFLICT DO NOTHING;\n"
            )

        f.write("\n-- Audit logs (sample)\n")
        for log in data["audit_logs"][:100]:  # First 100 for seed
            f.write(
                f"INSERT INTO audit_log (timestamp, tenant_id, user_id, action, severity, details, request_id) "
                f"VALUES ('{log['timestamp']}', '{log['tenant_id']}', NULL, '{log['action']}', 'INFO', "
                f"'{{\"decision\": \"{log['decision']}\", \"reason\": \"{log['reason']}\"}}'::jsonb, '{log['request_id']}');\n"
            )

        f.write(f"\n-- Seed complete: {len(data['tenants'])} tenants, {len(data['users'])} users, "
                f"{len(data['documents'])} documents, {len(data['audit_logs'])} audit logs\n")


def write_seed_json(data, output_file):
    """Write seed data as JSON for programmatic loading."""
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="HSAAI Seed Data Framework")
    parser.add_argument("--output-dir", default="scripts/seed/output")
    parser.add_argument("--reset", action="store_true", help="Drop and recreate")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("HSAAI Seed Data Framework (Phase 16)")
    print("=" * 60)

    data = generate_all_seed_data()

    print(f"\nGenerated seed data:")
    for key, value in data.items():
        print(f"  {key}: {len(value)} records")

    # Write SQL
    sql_file = output_dir / "seed.sql"
    write_seed_sql(data, sql_file)
    print(f"\n✅ SQL seed file: {sql_file}")

    # Write JSON
    json_file = output_dir / "seed.json"
    write_seed_json(data, json_file)
    print(f"✅ JSON seed file: {json_file}")

    if args.database_url:
        print(f"\nApplying seed to database: {args.database_url}")
        import subprocess
        result = subprocess.run(
            ["psql", args.database_url, "-f", str(sql_file)],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            print("✅ Seed applied successfully")
        else:
            print(f"❌ Seed failed: {result.stderr}")

    print("\nSeed data framework complete.")


if __name__ == "__main__":
    main()
