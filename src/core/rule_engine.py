"""
基于规则的硬冲突检测。
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional, Tuple
import re

from loguru import logger
from pydantic import BaseModel, Field


class SeverityLevel(str, Enum):
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"


class ConflictType(str, Enum):
    HARD_CONSTRAINT = "hard_constraint"
    SOFT_MISMATCH = "soft_mismatch"


class Conflict(BaseModel):
    conflict_id: str
    type: ConflictType
    severity: SeverityLevel
    rule_id: Optional[str] = None
    clause_1: str
    clause_2: str
    location_1: Tuple[int, int]
    location_2: Tuple[int, int]
    explanation: str
    suggestion: str


class ConflictDetectionRule(BaseModel):
    rule_id: str
    name: str
    description: str
    category: str
    positive_signals: List[str] = Field(default_factory=list)
    negative_signals: List[str] = Field(default_factory=list)
    scope_keywords: List[str] = Field(default_factory=list)
    severity: SeverityLevel = SeverityLevel.MAJOR
    explanation_template: str
    suggestion_template: str
    enabled: bool = True


class ClauseSpan(BaseModel):
    text: str
    start: int
    end: int


def extract_policy_clauses(text: str) -> List[ClauseSpan]:
    spans: List[ClauseSpan] = []
    for match in re.finditer(r"[^.!?;\n\u3002\uff01\uff1f\uff1b]+[.!?;\u3002\uff01\uff1f\uff1b]?", text or ""):
        segment = match.group(0).strip()
        if len(segment) < 8:
            continue
        spans.append(ClauseSpan(text=segment, start=match.start(), end=match.end()))
    if not spans and text.strip():
        stripped = text.strip()
        spans.append(ClauseSpan(text=stripped, start=0, end=len(stripped)))
    return spans


class ConflictDetectionEngine:
    def __init__(self) -> None:
        self.rules: Dict[str, ConflictDetectionRule] = {}
        self._initialize_rules()
        logger.info(f"冲突检测引擎初始化完成，共加载 {len(self.rules)} 条规则")

    def _initialize_rules(self) -> None:
        self.add_rule(
            ConflictDetectionRule(
                rule_id="retention_conflict",
                name="保存期限冲突",
                description="保存期限相关表述彼此矛盾。",
                category="retention",
                positive_signals=[
                    "retain indefinitely",
                    "permanent retention",
                    "long-term retention",
                    "\u6c38\u4e45\u4fdd\u5b58",
                    "\u957f\u671f\u4fdd\u5b58",
                ],
                negative_signals=[
                    "delete after",
                    "remove after",
                    "anonymize after",
                    "retention period",
                    "\u5230\u671f\u5220\u9664",
                    "\u6309\u671f\u5220\u9664",
                ],
                scope_keywords=["retain", "retention", "store", "storage", "\u4fdd\u5b58", "\u4fdd\u7559"],
                severity=SeverityLevel.MAJOR,
                explanation_template="保存期限表述冲突：{clause_1} 与 {clause_2}",
                suggestion_template="请为每类数据使用统一的保存期限规则，除非确有必要，否则避免使用无限期保存表述。",
            )
        )
        self.add_rule(
            ConflictDetectionRule(
                rule_id="consent_conflict",
                name="同意机制冲突",
                description="同一处理主题下同时出现需要同意和无需同意的表述。",
                category="consent",
                positive_signals=[
                    "explicit consent",
                    "separate consent",
                    "consent required",
                    "opt-in",
                    "\u660e\u793a\u540c\u610f",
                    "\u5355\u72ec\u540c\u610f",
                ],
                negative_signals=[
                    "no consent",
                    "implied consent",
                    "deemed consent",
                    "default consent",
                    "\u65e0\u9700\u540c\u610f",
                    "\u9ed8\u8ba4\u540c\u610f",
                ],
                scope_keywords=["consent", "authorization", "permission", "\u540c\u610f", "\u6388\u6743"],
                severity=SeverityLevel.CRITICAL,
                explanation_template="同意要求存在冲突：{clause_1} 与 {clause_2}",
                suggestion_template="请明确哪些处理活动需要明示同意，并说明撤回同意的具体方式。",
            )
        )
        self.add_rule(
            ConflictDetectionRule(
                rule_id="sharing_conflict",
                name="共享披露冲突",
                description="同一政策中同时存在禁止共享与允许广泛共享或出售的表述。",
                category="sharing",
                positive_signals=[
                    "share",
                    "sell",
                    "disclose",
                    "provide to third parties",
                    "\u5171\u4eab",
                    "\u51fa\u552e",
                    "\u62ab\u9732",
                ],
                negative_signals=[
                    "do not share",
                    "never sell",
                    "will not disclose",
                    "\u4e0d\u5171\u4eab",
                    "\u4e0d\u4f1a\u51fa\u552e",
                ],
                scope_keywords=["third party", "share", "sell", "service provider", "\u7b2c\u4e09\u65b9", "\u5171\u4eab"],
                severity=SeverityLevel.CRITICAL,
                explanation_template="第三方共享表述冲突：{clause_1} 与 {clause_2}",
                suggestion_template="请区分服务提供方、受托处理方和独立第三方，并统一披露一套一致的共享规则。",
            )
        )
        self.add_rule(
            ConflictDetectionRule(
                rule_id="rights_conflict",
                name="用户权利冲突",
                description="同一项用户权利同时被授予和否认。",
                category="rights",
                positive_signals=[
                    "may request deletion",
                    "may request access",
                    "right to correct",
                    "right to portability",
                    "\u6709\u6743\u5220\u9664",
                    "\u6709\u6743\u8bbf\u95ee",
                ],
                negative_signals=[
                    "cannot request",
                    "not available",
                    "no deletion right",
                    "no access right",
                    "\u65e0\u6743\u5220\u9664",
                    "\u65e0\u6cd5\u8bbf\u95ee",
                ],
                scope_keywords=["request", "deletion", "access", "correction", "portability", "\u5220\u9664", "\u8bbf\u95ee"],
                severity=SeverityLevel.MAJOR,
                explanation_template="用户权利表述冲突：{clause_1} 与 {clause_2}",
                suggestion_template="请用统一的适用范围和例外说明访问、更正、删除与可携带等权利。",
            )
        )
        self.add_rule(
            ConflictDetectionRule(
                rule_id="cross_border_conflict",
                name="跨境传输冲突",
                description="同一政策中同时存在否认跨境传输和披露跨境传输的表述。",
                category="cross_border",
                positive_signals=[
                    "international transfer",
                    "overseas storage",
                    "standard contractual clauses",
                    "cross-border transfer",
                    "\u5883\u5916",
                    "\u8de8\u5883\u4f20\u8f93",
                ],
                negative_signals=[
                    "no international transfer",
                    "domestic only",
                    "stored only locally",
                    "\u4e0d\u8de8\u5883",
                    "\u4ec5\u5883\u5185",
                ],
                scope_keywords=["transfer", "overseas", "international", "cross-border", "\u8de8\u5883", "\u5883\u5916"],
                severity=SeverityLevel.CRITICAL,
                explanation_template="跨境传输表述冲突：{clause_1} 与 {clause_2}",
                suggestion_template="请在统一表述中说明传输目的地、传输机制以及相应保障措施。",
            )
        )

    def add_rule(self, rule: ConflictDetectionRule) -> None:
        self.rules[rule.rule_id] = rule

    def detect_conflicts(self, text: str, rule_ids: Optional[List[str]] = None) -> List[Conflict]:
        # 先做条款切分，再按规则计算正负信号之间的冲突组合。
        clauses = extract_policy_clauses(text)
        rules = self._resolve_rules(rule_ids)
        conflicts: List[Conflict] = []

        for rule in rules:
            conflicts.extend(self._detect_rule_conflicts(clauses, rule))

        unique: Dict[str, Conflict] = {}
        for conflict in conflicts:
            unique[conflict.conflict_id] = conflict
        return list(unique.values())

    def _resolve_rules(self, rule_ids: Optional[List[str]]) -> List[ConflictDetectionRule]:
        if rule_ids:
            return [self.rules[rule_id] for rule_id in rule_ids if rule_id in self.rules and self.rules[rule_id].enabled]
        return [rule for rule in self.rules.values() if rule.enabled]

    def _detect_rule_conflicts(self, clauses: List[ClauseSpan], rule: ConflictDetectionRule) -> List[Conflict]:
        positives = [clause for clause in clauses if self._matches_rule(clause.text, rule.positive_signals, rule.scope_keywords)]
        negatives = [clause for clause in clauses if self._matches_rule(clause.text, rule.negative_signals, rule.scope_keywords)]
        conflicts: List[Conflict] = []

        if rule.category == "retention":
            conflicts.extend(self._detect_retention_conflicts(rule, clauses))

        for positive in positives:
            for negative in negatives:
                if positive.start == negative.start:
                    continue
                conflict_id = f"{rule.rule_id}_{positive.start}_{negative.start}"
                conflicts.append(
                    Conflict(
                        conflict_id=conflict_id,
                        type=ConflictType.HARD_CONSTRAINT,
                        severity=rule.severity,
                        rule_id=rule.rule_id,
                        clause_1=positive.text,
                        clause_2=negative.text,
                        location_1=(positive.start, positive.end),
                        location_2=(negative.start, negative.end),
                        explanation=rule.explanation_template.format(
                            clause_1=positive.text[:80],
                            clause_2=negative.text[:80],
                        ),
                        suggestion=rule.suggestion_template,
                    )
                )
        return conflicts

    def _detect_retention_conflicts(self, rule: ConflictDetectionRule, clauses: List[ClauseSpan]) -> List[Conflict]:
        retention_clauses = [clause for clause in clauses if self._matches_rule(clause.text, rule.scope_keywords, [])]
        seen_values: Dict[str, ClauseSpan] = {}
        conflicts: List[Conflict] = []

        for clause in retention_clauses:
            value = self._extract_retention_value(clause.text)
            if not value:
                continue
            if value in seen_values:
                continue
            for other_value, other_clause in seen_values.items():
                if other_value != value:
                    conflict_id = f"{rule.rule_id}_{other_clause.start}_{clause.start}"
                    conflicts.append(
                        Conflict(
                            conflict_id=conflict_id,
                            type=ConflictType.HARD_CONSTRAINT,
                            severity=rule.severity,
                            rule_id=rule.rule_id,
                            clause_1=other_clause.text,
                            clause_2=clause.text,
                            location_1=(other_clause.start, other_clause.end),
                            location_2=(clause.start, clause.end),
                            explanation=rule.explanation_template.format(
                                clause_1=other_clause.text[:80],
                                clause_2=clause.text[:80],
                            ),
                            suggestion=rule.suggestion_template,
                        )
                    )
            seen_values[value] = clause
        return conflicts

    def _matches_rule(self, text: str, signals: List[str], scope_keywords: List[str]) -> bool:
        normalized = text.lower()
        if scope_keywords and not any(keyword.lower() in normalized for keyword in scope_keywords):
            return False
        return any(signal.lower() in normalized for signal in signals)

    def _extract_retention_value(self, text: str) -> Optional[str]:
        match = re.search(
            r"(\d+\s*(?:days|months|years|\u5929|\u4e2a\u6708|\u6708|\u5e74))|"
            r"(indefinite(?:ly)?|permanent|long-term|\u6c38\u4e45|\u957f\u671f|\u65e0\u9650\u671f)",
            text,
            re.IGNORECASE,
        )
        return match.group(0).lower() if match else None

    def get_rule(self, rule_id: str) -> Optional[ConflictDetectionRule]:
        return self.rules.get(rule_id)

    def list_rules(self, category: Optional[str] = None) -> List[ConflictDetectionRule]:
        rules = list(self.rules.values())
        return [rule for rule in rules if not category or rule.category == category]


_conflict_engine: Optional[ConflictDetectionEngine] = None


def get_conflict_detection_engine() -> ConflictDetectionEngine:
    global _conflict_engine
    if _conflict_engine is None:
        _conflict_engine = ConflictDetectionEngine()
    return _conflict_engine
