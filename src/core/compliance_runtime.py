"""合规分析、法规检索和冲突检测的确定性运行时。"""

from __future__ import annotations

import asyncio
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from loguru import logger

try:
    from src.core.compliance_status import ComplianceFindingStatus
    from src.core.jurisdiction import get_jurisdiction_manager
    from src.core.knowledge_graph import get_regulation_knowledge_graph
    from src.core.rag import get_rag_pipeline
    from src.core.report_generator import ComplianceReportGenerator, Violation
    from src.core.rule_engine import extract_policy_clauses, get_conflict_detection_engine
    from src.core.similarity import get_soft_conflict_detector
except ImportError:
    from .compliance_status import ComplianceFindingStatus
    from .jurisdiction import get_jurisdiction_manager
    from .knowledge_graph import get_regulation_knowledge_graph
    from .rag import get_rag_pipeline
    from .report_generator import ComplianceReportGenerator, Violation
    from .rule_engine import extract_policy_clauses, get_conflict_detection_engine
    from .similarity import get_soft_conflict_detector


class ComplianceRuntime:
    def __init__(self) -> None:
        self.graph = get_regulation_knowledge_graph()
        self.jurisdiction_manager = get_jurisdiction_manager()
        self.rag_pipeline = get_rag_pipeline()
        self.rule_engine = get_conflict_detection_engine()
        self.soft_detector = get_soft_conflict_detector()
        self.report_generator = ComplianceReportGenerator()

    def build_generation_context(
        self,
        jurisdiction: str,
        topic: str,
        context: str = "",
    ) -> Dict[str, Any]:
        retrieval = self.rag_pipeline.retrieve_for_generation(
            jurisdiction=jurisdiction,
            topic=topic,
            context=context,
        )
        jurisdiction_config = self.jurisdiction_manager.get_jurisdiction(jurisdiction)
        jurisdiction_profile = (
            jurisdiction_config.jurisdiction_embedding
            if jurisdiction_config
            else f"法域代码：{jurisdiction}"
        )
        retrieval["prompt_context"] = (
            f"{retrieval['context_summary']}\n\n"
            f"法域画像：{jurisdiction_profile}\n"
            "说明：原始法规证据可能包含英文内容，生成结果必须用简体中文概括。"
        )
        return retrieval

    def detect_conflicts(self, policy_text: str, detection_mode: str = "both") -> Dict[str, Any]:
        clauses = [span.text for span in extract_policy_clauses(policy_text)]
        hard_conflicts: List[Dict[str, Any]] = []
        soft_conflicts: List[Dict[str, Any]] = []

        if detection_mode in {"hard", "both", None}:
            hard_conflicts = [
                {
                    **item.model_dump(mode="json"),
                    "status": ComplianceFindingStatus.CONFLICT.value,
                }
                for item in self.rule_engine.detect_conflicts(policy_text)
            ]
        if detection_mode in {"soft", "both", None}:
            soft_conflicts = [
                {
                    **item,
                    "status": ComplianceFindingStatus.CONFLICT.value,
                }
                for item in self.soft_detector.detect_soft_conflicts(clauses)
            ]

        critical_count = sum(1 for item in hard_conflicts if item.get("severity") == "critical")
        major_count = sum(1 for item in hard_conflicts if item.get("severity") == "major")
        minor_count = sum(1 for item in hard_conflicts if item.get("severity") == "minor")
        summary = self._format_conflict_summary(hard_conflicts, soft_conflicts)
        return {
            "hard_conflicts": hard_conflicts,
            "soft_conflicts": soft_conflicts,
            "total_conflicts": len(hard_conflicts) + len(soft_conflicts),
            "critical_count": critical_count,
            "major_count": major_count,
            "minor_count": minor_count,
            "clauses_count": len(clauses),
            "summary_markdown": summary,
            "prompt_context": summary,
        }

    async def analyze_compliance(
        self,
        policy_text: str,
        jurisdictions: Optional[Sequence[str]] = None,
        policy_title: str = "Untitled Policy",
        parallel_execution: bool = True,
    ) -> Dict[str, Any]:
        normalized = self.jurisdiction_manager.sanitize_jurisdictions(jurisdictions)
        if parallel_execution and len(normalized) > 1:
            reports = await asyncio.gather(
                *[self._analyze_single(policy_text, code) for code in normalized]
            )
        else:
            reports = []
            for code in normalized:
                reports.append(await self._analyze_single(policy_text, code))

        multi_report = self.report_generator.generate_multi_jurisdiction_report(
            policy_title=policy_title or "Untitled Policy",
            policy_summary=policy_text[:240],
            jurisdiction_reports=reports,
        )
        markdown_report = self.report_generator.format_report_as_markdown(multi_report)
        return {
            "overall_status": multi_report.overall_status.value,
            "overall_score": multi_report.overall_score,
            "jurisdiction_results": [
                report.model_dump(mode="json") for report in multi_report.jurisdictions
            ],
            "critical_violations": [
                item.model_dump(mode="json") for item in multi_report.critical_violations
            ],
            "recommendations": multi_report.global_recommendations,
            "markdown_report": markdown_report,
            "prompt_context": markdown_report,
            "report": multi_report.model_dump(mode="json"),
        }

    async def _analyze_single(self, policy_text: str, jurisdiction: str):
        config = self.jurisdiction_manager.get_jurisdiction(jurisdiction)
        if not config:
            raise ValueError(f"Unsupported jurisdiction: {jurisdiction}")

        obligations = self.graph.get_obligations_for_jurisdiction(config.code)
        check_results: Dict[str, ComplianceFindingStatus] = {}
        violations: List[Violation] = []
        recommendations: List[str] = []

        for obligation in obligations:
            matched, matched_kws, snippets = self._policy_matches_obligation(
                policy_text, obligation.keywords,
            )
            finding_status = (
                ComplianceFindingStatus.COVERED
                if matched
                else (
                    ComplianceFindingStatus.HIGH_RISK
                    if obligation.risk_level == "critical"
                    else ComplianceFindingStatus.MISSING
                )
            )
            check_results[obligation.title] = finding_status
            if matched:
                continue

            # Build rich evidence string
            evidence_parts: List[str] = []
            if matched_kws:
                evidence_parts.append(
                    "匹配到的关键词: " + ", ".join(matched_kws[:6])
                )
            if snippets:
                for snip in snippets[:2]:
                    evidence_parts.append(f"上下文片段: \"{snip}\"")
            if not evidence_parts:
                evidence_parts.append(
                    "在政策文本中未找到足够明确的关键词或条款证据。"
                )
            evidence = " | ".join(evidence_parts)

            related_law = self.graph.get_related_laws_for_obligation(obligation.obligation_id)
            violations.append(
                Violation(
                    violation_id=f"{config.code}_{obligation.category}",
                    clause=obligation.title,
                    law=related_law[0] if related_law else (config.laws[0] if config.laws else config.name),
                    severity=obligation.risk_level,
                    status=finding_status,
                    description=f"未发现对“{obligation.title}”的清晰披露。",
                    evidence=evidence,
                    remediation=obligation.recommended_policy_language,
                )
            )
            recommendations.append(obligation.recommended_policy_language)

        recommendations = list(dict.fromkeys(recommendations))[:8]
        return self.report_generator.generate_jurisdiction_report(
            jurisdiction=config.code,
            jurisdiction_name=config.name,
            policy_text=policy_text,
            check_results=check_results,
            violations=violations,
            recommendations=recommendations,
        )

    # ------------------------------------------------------------------
    # Compliance keyword matching
    # ------------------------------------------------------------------

    @staticmethod
    def _is_cjk_char(ch: str) -> bool:
        """Return True if *ch* is a CJK Unified Ideograph."""
        cp = ord(ch)
        return (
            0x4E00 <= cp <= 0x9FFF
            or 0x3400 <= cp <= 0x4DBF
            or 0x20000 <= cp <= 0x2A6DF
            or 0x2A700 <= cp <= 0x2B73F
            or 0xF900 <= cp <= 0xFAFF
        )

    @staticmethod
    def _has_cjk(text: str) -> bool:
        """Return True if *text* contains at least one CJK character."""
        return any(ComplianceRuntime._is_cjk_char(ch) for ch in text)

    @staticmethod
    def _word_boundary_match(keyword: str, text_lower: str) -> bool:
        """Match *keyword* only at ASCII word boundaries inside *text_lower*.

        For CJK keywords (>= 2 CJK chars) a substring match is acceptable.
        For ASCII keywords, ``\\b``-anchored regex prevents partial matches
        (e.g. "at" inside "data").
        """
        if ComplianceRuntime._has_cjk(keyword):
            kw = keyword.lower()
            return kw in text_lower
        # ASCII / Latin keyword -> word boundary match
        pattern = r"\b" + re.escape(keyword.lower()) + r"\b"
        return bool(re.search(pattern, text_lower))

    @staticmethod
    def _find_context_snippet(
        text: str, keyword: str, window: int = 40
    ) -> str:
        """Return a short snippet of *text* around the first occurrence of *keyword*."""
        idx = text.lower().find(keyword.lower())
        if idx < 0:
            return ""
        start = max(0, idx - window)
        end = min(len(text), idx + len(keyword) + window)
        snippet = text[start:end].replace("\n", " ").strip()
        prefix = "..." if start > 0 else ""
        suffix = "..." if end < len(text) else ""
        return f"{prefix}{snippet}{suffix}"

    def _policy_matches_obligation(
        self, policy_text: str, keywords: Sequence[str]
    ) -> Tuple[bool, List[str], List[str]]:
        """Check whether *policy_text* addresses the given obligation *keywords*.

        Returns
        -------
        matched : bool
            Whether enough keywords were found.
        matched_keywords : list[str]
            Keywords that were actually matched (for evidence).
        context_snippets : list[str]
            Short text excerpts around each matched keyword.
        """
        text_lower = (policy_text or "").lower()
        matched_kws: List[str] = []
        snippets: List[str] = []

        for keyword in keywords:
            if not keyword or len(keyword.strip()) < 2:
                continue
            keyword = keyword.strip()
            if self._word_boundary_match(keyword, text_lower):
                matched_kws.append(keyword)
                snippet = self._find_context_snippet(policy_text, keyword)
                if snippet and snippet not in snippets:
                    snippets.append(snippet)

        # Length-aware threshold: longer keyword lists need more hits.
        kw_count = len([k for k in keywords if k and len(k.strip()) >= 2])
        if kw_count <= 2:
            threshold = 1
        elif kw_count <= 6:
            threshold = 2
        else:
            threshold = max(2, kw_count // 3)

        return len(matched_kws) >= threshold, matched_kws, snippets

    def _format_conflict_summary(
        self,
        hard_conflicts: List[Dict[str, Any]],
        soft_conflicts: List[Dict[str, Any]],
    ) -> str:
        lines = [
            "## 冲突检测摘要",
            f"- 规则冲突：{len(hard_conflicts)}",
            f"- 语义冲突：{len(soft_conflicts)}",
        ]
        if hard_conflicts:
            lines.extend(["", "### 规则冲突"])
            for item in hard_conflicts[:5]:
                lines.append(
                    f"- [{ComplianceFindingStatus.CONFLICT.value}] {item.get('explanation', '')}"
                )
        if soft_conflicts:
            lines.extend(["", "### 语义冲突"])
            for item in soft_conflicts[:5]:
                lines.append(
                    f"- [{ComplianceFindingStatus.CONFLICT.value}] 相似度 {item.get('similarity', 0)}：{item.get('reason', '')}"
                )
        if not hard_conflicts and not soft_conflicts:
            lines.append("- 当前未发现明确冲突。")
        return "\n".join(lines)


_runtime: Optional[ComplianceRuntime] = None


def get_compliance_runtime() -> ComplianceRuntime:
    global _runtime
    if _runtime is None:
        _runtime = ComplianceRuntime()
        logger.info("Compliance runtime initialized")
    return _runtime
