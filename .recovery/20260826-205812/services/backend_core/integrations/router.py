from fastapi import APIRouter
from backend_core.integrations.catalog import integration_catalog
from backend_core.integrations.security.policies import ENTERPRISE_INTEGRATION_SECURITY_RULES

router = APIRouter(prefix="/integrations", tags=["Enterprise Integrations"])


@router.get("/catalog")
def catalog():
    return integration_catalog()


@router.get("/security-rules")
def security_rules():
    return {"rules": ENTERPRISE_INTEGRATION_SECURITY_RULES}


@router.get("/target-architecture")
def target_architecture():
    return {
        "name": "HSAAI Enterprise Systems Integration Architecture",
        "layers": [
            {"layer": "User", "components": ["Frontend", "Admin Portal", "API Clients"]},
            {"layer": "Access", "components": ["API Gateway", "Auth Service", "Keycloak", "Active Directory"]},
            {"layer": "AI", "components": ["AI Orchestrator", "RAG Engine", "Multi-Agents", "LLM Gateway", "Workflow Engine"]},
            {"layer": "Data", "components": ["PostgreSQL", "Redis", "Qdrant", "Local File Storage"]},
            {"layer": "Enterprise Systems", "components": ["SAP S/4HANA", "SAP Business ByDesign", "Windows Server", "File Server", "SharePoint", "BI", "HR", "ITSM"]},
        ],
    }
