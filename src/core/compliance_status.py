"""
Unified compliance finding statuses used across prompts, runtime reports, and API payloads.
"""

from __future__ import annotations

from enum import Enum
from typing import Iterable, Optional


class ComplianceFindingStatus(str, Enum):
    COVERED = "已覆盖"
    PARTIAL = "部分覆盖"
    MISSING = "缺失"
    CONFLICT = "冲突"
    HIGH_RISK = "高风险"
    TO_BE_CONFIRMED = "待确认"


STATUS_SCORE_WEIGHTS = {
    ComplianceFindingStatus.COVERED: 1.0,
    ComplianceFindingStatus.PARTIAL: 0.5,
    ComplianceFindingStatus.TO_BE_CONFIRMED: 0.5,
    ComplianceFindingStatus.MISSING: 0.0,
    ComplianceFindingStatus.CONFLICT: 0.0,
    ComplianceFindingStatus.HIGH_RISK: 0.0,
}


STATUS_ALIASES = {
    "covered": ComplianceFindingStatus.COVERED,
    "disclosed": ComplianceFindingStatus.COVERED,
    "compliant": ComplianceFindingStatus.COVERED,
    "partial": ComplianceFindingStatus.PARTIAL,
    "partially_compliant": ComplianceFindingStatus.PARTIAL,
    "missing": ComplianceFindingStatus.MISSING,
    "conflict": ComplianceFindingStatus.CONFLICT,
    "high_risk": ComplianceFindingStatus.HIGH_RISK,
    "non_compliant": ComplianceFindingStatus.HIGH_RISK,
    "to_be_confirmed": ComplianceFindingStatus.TO_BE_CONFIRMED,
    "undetermined": ComplianceFindingStatus.TO_BE_CONFIRMED,
}


def normalize_compliance_status(
    value: str | ComplianceFindingStatus | None,
    default: Optional[ComplianceFindingStatus] = None,
) -> Optional[ComplianceFindingStatus]:
    if value is None:
        return default
    if isinstance(value, ComplianceFindingStatus):
        return value

    normalized = str(value).strip()
    if not normalized:
        return default

    for status in ComplianceFindingStatus:
        if normalized == status.value:
            return status

    return STATUS_ALIASES.get(normalized.lower(), default)


def calculate_status_score(statuses: Iterable[ComplianceFindingStatus | str]) -> float:
    normalized = [
        normalize_compliance_status(status)
        for status in statuses
    ]
    resolved = [status for status in normalized if status is not None]
    if not resolved:
        return 0.0
    return round(
        sum(STATUS_SCORE_WEIGHTS.get(status, 0.0) for status in resolved) / len(resolved) * 100.0,
        2,
    )


def summarize_compliance_status(
    statuses: Iterable[ComplianceFindingStatus | str],
    *,
    has_critical_risk: bool = False,
) -> ComplianceFindingStatus:
    resolved = [
        normalize_compliance_status(status)
        for status in statuses
    ]
    normalized = [status for status in resolved if status is not None]

    if not normalized:
        return ComplianceFindingStatus.HIGH_RISK if has_critical_risk else ComplianceFindingStatus.COVERED

    if has_critical_risk or ComplianceFindingStatus.HIGH_RISK in normalized:
        return ComplianceFindingStatus.HIGH_RISK
    if ComplianceFindingStatus.CONFLICT in normalized:
        return ComplianceFindingStatus.CONFLICT
    if all(status == ComplianceFindingStatus.MISSING for status in normalized):
        return ComplianceFindingStatus.MISSING
    if (
        ComplianceFindingStatus.MISSING in normalized
        or ComplianceFindingStatus.PARTIAL in normalized
    ):
        return ComplianceFindingStatus.PARTIAL
    if ComplianceFindingStatus.TO_BE_CONFIRMED in normalized:
        return ComplianceFindingStatus.TO_BE_CONFIRMED
    return ComplianceFindingStatus.COVERED
