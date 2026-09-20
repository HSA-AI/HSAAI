
from dataclasses import dataclass
from typing import Any

@dataclass
class SearchResult:
    document_id: str
    title: str
    score: float
    source: str
    snippet: str
    metadata: dict[str, Any]

class BM25Engine:
    def search(self, query: str, filters: dict | None = None):
        return [SearchResult('doc-hr-001','HR Policy Handbook',0.82,'bm25','...matching policy keyword evidence...',{'department':'HR','classification':'internal'})]

class VectorEngine:
    def search(self, query: str, filters: dict | None = None):
        return [SearchResult('doc-fin-014','Finance Delegation Matrix',0.88,'vector','...semantic match about approvals...',{'department':'Finance','classification':'confidential'})]

class Reranker:
    def rerank(self, query: str, results: list[SearchResult]):
        return sorted(results, key=lambda r: r.score, reverse=True)

class HybridSearchService:
    def __init__(self):
        self.bm25 = BM25Engine(); self.vector = VectorEngine(); self.reranker = Reranker()

    def search(self, query: str, filters: dict | None = None):
        bm25 = self.bm25.search(query, filters)
        vector = self.vector.search(query, filters)
        merged = {r.document_id: r for r in bm25 + vector}
        ranked = self.reranker.rerank(query, list(merged.values()))
        return {
            'query': query,
            'pipeline': ['bm25','vector','hybrid_merge','rerank'],
            'filters': filters or {},
            'results': [r.__dict__ for r in ranked],
            'analytics': {'bm25_hits': len(bm25), 'vector_hits': len(vector), 'final_hits': len(ranked)}
        }

service = HybridSearchService()
