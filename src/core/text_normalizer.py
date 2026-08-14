"""
Utilities for normalizing uploaded policy text and repairing common mojibake.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Callable, List, Optional, Sequence, Tuple


SUSPICIOUS_TOKEN_WEIGHTS: Tuple[Tuple[str, int], ...] = (
    ("\ufffd", 12),
    ("\u951f", 10),
    ("\u9286", 8),
    ("\u951b", 8),
    ("\u9225", 8),
    ("\u20ac", 8),
    ("\u9369\u70d8\u6e70", 8),
    ("\u95c5\u612e\ue746", 8),
    ("\u93c0\u8de8\u74e5", 8),
    ("\u935a\u5823\ue749", 8),
    ("\u59ab\u20ac\u5a34", 8),
    ("\u93c9\u2103\ue0d9", 8),
    ("\u9350\u832c\u734a", 8),
    ("\u6dc7\u6fc6\u74e8", 8),
    ("\u93c1\u7248\u5d41", 8),
    ("\u7ed7\ue0ff\u7b01\u93c2", 8),
    ("\u74ba\u3125\ue568", 8),
    ("\u93c9\u51a8\u57c4", 8),
)

NORMAL_PUNCTUATION = (
    ",.!?;:()[]{}<>\"'/-_"
    "\u3002\uff0c\uff01\uff1f\uff1b\uff1a\u3001"
    "\u201c\u201d\u2018\u2019\uff08\uff09\u300a\u300b\u3010\u3011"
)


@dataclass
class TextNormalizationResult:
    text: str
    applied_fixes: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    encoding_hint: Optional[str] = None

    @property
    def modified(self) -> bool:
        return bool(self.applied_fixes)


def _basic_cleanup(text: str) -> str:
    cleaned = (text or "").replace("\ufeff", "").replace("\u00a0", " ")
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _suspicious_score(text: str) -> int:
    if not text:
        return 0
    return sum(text.count(token) * weight for token, weight in SUSPICIOUS_TOKEN_WEIGHTS)


def _quality_score(text: str) -> int:
    compact = re.sub(r"\s+", "", text or "")
    if not compact:
        return -10_000

    cjk_count = sum(1 for char in compact if "\u4e00" <= char <= "\u9fff")
    ascii_count = sum(1 for char in compact if char.isascii() and (char.isalnum() or char in "._-"))
    punctuation_count = sum(1 for char in compact if char in NORMAL_PUNCTUATION)
    suspicious = _suspicious_score(text)
    replacement_count = text.count("\ufffd")
    control_count = sum(1 for char in compact if ord(char) < 32 and char not in "\n\t")

    return (
        cjk_count * 2
        + ascii_count
        + punctuation_count
        - suspicious
        - replacement_count * 12
        - control_count * 20
    )


def _repair_candidates() -> Sequence[Tuple[str, Callable[[str], str]]]:
    return (
        ("GB18030 -> UTF-8", lambda value: value.encode("gb18030").decode("utf-8")),
        ("GBK -> UTF-8", lambda value: value.encode("gbk").decode("utf-8")),
        ("Latin-1 -> UTF-8", lambda value: value.encode("latin1").decode("utf-8")),
        ("CP1252 -> UTF-8", lambda value: value.encode("cp1252").decode("utf-8")),
    )


def _try_repair_mojibake(text: str) -> Tuple[str, Optional[str]]:
    baseline = _basic_cleanup(text)
    best_text = baseline
    best_score = _quality_score(baseline)
    best_suspicious = _suspicious_score(baseline)
    best_fix = None

    for label, repair in _repair_candidates():
        try:
            candidate = _basic_cleanup(repair(baseline))
        except (UnicodeDecodeError, UnicodeEncodeError):
            continue

        if len(candidate) < max(6, int(len(baseline) * 0.6)):
            continue

        candidate_score = _quality_score(candidate)
        candidate_suspicious = _suspicious_score(candidate)
        if (
            candidate_suspicious + 8 <= best_suspicious
            and candidate_score >= best_score - 4
        ) or candidate_score > best_score + 12:
            best_text = candidate
            best_score = candidate_score
            best_suspicious = candidate_suspicious
            best_fix = label

    return best_text, best_fix


def normalize_policy_text(text: str) -> TextNormalizationResult:
    cleaned = _basic_cleanup(text)
    applied_fixes: List[str] = []
    warnings: List[str] = []
    encoding_hint = None

    if _suspicious_score(cleaned) >= 16:
        repaired, repair_label = _try_repair_mojibake(cleaned)
        if repair_label and repaired != cleaned:
            cleaned = repaired
            encoding_hint = repair_label
            applied_fixes.append(f"Detected likely mojibake and auto-repaired text via {repair_label}.")

    if _suspicious_score(cleaned) >= 16:
        warnings.append("The input still contains suspicious mojibake fragments; review the source file encoding.")

    return TextNormalizationResult(
        text=cleaned,
        applied_fixes=applied_fixes,
        warnings=warnings,
        encoding_hint=encoding_hint,
    )
