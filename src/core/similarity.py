"""
用于软冲突检测的语义相似度工具。
"""

from __future__ import annotations

from collections import Counter
from typing import Dict, List
import math
import re

from loguru import logger
from pydantic import BaseModel


class SimilarityResult(BaseModel):
    text1: str
    text2: str
    similarity_score: float
    similarity_type: str
    explanation: str


class SimilarityCalculator:
    @staticmethod
    def _tokenize(text: str) -> List[str]:
        normalized = re.sub(r"\s+", " ", text.lower()).strip()
        ascii_tokens = re.findall(r"[a-z0-9_]+", normalized)
        cjk_chunks = re.findall(r"[\u4e00-\u9fff]+", normalized)
        cjk_tokens: List[str] = []
        # 中文按双字滑窗切分，兼顾短语匹配和实现复杂度。
        for chunk in cjk_chunks:
            if len(chunk) <= 2:
                cjk_tokens.append(chunk)
            else:
                cjk_tokens.extend(chunk[index : index + 2] for index in range(len(chunk) - 1))
        return ascii_tokens + cjk_tokens

    @staticmethod
    def jaccard_similarity(text1: str, text2: str) -> float:
        set1 = set(SimilarityCalculator._tokenize(text1))
        set2 = set(SimilarityCalculator._tokenize(text2))
        if not set1 and not set2:
            return 1.0
        if not set1 or not set2:
            return 0.0
        return len(set1 & set2) / len(set1 | set2)

    @staticmethod
    def cosine_similarity(text1: str, text2: str) -> float:
        counter1 = Counter(SimilarityCalculator._tokenize(text1))
        counter2 = Counter(SimilarityCalculator._tokenize(text2))
        vocabulary = set(counter1) | set(counter2)
        if not vocabulary:
            return 1.0
        dot_product = sum(counter1.get(term, 0) * counter2.get(term, 0) for term in vocabulary)
        norm1 = math.sqrt(sum(value * value for value in counter1.values()))
        norm2 = math.sqrt(sum(value * value for value in counter2.values()))
        if not norm1 or not norm2:
            return 0.0
        return dot_product / (norm1 * norm2)

    @staticmethod
    def levenshtein_similarity(text1: str, text2: str) -> float:
        distance = SimilarityCalculator._levenshtein_distance(text1.lower(), text2.lower())
        max_length = max(len(text1), len(text2))
        return 1.0 if max_length == 0 else 1.0 - distance / max_length

    @staticmethod
    def _levenshtein_distance(text1: str, text2: str) -> int:
        if len(text1) < len(text2):
            return SimilarityCalculator._levenshtein_distance(text2, text1)
        if len(text2) == 0:
            return len(text1)
        previous = list(range(len(text2) + 1))
        for index, char1 in enumerate(text1):
            current = [index + 1]
            for inner_index, char2 in enumerate(text2):
                insertions = previous[inner_index + 1] + 1
                deletions = current[inner_index] + 1
                substitutions = previous[inner_index] + (char1 != char2)
                current.append(min(insertions, deletions, substitutions))
            previous = current
        return previous[-1]

    @staticmethod
    def combined_similarity(text1: str, text2: str, weights: Dict[str, float] | None = None) -> float:
        weights = weights or {"jaccard": 0.3, "cosine": 0.4, "levenshtein": 0.3}
        return (
            SimilarityCalculator.jaccard_similarity(text1, text2) * weights["jaccard"]
            + SimilarityCalculator.cosine_similarity(text1, text2) * weights["cosine"]
            + SimilarityCalculator.levenshtein_similarity(text1, text2) * weights["levenshtein"]
        )


class SoftConflictDetector:
    def __init__(self, similarity_threshold: float = 0.68) -> None:
        self.similarity_threshold = similarity_threshold
        logger.info(f"软冲突检测器初始化完成，相似度阈值={similarity_threshold}")

    def detect_soft_conflicts(self, clauses: List[str]) -> List[Dict]:
        conflicts: List[Dict] = []
        for index in range(len(clauses)):
            for inner_index in range(index + 1, len(clauses)):
                clause1 = clauses[index]
                clause2 = clauses[inner_index]
                similarity = SimilarityCalculator.combined_similarity(clause1, clause2)
                if similarity < self.similarity_threshold:
                    continue
                if not self._is_potential_conflict(clause1, clause2):
                    continue
                conflicts.append(
                    {
                        "clause_1": clause1,
                        "clause_2": clause2,
                        "similarity": round(similarity, 4),
                        "conflict_type": "soft_mismatch",
                        "reason": self._explain_conflict(clause1, clause2),
                    }
                )
        return conflicts

    def _is_potential_conflict(self, clause1: str, clause2: str) -> bool:
        normalized1 = clause1.lower()
        normalized2 = clause2.lower()
        contradiction_pairs = [
            ("consent required", "no consent"),
            ("explicit consent", "implied consent"),
            ("do not share", "share"),
            ("never sell", "sell"),
            ("domestic only", "international transfer"),
            ("retain indefinitely", "delete after"),
            ("\u9700\u7ecf\u540c\u610f", "\u65e0\u9700\u540c\u610f"),
            ("\u660e\u793a\u540c\u610f", "\u9ed8\u8ba4\u540c\u610f"),
            ("\u4e0d\u5171\u4eab", "\u5171\u4eab"),
            ("\u4e0d\u4f1a\u51fa\u552e", "\u51fa\u552e"),
            ("\u4ec5\u5883\u5185", "\u5883\u5916"),
            ("\u6c38\u4e45\u4fdd\u5b58", "\u5220\u9664"),
        ]
        for left, right in contradiction_pairs:
            if (left in normalized1 and right in normalized2) or (left in normalized2 and right in normalized1):
                return True

        numbers1 = re.findall(r"\d+", normalized1)
        numbers2 = re.findall(r"\d+", normalized2)
        if numbers1 and numbers2 and numbers1 != numbers2:
            scope_terms = [
                "retention",
                "days",
                "months",
                "years",
                "delete",
                "storage",
                "\u4fdd\u5b58",
                "\u4fdd\u7559",
                "\u5220\u9664",
                "\u5929",
                "\u6708",
                "\u5e74",
            ]
            if any(term in normalized1 for term in scope_terms) and any(term in normalized2 for term in scope_terms):
                return True

        negations = [" no ", " not ", " never ", "cannot", "without ", "\u4e0d", "\u65e0", "\u672a"]
        return any(token in f" {normalized1} " for token in negations) != any(token in f" {normalized2} " for token in negations)

    def _explain_conflict(self, clause1: str, clause2: str) -> str:
        return "这两条条款语义接近，但在同意、共享、保存期限或传输要求上存在相反约束。"


_soft_conflict_detector: SoftConflictDetector | None = None


def get_soft_conflict_detector(threshold: float = 0.68) -> SoftConflictDetector:
    global _soft_conflict_detector
    if _soft_conflict_detector is None:
        _soft_conflict_detector = SoftConflictDetector(threshold)
    return _soft_conflict_detector


def calculate_similarity(text1: str, text2: str, method: str = "combined") -> float:
    if method == "jaccard":
        return SimilarityCalculator.jaccard_similarity(text1, text2)
    if method == "cosine":
        return SimilarityCalculator.cosine_similarity(text1, text2)
    if method == "levenshtein":
        return SimilarityCalculator.levenshtein_similarity(text1, text2)
    return SimilarityCalculator.combined_similarity(text1, text2)
