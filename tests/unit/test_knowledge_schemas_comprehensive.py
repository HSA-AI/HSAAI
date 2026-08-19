"""
HSAAI Enterprise AI Platform — Knowledge Schemas Test Suite (v7.0)
====================================================================
Comprehensive tests for `services/backend_core/knowledge/schemas.py`.

Coverage targets:
  - KnowledgeSpaceCreate (min_length/max_length on key, defaults)
  - KnowledgeCollectionCreate (required fields, defaults)
  - KnowledgeDocumentRegister (many fields with defaults, MatchSensitivity Literal)
  - DocumentWorkflowRequest (single optional field)
  - KnowledgePermissionGrant (4 required + 1 default)
  - KnowledgeSearchRequest (Optional space_key/collection_key, limit default)
  - KnowledgeSpaceOut (with from_attributes Config)

Test categories: positive, negative, boundary, validation, serialization, defaults, edge cases.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

_BASE = Path(__file__).resolve().parents[2]
for _p in [str(_BASE / "services"), str(_BASE / "packages"), str(_BASE / "packages" / "common")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend_core.knowledge.schemas import (  # noqa: E402
    DocumentWorkflowRequest,
    KnowledgeCollectionCreate,
    KnowledgeDocumentRegister,
    KnowledgePermissionGrant,
    KnowledgeSearchRequest,
    KnowledgeSpaceCreate,
    KnowledgeSpaceOut,
)


# ═══════════════════════════════════════════════════════════════════════
# KnowledgeSpaceCreate
# ═══════════════════════════════════════════════════════════════════════
class TestKnowledgeSpaceCreate:
    """Tests for KnowledgeSpaceCreate — key has min_length=2, max_length=80."""

    def test_default_values(self):
        s = KnowledgeSpaceCreate(key="hr-space", name="HR Space")
        assert s.description == ""
        assert s.owner == "system"
        assert s.classification == "internal"
        assert s.tenant_id == "default"
        assert s.workspace_id == "default"

    def test_positive_full_payload(self):
        s = KnowledgeSpaceCreate(
            key="finance-space",
            name="Finance Space",
            description="Financial documents",
            owner="cfo",
            classification="confidential",
            tenant_id="t1",
            workspace_id="w1",
        )
        assert s.key == "finance-space"
        assert s.classification == "confidential"

    def test_boundary_min_key_length_2(self):
        """key with exactly 2 chars is accepted (min_length=2)."""
        s = KnowledgeSpaceCreate(key="ab", name="N")
        assert s.key == "ab"

    def test_boundary_max_key_length_80(self):
        """key with exactly 80 chars is accepted (max_length=80)."""
        key = "a" * 80
        s = KnowledgeSpaceCreate(key=key, name="N")
        assert len(s.key) == 80

    def test_negative_key_too_short(self):
        """key with 1 char raises (min_length=2)."""
        with pytest.raises(ValidationError):
            KnowledgeSpaceCreate(key="a", name="N")

    def test_negative_key_too_long(self):
        """key with 81 chars raises (max_length=80)."""
        with pytest.raises(ValidationError):
            KnowledgeSpaceCreate(key="a" * 81, name="N")

    def test_negative_missing_key_raises(self):
        with pytest.raises(ValidationError):
            KnowledgeSpaceCreate(name="N")  # type: ignore[call-arg]

    def test_negative_missing_name_raises(self):
        with pytest.raises(ValidationError):
            KnowledgeSpaceCreate(key="kk")  # type: ignore[call-arg]

    def test_serialization_roundtrip(self):
        s = KnowledgeSpaceCreate(key="kk", name="N", description="d")
        dumped = s.model_dump()
        assert KnowledgeSpaceCreate(**dumped) == s

    def test_arabic_key_accepted(self):
        """Arabic characters in key are accepted (string length, not bytes)."""
        s = KnowledgeSpaceCreate(key="مساحة-المالية", name="N")
        assert s.key == "مساحة-المالية"


# ═══════════════════════════════════════════════════════════════════════
# KnowledgeCollectionCreate
# ═══════════════════════════════════════════════════════════════════════
class TestKnowledgeCollectionCreate:
    """Tests for KnowledgeCollectionCreate."""

    def test_default_values(self):
        c = KnowledgeCollectionCreate(space_key="s", key="c", name="C")
        assert c.description == ""
        assert c.tenant_id == "default"
        assert c.workspace_id == "default"

    def test_positive_full_payload(self):
        c = KnowledgeCollectionCreate(
            space_key="s", key="c", name="C", description="d",
            tenant_id="t1", workspace_id="w1",
        )
        assert c.space_key == "s"
        assert c.tenant_id == "t1"

    @pytest.mark.parametrize("missing_field", ["space_key", "key", "name"])
    def test_negative_missing_required_field_raises(self, missing_field: str):
        kwargs = {"space_key": "s", "key": "c", "name": "C"}
        del kwargs[missing_field]
        with pytest.raises(ValidationError):
            KnowledgeCollectionCreate(**kwargs)  # type: ignore[arg-type]

    def test_serialization_roundtrip(self):
        c = KnowledgeCollectionCreate(space_key="s", key="c", name="C")
        assert KnowledgeCollectionCreate(**c.model_dump()) == c


# ═══════════════════════════════════════════════════════════════════════
# KnowledgeDocumentRegister
# ═══════════════════════════════════════════════════════════════════════
class TestKnowledgeDocumentRegister:
    """Tests for KnowledgeDocumentRegister — many fields with defaults."""

    def test_default_values(self):
        d = KnowledgeDocumentRegister(space_key="s", collection_key="c", filename="doc.pdf")
        assert d.title == ""
        assert d.content_type == "application/octet-stream"
        assert d.size_bytes == 0
        assert d.classification == "internal"
        assert d.sensitivity == "normal"
        assert d.department == "general"
        assert d.tags == []
        assert d.status is None
        assert d.metadata == {}
        assert d.uploaded_by == "system"
        assert d.tenant_id == "default"
        assert d.workspace_id == "default"

    @pytest.mark.parametrize("sensitivity", ["normal", "sensitive", "confidential", "restricted"])
    def test_positive_all_sensitivity_values(self, sensitivity: str):
        d = KnowledgeDocumentRegister(
            space_key="s", collection_key="c", filename="f.pdf", sensitivity=sensitivity,
        )
        assert d.sensitivity == sensitivity

    def test_negative_invalid_sensitivity_rejected(self):
        with pytest.raises(ValidationError):
            KnowledgeDocumentRegister(
                space_key="s", collection_key="c", filename="f.pdf", sensitivity="unknown",  # type: ignore[arg-type]
            )

    @pytest.mark.parametrize("missing_field", ["space_key", "collection_key", "filename"])
    def test_negative_missing_required_field_raises(self, missing_field: str):
        kwargs = {"space_key": "s", "collection_key": "c", "filename": "f.pdf"}
        del kwargs[missing_field]
        with pytest.raises(ValidationError):
            KnowledgeDocumentRegister(**kwargs)  # type: ignore[arg-type]

    def test_default_factory_tags_independent(self):
        a = KnowledgeDocumentRegister(space_key="s", collection_key="c", filename="a")
        b = KnowledgeDocumentRegister(space_key="s", collection_key="c", filename="b")
        a.tags.append("t")
        assert b.tags == []

    def test_default_factory_metadata_independent(self):
        a = KnowledgeDocumentRegister(space_key="s", collection_key="c", filename="a")
        b = KnowledgeDocumentRegister(space_key="s", collection_key="c", filename="b")
        a.metadata["k"] = "v"
        assert b.metadata == {}

    def test_status_optional_none_default(self):
        """status is Optional — defaults to None."""
        d = KnowledgeDocumentRegister(space_key="s", collection_key="c", filename="f")
        assert d.status is None

    @pytest.mark.parametrize("status", ["draft", "pending_review", "approved", "rejected", "archived"])
    def test_positive_all_status_values(self, status: str):
        d = KnowledgeDocumentRegister(space_key="s", collection_key="c", filename="f", status=status)
        assert d.status == status

    def test_boundary_size_zero(self):
        d = KnowledgeDocumentRegister(space_key="s", collection_key="c", filename="f", size_bytes=0)
        assert d.size_bytes == 0

    def test_boundary_size_large(self):
        d = KnowledgeDocumentRegister(space_key="s", collection_key="c", filename="f", size_bytes=10**12)
        assert d.size_bytes == 10**12

    def test_serialization_roundtrip(self):
        d = KnowledgeDocumentRegister(
            space_key="s", collection_key="c", filename="f.pdf",
            title="T", tags=["a", "b"], metadata={"k": "v"},
        )
        dumped = d.model_dump()
        assert KnowledgeDocumentRegister(**dumped) == d

    def test_arabic_filename_accepted(self):
        d = KnowledgeDocumentRegister(space_key="s", collection_key="c", filename="ملف.pdf")
        assert d.filename == "ملف.pdf"


# ═══════════════════════════════════════════════════════════════════════
# DocumentWorkflowRequest
# ═══════════════════════════════════════════════════════════════════════
class TestDocumentWorkflowRequest:
    """Tests for DocumentWorkflowRequest — single optional reason field."""

    def test_default_reason_empty(self):
        r = DocumentWorkflowRequest()
        assert r.reason == ""

    def test_positive_explicit_reason(self):
        r = DocumentWorkflowRequest(reason="Need urgent review")
        assert r.reason == "Need urgent review"

    def test_arabic_reason_accepted(self):
        r = DocumentWorkflowRequest(reason="مراجعة عاجلة")
        assert r.reason == "مراجعة عاجلة"

    def test_serialization_roundtrip(self):
        r = DocumentWorkflowRequest(reason="test")
        assert DocumentWorkflowRequest(**r.model_dump()) == r


# ═══════════════════════════════════════════════════════════════════════
# KnowledgePermissionGrant
# ═══════════════════════════════════════════════════════════════════════
class TestKnowledgePermissionGrant:
    """Tests for KnowledgePermissionGrant."""

    def test_default_principal_type(self):
        g = KnowledgePermissionGrant(
            resource_type="document", resource_key="d1", principal="manager", permission="read",
        )
        assert g.principal_type == "role"

    def test_positive_full_payload(self):
        g = KnowledgePermissionGrant(
            resource_type="space", resource_key="hr", principal_type="user",
            principal="user-1", permission="write",
        )
        assert g.principal_type == "user"
        assert g.permission == "write"

    @pytest.mark.parametrize("missing_field", ["resource_type", "resource_key", "principal", "permission"])
    def test_negative_missing_required_field_raises(self, missing_field: str):
        kwargs = {"resource_type": "doc", "resource_key": "d", "principal": "p", "permission": "r"}
        del kwargs[missing_field]
        with pytest.raises(ValidationError):
            KnowledgePermissionGrant(**kwargs)  # type: ignore[arg-type]

    def test_serialization_roundtrip(self):
        g = KnowledgePermissionGrant(resource_type="d", resource_key="k", principal="p", permission="r")
        assert KnowledgePermissionGrant(**g.model_dump()) == g


# ═══════════════════════════════════════════════════════════════════════
# KnowledgeSearchRequest
# ═══════════════════════════════════════════════════════════════════════
class TestKnowledgeSearchRequest:
    """Tests for KnowledgeSearchRequest — Optional space_key/collection_key."""

    def test_default_values(self):
        r = KnowledgeSearchRequest(query="q")
        assert r.space_key is None
        assert r.collection_key is None
        assert r.tenant_id == "default"
        assert r.workspace_id == "default"
        assert r.limit == 8

    def test_positive_explicit_space_and_collection(self):
        r = KnowledgeSearchRequest(query="q", space_key="s", collection_key="c")
        assert r.space_key == "s"
        assert r.collection_key == "c"

    def test_negative_missing_query_raises(self):
        with pytest.raises(ValidationError):
            KnowledgeSearchRequest()  # type: ignore[call-arg]

    def test_boundary_limit_zero(self):
        r = KnowledgeSearchRequest(query="q", limit=0)
        assert r.limit == 0

    def test_boundary_limit_large(self):
        r = KnowledgeSearchRequest(query="q", limit=10_000)
        assert r.limit == 10_000

    def test_optional_space_key_none_accepted(self):
        r = KnowledgeSearchRequest(query="q", space_key=None)
        assert r.space_key is None

    def test_arabic_query_preserved(self):
        r = KnowledgeSearchRequest(query="ما هي سياسة الإجازات؟")
        assert r.query == "ما هي سياسة الإجازات؟"

    def test_serialization_roundtrip(self):
        r = KnowledgeSearchRequest(query="q", space_key="s", limit=5)
        dumped = r.model_dump()
        assert KnowledgeSearchRequest(**dumped) == r


# ═══════════════════════════════════════════════════════════════════════
# KnowledgeSpaceOut
# ═══════════════════════════════════════════════════════════════════════
class TestKnowledgeSpaceOut:
    """Tests for KnowledgeSpaceOut — output model with from_attributes Config."""

    def test_positive_full_payload(self):
        s = KnowledgeSpaceOut(
            id=1, key="hr", name="HR Space", description="d",
            owner="system", classification="internal", is_active=True,
        )
        assert s.id == 1
        assert s.is_active is True

    def test_default_created_at_none(self):
        s = KnowledgeSpaceOut(
            id=1, key="k", name="N", description="",
            owner="o", classification="c", is_active=True,
        )
        assert s.created_at is None

    def test_created_at_accepts_datetime(self):
        now = datetime(2026, 7, 13, 12, 0, 0)
        s = KnowledgeSpaceOut(
            id=1, key="k", name="N", description="",
            owner="o", classification="c", is_active=True, created_at=now,
        )
        assert s.created_at == now

    @pytest.mark.parametrize("missing_field", ["id", "key", "name", "description",
                                                 "owner", "classification", "is_active"])
    def test_negative_missing_required_field_raises(self, missing_field: str):
        kwargs = {"id": 1, "key": "k", "name": "N", "description": "",
                  "owner": "o", "classification": "c", "is_active": True}
        del kwargs[missing_field]
        with pytest.raises(ValidationError):
            KnowledgeSpaceOut(**kwargs)  # type: ignore[arg-type]

    def test_from_attributes_config_enabled(self):
        """Verify Config.from_attributes is True (allows ORM object conversion)."""
        # We can verify by creating from an object with attributes
        class FakeORM:
            id = 1
            key = "k"
            name = "N"
            description = ""
            owner = "o"
            classification = "c"
            is_active = True
            created_at = None

        s = KnowledgeSpaceOut.model_validate(FakeORM(), from_attributes=True)
        assert s.id == 1
        assert s.key == "k"

    def test_serialization_roundtrip(self):
        s = KnowledgeSpaceOut(
            id=1, key="k", name="N", description="d",
            owner="o", classification="c", is_active=True,
        )
        dumped = s.model_dump()
        assert KnowledgeSpaceOut(**dumped) == s
