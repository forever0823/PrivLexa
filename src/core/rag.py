"""
Knowledge-graph-backed retrieval for multi-jurisdiction privacy analysis.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from loguru import logger
from pydantic import BaseModel, Field

try:
    from src.core.embedding_reranker import EmbeddingReranker
except ImportError:
    from .embedding_reranker import EmbeddingReranker

try:
    from src.core.knowledge_graph import get_regulation_knowledge_graph
except ImportError:
    from .knowledge_graph import get_regulation_knowledge_graph

try:
    from src.utils.utils import get_config
except ImportError:
    from ..utils.utils import get_config


def _parse_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


class Document(BaseModel):
    doc_id: str
    title: str
    content: str
    jurisdiction: str
    category: str
    tags: List[str] = Field(default_factory=list)
    concept_ids: List[str] = Field(default_factory=list)
    relevance_score: float = 0.0
    graph_score: float = 0.0
    graph_rank: Optional[int] = None
    semantic_score: Optional[float] = None
    semantic_rank: Optional[int] = None
    fusion_score: Optional[float] = None
    fusion_rank: Optional[int] = None
    law_name: Optional[str] = None
    article_reference: Optional[str] = None
    obligation_ids: List[str] = Field(default_factory=list)


class RetrievalResult(BaseModel):
    query: str
    documents: List[Document]
    total_count: int


class DocumentIndex:
    def __init__(self) -> None:
        self.graph = get_regulation_knowledge_graph()
        self.documents: List[Document] = []
        self._build_index()
        logger.info(f"Document index initialized with {len(self.documents)} graph-backed documents")

    def _build_index(self) -> None:
        self.documents = [
            Document(
                doc_id=clause.clause_id,
                title=f"{clause.law_name} {clause.article_reference} {clause.title}",
                content=f"{clause.summary}\n{clause.text}",
                jurisdiction=clause.jurisdiction,
                category=clause.category,
                tags=clause.tags,
                concept_ids=clause.concept_ids,
                graph_score=0.0,
                law_name=clause.law_name,
                article_reference=clause.article_reference,
                obligation_ids=clause.obligation_ids,
            )
            for clause in self.graph.iter_clauses()
        ]

    def retrieve(
        self,
        query: str,
        jurisdiction: Optional[str] = None,
        top_k: int = 5,
        concept_ids: Optional[List[str]] = None,
    ) -> RetrievalResult:
        matches = self.graph.search_clauses(
            query=query,
            jurisdiction=jurisdiction,
            top_k=top_k,
            concept_ids=concept_ids,
        )
        documents = [
            Document(
                doc_id=clause.clause_id,
                title=f"{clause.law_name} {clause.article_reference} {clause.title}",
                content=f"{clause.summary}\n{clause.text}",
                jurisdiction=clause.jurisdiction,
                category=clause.category,
                tags=clause.tags,
                concept_ids=clause.concept_ids,
                relevance_score=score,
                graph_score=score,
                law_name=clause.law_name,
                article_reference=clause.article_reference,
                obligation_ids=clause.obligation_ids,
            )
            for clause, score in matches
        ]
        return RetrievalResult(query=query, documents=documents, total_count=len(documents))

    def search_by_category(self, jurisdiction: str, category: str) -> List[Document]:
        result = self.graph.search_clauses(query="", jurisdiction=jurisdiction, top_k=20, categories=[category])
        return [
            Document(
                doc_id=clause.clause_id,
                title=f"{clause.law_name} {clause.article_reference} {clause.title}",
                content=f"{clause.summary}\n{clause.text}",
                jurisdiction=clause.jurisdiction,
                category=clause.category,
                tags=clause.tags,
                concept_ids=clause.concept_ids,
                relevance_score=score,
                graph_score=score,
                law_name=clause.law_name,
                article_reference=clause.article_reference,
                obligation_ids=clause.obligation_ids,
            )
            for clause, score in result
        ]


class RAGPipeline:
    def __init__(self) -> None:
        self.graph = get_regulation_knowledge_graph()
        self.index = DocumentIndex()
        self.settings = self._load_settings()
        self.reranker = EmbeddingReranker(
            enabled=self.settings["embedding_rerank_enabled"],
            rrf_k=self.settings["rrf_k"],
            min_candidates=self.settings["embedding_min_candidates"],
        )
        logger.info("RAG pipeline initialized with concept-aware retrieval and optional embedding rerank")

    def retrieve_for_generation(self, jurisdiction: str, topic: str, context: str) -> Dict[str, Any]:
        code = self.graph.normalize_jurisdiction(jurisdiction) or "CN"
        query = " ".join(part for part in [topic, context[:240] if context else ""] if part).strip()
        graph_result = self.graph.query_knowledge_graph(
            query=query,
            jurisdictions=[code],
            top_k=max(6, self.settings["graph_candidate_pool"] // 2),
        )
        matched_concepts = [item["concept_id"] for item in graph_result["matched_concepts"]]
        profile = self.graph.get_jurisdiction_profile(code)
        all_docs: Dict[str, Document] = {}
        for jurisdiction_result in graph_result["jurisdiction_results"]:
            for clause in jurisdiction_result.get("clauses", []):
                document = Document(
                    doc_id=clause["clause_id"],
                    title=f"{clause['law_name']} {clause['article_reference']} {clause['title']}",
                    content=f"{clause.get('summary', '')}\n{clause.get('text', '')}",
                    jurisdiction=clause["jurisdiction"],
                    category=clause["category"],
                    tags=clause.get("tags", []),
                    concept_ids=clause.get("concept_ids", []),
                    relevance_score=clause.get("score", 0.0),
                    graph_score=clause.get("score", 0.0),
                    law_name=clause.get("law_name"),
                    article_reference=clause.get("article_reference"),
                    obligation_ids=clause.get("obligation_ids", []),
                )
                all_docs[document.doc_id] = document
        for document in self.index.retrieve(
            query=query,
            jurisdiction=code,
            top_k=self.settings["graph_candidate_pool"],
            concept_ids=matched_concepts or None,
        ).documents:
            existing = all_docs.get(document.doc_id)
            if existing is None or document.graph_score > existing.graph_score:
                all_docs[document.doc_id] = document

        candidates = sorted(all_docs.values(), key=lambda item: item.graph_score, reverse=True)
        rerank_query = self._build_rerank_query(
            query=query,
            jurisdiction=code,
            matched_concepts=graph_result["matched_concepts"],
            profile=profile,
        )
        reranked_payloads, rerank_metadata = self.reranker.rerank_candidates(
            query=rerank_query,
            candidates=[document.model_dump() for document in candidates],
            top_k=self.settings["final_top_k"],
        )
        documents = [Document(**payload) for payload in reranked_payloads]
        retrieval_strategy = self._build_retrieval_strategy(rerank_metadata)
        return {
            "jurisdiction": code,
            "topic": topic,
            "relevant_documents": [doc.model_dump() for doc in documents],
            "document_count": len(documents),
            "context_summary": self._summarize_documents(documents, graph_result["summary_markdown"]),
            "knowledge_graph_stats": self.graph.get_stats().model_dump(),
            "jurisdiction_embedding": profile["jurisdiction_embedding"],
            "retrieval_strategy": retrieval_strategy,
            "matched_concepts": graph_result["matched_concepts"],
            "cross_jurisdiction_links": graph_result["cross_jurisdiction_links"],
            "summary_markdown": graph_result["summary_markdown"],
            "rerank_metadata": rerank_metadata,
        }

    def _summarize_documents(self, documents: List[Document], summary_markdown: str) -> str:
        if not documents:
            return summary_markdown or "未检索到相关法规条款。"

        lines = [summary_markdown.strip(), "", "优先参考的法规条款证据："]
        for document in documents[:6]:
            lines.append(f"- {document.title}: {document.content[:180]}...")
        return "\n".join(line for line in lines if line)

    def _build_rerank_query(
        self,
        *,
        query: str,
        jurisdiction: str,
        matched_concepts: List[Dict[str, Any]],
        profile: Dict[str, Any],
    ) -> str:
        concepts = ", ".join(
            item.get("label_zh") or item.get("label_en", "")
            for item in matched_concepts[:6]
            if item.get("label_zh") or item.get("label_en")
        )
        parts = [
            query,
            f"法域：{jurisdiction}",
            f"匹配概念：{concepts}" if concepts else "",
            f"内部生成策略：{profile.get('generation_style', '')}",
        ]
        return "\n".join(part for part in parts if part).strip()

    def _build_retrieval_strategy(self, rerank_metadata: Dict[str, Any]) -> str:
        base = "concept-filter + jurisdiction-aggregate"
        if rerank_metadata.get("enabled"):
            return (
                f"{base} + embedding-rerank[{rerank_metadata.get('backend', 'unknown')}]"
                f" + RRF(k={rerank_metadata.get('rrf_k', self.settings['rrf_k'])}) + summary"
            )
        return f"{base} + summary"

    def _load_settings(self) -> Dict[str, int | bool]:
        config = get_config() or {}
        retrieval = dict(config.get("retrieval") or {})
        graph_candidate_pool = int(
            os.getenv("RAG_GRAPH_CANDIDATE_POOL", retrieval.get("graph_candidate_pool", 18))
        )
        final_top_k = int(os.getenv("RAG_FINAL_TOP_K", retrieval.get("final_top_k", 8)))
        final_top_k = max(1, min(final_top_k, graph_candidate_pool))
        embedding_min_candidates = int(
            os.getenv("RAG_EMBEDDING_MIN_CANDIDATES", retrieval.get("embedding_min_candidates", 6))
        )
        return {
            "graph_candidate_pool": max(6, graph_candidate_pool),
            "final_top_k": final_top_k,
            "rrf_k": int(os.getenv("RAG_RRF_K", retrieval.get("rrf_k", 60))),
            "embedding_rerank_enabled": _parse_bool(
                os.getenv("RAG_EMBEDDING_ENABLED", retrieval.get("embedding_rerank_enabled")),
                default=False,
            ),
            "embedding_min_candidates": max(2, embedding_min_candidates),
        }


_rag_pipeline: Optional[RAGPipeline] = None


def get_rag_pipeline() -> RAGPipeline:
    global _rag_pipeline
    if _rag_pipeline is None:
        _rag_pipeline = RAGPipeline()
    return _rag_pipeline
