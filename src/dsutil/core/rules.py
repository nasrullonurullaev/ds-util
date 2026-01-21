from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Pattern

from .models import Issue, Severity


@dataclass(frozen=True)
class Rule:
    pattern: Pattern[str]
    severity: Severity
    title: str
    hint: str


def default_rules() -> list[Rule]:
    def r(p: str, sev: Severity, title: str, hint: str) -> Rule:
        return Rule(re.compile(p, re.IGNORECASE), sev, title, hint)

    return [
        r(r"\b502\b|\b504\b", "warn", "HTTP gateway errors detected",
          "Often means upstream (internal DS service) is down or timing out."),
        r(r"upstream timed out|proxy_read_timeout|timeout", "warn", "Timeouts detected",
          "Check CPU/IO pressure; consider increasing nginx timeouts if needed."),
        r(r"connect\(\) failed \(111|Connection refused", "crit", "Connection refused detected",
          "Usually the target service/port is not listening or crashed."),
        r(r"OOMKilled|Out of memory|Killed process", "crit", "Possible OOM condition",
          "Likely memory pressure or container memory limits; review memory usage/limits."),
        r(r"too many open files|EMFILE", "crit", "File descriptor limit reached",
          "Increase nofile/ulimit; otherwise services can fail under load."),
        r(r"(password authentication failed|could not connect to server|connection refused|FATAL:\s)", "warn",
          "PostgreSQL connectivity/auth errors detected",
          "Check PostgreSQL is running, credentials, and local connectivity."),
        r(r"(AMQP.*(ACCESS_REFUSED|NOT_ALLOWED)|ECONNREFUSED|Connection refused).*amqp|amqp.*(ACCESS_REFUSED|NOT_ALLOWED|ECONNREFUSED)", "warn",
          "RabbitMQ connectivity/auth errors detected",
          "Check RabbitMQ is running and AMQP credentials/permissions are correct."),
        r(r"fontconfig|No fonts|FcConfig|Fontconfig error", "warn", "Fontconfig/fonts issue",
          "Check font volumes (/usr/share/fonts) and font cache; missing fonts can break rendering."),
    ]


def scan_text(text: str, rules: Iterable[Rule]) -> list[Issue]:
    issues: list[Issue] = []
    if not text:
        return issues
    for rule in rules:
        if rule.pattern.search(text):
            issues.append(Issue(rule.severity, rule.title, rule.hint))
    return issues
