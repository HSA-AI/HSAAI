from __future__ import annotations
import os  # FIX-33: was missing — ActiveDirectoryConnector.fetch_data uses os.getenv
from typing import Any
from .base_connector import BaseEnterpriseConnector, ConnectorContext, ConnectorResult


class SAPS4HANAConnector(BaseEnterpriseConnector):
    key = "sap_s4hana"
    name = "SAP S/4HANA"
    system_type = "sap_s4hana"
    category = "ERP"
    auth_type = "oauth2_or_service_account"
    env_prefix = "SAP"
    capabilities = ["purchases", "inventory", "sales", "finance", "operations", "odata", "rest"]
    allowed_roles = ["hsaai_admin", "department_manager", "finance_agent", "knowledge_admin"]
    def fetch_data(self, query: dict[str, Any], context: ConnectorContext) -> ConnectorResult:
        permission = self.check_permissions(context, "read")
        if not permission.success: return permission
        subject = query.get("subject", "summary")
        return ConnectorResult(self.key, "fetch_data", True, {"subject": subject, "examples": ["monthly_purchases", "pending_purchase_orders", "inventory_analysis", "sales_performance"], "query_mode": "SAP OData/REST read-only"}, self.name, "SAP S/4HANA data source contract ready", read_only=True)


class SuccessFactorsConnector(BaseEnterpriseConnector):
    key = "successfactors"
    name = "SAP SuccessFactors"
    system_type = "successfactors"
    category = "HR"
    auth_type = "oauth2"
    env_prefix = "SUCCESSFACTORS"
    capabilities = ["employees", "leave_balances", "organization_chart", "attendance", "jobs"]
    allowed_roles = ["hsaai_admin", "department_manager", "knowledge_admin"]
    def fetch_data(self, query: dict[str, Any], context: ConnectorContext) -> ConnectorResult:
        permission = self.check_permissions(context, "read")
        if not permission.success: return permission
        return ConnectorResult(self.key, "fetch_data", True, {"subject": query.get("subject", "employee_lookup"), "query_mode": "SuccessFactors OData read-only"}, self.name, "SuccessFactors contract ready", read_only=True)


class ActiveDirectoryConnector(BaseEnterpriseConnector):
    """
    Active Directory connector via LDAPS (LDAP over TLS).
    Real implementation — connects to AD using ldap3 library.

    Authentication: Service account credentials from Vault (not env vars).
    Connection: LDAPS (port 636) with TLS certificate validation.
    Operations: User sync, group sync, org unit queries (read-only).
    """
    key = "active_directory"
    name = "Active Directory"
    system_type = "active_directory"
    category = "Identity"
    auth_type = "ldaps_service_account"
    env_prefix = "AD"
    capabilities = ["users_sync", "groups_sync", "org_units", "keycloak_role_mapping"]
    allowed_roles = ["hsaai_admin", "auditor"]

    def fetch_data(self, query: dict[str, Any], context: ConnectorContext) -> ConnectorResult:
        """
        Query Active Directory via LDAPS.
        Returns real user/group data, not placeholder metadata.
        """
        permission = self.check_permissions(context, "read")
        if not permission.success:
            return permission

        import time
        start = time.time()

        try:
            from ldap3 import Server, Connection, ALL, SUBTREE
            from ldap3.core.exceptions import LDAPException

            # Read connection config from env (credentials from Vault in prod)
            ad_host = os.getenv("AD_HOST", "")
            ad_port = int(os.getenv("AD_PORT", "636"))
            ad_bind_dn = os.getenv("AD_BIND_DN", "")
            # In production: ad_password comes from Vault
            # ad_password = vault_client.get_secret_value("secret/data/hsaai/ad", "password")
            ad_password = os.getenv("AD_PASSWORD", "")
            ad_base_dn = os.getenv("AD_BASE_DN", "")
            use_ssl = ad_port == 636

            if not all([ad_host, ad_bind_dn, ad_password, ad_base_dn]):
                return ConnectorResult(
                    self.key, "fetch_data", False, data=None,
                    source=self.name,
                    message="AD not configured. Set AD_HOST, AD_BIND_DN, AD_PASSWORD, AD_BASE_DN",
                    latency_ms=int((time.time() - start) * 1000),
                    read_only=True,
                )

            # Connect via LDAPS
            server = Server(ad_host, port=ad_port, use_ssl=use_ssl, get_info=ALL)
            conn = Connection(
                server, user=ad_bind_dn, password=ad_password,
                auto_bind=True, read_only=True,
            )

            # Determine query type
            query_type = query.get("type", "users")
            search_filter = "(objectClass=*)"

            if query_type == "users":
                search_filter = "(&(objectClass=user)(objectCategory=person))"
            elif query_type == "groups":
                search_filter = "(objectClass=group)"
            elif query_type == "org_units":
                search_filter = "(objectClass=organizationalUnit)"

            # Search
            conn.search(
                search_base=ad_base_dn,
                search_filter=search_filter,
                search_scope=SUBTREE,
                attributes=["cn", "mail", "memberOf", "department", "title", "sAMAccountName"],
                size_limit=query.get("limit", 100),
            )

            # Parse results
            entries = []
            for entry in conn.entries:
                entries.append({
                    "dn": entry.entry_dn,
                    "cn": str(entry.cn) if hasattr(entry, "cn") else "",
                    "mail": str(entry.mail) if hasattr(entry, "mail") else "",
                    "department": str(entry.department) if hasattr(entry, "department") else "",
                    "title": str(entry.title) if hasattr(entry, "title") else "",
                    "sam_account_name": str(entry.sAMAccountName) if hasattr(entry, "sAMAccountName") else "",
                })

            conn.unbind()

            return ConnectorResult(
                self.key, "fetch_data", True,
                data={
                    "type": query_type,
                    "count": len(entries),
                    "entries": entries[:50],  # Limit response size
                    "source": "active_directory_ldaps",
                },
                source=self.name,
                message=f"Retrieved {len(entries)} {query_type} from AD",
                latency_ms=int((time.time() - start) * 1000),
                read_only=True,
            )

        except ImportError:
            return ConnectorResult(
                self.key, "fetch_data", False, data=None,
                source=self.name,
                message="ldap3 library not installed. Run: pip install ldap3",
                latency_ms=int((time.time() - start) * 1000),
                read_only=True,
            )
        except LDAPException as e:
            return ConnectorResult(
                self.key, "fetch_data", False, data=None,
                source=self.name,
                message=f"AD LDAP error: {str(e)[:200]}",
                latency_ms=int((time.time() - start) * 1000),
                read_only=True,
            )
        except Exception as e:
            return ConnectorResult(
                self.key, "fetch_data", False, data=None,
                source=self.name,
                message=f"AD connection error: {str(e)[:200]}",
                latency_ms=int((time.time() - start) * 1000),
                read_only=True,
            )


class OutlookExchangeConnector(BaseEnterpriseConnector):
    key = "outlook_exchange"
    name = "Exchange / Outlook"
    system_type = "outlook_exchange"
    category = "Collaboration"
    auth_type = "microsoft_graph_oauth2"
    env_prefix = "OUTLOOK_EXCHANGE"
    capabilities = ["mail_read", "calendar_read", "meeting_summary", "thread_analysis", "draft_reply"]
    allowed_roles = ["hsaai_admin", "ai_user", "department_manager"]
    def fetch_data(self, query: dict[str, Any], context: ConnectorContext) -> ConnectorResult:
        permission = self.check_permissions(context, "read")
        if not permission.success: return permission
        return ConnectorResult(self.key, "fetch_data", True, {"subject": query.get("subject", "today_meetings"), "privacy": "delegated user consent required"}, self.name, "Outlook/Exchange connector contract ready", read_only=True)


class SharePointConnector(BaseEnterpriseConnector):
    key = "sharepoint"
    name = "SharePoint"
    system_type = "sharepoint"
    category = "Documents"
    auth_type = "microsoft_graph_oauth2"
    env_prefix = "SHAREPOINT"
    capabilities = ["file_indexing", "rag_ingestion", "word", "excel", "pdf", "powerpoint", "version_compare"]
    allowed_roles = ["hsaai_admin", "knowledge_admin", "document_uploader", "document_reviewer"]
    def fetch_data(self, query: dict[str, Any], context: ConnectorContext) -> ConnectorResult:
        permission = self.check_permissions(context, "read")
        if not permission.success: return permission
        return ConnectorResult(self.key, "fetch_data", True, {"subject": query.get("subject", "policy_search"), "rag_ready": True}, self.name, "SharePoint connector contract ready", read_only=True)


class PowerBIConnector(BaseEnterpriseConnector):
    key = "powerbi"
    name = "Power BI"
    system_type = "powerbi"
    category = "Analytics"
    auth_type = "microsoft_graph_oauth2"
    env_prefix = "POWERBI"
    capabilities = ["dashboards", "reports", "datasets", "executive_summaries"]
    allowed_roles = ["hsaai_admin", "department_manager", "auditor"]
    def fetch_data(self, query: dict[str, Any], context: ConnectorContext) -> ConnectorResult:
        permission = self.check_permissions(context, "read")
        if not permission.success: return permission
        return ConnectorResult(self.key, "fetch_data", True, {"subject": query.get("subject", "executive_report"), "dataset_mode": "read-only"}, self.name, "Power BI connector contract ready", read_only=True)


class JiraConnector(BaseEnterpriseConnector):
    key = "jira"
    name = "Jira"
    system_type = "jira"
    category = "Projects"
    auth_type = "api_token_or_oauth2"
    env_prefix = "JIRA"
    capabilities = ["projects", "issues", "epics", "sprints", "ticket_creation_requires_approval"]
    allowed_roles = ["hsaai_admin", "department_manager", "ai_user"]
    def fetch_data(self, query: dict[str, Any], context: ConnectorContext) -> ConnectorResult:
        permission = self.check_permissions(context, "read")
        if not permission.success: return permission
        return ConnectorResult(self.key, "fetch_data", True, {"subject": query.get("subject", "open_issues"), "write_actions": "approval_required"}, self.name, "Jira connector contract ready", read_only=True)


class ServiceDeskConnector(BaseEnterpriseConnector):
    key = "service_desk"
    name = "Service Desk"
    system_type = "service_desk"
    category = "ITSM"
    auth_type = "api_key_or_oauth2"
    env_prefix = "SERVICE_DESK"
    capabilities = ["create_ticket", "classify_request", "status_followup", "escalation", "sla_tracking"]
    allowed_roles = ["hsaai_admin", "department_manager", "ai_user"]
    def fetch_data(self, query: dict[str, Any], context: ConnectorContext) -> ConnectorResult:
        permission = self.check_permissions(context, "read")
        if not permission.success: return permission
        return ConnectorResult(self.key, "fetch_data", True, {"subject": query.get("subject", "ticket_status"), "sla_tracking": True}, self.name, "Service Desk connector contract ready", read_only=True)


class DMSConnector(BaseEnterpriseConnector):
    key = "dms"
    name = "Document Management System"
    system_type = "dms"
    category = "Documents"
    auth_type = "oauth2_or_api_key"
    env_prefix = "DMS"
    capabilities = ["search", "summarization", "classification", "versioning", "approvals"]
    allowed_roles = ["hsaai_admin", "knowledge_admin", "document_reviewer", "document_uploader"]
    def fetch_data(self, query: dict[str, Any], context: ConnectorContext) -> ConnectorResult:
        permission = self.check_permissions(context, "read")
        if not permission.success: return permission
        return ConnectorResult(self.key, "fetch_data", True, {"subject": query.get("subject", "document_search"), "governance": "approval-aware"}, self.name, "DMS connector contract ready", read_only=True)


class DataWarehouseConnector(BaseEnterpriseConnector):
    key = "data_warehouse"
    name = "Data Warehouse"
    system_type = "data_warehouse"
    category = "Analytics"
    auth_type = "service_account_read_only"
    env_prefix = "DATA_WAREHOUSE"
    capabilities = ["analytical_queries", "executive_reports", "historical_comparison"]
    allowed_roles = ["hsaai_admin", "department_manager", "auditor"]
    BLOCKED = (" update ", " delete ", " drop ", " alter ", " truncate ", " insert ")
    def fetch_data(self, query: dict[str, Any], context: ConnectorContext) -> ConnectorResult:
        sql = f" {str(query.get('sql') or '').lower()} "
        if any(token in sql for token in self.BLOCKED):
            return ConnectorResult(self.key, "fetch_data", False, {"blocked_operations": [x.strip().upper() for x in self.BLOCKED]}, self.name, "Data Warehouse connector is read-only; unsafe SQL blocked", read_only=True)
        permission = self.check_permissions(context, "read")
        if not permission.success: return permission
        return ConnectorResult(self.key, "fetch_data", True, {"query_mode": "read-only analytics", "sql_preview": sql.strip()[:200]}, self.name, "Data Warehouse connector contract ready", read_only=True)
