"""
HSAAI Feature Store Definitions (Feast) — Phase 3 — Scale
===========================================================

FIX v2.3 (Phase 3): Defines the feature views for the HSAAI Feature Store.
These features are shared across all ML models in the platform, ensuring
consistency between training and serving.

Feature groups:
  1. Employee features — department, tenure, clearance, activity patterns
  2. Tenant features — usage volume, cost trends, SLO compliance
  3. Agent features — execution count, success rate, latency, cost
  4. Document features — upload frequency, access patterns, classification
  5. Model features — token consumption, latency, hallucination rate

Usage:
    from feast import FeatureStore
    store = FeatureStore(repo_path="infrastructure/feature-store")

    # Get online features for real-time inference
    features = store.get_online_features(
        features=[
            "employee_features:department_id",
            "employee_features:tenure_days",
            "employee_features:avg_daily_queries",
        ],
        entity_rows=[{"employee_id": "EMP001", "tenant_id": "hsa-foods"}],
    ).to_dict()

    # Get historical features for training
    training_data = store.get_historical_features(
        entity_df=training_dataframe,
        features=[
            "employee_features:department_id",
            "tenant_features:monthly_token_usage",
            "agent_features:success_rate",
        ],
    ).to_df()
"""
from datetime import timedelta
from feast import Entity, FeatureView, Field, FileSource, ValueType
from feast.types import Float32, Int64, String


# ═══════════════════════════════════════════════════════════════
# Entities — the primary keys that features are grouped by
# ═══════════════════════════════════════════════════════════════

employee = Entity(
    name="employee",
    join_keys=["employee_id"],
    description="An employee in the HSA Group organization",
)

tenant = Entity(
    name="tenant",
    join_keys=["tenant_id"],
    description="A tenant (business unit) in the HSAAI platform",
)

agent = Entity(
    name="agent",
    join_keys=["agent_id"],
    description="An AI agent in the HSAAI platform",
)

document = Entity(
    name="document",
    join_keys=["document_id"],
    description="A document in the knowledge base",
)

model = Entity(
    name="model",
    join_keys=["model_name"],
    description="An LLM model used by the platform",
)


# ═══════════════════════════════════════════════════════════════
# Feature Views — groups of features sourced from a data source
# ═══════════════════════════════════════════════════════════════

# Employee features — sourced from PostgreSQL (hr_employees table).
employee_features = FeatureView(
    name="employee_features",
    entities=[employee],
    ttl=timedelta(days=30),
    schema=[
        Field(name="department_id", dtype=String),
        Field(name="department_name", dtype=String),
        Field(name="job_title", dtype=String),
        Field(name="tenure_days", dtype=Int64),
        Field(name="clearance_level", dtype=String),
        Field(name="avg_daily_queries", dtype=Float32),
        Field(name="avg_daily_tokens", dtype=Float32),
        Field(name="last_login_hours_ago", dtype=Float32),
        Field(name="preferred_language", dtype=String),
        Field(name="satisfaction_score", dtype=Float32),
    ],
    source=FileSource(
        name="employee_source",
        path="data/features/employees.parquet",
        timestamp_field="event_timestamp",
    ),
    online=True,
    description="Employee attributes + usage patterns for personalization.",
    tags={"category": "hr", "sensitivity": "internal"},
)

# Tenant features — aggregated usage metrics per tenant.
tenant_features = FeatureView(
    name="tenant_features",
    entities=[tenant],
    ttl=timedelta(days=7),
    schema=[
        Field(name="monthly_token_usage", dtype=Int64),
        Field(name="monthly_token_budget", dtype=Int64),
        Field(name="budget_utilization_pct", dtype=Float32),
        Field(name="active_users_count", dtype=Int64),
        Field(name="total_documents_indexed", dtype=Int64),
        Field(name="avg_daily_queries", dtype=Float32),
        Field(name="cache_hit_rate", dtype=Float32),
        Field(name="slo_availability_pct", dtype=Float32),
        Field(name="slo_latency_p95_ms", dtype=Float32),
        Field(name="monthly_cost_usd", dtype=Float32),
    ],
    source=FileSource(
        name="tenant_source",
        path="data/features/tenants.parquet",
        timestamp_field="event_timestamp",
    ),
    online=True,
    description="Tenant-level usage + cost metrics for FinOps + capacity planning.",
    tags={"category": "finops", "sensitivity": "confidential"},
)

# Agent features — quality + performance metrics per agent.
agent_features = FeatureView(
    name="agent_features",
    entities=[agent],
    ttl=timedelta(days=1),
    schema=[
        Field(name="agent_name", dtype=String),
        Field(name="category", dtype=String),
        Field(name="status", dtype=String),
        Field(name="version_number", dtype=Int64),
        Field(name="total_executions_7d", dtype=Int64),
        Field(name="success_rate_7d", dtype=Float32),
        Field(name="avg_latency_ms_7d", dtype=Float32),
        Field(name="hallucination_rate_7d", dtype=Float32),
        Field(name="avg_satisfaction_7d", dtype=Float32),
        Field(name="tool_failure_rate_7d", dtype=Float32),
        Field(name="total_tokens_7d", dtype=Int64),
        Field(name="cost_usd_7d", dtype=Float32),
    ],
    source=FileSource(
        name="agent_source",
        path="data/features/agents.parquet",
        timestamp_field="event_timestamp",
    ),
    online=True,
    description="Agent quality + performance metrics for A/B testing + auto-rollback.",
    tags={"category": "ai_quality", "sensitivity": "internal"},
)

# Document features — access patterns + classification.
document_features = FeatureView(
    name="document_features",
    entities=[document],
    ttl=timedelta(days=30),
    schema=[
        Field(name="title", dtype=String),
        Field(name="classification", dtype=String),
        Field(name="content_type", dtype=String),
        Field(name="page_count", dtype=Int64),
        Field(name="word_count", dtype=Int64),
        Field(name="language", dtype=String),
        Field(name="access_count_30d", dtype=Int64),
        Field(name="citation_count_30d", dtype=Int64),
        Field(name="avg_relevance_score", dtype=Float32),
        Field(name="last_accessed_hours_ago", dtype=Float32),
    ],
    source=FileSource(
        name="document_source",
        path="data/features/documents.parquet",
        timestamp_field="event_timestamp",
    ),
    online=True,
    description="Document access + relevance metrics for RAG optimization.",
    tags={"category": "knowledge", "sensitivity": "internal"},
)

# Model features — LLM performance + cost metrics.
model_features = FeatureView(
    name="model_features",
    entities=[model],
    ttl=timedelta(days=1),
    schema=[
        Field(name="provider", dtype=String),
        Field(name="total_requests_24h", dtype=Int64),
        Field(name="total_tokens_24h", dtype=Int64),
        Field(name="avg_latency_ms_24h", dtype=Float32),
        Field(name="p99_latency_ms_24h", dtype=Float32),
        Field(name="error_rate_24h", dtype=Float32),
        Field(name="hallucination_rate_24h", dtype=Float32),
        Field(name="cost_usd_24h", dtype=Float32),
        Field(name="cache_hit_rate_24h", dtype=Float32),
        Field(name="avg_tokens_per_request", dtype=Float32),
    ],
    source=FileSource(
        name="model_source",
        path="data/features/models.parquet",
        timestamp_field="event_timestamp",
    ),
    online=True,
    description="LLM model performance + cost metrics for Model Router optimization.",
    tags={"category": "finops", "sensitivity": "internal"},
)


# ═══════════════════════════════════════════════════════════════
# Feature Services — curated groups of features for specific use cases
# ═══════════════════════════════════════════════════════════════

from feast import FeatureService

# Features for the Model Router (selects optimal model per request).
model_router_features = FeatureService(
    name="model_router_features",
    features=[
        model_features[
            "provider",
            "avg_latency_ms_24h",
            "p99_latency_ms_24h",
            "error_rate_24h",
            "cost_usd_24h",
            "cache_hit_rate_24h",
        ],
        tenant_features[
            "budget_utilization_pct",
            "cache_hit_rate",
        ],
    ],
    description="Features used by the AI Gateway Model Router to select the optimal model.",
)

# Features for agent quality monitoring (auto-rollback decisions).
agent_quality_features = FeatureService(
    name="agent_quality_features",
    features=[
        agent_features[
            "success_rate_7d",
            "hallucination_rate_7d",
            "avg_satisfaction_7d",
            "tool_failure_rate_7d",
        ],
    ],
    description="Features used by the Agent Marketplace for quality monitoring + auto-rollback.",
)

# Features for FinOps cost optimization.
finops_features = FeatureService(
    name="finops_features",
    features=[
        tenant_features[
            "monthly_token_usage",
            "monthly_token_budget",
            "budget_utilization_pct",
            "monthly_cost_usd",
            "cache_hit_rate",
        ],
        model_features[
            "cost_usd_24h",
            "avg_tokens_per_request",
            "cache_hit_rate_24h",
        ],
    ],
    description="Features for FinOps dashboards + cost optimization.",
)
