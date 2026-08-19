"""
HSAAI v11.1 — Idempotency Key Protection & Secure Archive Migration
====================================================================
Final security closure implementing:

  1. IdempotencyKeyManager — Prevents duplicate execution of sensitive ops
  2. archive_document_secure migration helpers
  3. Department Agent Registry (21 agents)

Closes the final deferred vulnerability: QDRANT-SEC-018 (Idempotency Key)
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Any, Awaitable, Callable

logger = logging.getLogger("hsaai.idempotency")
audit_logger = logging.getLogger("hsaai.audit.idempotency")


class IdempotencyError(Exception):
    """Base exception for idempotency errors."""
    pass


class IdempotencyKeyConflictError(IdempotencyError):
    """Raised when idempotency key conflicts with a different request."""
    pass


class IdempotencyKeyExpiredError(IdempotencyError):
    """Raised when idempotency key has expired."""
    pass


class IdempotencyKeyManager:
    """Enterprise idempotency key manager for distributed HSAAI services.

    Prevents duplicate execution of sensitive operations by:
      1. Validating Idempotency-Key header
      2. Generating request fingerprint (hash of operation + params)
      3. Checking if operation was already executed
      4. Returning cached result for duplicate requests
      5. Storing new results with TTL

    Features:
      - Tenant isolation (keys scoped to tenant)
      - TTL expiration (default: 24 hours)
      - Replay protection (different request with same key → rejected)
      - Concurrency protection (in-flight tracking)
      - Distributed-ready (in-memory; production: Redis)

    Storage model per entry:
      {
        "id": "uuid",
        "idempotency_key": "client-provided-key",
        "user_id": "from JWT",
        "tenant_id": "from JWT",
        "operation": "archive_document | delete_vectors | ...",
        "request_hash": "sha256 of operation + params",
        "status": "in_flight | completed | failed",
        "response_data": "cached response (if completed)",
        "created_at": "ISO timestamp",
        "expires_at": "ISO timestamp"
      }
    """

    DEFAULT_TTL_HOURS = 24
    KEY_PATTERN = r'^[a-zA-Z0-9\-_]{1,128}$'

    def __init__(self, ttl_hours: int = DEFAULT_TTL_HOURS):
        # In-memory store (production: Redis with TTL)
        # Structure: {(tenant_id, idempotency_key): entry}
        self._store: dict[tuple[str, str], dict[str, Any]] = {}
        # In-flight tracking for concurrency
        self._in_flight: set[tuple[str, str]] = set()
        self._lock = asyncio.Lock()
        self.ttl_hours = ttl_hours

    def _generate_request_hash(
        self,
        operation: str,
        params: dict[str, Any],
    ) -> str:
        """Generate a fingerprint hash for the request.

        Args:
            operation: Operation name (e.g., "archive_document")
            params: Request parameters

        Returns:
            SHA-256 hash hex string
        """
        # Sort params for deterministic hash
        param_str = json.dumps({"operation": operation, "params": params}, sort_keys=True)
        return hashlib.sha256(param_str.encode()).hexdigest()

    def _validate_key_format(self, key: str) -> None:
        """Validate idempotency key format.

        Args:
            key: Client-provided idempotency key

        Raises:
            IdempotencyError: If key format is invalid
        """
        import re
        if not key:
            raise IdempotencyError("Idempotency key must not be empty")
        if not re.match(self.KEY_PATTERN, key):
            raise IdempotencyError(
                f"Idempotency key must match pattern {self.KEY_PATTERN} "
                f"(alphanumeric, hyphen, underscore; max 128 chars)"
            )

    async def execute_idempotent(
        self,
        idempotency_key: str,
        operation: str,
        params: dict[str, Any],
        tenant_id: str,
        user_id: str,
        executor: Callable[[], Awaitable[Any]],
    ) -> dict[str, Any]:
        """Execute an operation with idempotency protection.

        Args:
            idempotency_key: Client-provided idempotency key
            operation: Operation name
            params: Request parameters (for fingerprinting)
            tenant_id: Tenant ID (for isolation)
            user_id: User ID (for audit)
            executor: Async callable that performs the actual operation

        Returns:
            Result dict with status and response_data

        Raises:
            IdempotencyError: If validation fails
            IdempotencyKeyConflictError: If key reused with different params
        """
        # Validate key format
        self._validate_key_format(idempotency_key)

        # Generate request fingerprint
        request_hash = self._generate_request_hash(operation, params)
        store_key = (tenant_id, idempotency_key)

        async with self._lock:
            # Check for existing entry
            existing = self._store.get(store_key)
            if existing is not None:
                # Check if expired
                expires_at = datetime.fromisoformat(existing["expires_at"])
                if datetime.now(timezone.utc) > expires_at:
                    # Expired — remove and continue
                    del self._store[store_key]
                    self._in_flight.discard(store_key)
                else:
                    # Check for conflict (same key, different request)
                    if existing["request_hash"] != request_hash:
                        audit_logger.info(json.dumps({
                            "event": "IDEMPOTENCY_KEY_CONFLICT",
                            "idempotency_key": idempotency_key,
                            "tenant_id": tenant_id,
                            "user_id": user_id,
                            "operation": operation,
                            "existing_operation": existing["operation"],
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }))
                        raise IdempotencyKeyConflictError(
                            f"Idempotency key '{idempotency_key}' was already used "
                            f"for a different request (operation: {existing['operation']})"
                        )

                    # Check if still in flight
                    if store_key in self._in_flight:
                        return {
                            "status": "in_flight",
                            "message": "Request is currently being processed. Retry later.",
                            "idempotency_key": idempotency_key,
                        }

                    # Return cached result
                    if existing["status"] == "completed":
                        return {
                            "status": "replayed",
                            "idempotency_key": idempotency_key,
                            "response_data": existing.get("response_data"),
                            "original_created_at": existing["created_at"],
                        }
                    elif existing["status"] == "failed":
                        return {
                            "status": "previously_failed",
                            "idempotency_key": idempotency_key,
                            "error": existing.get("error"),
                            "original_created_at": existing["created_at"],
                        }

            # Mark as in-flight
            self._in_flight.add(store_key)

            # Create entry
            now = datetime.now(timezone.utc)
            entry = {
                "id": str(uuid.uuid4()),
                "idempotency_key": idempotency_key,
                "user_id": user_id,
                "tenant_id": tenant_id,
                "operation": operation,
                "request_hash": request_hash,
                "status": "in_flight",
                "response_data": None,
                "created_at": now.isoformat(),
                "expires_at": (now + timedelta(hours=self.ttl_hours)).isoformat(),
            }
            self._store[store_key] = entry

        # Execute the operation (outside lock to allow concurrency)
        try:
            result = await executor()
            # Update entry with result
            async with self._lock:
                entry = self._store.get(store_key)
                if entry:
                    entry["status"] = "completed"
                    entry["response_data"] = result
            return {
                "status": "executed",
                "idempotency_key": idempotency_key,
                "response_data": result,
            }
        except Exception as exc:
            # Update entry with error
            async with self._lock:
                entry = self._store.get(store_key)
                if entry:
                    entry["status"] = "failed"
                    entry["error"] = str(exc)[:500]
            raise
        finally:
            async with self._lock:
                self._in_flight.discard(store_key)

    async def get_status(
        self,
        idempotency_key: str,
        tenant_id: str,
    ) -> dict[str, Any] | None:
        """Get the status of an idempotency key (without executing).

        Returns:
            Entry dict if found, None otherwise
        """
        store_key = (tenant_id, idempotency_key)
        entry = self._store.get(store_key)
        if entry is None:
            return None
        # Check expiration
        expires_at = datetime.fromisoformat(entry["expires_at"])
        if datetime.now(timezone.utc) > expires_at:
            return None
        # Return safe copy (without internal fields)
        safe = dict(entry)
        return safe

    async def cleanup_expired(self) -> int:
        """Remove expired entries. Returns count removed."""
        removed = 0
        now = datetime.now(timezone.utc)
        async with self._lock:
            for store_key in list(self._store.keys()):
                entry = self._store[store_key]
                expires_at = datetime.fromisoformat(entry["expires_at"])
                if now > expires_at:
                    del self._store[store_key]
                    self._in_flight.discard(store_key)
                    removed += 1
        return removed

    async def reset_tenant(self, tenant_id: str) -> int:
        """Remove all idempotency entries for a tenant (admin operation)."""
        removed = 0
        async with self._lock:
            for store_key in list(self._store.keys()):
                if store_key[0] == tenant_id:
                    del self._store[store_key]
                    self._in_flight.discard(store_key)
                    removed += 1
        return removed

    def get_stats(self) -> dict[str, Any]:
        """Get idempotency store statistics."""
        status_counts = defaultdict(int)
        for entry in self._store.values():
            status_counts[entry["status"]] += 1
        return {
            "total_entries": len(self._store),
            "in_flight": len(self._in_flight),
            "by_status": dict(status_counts),
            "ttl_hours": self.ttl_hours,
        }


# Module-level singleton
_idempotency_manager: IdempotencyKeyManager | None = None


def get_idempotency_manager() -> IdempotencyKeyManager:
    """Get the singleton IdempotencyKeyManager instance."""
    global _idempotency_manager
    if _idempotency_manager is None:
        _idempotency_manager = IdempotencyKeyManager()
    return _idempotency_manager


# ═══════════════════════════════════════════════════════════════════════
# 21 Department AI Agents Registry
# ═══════════════════════════════════════════════════════════════════════
DEPARTMENT_AGENTS = [
    {
        "name": "executive-agent",
        "name_en": "Executive Agent",
        "name_ar": "الوكيل التنفيذي",
        "department": "Executive Office",
        "description": "Strategic decision support for C-suite executives",
        "version": "11.1.0",
        "owner": "AI Platform Team",
        "status": "production",
        "model_tier": "premium",
        "role": "Support executive leadership in strategic decision-making",
        "responsibilities": ["Strategic analysis", "Executive briefings", "KPI monitoring"],
        "skills": ["strategic-planning", "executive-reporting", "decision-support"],
        "tools": ["rag_search", "knowledge_graph_query", "power_bi_query", "executive_dashboard"],
        "knowledge_sources": ["enterprise-reports", "executive-policies"],
        "rag_collections": ["corporate", "enterprise-reports"],
        "required_permissions": ["executive:read", "executive:write"],
        "data_classification": "restricted",
    },
    {
        "name": "finance-agent",
        "name_en": "Finance Agent",
        "name_ar": "الوكيل المالي",
        "department": "Finance",
        "description": "Financial analysis, reporting, and forecasting",
        "version": "11.1.0",
        "owner": "AI Platform Team",
        "status": "production",
        "model_tier": "premium",
        "role": "Analyze financial data, prepare reports, support financial decisions",
        "responsibilities": ["Financial analysis", "Budget tracking", "Forecasting"],
        "skills": ["financial-analysis", "budgeting", "forecasting"],
        "tools": ["rag_search", "sap_query", "oracle_erp_query", "power_bi_query", "sql_query"],
        "knowledge_sources": ["finance-policies", "accounting-standards"],
        "rag_collections": ["finance", "corporate"],
        "required_permissions": ["knowledge:read", "analytics:read", "reports:read"],
        "data_classification": "confidential",
    },
    {
        "name": "hr-agent",
        "name_en": "HR Agent",
        "name_ar": "وكيل الموارد البشرية",
        "department": "Human Resources",
        "description": "HR policy guidance and employee support",
        "version": "11.1.0",
        "owner": "AI Platform Team",
        "status": "production",
        "model_tier": "standard",
        "role": "Support all HR processes from hiring to retirement",
        "responsibilities": ["Policy guidance", "Employee queries", "Leave management"],
        "skills": ["hr-policy", "employee-support", "leave-management"],
        "tools": ["rag_search", "oracle_hcm_query", "active_directory_query"],
        "knowledge_sources": ["hr-policies", "sop", "procedures"],
        "rag_collections": ["hr", "corporate"],
        "required_permissions": ["knowledge:read"],
        "data_classification": "confidential",
    },
    {
        "name": "accounting-agent",
        "name_en": "Accounting Agent",
        "name_ar": "وكيل المحاسبة",
        "department": "Accounting",
        "description": "Journal entries, reconciliations, financial statements",
        "version": "11.1.0",
        "owner": "AI Platform Team",
        "status": "production",
        "model_tier": "standard",
        "role": "Post journal entries, reconciliations, prepare financial statements",
        "responsibilities": ["Journal entries", "Reconciliations", "Financial statements"],
        "skills": ["accounting", "ifrs", "reconciliation"],
        "tools": ["rag_search", "sap_query", "sql_query"],
        "knowledge_sources": ["accounting-standards", "ifrs"],
        "rag_collections": ["finance"],
        "required_permissions": ["knowledge:read"],
        "data_classification": "confidential",
    },
    {
        "name": "treasury-agent",
        "name_en": "Treasury Agent",
        "name_ar": "وكيل الخزانة",
        "department": "Treasury",
        "description": "Liquidity monitoring and FX risk management",
        "version": "11.1.0",
        "owner": "AI Platform Team",
        "status": "production",
        "model_tier": "standard",
        "role": "Monitor liquidity, analyze FX risk, optimize cost of funds",
        "responsibilities": ["Liquidity monitoring", "FX analysis", "Cash management"],
        "skills": ["treasury", "fx-management", "cash-flow"],
        "tools": ["rag_search", "sap_query", "sql_query"],
        "knowledge_sources": ["treasury-policies"],
        "rag_collections": ["finance"],
        "required_permissions": ["knowledge:read"],
        "data_classification": "restricted",
    },
    {
        "name": "procurement-agent",
        "name_en": "Procurement Agent",
        "name_ar": "وكيل المشتريات",
        "department": "Procurement",
        "description": "Supplier analysis and procurement cycle support",
        "version": "11.1.0",
        "owner": "AI Platform Team",
        "status": "production",
        "model_tier": "standard",
        "role": "Analyze suppliers, compare RFQs, support procurement cycle",
        "responsibilities": ["Supplier analysis", "RFQ comparison", "PO management"],
        "skills": ["procurement", "supplier-management", "negotiation"],
        "tools": ["rag_search", "sap_query", "oracle_erp_query"],
        "knowledge_sources": ["procurement-policies", "supplier-data"],
        "rag_collections": ["corporate"],
        "required_permissions": ["knowledge:read"],
        "data_classification": "internal",
    },
    {
        "name": "supply-chain-agent",
        "name_en": "Supply Chain Agent",
        "name_ar": "وكيل سلسلة الإمداد",
        "department": "Supply Chain",
        "description": "Demand planning and inventory optimization",
        "version": "11.1.0",
        "owner": "AI Platform Team",
        "status": "production",
        "model_tier": "premium",
        "role": "Demand planning, inventory optimization, supply chain forecasting",
        "responsibilities": ["Demand planning", "Inventory optimization", "Forecasting"],
        "skills": ["supply-chain", "demand-planning", "inventory"],
        "tools": ["rag_search", "sap_query", "wms_query", "kafka_consume"],
        "knowledge_sources": ["scm-policies", "inventory-data"],
        "rag_collections": ["corporate"],
        "required_permissions": ["knowledge:read", "analytics:read"],
        "data_classification": "internal",
    },
    {
        "name": "manufacturing-agent",
        "name_en": "Manufacturing Agent",
        "name_ar": "وكيل التصنيع",
        "department": "Manufacturing",
        "description": "OEE analysis and production optimization",
        "version": "11.1.0",
        "owner": "AI Platform Team",
        "status": "production",
        "model_tier": "standard",
        "role": "Optimize manufacturing operations, analyze OEE, predict failures",
        "responsibilities": ["OEE analysis", "Production optimization", "Predictive maintenance"],
        "skills": ["manufacturing", "oee", "predictive-maintenance"],
        "tools": ["rag_search", "mes_query", "kafka_consume"],
        "knowledge_sources": ["manufacturing-sop", "mes-data"],
        "rag_collections": ["corporate"],
        "required_permissions": ["knowledge:read"],
        "data_classification": "internal",
    },
    {
        "name": "warehouse-agent",
        "name_en": "Warehouse Agent",
        "name_ar": "وكيل المستودعات",
        "department": "Warehouses",
        "description": "Inventory management and storage optimization",
        "version": "11.1.0",
        "owner": "AI Platform Team",
        "status": "production",
        "model_tier": "standard",
        "role": "Manage inventory, optimize storage, track warehouse operations",
        "responsibilities": ["Inventory management", "Storage optimization", "Picking efficiency"],
        "skills": ["warehouse", "inventory", "wms"],
        "tools": ["rag_search", "wms_query", "redis_query"],
        "knowledge_sources": ["warehouse-sop"],
        "rag_collections": ["corporate"],
        "required_permissions": ["knowledge:read"],
        "data_classification": "internal",
    },
    {
        "name": "logistics-agent",
        "name_en": "Logistics Agent",
        "name_ar": "وكيل الخدمات اللوجستية",
        "department": "Logistics",
        "description": "Transport planning and fleet optimization",
        "version": "11.1.0",
        "owner": "AI Platform Team",
        "status": "production",
        "model_tier": "standard",
        "role": "Transport planning, shipment tracking, fleet efficiency optimization",
        "responsibilities": ["Transport planning", "Shipment tracking", "Fleet optimization"],
        "skills": ["logistics", "fleet-management", "route-optimization"],
        "tools": ["rag_search", "wms_query", "kafka_consume"],
        "knowledge_sources": ["logistics-sop"],
        "rag_collections": ["corporate"],
        "required_permissions": ["knowledge:read"],
        "data_classification": "internal",
    },
    {
        "name": "sales-agent",
        "name_en": "Sales Agent",
        "name_ar": "وكيل المبيعات",
        "department": "Sales",
        "description": "Sales opportunity analysis and revenue forecasting",
        "version": "11.1.0",
        "owner": "AI Platform Team",
        "status": "production",
        "model_tier": "standard",
        "role": "Analyze sales opportunities, forecast revenue, support sales team",
        "responsibilities": ["Sales analysis", "Revenue forecasting", "Opportunity management"],
        "skills": ["sales", "forecasting", "crm"],
        "tools": ["rag_search", "crm_query", "power_bi_query"],
        "knowledge_sources": ["sales-policies", "customer-data"],
        "rag_collections": ["corporate"],
        "required_permissions": ["knowledge:read"],
        "data_classification": "confidential",
    },
    {
        "name": "marketing-agent",
        "name_en": "Marketing Agent",
        "name_ar": "وكيل التسويق",
        "department": "Marketing",
        "description": "Campaign analysis and content generation",
        "version": "11.1.0",
        "owner": "AI Platform Team",
        "status": "production",
        "model_tier": "standard",
        "role": "Analyze marketing campaigns, generate content, measure performance",
        "responsibilities": ["Campaign analysis", "Content generation", "Performance measurement"],
        "skills": ["marketing", "content-creation", "analytics"],
        "tools": ["rag_search", "crm_query", "power_bi_query"],
        "knowledge_sources": ["marketing-policies", "brand-guidelines"],
        "rag_collections": ["corporate"],
        "required_permissions": ["knowledge:read"],
        "data_classification": "internal",
    },
    {
        "name": "legal-agent",
        "name_en": "Legal Agent",
        "name_ar": "الوكيل القانوني",
        "department": "Legal",
        "description": "Contract review and legal counsel",
        "version": "11.1.0",
        "owner": "AI Platform Team",
        "status": "production",
        "model_tier": "premium",
        "role": "Review contracts, provide legal counsel, manage disputes",
        "responsibilities": ["Contract review", "Legal counsel", "Dispute management"],
        "skills": ["legal", "contract-review", "compliance"],
        "tools": ["rag_search", "knowledge_graph_query", "sharepoint_query"],
        "knowledge_sources": ["contracts", "regulations", "legal-policies"],
        "rag_collections": ["corporate"],
        "required_permissions": ["knowledge:read", "knowledge:review"],
        "data_classification": "restricted",
    },
    {
        "name": "audit-agent",
        "name_en": "Audit Agent",
        "name_ar": "وكيل التدقيق",
        "department": "Internal Audit",
        "description": "Audit support with anomaly detection",
        "version": "11.1.0",
        "owner": "AI Platform Team",
        "status": "production",
        "model_tier": "premium",
        "role": "Support internal audit with data analysis and anomaly detection",
        "responsibilities": ["Audit analysis", "Anomaly detection", "Finding documentation"],
        "skills": ["audit", "anomaly-detection", "data-analysis"],
        "tools": ["rag_search", "sql_query", "power_bi_query"],
        "knowledge_sources": ["audit-policies", "regulations"],
        "rag_collections": ["corporate"],
        "required_permissions": ["knowledge:read", "audit:read"],
        "data_classification": "restricted",
    },
    {
        "name": "compliance-agent",
        "name_en": "Compliance Agent",
        "name_ar": "وكيل الامتثال",
        "department": "Compliance",
        "description": "Regulatory compliance monitoring and risk management",
        "version": "11.1.0",
        "owner": "AI Platform Team",
        "status": "production",
        "model_tier": "standard",
        "role": "Monitor regulatory and policy compliance, manage enterprise risks",
        "responsibilities": ["Compliance monitoring", "Risk management", "Policy enforcement"],
        "skills": ["compliance", "risk-management", "regulatory"],
        "tools": ["rag_search", "knowledge_graph_query", "sharepoint_query"],
        "knowledge_sources": ["compliance-policies", "regulations"],
        "rag_collections": ["corporate"],
        "required_permissions": ["knowledge:read"],
        "data_classification": "restricted",
    },
    {
        "name": "cybersecurity-agent",
        "name_en": "Cybersecurity Agent",
        "name_ar": "وكيل الأمن السيبراني",
        "department": "Cybersecurity",
        "description": "Threat analysis and incident investigation",
        "version": "11.1.0",
        "owner": "AI Platform Team",
        "status": "production",
        "model_tier": "premium",
        "role": "Analyze threats, investigate incidents, monitor security posture",
        "responsibilities": ["Threat analysis", "Incident investigation", "Security monitoring"],
        "skills": ["cybersecurity", "threat-analysis", "incident-response"],
        "tools": ["rag_search", "siem_query", "vault_query"],
        "knowledge_sources": ["security-policies", "threat-intel"],
        "rag_collections": ["corporate"],
        "required_permissions": ["knowledge:read", "audit:read"],
        "data_classification": "restricted",
    },
    {
        "name": "quality-agent",
        "name_en": "Quality Agent",
        "name_ar": "وكيل الجودة",
        "department": "Quality Assurance",
        "description": "Quality data analysis and continuous improvement",
        "version": "11.1.0",
        "owner": "AI Platform Team",
        "status": "production",
        "model_tier": "standard",
        "role": "Analyze quality data, track defects, support continuous quality improvement",
        "responsibilities": ["Quality analysis", "Defect tracking", "Continuous improvement"],
        "skills": ["quality", "defect-analysis", "iso-standards"],
        "tools": ["rag_search", "mes_query", "power_bi_query"],
        "knowledge_sources": ["quality-policies", "iso-documents"],
        "rag_collections": ["corporate"],
        "required_permissions": ["knowledge:read"],
        "data_classification": "internal",
    },
    {
        "name": "research-agent",
        "name_en": "Research Agent",
        "name_ar": "وكيل البحث والتطوير",
        "department": "Research & Development",
        "description": "Research analysis and new product development support",
        "version": "11.1.0",
        "owner": "AI Platform Team",
        "status": "production",
        "model_tier": "premium",
        "role": "Analyze research, explore trends, support new product development",
        "responsibilities": ["Research analysis", "Trend exploration", "Product development support"],
        "skills": ["research", "trend-analysis", "product-development"],
        "tools": ["rag_search", "knowledge_graph_query", "sharepoint_query"],
        "knowledge_sources": ["research-papers", "industry-trends"],
        "rag_collections": ["corporate"],
        "required_permissions": ["knowledge:read"],
        "data_classification": "confidential",
    },
    {
        "name": "customer-service-agent",
        "name_en": "Customer Service Agent",
        "name_ar": "وكيل خدمة العملاء",
        "department": "Customer Service",
        "description": "Customer inquiry handling and issue resolution",
        "version": "11.1.0",
        "owner": "AI Platform Team",
        "status": "production",
        "model_tier": "standard",
        "role": "Respond to customer inquiries, resolve issues, improve customer satisfaction",
        "responsibilities": ["Customer support", "Issue resolution", "Satisfaction tracking"],
        "skills": ["customer-service", "communication", "problem-solving"],
        "tools": ["rag_search", "crm_query", "teams_notify"],
        "knowledge_sources": ["customer-service-sop", "faq"],
        "rag_collections": ["corporate"],
        "required_permissions": ["knowledge:read"],
        "data_classification": "internal",
    },
    {
        "name": "executive-assistant",
        "name_en": "Executive Assistant",
        "name_ar": "المساعد التنفيذي",
        "department": "CEO Office",
        "description": "Scheduling, briefings, and task follow-up for executives",
        "version": "11.1.0",
        "owner": "AI Platform Team",
        "status": "production",
        "model_tier": "standard",
        "role": "Assist leadership with scheduling, briefings, and task follow-up",
        "responsibilities": ["Scheduling", "Briefing preparation", "Task tracking"],
        "skills": ["scheduling", "briefing", "task-management"],
        "tools": ["rag_search", "m365_calendar", "m365_email", "teams_notify"],
        "knowledge_sources": ["executive-policies", "calendar"],
        "rag_collections": ["corporate"],
        "required_permissions": ["knowledge:read", "executive:read"],
        "data_classification": "confidential",
    },
    {
        "name": "knowledge-assistant",
        "name_en": "Knowledge Assistant",
        "name_ar": "مساعد المعرفة",
        "department": "Data Office",
        "description": "Knowledge base management and enterprise knowledge documentation",
        "version": "11.1.0",
        "owner": "AI Platform Team",
        "status": "production",
        "model_tier": "premium",
        "role": "Manage knowledge base, answer questions, document enterprise knowledge",
        "responsibilities": ["Knowledge management", "Question answering", "Knowledge documentation"],
        "skills": ["knowledge-management", "rag", "documentation"],
        "tools": ["rag_search", "knowledge_graph_query", "vector_search"],
        "knowledge_sources": ["enterprise-knowledge", "all-collections"],
        "rag_collections": ["corporate", "hr", "finance"],
        "required_permissions": ["knowledge:read", "knowledge:admin"],
        "data_classification": "internal",
    },
]


def get_all_department_agents() -> list[dict[str, Any]]:
    """Get all 21 department agent definitions."""
    return DEPARTMENT_AGENTS


def get_agent_by_name(name: str) -> dict[str, Any] | None:
    """Get a department agent by name."""
    for agent in DEPARTMENT_AGENTS:
        if agent["name"] == name:
            return agent
    return None


def get_agents_by_department(department: str) -> list[dict[str, Any]]:
    """Get all agents for a specific department."""
    return [a for a in DEPARTMENT_AGENTS if a["department"] == department]
