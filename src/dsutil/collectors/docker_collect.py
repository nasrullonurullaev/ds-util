from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from dsutil.backends.base import Backend
from dsutil.core.models import CheckResult, Issue, Report
from dsutil.core.report import finalize
from dsutil.core.rules import default_rules, scan_text

REQUIRED_PROGRAMS = {"ds:docservice", "ds:converter"}
OPTIONAL_PROGRAMS = {"ds:adminpanel", "ds:example", "ds:metrics"}

DS_LOG_BASE = "/var/log/onlyoffice/documentserver"
DS_LOG_TARGETS = [
    f"{DS_LOG_BASE}/docservice/err.log",
    f"{DS_LOG_BASE}/docservice/out.log",
    f"{DS_LOG_BASE}/converter/err.log",
    f"{DS_LOG_BASE}/converter/out.log",
    f"{DS_LOG_BASE}/nginx.error.log",
]

_SUP_RE = re.compile(r"^(?P<name>\S+)\s+(?P<state>RUNNING|STOPPED|FATAL|BACKOFF|EXITED|STARTING)\s+(?P<rest>.*)$")


def _parse_supervisor_status(text: str) -> dict[str, dict[str, str]]:
    res: dict[str, dict[str, str]] = {}
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        m = _SUP_RE.match(line)
        if not m:
            continue
        res[m.group("name")] = {"state": m.group("state"), "rest": m.group("rest")}
    return res


def _tail_file(backend: Backend, target: str, path: str, lines: int) -> tuple[bool, str]:
    r = backend.exec(target, f"test -f {path!s} && tail -n {int(lines)} {path!s} || true", timeout_s=20)
    if r.rc == 0 and r.out.strip():
        return True, r.out
    r2 = backend.exec(target, f"test -f {path!s} && echo EXISTS || echo MISSING", timeout_s=10)
    return (r2.out.strip() == "EXISTS"), (r.out or r.err)


def collect_docker_report(
    backend: Backend,
    container: str,
    docker_tail: int = 400,
    file_tail: int = 800,
) -> Report:
    ts = datetime.now(timezone.utc).isoformat()
    report = Report(tool="dsutil", timestamp_utc=ts, platform="docker", target=container)

    ok, info = backend.check_available()
    if not ok:
        report.add_issue(Issue("crit", "Docker is not available", info))
        return finalize(report)

    ins = backend.inspect(container)
    if "_error" in ins:
        report.add_issue(Issue("crit", "Container inspect failed", ins["_error"]))
        return finalize(report)

    state = (ins.get("State") or {})
    running = bool(state.get("Running"))
    health = ((state.get("Health") or {}).get("Status")) if state.get("Health") else None

    report.add_check(CheckResult("container_running", running, "docker inspect .State.Running", state.get("Status")))
    if health:
        report.add_check(CheckResult("container_health", health == "healthy", "docker inspect .State.Health", health))
        if health != "healthy":
            report.add_issue(Issue("crit", f"Container health is {health}", "Check DS services and logs."))

    if not running:
        report.add_issue(Issue("crit", "Container is not running", "Check docker logs/inspect."))
        return finalize(report)

    # Health endpoint
    r = backend.exec(container, "curl -fsS http://localhost:8000/info/info.json | head -c 400", timeout_s=10)
    report.add_check(CheckResult("health_endpoint", r.rc == 0, "curl http://localhost:8000/info/info.json", r.out or r.err))
    if r.rc != 0:
        report.add_issue(Issue("crit", "Health endpoint failed", "Most often docservice/converter is down or nginx routing is broken."))

    # supervisorctl status (IMPORTANT: do NOT treat non-zero rc as failure if output is parseable)
    s = backend.exec(container, "supervisorctl status 2>&1", timeout_s=10)
    sup = _parse_supervisor_status(s.out or s.err)
    usable = bool(sup)
    report.add_check(CheckResult("supervisorctl_status", usable, "supervisorctl status", {"exit_code": s.rc, "raw": (s.out or s.err), "parsed": sup}))

    if not usable:
        report.add_issue(Issue("crit", "supervisorctl could not query supervisord", "Check supervisord and /var/log/supervisor/supervisord.log."))
        return finalize(report)

    # required services must be RUNNING
    for p in sorted(REQUIRED_PROGRAMS):
        stp = sup.get(p)
        if not stp:
            report.add_issue(Issue("crit", f"Missing required service: {p}", "Supervisor config may be missing."))
            continue
        if stp["state"] != "RUNNING":
            report.add_issue(Issue("crit", f"Required service not RUNNING: {p} ({stp['state']})", f"Check logs in {DS_LOG_BASE}/{p.split(':',1)[1]}/"))

    # optional services: STOPPED is OK; unhealthy states warn
    for p in sorted(OPTIONAL_PROGRAMS):
        stp = sup.get(p)
        if not stp:
            continue
        if stp["state"] in ("FATAL", "BACKOFF", "EXITED"):
            report.add_issue(Issue("warn", f"Optional service unhealthy: {p} ({stp['state']})", "If enabled manually, inspect its logs/config."))

    # nginx config test
    n = backend.exec(container, "nginx -t 2>&1 | tail -n 80", timeout_s=10)
    if n.rc != 127:
        report.add_check(CheckResult("nginx_test", n.rc == 0, "nginx -t", n.out or n.err))
        if n.rc != 0:
            report.add_issue(Issue("warn", "nginx -t failed", "Inspect nginx configs and includes."))

    # postgresql check
    pg = backend.exec(container, "pg_isready -h localhost -p 5432 2>&1", timeout_s=10)
    if pg.rc != 127:
        report.add_check(CheckResult("postgres_ready", pg.rc == 0, "pg_isready -h localhost -p 5432", pg.out or pg.err))
        if pg.rc != 0:
            report.add_issue(Issue("crit", "PostgreSQL is not ready", "Check /var/log/postgresql/*.log and service status."))
    
    # rabbitmq check
    rmq = backend.exec(container, "rabbitmq-diagnostics -q status 2>&1 | head -n 40", timeout_s=10)
    if rmq.rc != 127:
        report.add_check(CheckResult("rabbitmq_status", rmq.rc == 0, "rabbitmq-diagnostics status", rmq.out or rmq.err))
        if rmq.rc != 0:
            report.add_issue(Issue("crit", "RabbitMQ status check failed", "Check /var/log/rabbitmq/* and rabbitmq service."))

    # redis check
    rr = backend.exec(container, "redis-cli -h 127.0.0.1 ping 2>&1", timeout_s=10)
    okr = rr.rc == 0 and "PONG" in (rr.out or "")
    report.add_check(CheckResult("redis_ping", okr, "redis-cli ping", rr.out or rr.err))
    if not okr:
        report.add_issue(Issue("warn", "Redis ping failed", "Redis is not running or not responding; check /var/log/redis/*.log if Redis is expected."))

    # docker logs scan (broad)
    dlogs = backend.logs(container, tail=docker_tail)
    for i in scan_text(dlogs, default_rules()):
        report.add_issue(i)

    # DS log snippets scan (targeted)
    snippets: dict[str, str] = {}
    for p in DS_LOG_TARGETS:
        exists, content = _tail_file(backend, container, p, file_tail)
        if exists:
            snippets[p] = content
            for i in scan_text(content, default_rules()):
                report.add_issue(i)
    report.add_check(CheckResult("ds_log_snippets", True, f"tail DS logs ({file_tail} lines)", {"files": list(snippets.keys())}))

    return finalize(report)
