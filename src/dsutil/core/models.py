from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional

Severity = Literal["info", "warn", "crit"]


@dataclass(frozen=True)
class Issue:
    severity: Severity
    title: str
    hint: str


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    command: str
    output: Any = None


@dataclass
class Report:
    tool: str
    timestamp_utc: str
    platform: str
    target: str

    checks: list[CheckResult] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)

    def add_check(self, check: CheckResult) -> None:
        self.checks.append(check)

    def add_issue(self, issue: Issue) -> None:
        self.issues.append(issue)
