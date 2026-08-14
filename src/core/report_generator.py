"""
Structured compliance report generator.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List

from pydantic import BaseModel, Field

try:
    from src.core.compliance_status import (
        ComplianceFindingStatus,
        calculate_status_score,
        summarize_compliance_status,
    )
except ImportError:
    from .compliance_status import (
        ComplianceFindingStatus,
        calculate_status_score,
        summarize_compliance_status,
    )


class Violation(BaseModel):
    violation_id: str
    clause: str
    law: str
    severity: str
    status: ComplianceFindingStatus
    description: str
    evidence: str
    remediation: str


class JurisdictionComplianceReport(BaseModel):
    jurisdiction: str
    jurisdiction_name: str
    status: ComplianceFindingStatus
    compliance_score: float
    violations_count: int
    violations: List[Violation] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    checked_points: Dict[str, ComplianceFindingStatus] = Field(default_factory=dict)
    generated_at: str


class MultiJurisdictionComplianceReport(BaseModel):
    policy_title: str
    policy_summary: str
    overall_status: ComplianceFindingStatus
    overall_score: float
    jurisdictions: List[JurisdictionComplianceReport]
    critical_violations: List[Violation] = Field(default_factory=list)
    global_recommendations: List[str] = Field(default_factory=list)
    generated_at: str

    def get_summary(self) -> Dict[str, float | int | str]:
        return {
            "overall_status": self.overall_status.value,
            "overall_score": self.overall_score,
            "jurisdictions_count": len(self.jurisdictions),
            "critical_violations_count": len(self.critical_violations),
            "total_violations": sum(report.violations_count for report in self.jurisdictions),
        }


class ComplianceReportGenerator:
    SEVERITY_LABELS = {
        "critical": "高风险",
        "major": "中风险",
        "minor": "低风险",
    }

    JURISDICTION_LABELS = {
        "CN": "中国",
        "US": "美国",
        "EU": "欧盟",
    }

    @staticmethod
    def generate_jurisdiction_report(
        jurisdiction: str,
        jurisdiction_name: str,
        policy_text: str,
        check_results: Dict[str, ComplianceFindingStatus],
        violations: List[Violation],
        recommendations: List[str],
    ) -> JurisdictionComplianceReport:
        score = calculate_status_score(check_results.values())
        status = summarize_compliance_status(
            check_results.values(),
            has_critical_risk=any(item.severity == "critical" for item in violations),
        )

        return JurisdictionComplianceReport(
            jurisdiction=jurisdiction,
            jurisdiction_name=jurisdiction_name,
            status=status,
            compliance_score=score,
            violations_count=len(violations),
            violations=violations,
            recommendations=recommendations,
            checked_points=check_results,
            generated_at=datetime.now().isoformat(),
        )

    @staticmethod
    def generate_multi_jurisdiction_report(
        policy_title: str,
        policy_summary: str,
        jurisdiction_reports: List[JurisdictionComplianceReport],
    ) -> MultiJurisdictionComplianceReport:
        overall_score = round(
            sum(report.compliance_score for report in jurisdiction_reports) / len(jurisdiction_reports),
            2,
        ) if jurisdiction_reports else 0.0

        overall_status = summarize_compliance_status(
            [report.status for report in jurisdiction_reports],
            has_critical_risk=any(
                violation.severity == "critical"
                for report in jurisdiction_reports
                for violation in report.violations
            ),
        )

        critical_violations = [
            violation
            for report in jurisdiction_reports
            for violation in report.violations
            if violation.severity == "critical"
        ]
        recommendations = ComplianceReportGenerator._generate_global_recommendations(
            jurisdiction_reports,
            critical_violations,
        )
        return MultiJurisdictionComplianceReport(
            policy_title=policy_title,
            policy_summary=policy_summary,
            overall_status=overall_status,
            overall_score=overall_score,
            jurisdictions=jurisdiction_reports,
            critical_violations=critical_violations,
            global_recommendations=recommendations,
            generated_at=datetime.now().isoformat(),
        )

    @staticmethod
    def _generate_global_recommendations(
        jurisdiction_reports: List[JurisdictionComplianceReport],
        critical_violations: List[Violation],
    ) -> List[str]:
        recommendations: List[str] = []
        if critical_violations:
            recommendations.append(
                "优先补齐最高风险问题涉及的关键义务："
                + ", ".join(item.clause for item in critical_violations[:3])
            )
        if jurisdiction_reports:
            weakest = min(jurisdiction_reports, key=lambda item: item.compliance_score)
            if weakest.compliance_score < 75:
                recommendations.append(
                    f"优先修复当前最薄弱的法域基线："
                    f"{ComplianceReportGenerator.JURISDICTION_LABELS.get(weakest.jurisdiction, weakest.jurisdiction_name)}"
                    f"当前得分为 {weakest.compliance_score:.1f}。"
                )
        recommendations.extend(
            [
                "保持第三方披露、权利入口和保存期限与产品实际行为同步更新。",
                "上线前重点复核高风险处理、跨境提供和广告技术相关共享行为。",
                "将 SDK 新增和权限变更视为隐私政策更新触发条件。",
            ]
        )
        return recommendations

    @staticmethod
    def format_report_as_markdown(report: MultiJurisdictionComplianceReport) -> str:
        priority_violations = ComplianceReportGenerator._select_priority_violations(report)
        lines = [
            "# 多法域隐私合规检测报告",
            "",
            "## 总览",
            f"- 政策标题：{report.policy_title}",
            f"- 生成时间：{report.generated_at}",
            f"- 检测法域：{', '.join(item.jurisdiction for item in report.jurisdictions)}",
            f"- 整体状态：{report.overall_status.value}",
            f"- 整体得分：{report.overall_score:.1f}/100",
            f"- 风险问题总数：{sum(item.violations_count for item in report.jurisdictions)}",
            "",
            "## 重点发现",
        ]
        if priority_violations:
            for index, (jurisdiction, violation) in enumerate(priority_violations, start=1):
                lines.extend(
                    [
                        f"{index}. [{ComplianceReportGenerator.JURISDICTION_LABELS.get(jurisdiction, jurisdiction)}] "
                        f"{violation.status.value} - {violation.clause}",
                        f"   - 风险等级：{ComplianceReportGenerator.SEVERITY_LABELS.get(violation.severity, violation.severity)}",
                        f"   - 问题说明：{violation.description}",
                        f"   - 证据：{violation.evidence}",
                        f"   - 整改建议：{violation.remediation}",
                    ]
                )
        else:
            lines.append("- 当前未发现需要优先处理的确定性高风险问题。")

        lines.extend(["", "## 法域详情"])
        for item in report.jurisdictions:
            label = ComplianceReportGenerator.JURISDICTION_LABELS.get(item.jurisdiction, item.jurisdiction_name)
            passed = sum(
                1 for status in item.checked_points.values() if status == ComplianceFindingStatus.COVERED
            )
            total = len(item.checked_points)
            lines.extend(
                [
                    "",
                    f"### {label} ({item.jurisdiction})",
                    f"- 状态：{item.status.value}",
                    f"- 得分：{item.compliance_score:.1f}/100",
                    f"- 已覆盖项：{passed}/{total}",
                    f"- 风险项：{item.violations_count}",
                ]
            )
            if item.violations:
                lines.append("- 关键问题：")
                for violation in item.violations[:5]:
                    lines.append(
                        "  - "
                        f"[{violation.status.value} | "
                        f"{ComplianceReportGenerator.SEVERITY_LABELS.get(violation.severity, violation.severity)}] "
                        f"{violation.clause}: {violation.description}"
                    )
                    lines.append(f"    - 证据：{violation.evidence}")
                    lines.append(f"    - 整改建议：{violation.remediation}")
            if item.recommendations:
                lines.append("- 建议动作：")
                for recommendation in item.recommendations[:4]:
                    lines.append(f"  - {recommendation}")

        if report.global_recommendations:
            lines.extend(["", "## 全局建议"])
            for recommendation in report.global_recommendations:
                lines.append(f"- {recommendation}")
        return "\n".join(lines)

    @staticmethod
    def _select_priority_violations(
        report: MultiJurisdictionComplianceReport,
        limit: int = 5,
    ) -> List[tuple[str, Violation]]:
        severity_rank = {"critical": 0, "major": 1, "minor": 2}
        items: List[tuple[str, Violation]] = [
            (jurisdiction_report.jurisdiction, violation)
            for jurisdiction_report in report.jurisdictions
            for violation in jurisdiction_report.violations
        ]
        items.sort(
            key=lambda entry: (
                severity_rank.get(entry[1].severity, 9),
                len(entry[1].description),
            )
        )
        return items[:limit]


_report_generator = ComplianceReportGenerator()


def get_report_generator() -> ComplianceReportGenerator:
    return _report_generator
