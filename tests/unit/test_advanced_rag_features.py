import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services"))

from rag_engine.chunking import chunk_text_advanced, normalize_for_search, tokenize
from rag_engine.reranker import bm25_scores, rerank


def test_arabic_normalization_handles_common_forms():
    assert normalize_for_search("إدارةُ الموارد البشرية") == "اداره الموارد البشريه"
    assert "الموارد" in tokenize("المَوارد")


def test_advanced_chunking_keeps_offsets():
    text = "عنوان:\n" + "هذه جملة عربية مهمة. " * 80
    chunks = chunk_text_advanced(text, size=260, overlap=40)
    assert len(chunks) > 1
    assert chunks[0].start_char >= 0
    assert chunks[0].end_char > chunks[0].start_char


def test_hybrid_reranker_promotes_lexical_match():
    hits = [
        {"score": 0.9, "text": "general policy unrelated", "filename": "a.txt"},
        {"score": 0.2, "text": "سياسة الموارد البشرية والاجازات", "filename": "b.txt"},
    ]
    ranked = rerank("الموارد البشرية", hits)
    assert ranked[0]["filename"] == "b.txt"
    assert bm25_scores("الموارد البشرية", [h["text"] for h in hits])[1] > 0
