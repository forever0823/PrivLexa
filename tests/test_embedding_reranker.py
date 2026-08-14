from __future__ import annotations

import sys
from pathlib import Path

if str(Path(__file__).resolve().parents[1]) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.embedding_reranker import EmbeddingReranker


class FakeBackend:
    def __init__(self, vectors):
        self.vectors = vectors

    def embed_texts(self, texts):
        return [self.vectors[text] for text in texts]


class BrokenBackend:
    def embed_texts(self, texts):
        raise RuntimeError("backend offline")


def build_candidate(doc_id: str, graph_score: float) -> dict[str, object]:
    return {
        "doc_id": doc_id,
        "title": doc_id,
        "content": "",
        "graph_score": graph_score,
        "relevance_score": graph_score,
    }


def build_reranker(
    tmp_path: Path,
    *,
    enabled: bool,
    backend,
    min_candidates: int = 1,
) -> EmbeddingReranker:
    return EmbeddingReranker(
        enabled=enabled,
        backend=backend,
        backend_name="fake",
        model_name="fake-model",
        min_candidates=min_candidates,
        rrf_k=60,
        cache_path=tmp_path / "embedding_cache.json",
    )


def test_rrf_fusion_promotes_consensus_candidate(tmp_path: Path):
    """RRF 融合会把图排序和语义排序共同支持的候选项提升到前面"""
    backend = FakeBackend(
        {
            "query": [1.0, 0.0],
            "A": [0.1, 0.9],
            "B": [1.0, 0.0],
            "C": [0.7, 0.3],
        }
    )
    reranker = build_reranker(tmp_path, enabled=True, backend=backend, min_candidates=1)
    candidates = [
        build_candidate("A", 0.95),
        build_candidate("B", 0.80),
        build_candidate("C", 0.70),
    ]

    ranked, metadata = reranker.rerank_candidates("query", candidates, top_k=3)

    assert metadata["enabled"] is True
    assert metadata["candidate_count"] == 3
    assert [item["doc_id"] for item in ranked] == ["B", "A", "C"]
    assert ranked[0]["semantic_rank"] == 1
    assert ranked[0]["fusion_rank"] == 1


def test_disabled_reranker_returns_graph_order(tmp_path: Path):
    """禁用重排时会保留原始图排序结果"""
    reranker = build_reranker(tmp_path, enabled=False, backend=None)
    candidates = [
        build_candidate("A", 0.95),
        build_candidate("B", 0.80),
    ]

    ranked, metadata = reranker.rerank_candidates("query", candidates, top_k=2)

    assert metadata["enabled"] is False
    assert metadata["reason"] == "disabled_or_not_enough_candidates"
    assert [item["doc_id"] for item in ranked] == ["A", "B"]
    assert ranked[0]["fusion_rank"] == 1
    assert ranked[1]["fusion_rank"] == 2


def test_reranker_falls_back_to_graph_order_when_backend_errors(tmp_path: Path):
    """嵌入后端报错时会回退到图排序结果"""
    reranker = build_reranker(tmp_path, enabled=True, backend=BrokenBackend(), min_candidates=1)
    candidates = [
        build_candidate("A", 0.95),
        build_candidate("B", 0.80),
    ]

    ranked, metadata = reranker.rerank_candidates("query", candidates, top_k=2)

    assert metadata["enabled"] is False
    assert metadata["reason"] == "runtime_error:RuntimeError"
    assert [item["doc_id"] for item in ranked] == ["A", "B"]
    assert [item["fusion_rank"] for item in ranked] == [1, 2]
