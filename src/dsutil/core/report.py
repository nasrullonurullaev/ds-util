from __future__ import annotations

from .models import Issue, Report, Severity

_RANK: dict[Severity, int] = {"info": 1, "warn": 2, "crit": 3}


def dedupe_issues(issues: list[Issue]) -> list[Issue]:
    seen: set[tuple[str, str]] = set()
    out: list[Issue] = []
    for i in issues:
        key = (i.severity, i.title)
        if key in seen:
            continue
        seen.add(key)
        out.append(i)
    return out


def worst_severity(issues: list[Issue]) -> Severity:
    if not issues:
        return "info"
    worst = "info"
    for i in issues:
        if _RANK[i.severity] > _RANK[worst]:
            worst = i.severity
    return worst


def finalize(report: Report) -> Report:
    report.issues = dedupe_issues(report.issues)
    return report
