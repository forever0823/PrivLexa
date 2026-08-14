"""
Lightweight embedding reranker for graph-backed retrieval.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from loguru import logger

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - dependency is present in production requirements
    OpenAI = None

try:
    from src.utils.utils import get_config
except ImportError:
    from ..utils.utils import get_config


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE_PATH = PROJECT_ROOT / "output" / "normalized" / "embedding_cache.json"


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


def _normalize_text(value: str) -> str:
    return " ".join((value or "").split())


def _hash_text(value: str) -> str:
    return hashlib.sha256(_normalize_text(value).encode("utf-8")).hexdigest()


def _cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot_product = sum(float(a) * float(b) for a, b in zip(left, right))
    left_norm = math.sqrt(sum(float(a) * float(a) for a in left))
    right_norm = math.sqrt(sum(float(b) * float(b) for b in right))
    if not left_norm or not right_norm:
        return 0.0
    return dot_product / (left_norm * right_norm)


def reciprocal_rank_fusion(rankings: Sequence[Sequence[str]], k: int = 60) -> Dict[str, float]:
    scores: Dict[str, float] = {}
    for ranking in rankings:
        for index, doc_id in enumerate(ranking, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / float(k + index)
    return scores


class _SentenceTransformerBackend:
    def __init__(self, model_name: str) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("sentence-transformers is not installed") from exc
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)

    def embed_texts(self, texts: Sequence[str]) -> List[List[float]]:
        vectors = self.model.encode(list(texts), normalize_embeddings=True)
        return [list(map(float, vector)) for vector in vectors]


class _OpenAIEmbeddingBackend:
    def __init__(
        self,
        api_key: str,
        model_name: str,
        base_url: Optional[str] = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        if OpenAI is None:  # pragma: no cover - dependency is present in production requirements
            raise RuntimeError("openai package is not installed")
        self.model_name = model_name
        self.client = OpenAI(api_key=api_key, base_url=base_url or None, timeout=timeout_seconds)

    def embed_texts(self, texts: Sequence[str]) -> List[List[float]]:
        response = self.client.embeddings.create(
            model=self.model_name,
            input=list(texts),
            encoding_format="float",
        )
        return [list(map(float, item.embedding)) for item in response.data]


class EmbeddingReranker:
    def __init__(
        self,
        *,
        enabled: Optional[bool] = None,
        backend: Optional[Any] = None,
        backend_name: Optional[str] = None,
        model_name: Optional[str] = None,
        batch_size: Optional[int] = None,
        min_candidates: Optional[int] = None,
        rrf_k: Optional[int] = None,
        cache_path: Optional[Path] = None,
    ) -> None:
        settings = self._load_settings()
        self.enabled = settings["enabled"] if enabled is None else enabled
        self.batch_size = int(batch_size or settings["batch_size"])
        self.min_candidates = int(min_candidates or settings["min_candidates"])
        self.rrf_k = int(rrf_k or settings["rrf_k"])
        self.cache_path = Path(cache_path or settings["cache_path"])
        self._cache_lock = threading.Lock()
        self._cache_loaded = False
        self._cache: Dict[str, List[float]] = {}
        self._backend_name = backend_name or settings["backend_name"]
        self._model_name = model_name or settings["model_name"]
        self._backend = backend
        if self.enabled and self._backend is None:
            self._backend, resolved_name = self._build_backend(settings)
            self._backend_name = resolved_name
            if self._backend is None:
                self.enabled = False
                logger.info("Embedding reranker is configured but no usable backend was found; graph-only ranking will be used")

    @property
    def backend_name(self) -> str:
        return self._backend_name

    @property
    def model_name(self) -> str:
        return self._model_name

    def rerank_candidates(
        self,
        query: str,
        candidates: Sequence[Dict[str, Any]],
        *,
        top_k: int,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        ordered = [dict(item) for item in candidates]
        for index, item in enumerate(ordered, start=1):
            item["graph_rank"] = index
            item["graph_score"] = float(item.get("graph_score", item.get("relevance_score", 0.0) or 0.0))
            item["fusion_rank"] = index
            item["fusion_score"] = item["graph_score"]
            item["relevance_score"] = item["fusion_score"]

        if not self.enabled or self._backend is None or len(ordered) < self.min_candidates:
            return ordered[:top_k], {
                "enabled": False,
                "backend": self.backend_name,
                "reason": "disabled_or_not_enough_candidates",
            }

        try:
            semantic_query = _normalize_text(query)
            query_embedding = self._backend.embed_texts([semantic_query])[0]
            document_embeddings = self._get_document_embeddings(ordered)
            semantic_scores = {
                item["doc_id"]: _cosine_similarity(query_embedding, document_embeddings[item["doc_id"]])
                for item in ordered
                if item["doc_id"] in document_embeddings
            }
            semantic_ranking = [
                item["doc_id"]
                for item in sorted(
                    ordered,
                    key=lambda row: (semantic_scores.get(row["doc_id"], -1.0), -row["graph_rank"]),
                    reverse=True,
                )
            ]
            graph_ranking = [item["doc_id"] for item in ordered]
            fusion_scores = reciprocal_rank_fusion([graph_ranking, semantic_ranking], k=self.rrf_k)

            for item in ordered:
                item["semantic_score"] = round(semantic_scores.get(item["doc_id"], 0.0), 6)
                item["semantic_rank"] = semantic_ranking.index(item["doc_id"]) + 1
                item["fusion_score"] = round(fusion_scores.get(item["doc_id"], 0.0), 6)
                item["relevance_score"] = item["fusion_score"]

            ordered.sort(
                key=lambda row: (
                    row.get("fusion_score", 0.0),
                    row.get("semantic_score", 0.0),
                    row.get("graph_score", 0.0),
                ),
                reverse=True,
            )
            for index, item in enumerate(ordered, start=1):
                item["fusion_rank"] = index

            return ordered[:top_k], {
                "enabled": True,
                "backend": self.backend_name,
                "model": self.model_name,
                "rrf_k": self.rrf_k,
                "candidate_count": len(candidates),
            }
        except Exception as exc:
            logger.warning(f"Embedding rerank failed; falling back to graph ranking only: {exc}")
            return ordered[:top_k], {
                "enabled": False,
                "backend": self.backend_name,
                "reason": f"runtime_error:{type(exc).__name__}",
            }

    def _load_settings(self) -> Dict[str, Any]:
        config = get_config() or {}
        retrieval = dict(config.get("retrieval") or {})
        embedding_enabled = _parse_bool(
            os.getenv("RAG_EMBEDDING_ENABLED", retrieval.get("embedding_rerank_enabled")),
            default=False,
        )
        backend_name = str(
            os.getenv("RAG_EMBEDDING_BACKEND", retrieval.get("embedding_backend", "auto"))
        ).strip().lower()
        model_name = str(
            os.getenv("RAG_EMBEDDING_MODEL", retrieval.get("embedding_model", "text-embedding-3-small"))
        ).strip()
        base_url = os.getenv("RAG_EMBEDDING_BASE_URL", retrieval.get("embedding_base_url", "")) or None
        api_key = (
            os.getenv("RAG_EMBEDDING_API_KEY")
            or os.getenv("OPENAI_API_KEY")
            or retrieval.get("embedding_api_key")
            or None
        )
        timeout_seconds = float(
            os.getenv("RAG_EMBEDDING_TIMEOUT_SECONDS", retrieval.get("embedding_timeout_seconds", 30.0))
        )
        batch_size = int(os.getenv("RAG_EMBEDDING_BATCH_SIZE", retrieval.get("embedding_batch_size", 16)))
        min_candidates = int(
            os.getenv("RAG_EMBEDDING_MIN_CANDIDATES", retrieval.get("embedding_min_candidates", 6))
        )
        rrf_k = int(os.getenv("RAG_RRF_K", retrieval.get("rrf_k", 60)))
        cache_path = Path(
            os.getenv(
                "RAG_EMBEDDING_CACHE_PATH",
                retrieval.get("embedding_cache_path", str(DEFAULT_CACHE_PATH)),
            )
        )
        return {
            "enabled": embedding_enabled,
            "backend_name": backend_name,
            "model_name": model_name,
            "base_url": base_url,
            "api_key": api_key,
            "timeout_seconds": timeout_seconds,
            "batch_size": batch_size,
            "min_candidates": min_candidates,
            "rrf_k": rrf_k,
            "cache_path": cache_path,
        }

    def _build_backend(self, settings: Dict[str, Any]) -> Tuple[Optional[Any], str]:
        backend_name = settings["backend_name"]
        model_name = settings["model_name"]
        if backend_name in {"auto", "sentence-transformers", "sentence_transformers", "local"}:
            try:
                backend = _SentenceTransformerBackend(model_name)
                return backend, "sentence-transformers"
            except Exception as exc:
                if backend_name != "auto":
                    logger.warning(f"Local embedding backend is unavailable: {exc}")
                else:
                    logger.debug(f"Skipping local embedding backend: {exc}")
        if backend_name in {"auto", "openai", "api"}:
            api_key = settings.get("api_key")
            if api_key:
                try:
                    backend = _OpenAIEmbeddingBackend(
                        api_key=api_key,
                        model_name=model_name,
                        base_url=settings.get("base_url"),
                        timeout_seconds=settings.get("timeout_seconds", 30.0),
                    )
                    return backend, "openai"
                except Exception as exc:
                    logger.warning(f"OpenAI-compatible embedding backend is unavailable: {exc}")
            elif backend_name != "auto":
                logger.warning("OpenAI-compatible embedding backend requires RAG_EMBEDDING_API_KEY or OPENAI_API_KEY")
        return None, backend_name

    def _get_document_embeddings(self, candidates: Sequence[Dict[str, Any]]) -> Dict[str, List[float]]:
        self._ensure_cache_loaded()
        embeddings: Dict[str, List[float]] = {}
        missing: List[Tuple[str, str, str]] = []
        for item in candidates:
            doc_id = str(item["doc_id"])
            payload = self._build_embedding_payload(item)
            cache_key = self._build_cache_key(doc_id, payload)
            vector = self._cache.get(cache_key)
            if vector is not None:
                embeddings[doc_id] = vector
            else:
                missing.append((doc_id, payload, cache_key))

        if missing:
            new_vectors = self._embed_missing_payloads(missing)
            embeddings.update(new_vectors)
        return embeddings

    def _build_embedding_payload(self, item: Dict[str, Any]) -> str:
        content = _normalize_text(str(item.get("content", "")))
        title = _normalize_text(str(item.get("title", "")))
        tags = ", ".join(item.get("tags") or [])
        concepts = ", ".join(item.get("concept_ids") or [])
        payload = "\n".join(
            part
            for part in [
                title,
                content[:3000],
                f"tags: {tags}" if tags else "",
                f"concepts: {concepts}" if concepts else "",
            ]
            if part
        )
        return payload

    def _build_cache_key(self, doc_id: str, payload: str) -> str:
        return f"{self.backend_name}:{self.model_name}:{doc_id}:{_hash_text(payload)}"

    def _embed_missing_payloads(self, missing: Sequence[Tuple[str, str, str]]) -> Dict[str, List[float]]:
        created: Dict[str, List[float]] = {}
        for index in range(0, len(missing), self.batch_size):
            batch = list(missing[index : index + self.batch_size])
            batch_payloads = [payload for _, payload, _ in batch]
            vectors = self._backend.embed_texts(batch_payloads)
            if len(vectors) != len(batch):
                raise RuntimeError("Embedding backend returned a mismatched vector count")
            with self._cache_lock:
                for (doc_id, _, cache_key), vector in zip(batch, vectors):
                    self._cache[cache_key] = vector
                    created[doc_id] = vector
                self._persist_cache()
        return created

    def _ensure_cache_loaded(self) -> None:
        with self._cache_lock:
            if self._cache_loaded:
                return
            if self.cache_path.exists():
                try:
                    raw = json.loads(self.cache_path.read_text(encoding="utf-8"))
                    if isinstance(raw, dict):
                        self._cache = {
                            str(key): [float(value) for value in vector]
                            for key, vector in raw.items()
                            if isinstance(vector, list)
                        }
                except Exception as exc:
                    logger.warning(f"Failed to load embedding cache; rebuilding cache lazily: {exc}")
                    self._cache = {}
            self._cache_loaded = True

    def _persist_cache(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(
            json.dumps(self._cache, ensure_ascii=False),
            encoding="utf-8",
        )
