"""
HSAAI Enterprise Knowledge Graph Ontology (Phase 3 — Scale)
============================================================

FIX v2.3 (Phase 3): Implements a formal ontology for the enterprise
knowledge graph. The ontology defines:
  - Entity types (Employee, Department, Document, Policy, System, Vendor, etc.)
  - Relationship types (WORKS_IN, AUTHORED_BY, GOVERNED_BY, INTEGRATES_WITH, etc.)
  - Attributes (each entity type has required + optional attributes)
  - Constraints (cardinality, domain/range, uniqueness)
  - Taxonomy (hierarchical classification of entities)

This enables:
  - Entity resolution (merge duplicate entities from different sources)
  - Inference (if Employee A WORKS_IN Department B, and Department B
    GOVERNED_BY Policy C, then Employee A is subject to Policy C)
  - Consistency checking (detect missing required relationships)
  - Natural language queries over the graph ("Who is the CFO's direct report?")
  - Compliance auditing (verify all employees have assigned policies)

The ontology is loaded into Neo4j as a schema and enforced via constraints.
"""
from __future__ import annotations

from typing import Any
from dataclasses import dataclass, field
from enum import Enum


# ─── Entity Types (Taxonomy) ──────────────────────────────────

class EntityType(str, Enum):
    # People
    EMPLOYEE = "Employee"
    CONTRACTOR = "Contractor"
    EXECUTIVE = "Executive"
    # Organization
    DEPARTMENT = "Department"
    BUSINESS_UNIT = "BusinessUnit"
    SUBSIDIARY = "Subsidiary"
    # Documents
    DOCUMENT = "Document"
    POLICY = "Policy"
    CONTRACT = "Contract"
    REPORT = "Report"
    # Systems
    SYSTEM = "System"
    APPLICATION = "Application"
    DATABASE = "Database"
    API = "API"
    # External
    VENDOR = "Vendor"
    CUSTOMER = "Customer"
    PARTNER = "Partner"
    # AI
    AGENT = "Agent"
    MODEL = "Model"
    WORKFLOW = "Workflow"
    # Governance
    RISK = "Risk"
    CONTROL = "Control"
    COMPLIANCE_FRAMEWORK = "ComplianceFramework"
    # Data
    DATASET = "Dataset"
    DATA_SOURCE = "DataSource"
    # Physical
    FACILITY = "Facility"
    ASSET = "Asset"


# ─── Relationship Types ───────────────────────────────────────

class RelationshipType(str, Enum):
    # Organizational
    WORKS_IN = "WORKS_IN"              # Employee → Department
    MANAGES = "MANAGES"                # Employee → Department/Employee
    REPORTS_TO = "REPORTS_TO"          # Employee → Employee
    PART_OF = "PART_OF"                # Department → BusinessUnit
    SUBSIDIARY_OF = "SUBSIDIARY_OF"    # Subsidiary → Subsidiary
    # Document
    AUTHORED_BY = "AUTHORED_BY"        # Document → Employee
    GOVERNED_BY = "GOVERNED_BY"        # Employee/Department → Policy
    REFERENCES = "REFERENCES"          # Document → Document
    CLASSIFIED_AS = "CLASSIFIED_AS"    # Document → Classification
    # System
    INTEGRATES_WITH = "INTEGRATES_WITH"  # System → System
    DEPENDS_ON = "DEPENDS_ON"          # System → System
    HOSTS = "HOSTS"                     # System → Application
    ACCESSES = "ACCESSES"              # System/Employee → Database/Dataset
    # External
    SUPPLIED_BY = "SUPPLIED_BY"        # Asset/Product → Vendor
    SOLD_TO = "SOLD_TO"                # Product/Service → Customer
    PARTNERS_WITH = "PARTNERS_WITH"    # Subsidiary → Partner
    # AI
    BUILT_FROM = "BUILT_FROM"          # Model → Dataset
    DEPLOYED_IN = "DEPLOYED_IN"        # Model → System
    EXECUTES = "EXECUTES"              # Agent → Tool/Workflow
    TRAINED_ON = "TRAINED_ON"          # Model → Dataset
    # Governance
    MITIGATES = "MITIGATES"            # Control → Risk
    REQUIRED_BY = "REQUIRED_BY"        # Control → ComplianceFramework
    VIOLATES = "VIOLATES"              # Employee/System → Policy
    # Knowledge
    DERIVED_FROM = "DERIVED_FROM"      # Dataset → DataSource
    CONTAINS = "CONTAINS"              # Dataset → DataEntity


# ─── Entity Definitions ───────────────────────────────────────

@dataclass
class AttributeDef:
    name: str
    type: str  # string, int, float, boolean, datetime, enum
    required: bool = False
    unique: bool = False
    indexed: bool = False
    default: Any = None
    enum_values: list[str] = field(default_factory=list)
    description: str = ""


@dataclass
class EntityDef:
    entity_type: EntityType
    attributes: list[AttributeDef]
    description: str = ""
    parent_type: EntityType | None = None  # for taxonomy hierarchy


# Define all entity types with their attributes.
ENTITY_DEFINITIONS: list[EntityDef] = [
    EntityDef(
        entity_type=EntityType.EMPLOYEE,
        description="A person employed by HSA Group.",
        attributes=[
            AttributeDef(name="employee_id", type="string", required=True, unique=True, indexed=True, description="HR system employee ID"),
            AttributeDef(name="full_name", type="string", required=True, indexed=True),
            AttributeDef(name="email", type="string", required=True, unique=True, indexed=True),
            AttributeDef(name="phone", type="string"),
            AttributeDef(name="job_title", type="string", required=True, indexed=True),
            AttributeDef(name="department_id", type="string", required=True, indexed=True, description="Reference to Department"),
            AttributeDef(name="hire_date", type="datetime", required=True),
            AttributeDef(name="termination_date", type="datetime"),
            AttributeDef(name="clearance_level", type="enum", enum_values=["public", "internal", "confidential", "restricted"], default="internal"),
            AttributeDef(name="employment_status", type="enum", enum_values=["active", "on_leave", "terminated"], default="active", indexed=True),
            AttributeDef(name="manager_id", type="string", description="Direct manager's employee_id"),
            AttributeDef(name="tenant_id", type="string", required=True, indexed=True),
        ],
    ),
    EntityDef(
        entity_type=EntityType.EXECUTIVE,
        description="An employee with executive-level authority (C-suite, VP, Director).",
        parent_type=EntityType.EMPLOYEE,
        attributes=[
            AttributeDef(name="executive_level", type="enum", enum_values=["c_suite", "vp", "director", "senior_director"], required=True),
            AttributeDef(name="budget_authority_limit", type="float", description="Maximum amount they can approve without higher approval (SAR)"),
            AttributeDef(name="direct_reports_count", type="int", default=0),
        ],
    ),
    EntityDef(
        entity_type=EntityType.DEPARTMENT,
        description="An organizational department within a business unit.",
        attributes=[
            AttributeDef(name="department_id", type="string", required=True, unique=True, indexed=True),
            AttributeDef(name="name", type="string", required=True, indexed=True),
            AttributeDef(name="name_ar", type="string", description="Arabic name"),
            AttributeDef(name="business_unit_id", type="string", required=True, indexed=True),
            AttributeDef(name="head_employee_id", type="string", description="Department head's employee_id"),
            AttributeDef(name="budget_annual", type="float", description="Annual department budget (SAR)"),
            AttributeDef(name="tenant_id", type="string", required=True, indexed=True),
        ],
    ),
    EntityDef(
        entity_type=EntityType.BUSINESS_UNIT,
        description="A major business unit (HSA Foods, HSA Retail, etc.).",
        attributes=[
            AttributeDef(name="bu_id", type="string", required=True, unique=True, indexed=True),
            AttributeDef(name="name", type="string", required=True),
            AttributeDef(name="subsidiary_id", type="string", required=True),
            AttributeDef(name="ceo_employee_id", type="string"),
            AttributeDef(name="revenue_annual", type="float"),
            AttributeDef(name="tenant_id", type="string", required=True, indexed=True),
        ],
    ),
    EntityDef(
        entity_type=EntityType.DOCUMENT,
        description="Any document in the knowledge base.",
        attributes=[
            AttributeDef(name="document_id", type="string", required=True, unique=True, indexed=True),
            AttributeDef(name="title", type="string", required=True, indexed=True),
            AttributeDef(name="filename", type="string", required=True),
            AttributeDef(name="content_type", type="string", required=True),
            AttributeDef(name="classification", type="enum", enum_values=["public", "internal", "confidential", "restricted"], default="internal", indexed=True),
            AttributeDef(name="tenant_id", type="string", required=True, indexed=True),
            AttributeDef(name="workspace_id", type="string", required=True),
            AttributeDef(name="uploaded_by", type="string", required=True),
            AttributeDef(name="upload_date", type="datetime", required=True),
            AttributeDef(name="last_modified", type="datetime"),
            AttributeDef(name="page_count", type="int"),
            AttributeDef(name="word_count", type="int"),
            AttributeDef(name="language", type="string", default="ar"),
            AttributeDef(name="object_storage_key", type="string", description="MinIO object key"),
        ],
    ),
    EntityDef(
        entity_type=EntityType.POLICY,
        description="An organizational policy document.",
        parent_type=EntityType.DOCUMENT,
        attributes=[
            AttributeDef(name="policy_id", type="string", required=True, unique=True),
            AttributeDef(name="policy_type", type="enum", enum_values=["hr", "finance", "it", "security", "operations", "legal", "procurement"], required=True, indexed=True),
            AttributeDef(name="effective_date", type="datetime", required=True),
            AttributeDef(name="expiry_date", type="datetime"),
            AttributeDef(name="version", type="string", required=True),
            AttributeDef(name="approved_by", type="string", required=True),
            AttributeDef(name="applies_to_departments", type="string", description="Comma-separated department IDs, or 'all'"),
        ],
    ),
    EntityDef(
        entity_type=EntityType.SYSTEM,
        description="An IT system or application.",
        attributes=[
            AttributeDef(name="system_id", type="string", required=True, unique=True, indexed=True),
            AttributeDef(name="name", type="string", required=True, indexed=True),
            AttributeDef(name="system_type", type="enum", enum_values=["erp", "crm", "hr", "finance", "bi", "custom", "saas"], required=True),
            AttributeDef(name="vendor", type="string"),
            AttributeDef(name="version", type="string"),
            AttributeDef(name="criticality", type="enum", enum_values=["low", "medium", "high", "critical"], default="medium", indexed=True),
            AttributeDef(name="owner_department_id", type="string"),
            AttributeDef(name="tenant_id", type="string", required=True, indexed=True),
        ],
    ),
    EntityDef(
        entity_type=EntityType.VENDOR,
        description="An external supplier or service provider.",
        attributes=[
            AttributeDef(name="vendor_id", type="string", required=True, unique=True, indexed=True),
            AttributeDef(name="name", type="string", required=True, indexed=True),
            AttributeDef(name="contact_email", type="string"),
            AttributeDef(name="contact_phone", type="string"),
            AttributeDef(name="contract_start", type="datetime"),
            AttributeDef(name="contract_end", type="datetime"),
            AttributeDef(name="annual_spend", type="float", description="Annual spend with this vendor (SAR)"),
            AttributeDef(name="risk_rating", type="enum", enum_values=["low", "medium", "high", "critical"], default="medium"),
            AttributeDef(name="tenant_id", type="string", required=True, indexed=True),
        ],
    ),
    EntityDef(
        entity_type=EntityType.AGENT,
        description="An AI agent in the HSAAI platform.",
        attributes=[
            AttributeDef(name="agent_id", type="string", required=True, unique=True, indexed=True),
            AttributeDef(name="name", type="string", required=True),
            AttributeDef(name="category", type="enum", enum_values=["hr", "finance", "legal", "it", "operations", "sales", "procurement", "executive", "custom"], required=True),
            AttributeDef(name="status", type="enum", enum_values=["draft", "testing", "staging", "production", "canary", "retired"], required=True, indexed=True),
            AttributeDef(name="department", type="string", required=True),
            AttributeDef(name="version", type="int", required=True),
            AttributeDef(name="created_at", type="datetime", required=True),
            AttributeDef(name="tenant_id", type="string", required=True, indexed=True),
        ],
    ),
    EntityDef(
        entity_type=EntityType.RISK,
        description="An identified risk to the organization.",
        attributes=[
            AttributeDef(name="risk_id", type="string", required=True, unique=True),
            AttributeDef(name="description", type="string", required=True),
            AttributeDef(name="category", type="enum", enum_values=["financial", "operational", "security", "compliance", "strategic", "ai"], required=True, indexed=True),
            AttributeDef(name="severity", type="enum", enum_values=["low", "medium", "high", "critical"], required=True, indexed=True),
            AttributeDef(name="likelihood", type="enum", enum_values=["rare", "unlikely", "possible", "likely", "almost_certain"], required=True),
            AttributeDef(name="identified_date", type="datetime", required=True),
            AttributeDef(name="mitigation_status", type="enum", enum_values=["open", "in_progress", "mitigated", "accepted", "closed"], default="open", indexed=True),
            AttributeDef(name="owner_employee_id", type="string"),
            AttributeDef(name="tenant_id", type="string", required=True, indexed=True),
        ],
    ),
]


# ─── Relationship Definitions (with domain/range constraints) ─

@dataclass
class RelationshipDef:
    rel_type: RelationshipType
    domain: EntityType  # source entity type
    range: EntityType   # target entity type
    cardinality: str = "many_to_many"  # one_to_one, one_to_many, many_to_one, many_to_many
    description: str = ""


RELATIONSHIP_DEFINITIONS: list[RelationshipDef] = [
    # Organizational
    RelationshipDef(RelationshipType.WORKS_IN, EntityType.EMPLOYEE, EntityType.DEPARTMENT, "many_to_one",
                    "An employee works in a department"),
    RelationshipDef(RelationshipType.MANAGES, EntityType.EMPLOYEE, EntityType.DEPARTMENT, "one_to_one",
                    "An employee manages a department (department head)"),
    RelationshipDef(RelationshipType.REPORTS_TO, EntityType.EMPLOYEE, EntityType.EMPLOYEE, "many_to_one",
                    "An employee reports to their manager"),
    RelationshipDef(RelationshipType.PART_OF, EntityType.DEPARTMENT, EntityType.BUSINESS_UNIT, "many_to_one",
                    "A department is part of a business unit"),
    # Document
    RelationshipDef(RelationshipType.AUTHORED_BY, EntityType.DOCUMENT, EntityType.EMPLOYEE, "many_to_one",
                    "A document was authored by an employee"),
    RelationshipDef(RelationshipType.GOVERNED_BY, EntityType.EMPLOYEE, EntityType.POLICY, "many_to_many",
                    "An employee is governed by a policy"),
    RelationshipDef(RelationshipType.REFERENCES, EntityType.DOCUMENT, EntityType.DOCUMENT, "many_to_many",
                    "A document references another document"),
    # System
    RelationshipDef(RelationshipType.INTEGRATES_WITH, EntityType.SYSTEM, EntityType.SYSTEM, "many_to_many",
                    "A system integrates with another system"),
    RelationshipDef(RelationshipType.DEPENDS_ON, EntityType.SYSTEM, EntityType.SYSTEM, "many_to_many",
                    "A system depends on another system (runtime dependency)"),
    RelationshipDef(RelationshipType.ACCESSES, EntityType.SYSTEM, EntityType.DATABASE, "many_to_many",
                    "A system accesses a database"),
    # External
    RelationshipDef(RelationshipType.SUPPLIED_BY, EntityType.ASSET, EntityType.VENDOR, "many_to_one",
                    "An asset is supplied by a vendor"),
    # AI
    RelationshipDef(RelationshipType.EXECUTES, EntityType.AGENT, EntityType.WORKFLOW, "many_to_many",
                    "An agent executes a workflow"),
    RelationshipDef(RelationshipType.TRAINED_ON, EntityType.MODEL, EntityType.DATASET, "many_to_many",
                    "A model was trained on a dataset"),
    RelationshipDef(RelationshipType.DEPLOYED_IN, EntityType.MODEL, EntityType.SYSTEM, "many_to_one",
                    "A model is deployed in a system"),
    # Governance
    RelationshipDef(RelationshipType.MITIGATES, EntityType.CONTROL, EntityType.RISK, "many_to_many",
                    "A control mitigates a risk"),
    RelationshipDef(RelationshipType.REQUIRED_BY, EntityType.CONTROL, EntityType.COMPLIANCE_FRAMEWORK, "many_to_many",
                    "A control is required by a compliance framework"),
    RelationshipDef(RelationshipType.VIOLATES, EntityType.EMPLOYEE, EntityType.POLICY, "many_to_many",
                    "An employee violated a policy"),
]


# ─── Inference Rules ──────────────────────────────────────────

INFERENCE_RULES: list[dict[str, Any]] = [
    {
        "name": "policy_inheritance",
        "description": "If an Employee WORKS_IN a Department, and the Department GOVERNED_BY a Policy, then the Employee is GOVERNED_BY that Policy.",
        "cypher": """
            MATCH (e:Employee)-[:WORKS_IN]->(d:Department)-[:GOVERNED_BY]->(p:Policy)
            WHERE NOT (e)-[:GOVERNED_BY]->(p)
            MERGE (e)-[:GOVERNED_BY]->(p)
        """,
    },
    {
        "name": "manager_inherits_team_risks",
        "description": "If an Employee REPORTS_TO a Manager, and the Employee is associated with a Risk, the Manager is also associated with that Risk.",
        "cypher": """
            MATCH (e:Employee)-[:REPORTS_TO]->(m:Employee)
            MATCH (e)-[:ASSOCIATED_WITH]->(r:Risk)
            WHERE NOT (m)-[:ASSOCIATED_WITH]->(r)
            MERGE (m)-[:ASSOCIATED_WITH]->(r)
        """,
    },
    {
        "name": "system_dependency_transitive",
        "description": "If System A DEPENDS_ON System B, and System B DEPENDS_ON System C, then System A transitively depends on System C.",
        "cypher": """
            MATCH (a:System)-[:DEPENDS_ON]->(b:System)-[:DEPENDS_ON]->(c:System)
            WHERE a <> c AND NOT (a)-[:DEPENDS_ON]->(c)
            MERGE (a)-[:DEPENDS_ON {transitive: true}]->(c)
        """,
    },
    {
        "name": "vendor_risk_propagation",
        "description": "If a System is SUPPLIED_BY a Vendor with high risk_rating, flag the System as at-risk.",
        "cypher": """
            MATCH (s:System)-[:SUPPLIED_BY]->(v:Vendor)
            WHERE v.risk_rating IN ['high', 'critical']
            SET s.vendor_risk_flag = true
        """,
    },
]


# ─── Entity Resolution ────────────────────────────────────────

ENTITY_RESOLUTION_RULES: list[dict[str, Any]] = [
    {
        "entity_type": "Employee",
        "description": "Merge employees with the same email address (deduplicate from HR + AD + SuccessFactors).",
        "match_criteria": ["email"],
        "survivorship": {
            "employee_id": "prefer_source:hr_system",
            "full_name": "longest_value",
            "phone": "first_non_empty",
            "job_title": "prefer_source:hr_system",
            "clearance_level": "highest_clearance",
        },
    },
    {
        "entity_type": "Department",
        "description": "Merge departments with the same department_id across systems.",
        "match_criteria": ["department_id", "tenant_id"],
        "survivorship": {
            "name": "prefer_source:sap",
            "name_ar": "prefer_source:hr_system",
            "head_employee_id": "first_non_empty",
            "budget_annual": "max_value",
        },
    },
    {
        "entity_type": "Document",
        "description": "Detect duplicate documents by content hash (same file uploaded twice).",
        "match_criteria": ["content_hash", "tenant_id"],
        "survivorship": {
            "title": "first_created",
            "uploaded_by": "first_created",
            "classification": "highest_classification",
        },
    },
    {
        "entity_type": "Vendor",
        "description": "Merge vendors with similar names + same contact email.",
        "match_criteria": ["normalized_name", "contact_email"],
        "survivorship": {
            "name": "prefer_source:procurement_system",
            "annual_spend": "sum_values",
            "risk_rating": "highest_risk",
        },
    },
]


# ─── Taxonomy (Hierarchical Classification) ───────────────────

TAXONOMY: dict[str, list[str]] = {
    "Document": [
        "Policy",
        "Contract",
        "Report",
        "Invoice",
        "Manual",
        "Presentation",
        "Email",
        "Spreadsheet",
    ],
    "Policy": [
        "HR Policy",
        "Finance Policy",
        "IT Policy",
        "Security Policy",
        "Operations Policy",
        "Legal Policy",
        "Procurement Policy",
    ],
    "System": [
        "ERP",
        "CRM",
        "HR System",
        "Finance System",
        "BI Tool",
        "Custom Application",
        "SaaS",
        "Database",
        "API",
    ],
    "Risk": [
        "Financial Risk",
        "Operational Risk",
        "Security Risk",
        "Compliance Risk",
        "Strategic Risk",
        "AI Risk",
    ],
    "AI Risk": [
        "Hallucination Risk",
        "Bias Risk",
        "Privacy Risk",
        "Security Risk",
        "Model Drift",
        "Prompt Injection",
    ],
    "Employee": [
        "Full-time",
        "Part-time",
        "Contractor",
        "Consultant",
        "Intern",
    ],
}


def get_cypher_schema_constraints() -> list[str]:
    """Generate Neo4j Cypher constraint statements from the ontology.

    These are executed on graph initialization to enforce uniqueness
    and indexing on entity attributes.
    """
    constraints = []
    for entity_def in ENTITY_DEFINITIONS:
        entity_label = entity_def.entity_type.value
        for attr in entity_def.attributes:
            if attr.unique:
                constraints.append(
                    f"CREATE CONSTRAINT {entity_label}_{attr.name}_unique "
                    f"IF NOT EXISTS FOR (n:{entity_label}) "
                    f"REQUIRE n.{attr.name} IS UNIQUE"
                )
            elif attr.indexed:
                constraints.append(
                    f"CREATE INDEX {entity_label}_{attr.name}_index "
                    f"IF NOT EXISTS FOR (n:{entity_label}) ON (n.{attr.name})"
                )
    return constraints


__all__ = [
    "EntityType",
    "RelationshipType",
    "AttributeDef",
    "EntityDef",
    "RelationshipDef",
    "ENTITY_DEFINITIONS",
    "RELATIONSHIP_DEFINITIONS",
    "INFERENCE_RULES",
    "ENTITY_RESOLUTION_RULES",
    "TAXONOMY",
    "get_cypher_schema_constraints",
]
