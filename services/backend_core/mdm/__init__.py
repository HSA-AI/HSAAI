"""
HSAAI Master Data Management (MDM) Service (Phase 3 — Scale)
==============================================================

FIX v2.3 (Phase 3): Implements Master Data Management for enterprise
entities that appear in multiple systems (HR, SAP, Active Directory,
SuccessFactors). The MDM service:

  1. Ingests entity records from multiple source systems
  2. Matches + merges duplicate records using survivorship rules
  3. Creates a "Golden Record" — the authoritative version of each entity
  4. Tracks provenance (which source system contributed each attribute)
  5. Detects + resolves conflicts (e.g., different phone numbers in HR vs AD)
  6. Publishes golden records back to source systems (bidirectional sync)
  7. Maintains audit trail of all merges + changes

Master data entities:
  - Employee (HR system, Active Directory, SuccessFactors, SAP)
  - Vendor (Procurement system, SAP, Finance system)
  - Customer (CRM, SAP, Finance system)
  - Product (SAP, Inventory system, E-commerce)
  - Department (HR, SAP, AD)

Survivorship strategies:
  - "first_non_empty": take the first non-empty value across sources
  - "last_updated": take the value from the source with the most recent update
  - "prefer_source:system_name": always take from the specified source
  - "longest_value": take the longest non-empty value (for names)
  - "highest_clearance": take the highest security clearance level
  - "max_value" / "min_value": numeric comparison
  - "sum_values": sum across all sources (for financial aggregates)
  - "union_values": combine all unique values (for lists)

Usage:
    POST /v1/mdm/ingest          — ingest a record from a source system
    GET  /v1/mdm/golden/{type}/{id} — get the golden record for an entity
    GET  /v1/mdm/golden/{type}    — list all golden records of a type
    POST /v1/mdm/merge            — manually trigger merge + survivorship
    GET  /v1/mdm/conflicts        — list unresolved data conflicts
    POST /v1/mdm/conflicts/{id}/resolve — resolve a conflict manually
"""
from __future__ import annotations

import os
import json
import uuid
import logging
from datetime import datetime, timezone
from typing import Any, Optional
from dataclasses import dataclass, field, asdict
from enum import Enum

logger = logging.getLogger("hsaai.mdm")


class EntityType(str, Enum):
    EMPLOYEE = "employee"
    VENDOR = "vendor"
    CUSTOMER = "customer"
    PRODUCT = "product"
    DEPARTMENT = "department"


class SourceSystem(str, Enum):
    HR_SYSTEM = "hr_system"
    ACTIVE_DIRECTORY = "active_directory"
    SUCCESSFACTORS = "successfactors"
    SAP = "sap"
    CRM = "crm"
    PROCUREMENT = "procurement"
    FINANCE = "finance"
    INVENTORY = "inventory"
    ECOMMERCE = "ecommerce"
    MANUAL = "manual"


class ConflictStatus(str, Enum):
    UNRESOLVED = "unresolved"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


@dataclass
class SourceRecord:
    """A record from a source system, before merging."""
    record_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_system: SourceSystem = SourceSystem.MANUAL
    source_record_id: str = ""  # the ID in the source system
    entity_type: EntityType = EntityType.EMPLOYEE
    attributes: dict[str, Any] = field(default_factory=dict)
    ingested_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    ingested_by: str = ""


@dataclass
class GoldenRecord:
    """The authoritative, merged version of an entity.

    Each attribute has:
      - value: the winning value (after survivorship)
      - source: which source system contributed this value
      - confidence: 0.0-1.0 (how confident we are in this value)
      - last_updated: when this value was last changed
      - alternatives: list of other source values that were merged
    """
    golden_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    entity_type: EntityType = EntityType.EMPLOYEE
    attributes: dict[str, dict[str, Any]] = field(default_factory=dict)
    # Mapping of attribute_name → {value, source, confidence, last_updated, alternatives}
    source_record_ids: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_updated: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    merge_count: int = 0
    quality_score: float = 1.0  # 1.0 = perfect, 0.0 = all conflicts


@dataclass
class DataConflict:
    """A conflict between source systems for the same attribute."""
    conflict_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    golden_id: str = ""
    entity_type: EntityType = EntityType.EMPLOYEE
    attribute_name: str = ""
    conflicting_values: list[dict[str, Any]] = field(default_factory=list)
    # Each: {value, source_system, source_record_id, ingested_at}
    status: ConflictStatus = ConflictStatus.UNRESOLVED
    resolved_value: Any = None
    resolved_by: str = ""
    resolved_at: str = ""
    resolution_note: str = ""


# ─── Survivorship Rules ───────────────────────────────────────

SURVIVORSHIP_RULES: dict[str, dict[str, str]] = {
    "employee": {
        "employee_id": "prefer_source:hr_system",
        "full_name": "longest_value",
        "email": "prefer_source:active_directory",
        "phone": "first_non_empty",
        "job_title": "prefer_source:successfactors",
        "department_id": "prefer_source:hr_system",
        "manager_id": "prefer_source:hr_system",
        "hire_date": "prefer_source:hr_system",
        "clearance_level": "highest_clearance",
        "employment_status": "prefer_source:hr_system",
    },
    "vendor": {
        "vendor_id": "prefer_source:procurement",
        "name": "prefer_source:procurement",
        "contact_email": "first_non_empty",
        "contact_phone": "first_non_empty",
        "contract_start": "prefer_source:finance",
        "contract_end": "prefer_source:finance",
        "annual_spend": "sum_values",
        "risk_rating": "highest_risk",
    },
    "customer": {
        "customer_id": "prefer_source:sap",
        "name": "prefer_source:crm",
        "email": "prefer_source:crm",
        "phone": "first_non_empty",
        "address": "prefer_source:sap",
        "credit_limit": "prefer_source:finance",
        "payment_terms": "prefer_source:sap",
    },
    "department": {
        "department_id": "prefer_source:hr_system",
        "name": "prefer_source:sap",
        "name_ar": "prefer_source:hr_system",
        "head_employee_id": "prefer_source:hr_system",
        "budget_annual": "prefer_source:finance",
    },
}

CLEARANCE_ORDER = {"public": 0, "internal": 1, "confidential": 2, "restricted": 3}
RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def apply_survivorship(strategy: str, values: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Apply a survivorship strategy to a list of source values.

    Args:
        strategy: One of "first_non_empty", "last_updated", "prefer_source:X",
                  "longest_value", "highest_clearance", "max_value", "min_value",
                  "sum_values", "union_values".
        values: List of {value, source_system, source_record_id, ingested_at}.

    Returns:
        The winning value dict, or None if no values.
    """
    if not values:
        return None

    non_empty = [v for v in values if v.get("value") is not None and v.get("value") != ""]
    if not non_empty:
        return values[0]

    if strategy == "first_non_empty":
        return non_empty[0]

    if strategy == "last_updated":
        return sorted(non_empty, key=lambda v: v.get("ingested_at", ""))[-1]

    if strategy.startswith("prefer_source:"):
        preferred_source = strategy.split(":", 1)[1]
        for v in non_empty:
            if v.get("source_system") == preferred_source:
                return v
        return non_empty[0]  # fallback to first if preferred not found

    if strategy == "longest_value":
        return max(non_empty, key=lambda v: len(str(v.get("value", ""))))

    if strategy == "highest_clearance":
        return max(non_empty, key=lambda v: CLEARANCE_ORDER.get(str(v.get("value", "")).lower(), 0))

    if strategy == "highest_risk":
        return max(non_empty, key=lambda v: RISK_ORDER.get(str(v.get("value", "")).lower(), 0))

    if strategy == "max_value":
        return max(non_empty, key=lambda v: float(v.get("value", 0) or 0))

    if strategy == "min_value":
        return min(non_empty, key=lambda v: float(v.get("value", 0) or 0))

    if strategy == "sum_values":
        total = sum(float(v.get("value", 0) or 0) for v in non_empty)
        return {**non_empty[0], "value": total, "source_system": "aggregated"}

    if strategy == "union_values":
        unique_vals = list(set(str(v.get("value")) for v in non_empty))
        return {**non_empty[0], "value": unique_vals, "source_system": "aggregated"}

    # Default: first non-empty.
    return non_empty[0]


# ─── MDM Service ──────────────────────────────────────────────

class MDMService:
    """Master Data Management service — creates golden records from multiple sources."""

    def __init__(self):
        # In production, backed by PostgreSQL (golden_records + source_records + conflicts tables).
        self._source_records: dict[str, SourceRecord] = {}
        self._golden_records: dict[str, GoldenRecord] = {}
        self._conflicts: dict[str, DataConflict] = {}
        # Index: (entity_type, match_key) → golden_id
        # match_key is entity-specific (employee_id for employees, vendor_id for vendors, etc.)
        self._match_index: dict[tuple[str, str], str] = {}
        self._storage_file = os.getenv("MDM_STORAGE_FILE", "/data/mdm.json")
        self._load()

    def _load(self):
        """Load persisted state from file."""
        try:
            if os.path.exists(self._storage_file):
                with open(self._storage_file) as f:
                    data = json.load(f)
                # Reconstruct source records.
                for sr_data in data.get("source_records", []):
                    sr = SourceRecord(
                        record_id=sr_data["record_id"],
                        source_system=SourceSystem(sr_data["source_system"]),
                        source_record_id=sr_data.get("source_record_id", ""),
                        entity_type=EntityType(sr_data["entity_type"]),
                        attributes=sr_data.get("attributes", {}),
                        ingested_at=sr_data.get("ingested_at", ""),
                        ingested_by=sr_data.get("ingested_by", ""),
                    )
                    self._source_records[sr.record_id] = sr
                # Reconstruct golden records.
                for gr_data in data.get("golden_records", []):
                    gr = GoldenRecord(
                        golden_id=gr_data["golden_id"],
                        entity_type=EntityType(gr_data["entity_type"]),
                        attributes=gr_data.get("attributes", {}),
                        source_record_ids=gr_data.get("source_record_ids", []),
                        created_at=gr_data.get("created_at", ""),
                        last_updated=gr_data.get("last_updated", ""),
                        merge_count=gr_data.get("merge_count", 0),
                        quality_score=gr_data.get("quality_score", 1.0),
                    )
                    self._golden_records[gr.golden_id] = gr
                # Reconstruct conflicts.
                for c_data in data.get("conflicts", []):
                    c = DataConflict(
                        conflict_id=c_data["conflict_id"],
                        golden_id=c_data["golden_id"],
                        entity_type=EntityType(c_data["entity_type"]),
                        attribute_name=c_data["attribute_name"],
                        conflicting_values=c_data.get("conflicting_values", []),
                        status=ConflictStatus(c_data["status"]),
                        resolved_value=c_data.get("resolved_value"),
                        resolved_by=c_data.get("resolved_by", ""),
                        resolved_at=c_data.get("resolved_at", ""),
                        resolution_note=c_data.get("resolution_note", ""),
                    )
                    self._conflicts[c.conflict_id] = c
                # Rebuild match index.
                for gr in self._golden_records.values():
                    match_key = self._get_match_key(gr)
                    if match_key:
                        self._match_index[(gr.entity_type.value, match_key)] = gr.golden_id
        except Exception as e:
            logger.warning("Failed to load MDM state: %s", e)

    def _save(self):
        """Persist state to file."""
        try:
            os.makedirs(os.path.dirname(self._storage_file), exist_ok=True)
            data = {
                "source_records": [asdict(sr) for sr in self._source_records.values()],
                "golden_records": [asdict(gr) for gr in self._golden_records.values()],
                "conflicts": [asdict(c) for c in self._conflicts.values()],
            }
            # Convert enums to strings.
            for sr in data["source_records"]:
                sr["source_system"] = sr["source_system"].value if isinstance(sr["source_system"], SourceSystem) else sr["source_system"]
                sr["entity_type"] = sr["entity_type"].value if isinstance(sr["entity_type"], EntityType) else sr["entity_type"]
            for gr in data["golden_records"]:
                gr["entity_type"] = gr["entity_type"].value if isinstance(gr["entity_type"], EntityType) else gr["entity_type"]
            for c in data["conflicts"]:
                c["entity_type"] = c["entity_type"].value if isinstance(c["entity_type"], EntityType) else c["entity_type"]
                c["status"] = c["status"].value if isinstance(c["status"], ConflictStatus) else c["status"]
            with open(self._storage_file, "w") as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        except Exception as e:
            logger.error("Failed to save MDM state: %s", e)

    def _get_match_key(self, record: GoldenRecord | SourceRecord) -> str | None:
        """Get the match key for an entity (used for deduplication).

        Employee → employee_id
        Vendor → vendor_id
        Customer → customer_id
        Product → product_id
        Department → department_id
        """
        match_attr = f"{record.entity_type.value}_id"
        if isinstance(record, SourceRecord):
            return record.attributes.get(match_attr)
        else:
            attr_data = record.attributes.get(match_attr, {})
            return attr_data.get("value") if isinstance(attr_data, dict) else attr_data

    def ingest(self, source_system: SourceSystem, entity_type: EntityType,
               source_record_id: str, attributes: dict[str, Any],
               ingested_by: str = "") -> GoldenRecord:
        """Ingest a record from a source system + merge into golden record.

        This is the main entry point. Source systems (SAP, HR, AD, etc.)
        call this endpoint to push their data. The MDM service:
          1. Stores the source record
          2. Finds (or creates) the matching golden record
          3. Applies survivorship rules to merge attributes
          4. Detects + records conflicts
          5. Returns the updated golden record
        """
        # Create + store the source record.
        sr = SourceRecord(
            source_system=source_system,
            source_record_id=source_record_id,
            entity_type=entity_type,
            attributes=attributes,
            ingested_by=ingested_by,
        )
        self._source_records[sr.record_id] = sr

        # Find or create the golden record.
        match_key = attributes.get(f"{entity_type.value}_id")
        if not match_key:
            logger.warning("No match key found for %s from %s", entity_type.value, source_system.value)
            match_key = str(uuid.uuid4())

        golden_id = self._match_index.get((entity_type.value, match_key))
        if golden_id:
            golden = self._golden_records[golden_id]
        else:
            golden = GoldenRecord(entity_type=entity_type)
            self._golden_records[golden.golden_id] = golden
            self._match_index[(entity_type.value, match_key)] = golden.golden_id

        # Add the source record to the golden record.
        golden.source_record_ids.append(sr.record_id)
        golden.merge_count += 1
        golden.last_updated = datetime.now(timezone.utc).isoformat()

        # Apply survivorship rules for each attribute.
        rules = SURVIVORSHIP_RULES.get(entity_type.value, {})
        for attr_name, attr_value in attributes.items():
            strategy = rules.get(attr_name, "first_non_empty")
            # Collect all source values for this attribute.
            all_values = []
            for rid in golden.source_record_ids:
                src_rec = self._source_records.get(rid)
                if src_rec and attr_name in src_rec.attributes:
                    all_values.append({
                        "value": src_rec.attributes[attr_name],
                        "source_system": src_rec.source_system.value,
                        "source_record_id": rid,
                        "ingested_at": src_rec.ingested_at,
                    })

            # Check for conflicts (multiple distinct non-empty values).
            distinct_values = set(str(v["value"]) for v in all_values if v["value"] is not None and v["value"] != "")
            if len(distinct_values) > 1:
                # Record the conflict.
                conflict = DataConflict(
                    golden_id=golden.golden_id,
                    entity_type=entity_type,
                    attribute_name=attr_name,
                    conflicting_values=all_values,
                )
                self._conflicts[conflict.conflict_id] = conflict
                golden.quality_score = max(0.0, golden.quality_score - 0.1)

            # Apply survivorship.
            winner = apply_survivorship(strategy, all_values)
            if winner:
                golden.attributes[attr_name] = {
                    "value": winner["value"],
                    "source": winner["source_system"],
                    "confidence": 1.0 if len(distinct_values) <= 1 else 0.5,
                    "last_updated": datetime.now(timezone.utc).isoformat(),
                    "alternatives": [v for v in all_values if v["value"] != winner["value"]],
                }

        self._save()
        logger.info(
            "Ingested %s record from %s → golden_id=%s (merge_count=%d, quality=%.2f)",
            entity_type.value, source_system.value, golden.golden_id,
            golden.merge_count, golden.quality_score
        )
        return golden

    def get_golden(self, entity_type: EntityType, entity_id: str) -> Optional[GoldenRecord]:
        """Get the golden record for an entity."""
        golden_id = self._match_index.get((entity_type.value, entity_id))
        if not golden_id:
            return None
        return self._golden_records.get(golden_id)

    def list_golden(self, entity_type: EntityType) -> list[GoldenRecord]:
        """List all golden records of a type."""
        return [gr for gr in self._golden_records.values() if gr.entity_type == entity_type]

    def list_conflicts(self, status: ConflictStatus = ConflictStatus.UNRESOLVED) -> list[DataConflict]:
        """List data conflicts, optionally filtered by status."""
        return [c for c in self._conflicts.values() if c.status == status]

    def resolve_conflict(self, conflict_id: str, resolved_value: Any,
                         resolved_by: str, note: str = "") -> DataConflict:
        """Manually resolve a data conflict."""
        conflict = self._conflicts.get(conflict_id)
        if not conflict:
            raise ValueError(f"Conflict not found: {conflict_id}")
        conflict.status = ConflictStatus.RESOLVED
        conflict.resolved_value = resolved_value
        conflict.resolved_by = resolved_by
        conflict.resolved_at = datetime.now(timezone.utc).isoformat()
        conflict.resolution_note = note

        # Update the golden record with the resolved value.
        golden = self._golden_records.get(conflict.golden_id)
        if golden:
            golden.attributes[conflict.attribute_name] = {
                "value": resolved_value,
                "source": "manual_resolution",
                "confidence": 1.0,
                "last_updated": conflict.resolved_at,
                "alternatives": conflict.conflicting_values,
            }
            golden.quality_score = min(1.0, golden.quality_score + 0.1)

        self._save()
        logger.info("Conflict %s resolved by %s: %s", conflict_id, resolved_by, resolved_value)
        return conflict


# Singleton instance.
mdm_service = MDMService()

__all__ = [
    "MDMService",
    "mdm_service",
    "EntityType",
    "SourceSystem",
    "ConflictStatus",
    "SourceRecord",
    "GoldenRecord",
    "DataConflict",
    "SURVIVORSHIP_RULES",
    "apply_survivorship",
]
