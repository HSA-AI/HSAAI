#!/usr/bin/env python3
"""
HSAAI Demo Seed — Rich Arabic enterprise demo data for the dockerless runtime.

Populates (tenant: hsa-enterprise, workspace: hq-main):
  - Knowledge Spaces / Collections / Documents (realistic HSA Group content)
  - Smart Response templates (professional Arabic answers for demo questions)
  - Chat message history (a realistic prior conversation)
  - Audit log entries
  - Analytics events (Knowledge Hub KPIs)

Deterministic (fixed ids/dates) so video recordings are reproducible.
Demo data only — no real credentials, no real documents.
"""
import sys
import os
import json
from datetime import datetime, timezone, timedelta

ROOT = "/home/z/my-project/work/HSAAI_project"
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "services"))
sys.path.insert(0, os.path.join(ROOT, "packages"))

os.environ["DATABASE_URL"] = f"sqlite:///{ROOT}/demo-runtime/hsaai_demo.db"

from backend_core.db.database import SessionLocal, init_db  # noqa: E402
from backend_core.db.models import (  # noqa: E402
    KnowledgeSpace, KnowledgeCollection, KnowledgeDocument, KnowledgeVersion,
    KnowledgeAnalyticsEvent, AuditLog, Message,
)
from backend_core.smart_responses.models import SmartResponseTemplate  # noqa: E402

TENANT = "hsa-enterprise"
WS = "hq-main"
ADMIN = "مدير النظام"

SPACES = [
    ("corporate", "المعرفة المؤسسية", "السياسات والإجراءات والوثائق المؤسسية المعتمدة", "الأمانة العامة", "internal"),
    ("hr", "الموارد البشرية", "سياسات الموارد البشرية وشؤون الموظفين", "إدارة الموارد البشرية", "internal"),
    ("finance", "الشؤون المالية", "الميزانيات والفواتير والتقارير المالية", "الإدارة المالية", "confidential"),
    ("it", "تقنية المعلومات", "الأنظمة والشبكات والدعم الفني", "إدارة تقنية المعلومات", "internal"),
    ("procurement", "المشتريات والعقود", "عقود الموردين ومناقصات المشتريات", "إدارة المشتريات", "confidential"),
]

COLLECTIONS = [
    ("corporate", "policies", "السياسات المعتمدة"),
    ("corporate", "strategies", "الاستراتيجيات والخطط"),
    ("hr", "hr-policies", "سياسات الموارد البشرية"),
    ("finance", "quarterly-reports", "التقارير الربعية"),
    ("it", "runbooks", "أدلة التشغيل"),
    ("procurement", "contracts", "العقود والاتفاقيات"),
]

DOCS = [
    ("doc_policy_annual_leave", "سياسة الإجازات السنوية.pdf", "سياسة الإجازات السنوية المعتمدة", "corporate", "policies", "v3.2", "approved", "internal", 482_133, 46, 12),
    ("doc_policy_remote_work", "سياسة العمل المرن.pdf", "سياسة العمل المرن والعمل عن بعد", "corporate", "policies", "v2.0", "approved", "internal", 301_902, 31, 8),
    ("doc_strategy_2026", "الخطة الاستراتيجية 2026.pdf", "الخطة الاستراتيجية للمجموعة 2026-2028", "corporate", "strategies", "v1.4", "approved", "internal", 2_845_600, 128, 34),
    ("doc_hr_handbook", "دليل الموظف.pdf", "دليل الموظف الشامل", "hr", "hr-policies", "v5.1", "approved", "internal", 1_204_882, 96, 22),
    ("doc_hr_leave_procedure", "إجراء طلب الإجازة.pdf", "إجراء طلب الإجازة عبر البوابة الذاتية", "hr", "hr-policies", "v1.8", "approved", "internal", 190_444, 18, 5),
    ("doc_fin_q4_report", "التقرير المالي الربع الرابع.pdf", "التقرير المالي الربع الرابع 2025", "finance", "quarterly-reports", "v1.0", "approved", "confidential", 3_620_115, 142, 41),
    ("doc_fin_budget_2026", "ميزانية 2026 التشغيلية.xlsx", "الميزانية التشغيلية المعتمدة 2026", "finance", "quarterly-reports", "v2.1", "pending_review", "confidential", 845_200, 64, 17),
    ("doc_it_backup_runbook", "دليل النسخ الاحتياطي.pdf", "دليل تشغيل النسخ الاحتياطي والاستعادة", "it", "runbooks", "v4.0", "approved", "internal", 552_367, 38, 9),
    ("doc_proc_supplier_contract", "عقد مورد التغليف 2026.pdf", "عقد مورد مواد التغليف السنوي", "procurement", "contracts", "v1.0", "approved", "confidential", 977_010, 52, 11),
]

SMART_RESPONSES = [
    {
        "rule_name": "سياسة الإجازات السنوية",
        "intent": "hr_query",
        "keywords": ["سياسة الإجازات", "الإجازات السنوية", "الإجازات"],
        "match_type": "keyword",
        "response_text": ("وفق سياسة الإجازات السنوية المعتمدة (الإصدار 3.2):\n"
                          "• يستحق الموظف 30 يومًا سنويًا بعد إكمال سنة الخدمة، و21 يومًا خلال السنة الأولى (بواقع 1.75 يوم شهريًا).\n"
                          "• يُشترط تقديم الطلب عبر البوابة الذاتية قبل 7 أيام عمل للحصول على موافقة المدير المباشر.\n"
                          "• يمكن ترحيل ما لا يزيد على 10 أيام إلى السنة التالية وتُصرف بدلًا نقديًا عمّا يتجاوزها.\n"
                          "المصدر: doc_policy_annual_leave — سياسة الإجازات السنوية.pdf (مساحة: الموارد البشرية)."),
        "priority": 10,
    },
    {
        "rule_name": "ملخص التقرير التنفيذي",
        "intent": "executive_query",
        "keywords": ["لخص", "المخاطر", "التوصيات", "التقرير التنفيذي"],
        "match_type": "keyword",
        "response_text": ("ملخص التقرير التنفيذي — الربع الرابع 2025:\n\n"
                          "أبرز النتائج:\n"
                          "• نمو الإيرادات 8.4% مقارنة بالربع السابق مدفوعًا بقطاعي الأغذية والتغليف.\n"
                          "• تحسّن هامش الربح التشغيلي 1.2 نقطة مئوية بعد مبادرات كفاءة التشغيل.\n"
                          "• الالتزام بالميزانية التشغيلية بنسبة 96.8%.\n\n"
                          "أهم المخاطر:\n"
                          "1. تقلب أسعار المواد الخام وأسعار الشحن الدولي.\n"
                          "2. تركز الإيرادات في عدد محدود من الأسواق الإقليمية.\n"
                          "3. فجوة المهارات الرقمية في بعض وحدات الأعمال.\n\n"
                          "التوصيات:\n"
                          "1. تعزيز العقود طويلة الأجل مع الموردين الاستراتيجيين.\n"
                          "2. تسريع برنامج تنويع الأسواق خلال 2026.\n"
                          "3. إطلاق مسار تدريب رقمي موجه للكفاءات الواعدة.\n\n"
                          "المصادر: doc_fin_q4_report — التقرير المالي الربع الرابع 2025 | doc_strategy_2026 — الخطة الاستراتيجية."),
        "priority": 5,
    },
    {
        "rule_name": "سياسة العمل المرن",
        "intent": "hr_query",
        "keywords": ["العمل المرن", "عن بعد", "المرن"],
        "match_type": "keyword",
        "response_text": ("سياسة العمل المرن (الإصدار 2.0) تتيح:\n"
                          "• نموذجًا هجينًا: 3 أيام في المقر و2 أيام عن بعد للأدوار المؤهلة.\n"
                          "• ساعات العمل الأساسية من 9 صباحًا حتى 3 عصرًا بتوقيت عدن.\n"
                          "• التنسيق المسبق مع المدير المباشر وتحديث حالة التوفر في التقويم.\n"
                          "المصدر: doc_policy_remote_work — سياسة العمل المرن.pdf."),
        "priority": 30,
    },
    {
        "rule_name": "التقرير المالي الربعي",
        "intent": "finance_query",
        "keywords": ["التقرير المالي", "الربعي", "المالية"],
        "match_type": "keyword",
        "response_text": ("أبرز مؤشرات التقرير المالي للربع الرابع 2025:\n"
                          "• نمو الإيرادات 8.4% مقارنة بالربع السابق مدفوعًا بقطاعي الأغذية والتغليف.\n"
                          "• تحسّن هامش الربح التشغيلي 1.2 نقطة مئوية بعد مبادرات كفاءة التشغيل.\n"
                          "• الالتزام بالميزانية التشغيلية بنسبة 96.8%.\n"
                          "• المخاطر الرئيسة: تقلب أسعار المواد الخام وأسعار الشحن؛ والتوصية بتعزيز العقود طويلة الأجل.\n"
                          "للاطلاع على التفاصيل الكاملة راجع doc_fin_q4_report (تصنيف: سري — يتطلب صلاحية الإدارة المالية)."),
        "priority": 15,
    },
]

CHATS = [
    ("user", "general", "لخص لي هذا التقرير التنفيذي وحدد أهم المخاطر والتوصيات"),
    ("assistant", "knowledge", "سأقوم بتحليل التقرير التنفيذي واستخلاص الملخص والمخاطر والتوصيات بناءً على مصادر المعرفة المؤسسية المتاحة."),
]

AUDIT_EVENTS = [
    ("مدير النظام", "auth.login", "OIDC login via Demo IdP", "hq-main"),
    ("مدير النظام", "knowledge.document.approved", "doc_policy_annual_leave v3.2", "hq-main"),
    ("مدير النظام", "governance.policy.updated", "RAG citation policy: strict", "hq-main"),
    ("مدير النظام", "chat.message", "agent:knowledge;workspace:hq-main", "hq-main"),
    ("مراجع الوثائق", "knowledge.document.submitted", "doc_fin_budget_2026 v2.1", "hq-main"),
]

def seed():
    init_db()
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)

        # --- Knowledge Hub ---
        if not db.query(KnowledgeSpace).filter_by(tenant_id=TENANT).first():
            for i, (key, name, desc, owner, cls) in enumerate(SPACES):
                db.add(KnowledgeSpace(
                    key=key, name=name, description=desc, owner=owner,
                    classification=cls, is_active=True, tenant_id=TENANT, workspace_id=WS,
                    created_at=now - timedelta(days=120 - i * 9),
                ))
            db.commit()

        if not db.query(KnowledgeCollection).filter_by(tenant_id=TENANT).first():
            for i, (space, key, name) in enumerate(COLLECTIONS):
                db.add(KnowledgeCollection(
                    space_key=space, key=key, name=name, description=f"مجموعة {name}",
                    document_count=1, tenant_id=TENANT, workspace_id=WS,
                    created_at=now - timedelta(days=110 - i * 8),
                ))
            db.commit()

        if not db.query(KnowledgeDocument).filter_by(tenant_id=TENANT).first():
            for i, (doc_id, fname, title, space, coll, ver, status, cls, size, views, searches) in enumerate(DOCS):
                db.add(KnowledgeDocument(
                    document_id=doc_id, filename=fname, title=title, space_key=space,
                    collection_key=coll, version=ver, status=status, classification=cls,
                    sensitivity="" if cls == "internal" else cls,
                    department=space, size_bytes=size, uploaded_by=ADMIN,
                    content_type="application/pdf", qdrant_indexed=(status == "approved"),
                    extra_metadata=json.dumps({"views": views, "searches": searches, "language": "ar"}, ensure_ascii=False),
                    tags=json.dumps(["مؤسسي", space], ensure_ascii=False),
                    reviewed_by=ADMIN if status == "approved" else None,
                    approved_at=now - timedelta(days=10) if status == "approved" else None,
                    tenant_id=TENANT, workspace_id=WS,
                    created_at=now - timedelta(days=95 - i * 9),
                ))
                db.add(KnowledgeVersion(
                    document_id=doc_id, version=ver, storage_path=f"storage/{doc_id}/{ver}",
                    checksum=f"sha256:{doc_id}{i:02d}", change_note="إصدار معتمد",
                    created_by=ADMIN,
                    created_at=now - timedelta(days=95 - i * 9),
                ))
            db.commit()

        # --- Analytics events (KPIs for Knowledge Hub) ---
        if not db.query(KnowledgeAnalyticsEvent).filter_by(tenant_id=TENANT).first():
            events = []
            for d in range(30):
                base = now - timedelta(days=30 - d)
                events += [
                    KnowledgeAnalyticsEvent(event_type="search", resource_type="document", resource_key="doc_policy_annual_leave", actor=ADMIN, query="سياسة الإجازات", result_count=4, latency_ms=180, tenant_id=TENANT, workspace_id=WS, created_at=base + timedelta(hours=9)),
                    KnowledgeAnalyticsEvent(event_type="search", resource_type="document", resource_key="doc_fin_q4_report", actor="analyst@hsa", query="التقرير المالي", result_count=6, latency_ms=240, tenant_id=TENANT, workspace_id=WS, created_at=base + timedelta(hours=11)),
                    KnowledgeAnalyticsEvent(event_type="view", resource_type="document", resource_key="doc_hr_handbook", actor="hr.user@hsa", query="", result_count=1, latency_ms=90, tenant_id=TENANT, workspace_id=WS, created_at=base + timedelta(hours=13)),
                ]
            db.add_all(events)
            db.commit()

        # --- Smart Responses ---
        if not db.query(SmartResponseTemplate).filter_by(tenant_id=TENANT, workspace_id=WS).first():
            for item in SMART_RESPONSES:
                db.add(SmartResponseTemplate(
                    tenant_id=TENANT, workspace_id=WS,
                    rule_name=item["rule_name"], intent=item["intent"],
                    keywords_json=json.dumps(item["keywords"], ensure_ascii=False),
                    match_type=item["match_type"], response_text=item["response_text"],
                    priority=item["priority"], enabled=True, language="ar",
                    usage_count=48, success_count=46, fallback_count=2,
                    created_by="system", updated_by=ADMIN,
                ))
            # a couple of general workspace templates so the admin page has variety
            extra = [
                ("تحية المؤسسة", "general_query", ["مرحبا", "السلام", "أهلا"], 90,
                 "مرحبًا بك في مساعد HSAAI المؤسسي. يمكنني البحث في وثائق المؤسسة، تلخيص التقارير، وتنفيذ مهام الأقسام. كيف أساعدك اليوم؟"),
                ("الدعم الفني", "it_support", ["vpn", "بريد", "شبكة", "كلمة مرور"], 40,
                 "لتذاكر الدعم الفني: من البوابة الذاتية ← «الدعم الفني» ← «تذكرة جديدة»، أو الاتصال بالمركز الداخلي 1500. للأعطال العاجلة استخدم قناة الطوارئ في تطبيق HSAAI."),
            ]
            for name, intent, kws, pr, text in extra:
                db.add(SmartResponseTemplate(
                    tenant_id=TENANT, workspace_id=WS, rule_name=name, intent=intent,
                    keywords_json=json.dumps(kws, ensure_ascii=False), match_type="keyword",
                    response_text=text, priority=pr, enabled=True, language="ar",
                    usage_count=120, success_count=118, fallback_count=2,
                    created_by="system", updated_by="system",
                ))
            db.commit()

        # --- Chat history ---
        if not db.query(Message).filter_by(tenant_id=TENANT).first():
            t0 = now - timedelta(hours=3)
            for i, (role, agent, text) in enumerate(CHATS):
                db.add(Message(user=ADMIN, role=role, agent=agent, message=text,
                               workspace_id=WS, tenant_id=TENANT, created_at=t0 + timedelta(minutes=i * 4)))
            db.commit()

        # --- Audit log ---
        if not db.query(AuditLog).filter_by(tenant_id=TENANT).first():
            for i, (actor, action, resource, ws) in enumerate(AUDIT_EVENTS):
                db.add(AuditLog(actor=actor, action=action, resource=resource,
                                workspace_id=ws, tenant_id=TENANT, success=True,
                                created_at=now - timedelta(days=6 - i)))
            db.commit()

        # --- Summary ---
        print("=== SEED SUMMARY (tenant:", TENANT, ") ===")
        print("spaces:", db.query(KnowledgeSpace).filter_by(tenant_id=TENANT).count())
        print("collections:", db.query(KnowledgeCollection).filter_by(tenant_id=TENANT).count())
        print("documents:", db.query(KnowledgeDocument).filter_by(tenant_id=TENANT).count())
        print("analytics events:", db.query(KnowledgeAnalyticsEvent).filter_by(tenant_id=TENANT).count())
        print("smart responses:", db.query(SmartResponseTemplate).filter_by(tenant_id=TENANT, workspace_id=WS).count())
        print("messages:", db.query(Message).filter_by(tenant_id=TENANT).count())
        print("audit logs:", db.query(AuditLog).filter_by(tenant_id=TENANT).count())
    finally:
        db.close()

if __name__ == "__main__":
    seed()
