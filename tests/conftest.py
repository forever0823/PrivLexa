from __future__ import annotations

import inspect

import pytest


def _case_title(item: pytest.Item) -> str:
    doc = inspect.getdoc(getattr(item, "obj", None))
    title = doc.splitlines()[0].strip() if doc else item.name
    callspec = getattr(item, "callspec", None)
    if callspec is not None and callspec.id:
        return f"{title} [{callspec.id}]"
    return title


def _translated_outcome(report: pytest.TestReport) -> str:
    if report.passed:
        return "通过"
    if report.failed:
        return "失败"
    if report.skipped:
        return "跳过"
    return report.outcome


def pytest_runtest_setup(item: pytest.Item) -> None:
    print(f"\n开始测试：{_case_title(item)}")


def pytest_report_teststatus(report: pytest.TestReport, config: pytest.Config):
    if report.when != "call":
        return None
    if report.passed:
        return "passed", ".", "通过"
    if report.failed:
        return "failed", "F", "失败"
    if report.skipped:
        return "skipped", "s", "跳过"
    return None


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[None]):
    outcome = yield
    report = outcome.get_result()
    if report.when != "call":
        return
    print(f"测试结果：{_case_title(item)} -> {_translated_outcome(report)}")


def pytest_terminal_summary(terminalreporter: pytest.TerminalReporter, exitstatus: int, config: pytest.Config) -> None:
    passed = len(terminalreporter.stats.get("passed", []))
    failed = len(terminalreporter.stats.get("failed", []))
    skipped = len(terminalreporter.stats.get("skipped", []))
    errors = len(terminalreporter.stats.get("error", []))
    terminalreporter.write_sep(
        "=",
        f"中文汇总：通过 {passed}，失败 {failed}，跳过 {skipped}，错误 {errors}",
    )
