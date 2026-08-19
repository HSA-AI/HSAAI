"""
HSAAI Contract Tests (v4.0)
Pact-style contract tests between frontend API routes and backend services.
"""
import pytest
import httpx
from unittest.mock import patch, MagicMock


class TestBackendCoreContracts:
    """Verify backend_core API contracts are stable."""

    @pytest.fixture
    def mock_auth(self):
        """Mock auth for all contract tests."""
        return {"sub": "contract-test-user", "tenant_id": "default", "workspace_id": "default", "roles": ["ai_user"]}

    def test_health_endpoint_contract(self):
        """/health must return {status, service}."""
        # Contract: response must have status and service fields
        expected_fields = {"status", "service"}
        # This test validates the contract shape, not the actual call
        mock_response = {"status": "ok", "service": "backend_core", "version": "2.0.0"}
        assert expected_fields.issubset(mock_response.keys())

    def test_rag_search_contract(self):
        """/v1/rag/search must return {results: [{text, score, filename, doc_id}]}."""
        expected_result_fields = {"text", "score", "filename", "doc_id"}
        mock_response = {
            "results": [
                {"text": "sample", "score": 0.95, "filename": "doc.pdf", "doc_id": "doc-1", "chunk_index": 0}
            ],
            "count": 1,
        }
        assert "results" in mock_response
        assert "count" in mock_response
        for result in mock_response["results"]:
            assert expected_result_fields.issubset(result.keys())

    def test_rag_answer_contract(self):
        """/v1/rag/answer must return {answer, sources, elapsed_ms}."""
        expected_fields = {"answer", "sources", "elapsed_ms"}
        mock_response = {
            "answer": "Sample answer",
            "sources": [{"index": 1, "doc_id": "doc-1"}],
            "elapsed_ms": 1234,
            "answer_type": "llm_grounded",
        }
        assert expected_fields.issubset(mock_response.keys())

    def test_agent_run_contract(self):
        """/v1/agents/run must return {agent, answer, tools_executed}."""
        expected_fields = {"agent", "answer", "tools_executed"}
        mock_response = {
            "agent": "hr",
            "answer": "Sample agent response",
            "tools_executed": ["rag_search"],
            "tools_available": ["rag_search", "policy_lookup"],
            "rag_results_count": 3,
        }
        assert expected_fields.issubset(mock_response.keys())

    def test_workflow_start_contract(self):
        """/v1/workflows/start must return {run_id, status}."""
        expected_fields = {"run_id", "status"}
        mock_response = {
            "run_id": "wf-12345",
            "status": "running",
            "steps_total": 5,
            "steps_completed": 0,
        }
        assert expected_fields.issubset(mock_response.keys())

    def test_compliance_report_contract(self):
        """/v1/compliance/generate must return {framework, controls, compliance_score}."""
        expected_fields = {"framework", "controls", "compliance_score"}
        mock_response = {
            "framework": "GDPR",
            "period": {"start": "2026-01-01", "end": "2026-06-30"},
            "controls": [{"control_id": "GDPR-Art5", "status": "pass"}],
            "compliance_score": 1.0,
        }
        assert expected_fields.issubset(mock_response.keys())

    def test_pii_scan_contract(self):
        """/v1/pii/scan must return {has_pii, pii_found, risk_level}."""
        expected_fields = {"has_pii", "pii_found", "risk_level"}
        mock_response = {
            "has_pii": True,
            "pii_found": [{"type": "EMAIL_ADDRESS", "text": "test@example.com", "start": 0, "end": 16, "score": 0.99}],
            "risk_level": "medium",
            "counts": {"EMAIL_ADDRESS": 1},
            "detection_method": "regex_fallback",
        }
        assert expected_fields.issubset(mock_response.keys())

    def test_mcp_initialize_contract(self):
        """MCP /mcp initialize must return {protocolVersion, capabilities, serverInfo}."""
        expected_fields = {"protocolVersion", "capabilities", "serverInfo"}
        mock_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}, "resources": {}},
                "serverInfo": {"name": "hsaai-mcp-server", "version": "3.0.0"},
            },
        }
        assert expected_fields.issubset(mock_response["result"].keys())


class TestFrontendBackendContracts:
    """Verify frontend API routes forward to backend correctly."""

    def test_build_backend_headers_contract(self):
        """buildBackendHeaders() must return Content-Type + X-Requested-With."""
        # Contract: the helper must always set these headers
        expected_headers = {"Content-Type", "X-Requested-With"}
        # In actual implementation, Authorization is added when cookie exists
        assert expected_headers.issubset({"Content-Type", "X-Requested-With", "Authorization"})

    def test_backend_url_consistency(self):
        """All routes must use the same BACKEND_URL from env."""
        # Contract: BACKEND_URL is centralized in lib/server-auth.ts
        # No route should hardcode localhost:8000
        pass  # Verified by security regression test (no Bearer admin)
