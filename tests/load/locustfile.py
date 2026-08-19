"""
HSAAI Locust Load Test (Phase 14)
===================================
Run with: locust -f tests/load/locustfile.py --host=http://localhost:8000
Open http://localhost:8089 for web UI.
"""
from locust import HttpUser, task, between, events
import json
import random


class HSAAIUser(HttpUser):
    """Simulates a typical HSA Group employee using the AI platform."""

    wait_time = between(1, 5)  # 1-5 seconds between requests

    def on_start(self):
        """Login and store JWT."""
        # In production: login via Keycloak
        self.client.headers.update({
            'Authorization': 'Bearer test-token',
            'X-Tenant-Id': random.choice(['hsa-foods', 'hsa-retail', 'hsa-packaging']),
        })

    @task(3)  # weight 3 — most common
    def chat_query(self):
        """Send a chat query to the LLM."""
        prompts = [
            "ما سياسة المشتريات لدينا؟",
            "What is our procurement policy?",
            "حلل هذا العقد",
            "Analyze this contract",
            "كيف أبدأ طلب شراء؟",
            "How do I start a purchase order?",
        ]
        self.client.post(
            "http://llm-gateway:8090/v1/generate",
            json={
                "prompt": random.choice(prompts),
                "max_tokens": 256,
                "tenant_id": "hsa-foods",
                "use_cache": True,
            },
            name="LLM Generate",
        )

    @task(2)
    def rag_search(self):
        """Search the knowledge base."""
        queries = [
            "procurement policy",
            "supplier requirements",
            "compliance regulations",
            "workflow approval",
            "agent capabilities",
        ]
        self.client.post(
            "http://rag-engine:8001/query",
            json={
                "query": random.choice(queries),
                "tenant_id": "hsa-foods",
                "top_k": 5,
            },
            name="RAG Query",
        )

    @task(1)
    def dashboard_view(self):
        """View dashboard (read-only)."""
        self.client.get("/api/v1/dashboard", name="Dashboard")

    @task(1)
    def list_agents(self):
        """List available agents."""
        self.client.get("/api/v1/agents", name="List Agents")

    @task(1)
    def list_tasks(self):
        """View task center."""
        self.client.get("/api/v1/tasks", name="List Tasks")


class HSAAIAdminUser(HttpUser):
    """Simulates an admin user with heavier operations."""

    wait_time = between(2, 10)
    weight = 1  # 1 admin per 5 regular users

    def on_start(self):
        self.client.headers.update({
            'Authorization': 'Bearer admin-token',
            'X-Tenant-Id': 'hsa-corporate',
            'X-Roles': 'admin',
        })

    @task(2)
    def view_audit_log(self):
        """View audit log (governance)."""
        self.client.get("/api/v1/governance/audit/query?limit=100", name="Audit Query")

    @task(1)
    def view_compliance(self):
        """View compliance report."""
        self.client.get("/api/v1/governance/compliance/assess", name="Compliance Report")

    @task(1)
    def view_pending_approvals(self):
        """View pending approvals."""
        self.client.get("/api/v1/safety/approvals/pending", name="Pending Approvals")

    @task(1)
    def view_observability(self):
        """View observability metrics."""
        self.client.get("/api/v1/observability/metrics", name="Observability Metrics")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    print("=" * 60)
    print("HSAAI Locust Load Test Starting")
    print(f"Target: {environment.host}")
    print("=" * 60)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    print("=" * 60)
    print("HSAAI Locust Load Test Complete")
    stats = environment.stats.total
    print(f"Total requests: {stats.num_requests}")
    print(f"Total failures: {stats.num_failures}")
    print(f"Avg response time: {stats.avg_response_time:.2f}ms")
    print(f"Max response time: {stats.max_response_time:.2f}ms")
    print("=" * 60)
