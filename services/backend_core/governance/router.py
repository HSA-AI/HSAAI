from fastapi import APIRouter

router = APIRouter(prefix="/governance", tags=["enterprise-governance"])

@router.get("/digital-transformation/status")
def transformation_status():
    return {
        "program": "HSAAI - Hayel Saeed Anam Artificial Intelligence",
        "mode": "enterprise_internal_ai_program",
        "governance_layer": "enabled",
        "pilot_recommendation": "8-12 weeks limited pilot",
        "decision": "conditional approval for controlled internal pilot",
        "required_before_production": [
            "business_case_approval",
            "data_governance_approval",
            "security_review",
            "keycloak_ldap_validation",
            "rag_quality_validation",
            "pilot_kpi_report"
        ]
    }

@router.get("/use-cases")
def use_cases():
    return [
        {"code": "HR-POLICY", "name": "مساعد سياسات الموارد البشرية", "owner": "HR", "risk_level": "medium", "pilot_ready": True},
        {"code": "DOC-KNOWLEDGE", "name": "مساعد الوثائق المؤسسية", "owner": "Digital Transformation", "risk_level": "medium", "pilot_ready": True},
        {"code": "IT-SUPPORT", "name": "مساعد الدعم التقني الداخلي", "owner": "IT", "risk_level": "low", "pilot_ready": True},
        {"code": "EXEC-SUMMARY", "name": "مساعد الملخص التنفيذي", "owner": "Executive Office", "risk_level": "high", "pilot_ready": False},
        {"code": "FIN-ANALYSIS", "name": "مساعد التحليل المالي", "owner": "Finance", "risk_level": "high", "pilot_ready": False}
    ]

@router.get("/kpis")
def kpis():
    return [
        {"name": "active_users_30d", "target": "50+ during pilot", "owner": "Digital Transformation", "status": "planned"},
        {"name": "accepted_answers", "target": "75%+", "owner": "AI Governance", "status": "planned"},
        {"name": "rag_answers_with_sources", "target": "90%+", "owner": "Knowledge Management", "status": "planned"},
        {"name": "security_incidents", "target": "0 critical", "owner": "Cybersecurity", "status": "mandatory"},
        {"name": "avg_response_time", "target": "<5s normal load", "owner": "IT Operations", "status": "planned"}
    ]

@router.get("/readiness-checklist")
def readiness_checklist():
    return {
        "pilot": [
            "approve_use_cases",
            "approve_data_owners",
            "classify_documents",
            "enable_audit_logs",
            "validate_internal_only",
            "train_pilot_users"
        ],
        "production": [
            "keycloak_ldap_integration",
            "backup_restore_test",
            "load_test",
            "security_assessment",
            "governance_committee_approval",
            "executive_go_no_go_decision"
        ]
    }
