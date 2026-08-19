from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def test_required_services_exist():
    # CD-006 FIX: ai_orchestrator was merged into multi_agents in Phase 3
    # Updated to reflect the consolidated service architecture (11 services)
    required_services = [
        "api_gateway",
        "backend_core",
        "auth_service",
        "llm_gateway",
        "rag_engine",
        "multi_agents",
        "ai_alignment",
        "governance",
        "mcp_server",
        "workflow_engine",
        "pii_detector",
        "model_training",
    ]
    for service in required_services:
        assert (ROOT / "services" / service).exists(), f"Service directory missing: {service}"
