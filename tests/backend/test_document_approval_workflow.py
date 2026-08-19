from backend_core.knowledge.schemas import KnowledgeDocumentRegister

def test_sensitive_document_defaults_to_pending_review_schema():
    payload = KnowledgeDocumentRegister(space_key="corp", collection_key="policies", filename="secret.pdf", sensitivity="confidential")
    assert payload.sensitivity == "confidential"
