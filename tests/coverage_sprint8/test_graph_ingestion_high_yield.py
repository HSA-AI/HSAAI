import importlib.util
import re
import sys
import types
from pathlib import Path
from types import SimpleNamespace


_MODULE = "_hsaai_graph_ingestion_test"


def _slugify(value):
    text = str(value).strip().lower()
    text = re.sub(r"[^\w\u0600-\u06ff]+", "-", text)
    return text.strip("-") or "item"


def _m():
    existing = sys.modules.get(_MODULE)
    if existing is not None:
        return existing

    repo_root = Path(__file__).resolve().parents[2]
    source = (
        repo_root
        / "services"
        / "backend_core"
        / "knowledge_graph"
        / "graph_ingestion.py"
    )

    names = [
        "backend_core",
        "backend_core.knowledge_graph",
        "backend_core.knowledge_graph.graph_repository",
    ]
    old = {
        name: sys.modules.get(name)
        for name in names
    }

    try:
        backend = types.ModuleType("backend_core")
        backend.__path__ = []

        kg = types.ModuleType(
            "backend_core.knowledge_graph"
        )
        kg.__path__ = []

        graph_repo = types.ModuleType(
            "backend_core.knowledge_graph.graph_repository"
        )

        class GraphRepository:
            pass

        graph_repo.GraphRepository = GraphRepository
        graph_repo.slugify = _slugify

        sys.modules["backend_core"] = backend
        sys.modules[
            "backend_core.knowledge_graph"
        ] = kg
        sys.modules[
            "backend_core.knowledge_graph.graph_repository"
        ] = graph_repo

        spec = importlib.util.spec_from_file_location(
            _MODULE,
            source,
        )
        if spec is None or spec.loader is None:
            raise RuntimeError(
                f"Cannot load {source}"
            )

        module = importlib.util.module_from_spec(spec)
        sys.modules[_MODULE] = module
        spec.loader.exec_module(module)

        return module

    finally:
        for name, previous in old.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous


class FakeRepo:
    def __init__(self):
        self.entities = []
        self.maps = []
        self.relationships = []
        self.ingestions = []
        self.audits = []

    def upsert_entity(
        self,
        entity,
        *,
        actor,
        tenant_id,
        workspace_id,
    ):
        self.entities.append(
            (
                dict(entity),
                actor,
                tenant_id,
                workspace_id,
            )
        )
        return SimpleNamespace(
            entity_key=entity["entity_key"]
        )

    def record_document_map(
        self,
        document_id,
        title,
        entity_key,
        citation,
        chunk_ref,
        tenant_id,
        workspace_id,
    ):
        self.maps.append(
            (
                document_id,
                title,
                entity_key,
                citation,
                chunk_ref,
                tenant_id,
                workspace_id,
            )
        )

    def add_relationship(
        self,
        relationship,
        *,
        actor,
        tenant_id,
        workspace_id,
    ):
        self.relationships.append(
            (
                dict(relationship),
                actor,
                tenant_id,
                workspace_id,
            )
        )

    def record_ingestion(
        self,
        document_id,
        entities_count,
        relationships_count,
        tenant_id,
        workspace_id,
    ):
        self.ingestions.append(
            (
                document_id,
                entities_count,
                relationships_count,
                tenant_id,
                workspace_id,
            )
        )
        return SimpleNamespace(
            run_key="run-unit-1"
        )

    def audit(
        self,
        action,
        actor,
        resource_type,
        resource_id,
        *,
        detail,
        tenant_id,
        workspace_id,
    ):
        self.audits.append(
            (
                action,
                actor,
                resource_type,
                resource_id,
                detail,
                tenant_id,
                workspace_id,
            )
        )


def test_infer_type_known_and_default():
    m = _m()

    assert m.infer_type("Security Policy") == "Policy"
    assert m.infer_type("major risk") == "Risk"
    assert m.infer_type("SAP ERP") == "System"
    assert m.infer_type("Sales Department") == "Department"
    assert m.infer_type("Ordinary Thing") == "Document"


def test_extract_candidate_entities_title_text_and_dedup():
    m = _m()

    rows = m.extract_candidate_entities(
        "SecurityPolicy SAP Department "
        "SecurityPolicy سياسة المخاطر",
        title="Enterprise Governance",
    )

    assert rows

    keys = {
        row["entity_key"]
        for row in rows
    }

    assert (
        "document:enterprise-governance"
        in keys
    )

    assert any(
        row["name"] == "SAP"
        for row in rows
    )

    assert all(
        row["entity_type"]
        for row in rows
    )


def test_ingest_document_full_path():
    m = _m()
    repo = FakeRepo()

    title = "Risk Policy"

    doc_key = (
        "document:"
        + m.slugify(title)
    )

    payload = {
        "document_id": "doc-123",
        "title": title,
        "classification": "confidential",
        "permissions": ["auditor"],
        "entities": [
            {
                "entity_key": doc_key,
                "name": title,
                "entity_type": "Document",
            },
            {
                "entity_key": "policy:security",
                "name": "Security Policy",
                "entity_type": "Policy",
                "citation": "page 2",
                "chunk_ref": "chunk-7",
            },
        ],
        "relationships": [
            {
                "source_key": "policy:security",
                "target_key": "system:sap",
                "relationship_type": "USES",
            }
        ],
    }

    result = m.ingest_document(
        repo,
        payload,
        actor="user-1",
        tenant_id="tenant-1",
        workspace_id="workspace-1",
    )

    assert result["status"] == "completed"
    assert result["run_key"] == "run-unit-1"
    assert result["document_id"] == "doc-123"
    assert result["entities_count"] == 2

    # One generated MENTIONS relation +
    # one explicitly supplied relationship.
    assert result["relationships_count"] == 2

    assert len(repo.entities) == 2
    assert len(repo.maps) == 2
    assert len(repo.relationships) == 2
    assert len(repo.ingestions) == 1
    assert len(repo.audits) == 1

    policy = repo.entities[1][0]

    assert policy["classification"] == "confidential"
    assert policy["permissions"] == ["auditor"]
    assert policy["source_ref"] == "doc-123"

    explicit_rel = repo.relationships[-1][0]
    assert explicit_rel["source_ref"] == "doc-123"


def test_ingest_document_uses_extraction_defaults(
    monkeypatch,
):
    m = _m()
    repo = FakeRepo()

    monkeypatch.setattr(
        m,
        "extract_candidate_entities",
        lambda text, title="": [
            {
                "entity_key": "risk:one",
                "name": "Risk One",
                "entity_type": "Risk",
            }
        ],
    )

    result = m.ingest_document(
        repo,
        {
            "id": "doc-fallback",
            "filename": "Fallback.pdf",
            "content": "text",
        },
        actor="system",
        tenant_id="t",
        workspace_id="w",
    )

    assert result["entities_count"] == 1
    assert result["relationships_count"] == 1

    saved = repo.entities[0][0]
    assert saved["classification"] == "internal"
    assert saved["permissions"] == []
    assert saved["source_ref"] == "doc-fallback"
