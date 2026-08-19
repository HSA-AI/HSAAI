"""
HSAAI Enterprise Connectors — Concrete Implementations
=======================================================
حزمة الموصلات المؤسسية الجاهزة للإنتاج. يتم اكتشاف جميع الموصلات
الموجودة في هذه الحزمة تلقائيًا عبر ConnectorRegistry.discover().

الموصلات المتوفرة:

  ERP / HR / Identity / Documents:
    - sap_s4hana          : SAP S/4HANA (ERP, OData v4)
    - sap_successfactors  : SAP SuccessFactors (HR, OData v2)
    - oracle_erp          : Oracle ERP Cloud (ERP, REST + Basic Auth)
    - dynamics_365        : Microsoft Dynamics 365 (ERP, OData v4 + Azure AD)
    - active_directory    : Microsoft Active Directory (Identity, LDAPS)
    - sharepoint          : Microsoft SharePoint (Documents, MS Graph API)

  ITSM / Messaging / Collaboration / Email / Integration:
    - servicenow          : ServiceNow (ITSM, Table API + Basic Auth)
    - jira_service_mgmt   : Jira Service Management (ITSM, REST API v3 + API Token)
    - microsoft_teams     : Microsoft Teams (Collaboration, Graph API + OAuth2)
    - outlook             : Microsoft Outlook (Email, Graph API + OAuth2)
    - google_workspace    : Google Workspace Gmail/Drive/Calendar (Service Account + JWT)
    - kafka               : Apache Kafka (Messaging, kafka-python | confluent-kafka)
    - rabbitmq            : RabbitMQ (Messaging, pika + AMQP)
    - rest_api            : Generic REST API (Integration, bearer/basic/api_key/none)
"""

# استيراد صريح للموصلات لضمان تسجيلها في الـ registry عند الاستيراد.
# يُسمح بفشل الاستيراد الفردي إذا كانت مكتبة خارجية اختيارية غير مثبتة
# (مثل ldap3) دون تعطيل تحميل باقي الموصلات.

try:
    from .sap_s4hana import SAPS4HANAConnector
except Exception:  # pragma: no cover - defensive
    SAPS4HANAConnector = None  # type: ignore[assignment]

try:
    from .sap_successfactors import SAPSuccessFactorsConnector
except Exception:  # pragma: no cover - defensive
    SAPSuccessFactorsConnector = None  # type: ignore[assignment]

try:
    from .oracle_erp import OracleERPConnector
except Exception:  # pragma: no cover - defensive
    OracleERPConnector = None  # type: ignore[assignment]

try:
    from .dynamics_365 import Dynamics365Connector
except Exception:  # pragma: no cover - defensive
    Dynamics365Connector = None  # type: ignore[assignment]

try:
    from .active_directory import ActiveDirectoryConnector
except Exception:  # pragma: no cover - defensive
    ActiveDirectoryConnector = None  # type: ignore[assignment]

try:
    from .sharepoint import SharePointConnector
except Exception:  # pragma: no cover - defensive
    SharePointConnector = None  # type: ignore[assignment]

# ── ITSM / Messaging / Collaboration / Email / Integration ──────────────
try:
    from .servicenow import ServiceNowConnector
except Exception:  # pragma: no cover - defensive
    ServiceNowConnector = None  # type: ignore[assignment]

try:
    from .jira_service_mgmt import JiraServiceManagementConnector
except Exception:  # pragma: no cover - defensive
    JiraServiceManagementConnector = None  # type: ignore[assignment]

try:
    from .msteams import MSTeamsConnector
except Exception:  # pragma: no cover - defensive
    MSTeamsConnector = None  # type: ignore[assignment]

try:
    from .outlook import OutlookConnector
except Exception:  # pragma: no cover - defensive
    OutlookConnector = None  # type: ignore[assignment]

try:
    from .google_workspace import GoogleWorkspaceConnector
except Exception:  # pragma: no cover - defensive
    GoogleWorkspaceConnector = None  # type: ignore[assignment]

try:
    from .kafka import KafkaConnector
except Exception:  # pragma: no cover - defensive
    KafkaConnector = None  # type: ignore[assignment]

try:
    from .rabbitmq import RabbitMQConnector
except Exception:  # pragma: no cover - defensive
    RabbitMQConnector = None  # type: ignore[assignment]

try:
    from .rest_api import RestApiConnector
except Exception:  # pragma: no cover - defensive
    RestApiConnector = None  # type: ignore[assignment]

# ── Connectors الإضافية (الدفعة الثانية) ─────────────────────────────────
try:
    from .sap_ecc import SAPECCConnector
except Exception:  # pragma: no cover - defensive
    SAPECCConnector = None  # type: ignore[assignment]

try:
    from .oracle_hcm import OracleHCMConnector
except Exception:  # pragma: no cover - defensive
    OracleHCMConnector = None  # type: ignore[assignment]

try:
    from .dynamics_hr import DynamicsHRConnector
except Exception:  # pragma: no cover - defensive
    DynamicsHRConnector = None  # type: ignore[assignment]

try:
    from .azure_ad import AzureADConnector
except Exception:  # pragma: no cover - defensive
    AzureADConnector = None  # type: ignore[assignment]

try:
    from .opentext import OpenTextConnector
except Exception:  # pragma: no cover - defensive
    OpenTextConnector = None  # type: ignore[assignment]

try:
    from .graphql import GraphQLConnector
except Exception:  # pragma: no cover - defensive
    GraphQLConnector = None  # type: ignore[assignment]

__all__ = [
    # ERP / HR / Identity / Documents
    "SAPS4HANAConnector",
    "SAPSuccessFactorsConnector",
    "OracleERPConnector",
    "Dynamics365Connector",
    "ActiveDirectoryConnector",
    "SharePointConnector",
    # ITSM / Messaging / Collaboration / Email / Integration
    "ServiceNowConnector",
    "JiraServiceManagementConnector",
    "MSTeamsConnector",
    "OutlookConnector",
    "GoogleWorkspaceConnector",
    "KafkaConnector",
    "RabbitMQConnector",
    "RestApiConnector",
    # الدفعة الثانية: ERP / HR / Identity / Documents / Integration
    "SAPECCConnector",
    "OracleHCMConnector",
    "DynamicsHRConnector",
    "AzureADConnector",
    "OpenTextConnector",
    "GraphQLConnector",
]
