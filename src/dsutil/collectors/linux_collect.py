from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from dsutil.backends.base import Backend
from dsutil.backends.linux import LinuxBackend
from dsutil.core.models import CheckResult, Issue, Report
from dsutil.core.report import finalize
from dsutil.core.rules import default_rules, scan_text

TARGET_HOST = "host"
LOCAL_JSON = Path("/etc/onlyoffice/documentserver/local.json")

REQUIRED_UNITS = ["ds-docservice.service", "ds-converter.service"]
OPTIONAL_UNITS = ["ds-adminpanel.service", "ds-example.service", "ds-metrics.service"]

DS_LOG_TARGETS = [
    "/var/log/onlyoffice/documentserver/docservice/out.log",
    "/var/log/onlyoffice/documentserver/docservice/err.log",
    "/var/log/onlyoffice/documentserver/converter/out.log",
    "/var/log/onlyoffice/documentserver/converter/err.log",
    "/var/log/onlyoffice/documentserver/nginx.error.log",
]

NGINX_FILES = [
    "/etc/nginx/nginx.conf",
    "/etc/nginx/conf.d/ds.conf",
    "/etc/onlyoffice/documentserver/nginx/ds.conf",
]


def _tail_file(backend: Backend, target: str, path: str, lines: int) -> tuple[bool, str]:
    p = backend.exec(target, f"test -f {path} && tail -n {lines} {path} || true", timeout_s=10)
    exists = backend.exec(target, f"test -f {path}", timeout_s=5).rc == 0
    return exists, (p.out or "").strip()


def _load_local_json() -> dict | None:
    try:
        return json.loads(LOCAL_JSON.read_text(encoding="utf-8"))
    except Exception:
        return None


def _tcp_check(backend: Backend, target: str, host: str, port: int) -> tuple[bool, str]:
    r = backend.exec(
        target,
        f"timeout 2 bash -lc 'cat < /dev/null > /dev/tcp/{host}/{port}' 2>&1",
        timeout_s=5,
    )
    ok = r.rc == 0
    msg = (r.out or r.err or "").strip() or ("OK" if ok else f"rc={r.rc}")
    return ok, msg


def collect_linux_report(file_tail: int = 800) -> Report:
    ts = datetime.now(timezone.utc).isoformat()
    report = Report(tool="dsutil", timestamp_utc=ts, platform="linux", target=TARGET_HOST)

    backend = LinuxBackend()
    ok, info = backend.check_available()
    if not ok:
        report.add_issue(Issue("crit", "Linux backend is not available", info))
        return finalize(report)

    # Health endpoint
    h = backend.exec(
        TARGET_HOST,
        "curl -fsS http://localhost:8000/info/info.json >/dev/null 2>&1",
        timeout_s=10,
    )
    report.add_check(
        CheckResult(
            "health_endpoint",
            h.rc == 0,
            "curl -f http://localhost:8000/info/info.json",
            h.err or h.out,
        )
    )
    if h.rc != 0:
        report.add_issue(Issue("crit", "Health endpoint check failed", "Check nginx/docservice/converter status and logs."))

    # systemd units (required)
    for unit in REQUIRED_UNITS:
        r = backend.exec(TARGET_HOST, f"systemctl is-active {unit} 2>&1", timeout_s=10)
        ok_unit = (r.rc == 0 and (r.out or "").strip() == "active")
        report.add_check(CheckResult(f"systemd_{unit}", ok_unit, f"systemctl is-active {unit}", (r.out or r.err).strip()))
        if not ok_unit:
            report.add_issue(Issue("crit", f"Required service not active: {unit}", "Check systemctl status and journalctl logs."))

    # systemd units (optional)
    for unit in OPTIONAL_UNITS:
        r = backend.exec(TARGET_HOST, f"systemctl is-active {unit} 2>&1", timeout_s=10)
        ok_unit = (r.rc == 0 and (r.out or "").strip() == "active")
        report.add_check(CheckResult(f"systemd_{unit}", ok_unit, f"systemctl is-active {unit}", (r.out or r.err).strip()))
        if not ok_unit:
            report.add_issue(Issue("warn", f"Optional service is not active: {unit}", "This service is optional and disabled by default. Enable it only if you need this feature."))

    # nginx service + config
    ns = backend.exec(TARGET_HOST, "systemctl is-active nginx.service 2>&1", timeout_s=10)
    ok_ns = (ns.rc == 0 and (ns.out or "").strip() == "active")
    report.add_check(CheckResult("nginx_service", ok_ns, "systemctl is-active nginx.service", (ns.out or ns.err).strip()))
    if not ok_ns:
        report.add_issue(Issue("crit", "Nginx is not active", "Check `systemctl status nginx` and nginx logs."))

    nt = backend.exec(TARGET_HOST, "nginx -t 2>&1", timeout_s=10)
    out = (nt.out or nt.err or "").strip()

    fatal = any(x in out.lower() for x in ("test failed", "emerg", "is invalid"))

    # IMPORTANT: do NOT use rc here. nginx -t can warn and still be valid.
    ok = not fatal

    report.add_check(CheckResult("nginx_test", ok, "nginx -t", out))

    if fatal:
        report.add_issue(Issue("crit", "Nginx config test failed", "Fix nginx configuration errors before continuing."))
    elif "warn" in out.lower():
        report.add_issue(Issue("warn", "Nginx config warnings detected", "Warnings are usually safe; review nginx.conf directives if needed."))

    # nginx include tree sanity
    missing = [p for p in NGINX_FILES if backend.exec(TARGET_HOST, f"test -e {p}", timeout_s=5).rc != 0]
    report.add_check(CheckResult("nginx_tree", len(missing) == 0, "validate nginx include tree", {"missing": missing}))
    if missing:
        report.add_issue(Issue("warn", "Some nginx DS config files are missing", "Check /etc/nginx/conf.d/ds.conf and /etc/nginx/includes/*.conf links."))

    # Parse local.json and check deps connectivity
    cfg = _load_local_json()
    if cfg is None:
        report.add_check(CheckResult("local_json", False, f"read {LOCAL_JSON}", "Failed to read or parse local.json"))
        report.add_issue(Issue("warn", "Cannot read local.json", "Dependency checks may be incomplete. Ensure local.json exists and is valid JSON."))
    else:
        report.add_check(CheckResult("local_json", True, f"read {LOCAL_JSON}", "OK"))

        sql = (((cfg.get("services") or {}).get("CoAuthoring") or {}).get("sql") or {})
        if sql:
            host = str(sql.get("dbHost", "localhost"))
            port = int(sql.get("dbPort", 5432))
            ok_dep, msg = _tcp_check(backend, TARGET_HOST, host, port)
            report.add_check(CheckResult("postgres_tcp", ok_dep, f"tcp {host}:{port}", msg))
            if not ok_dep:
                report.add_issue(Issue("crit", "PostgreSQL is not reachable", "Check DB host/port in local.json and network connectivity."))

        red = (((cfg.get("services") or {}).get("CoAuthoring") or {}).get("redis") or {})
        if red:
            host = str(red.get("host", "localhost"))
            port = int(red.get("port", 6379)) if "port" in red else 6379
            ok_dep, msg = _tcp_check(backend, TARGET_HOST, host, port)
            report.add_check(CheckResult("redis_tcp", ok_dep, f"tcp {host}:{port}", msg))
            if not ok_dep:
                report.add_issue(Issue("crit", "Redis is not reachable", "Check redis host/port in local.json and network connectivity."))

        rmq_url = (cfg.get("rabbitmq") or {}).get("url")
        if rmq_url:
            u = urlparse(rmq_url)
            host = u.hostname or "localhost"
            port = u.port or 5672
            ok_dep, msg = _tcp_check(backend, TARGET_HOST, host, port)
            report.add_check(CheckResult("rabbitmq_tcp", ok_dep, f"tcp {host}:{port}", msg))
            if not ok_dep:
                report.add_issue(Issue("crit", "RabbitMQ is not reachable", "Check rabbitmq.url in local.json and network connectivity."))

    # DS log scan
    rules = default_rules()
    for p in DS_LOG_TARGETS:
        exists, content = _tail_file(backend, TARGET_HOST, p, file_tail)
        if exists and content:
            for i in scan_text(content, rules):
                report.add_issue(i)

    return finalize(report)
