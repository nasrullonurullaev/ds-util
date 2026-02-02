from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from dsutil.backends.base import Backend
from dsutil.backends.windows import WindowsBackend
from dsutil.core.models import CheckResult, Issue, Report
from dsutil.core.report import finalize
from dsutil.core.rules import default_rules, scan_text

TARGET_HOST = "host"
LOG_BASE = Path(r"C:\Program Files\ONLYOFFICE\DocumentServer\Log")

REQUIRED_SERVICES = ["DsConverterSvc", "DsDocServiceSvc"]
OPTIONAL_SERVICES = ["DsAdminPanelSvc", "DsExampleSvc", "DsProxySvc"]
DEPENDENCY_SERVICES = ["RabbitMQ", "postgresql-x64-18", "Redis"]

LOG_TARGETS = [
    LOG_BASE / "adminpanel" / "out.log",
    LOG_BASE / "adminpanel" / "err.log",
    LOG_BASE / "converter" / "out.log",
    LOG_BASE / "converter" / "err.log",
    LOG_BASE / "docservice" / "out.log",
    LOG_BASE / "docservice" / "err.log",
    LOG_BASE / "example" / "out.log",
    LOG_BASE / "example" / "err.log",
    LOG_BASE / "nginx" / "nginx.error.log",
]


def _service_status(backend: Backend, target: str, service_name: str) -> tuple[bool, str]:
    cmd = (
        f"try {{ "
        f"(Get-Service -Name '{service_name}' -ErrorAction Stop).Status.ToString() "
        f"}} catch {{ $_.Exception.Message; exit 1 }}"
    )
    r = backend.exec(target, cmd, timeout_s=10)
    status = (r.out or r.err or "").strip()
    ok = r.rc == 0 and status.lower() == "running"
    return ok, status or f"rc={r.rc}"


def _service_missing(status: str) -> bool:
    lowered = status.lower()
    return "cannot find any service" in lowered or "service was not found" in lowered


def _tail_file(backend: Backend, target: str, path: Path, lines: int) -> tuple[bool, str]:
    cmd = (
        f"if (Test-Path -LiteralPath '{path}') "
        f"{{ Get-Content -LiteralPath '{path}' -Tail {int(lines)} }} else {{ '' }}"
    )
    r = backend.exec(target, cmd, timeout_s=10)
    exists = backend.exec(target, f"Test-Path -LiteralPath '{path}'", timeout_s=5).rc == 0
    return exists, (r.out or "").strip()


def collect_windows_report(file_tail: int = 800) -> Report:
    ts = datetime.now(timezone.utc).isoformat()
    report = Report(tool="dsutil", timestamp_utc=ts, platform="windows", target=TARGET_HOST)

    backend = WindowsBackend()
    ok, info = backend.check_available()
    if not ok:
        report.add_issue(Issue("crit", "Windows backend is not available", info))
        return finalize(report)

    # Health endpoint
    h = backend.exec(
        TARGET_HOST,
        "try { "
        "(Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 http://localhost:8000/info/info.json).StatusCode "
        "} catch { $_.Exception.Message; exit 1 }",
        timeout_s=10,
    )
    ok_health = h.rc == 0 and (h.out or "").strip() == "200"
    report.add_check(
        CheckResult(
            "health_endpoint",
            ok_health,
            "Invoke-WebRequest http://localhost:8000/info/info.json",
            h.out or h.err,
        )
    )
    if not ok_health:
        report.add_issue(Issue("crit", "Health endpoint check failed", "Check nginx/docservice/converter status and logs."))

    # Required services
    for svc in REQUIRED_SERVICES:
        ok_svc, status = _service_status(backend, TARGET_HOST, svc)
        report.add_check(CheckResult(f"service_{svc}", ok_svc, f"Get-Service {svc}", status))
        if not ok_svc:
            report.add_issue(Issue("crit", f"Required service not running: {svc}", "Check Windows Service status and logs."))

    # Optional services
    for svc in OPTIONAL_SERVICES:
        ok_svc, status = _service_status(backend, TARGET_HOST, svc)
        report.add_check(CheckResult(f"service_{svc}", ok_svc, f"Get-Service {svc}", status))
        if not ok_svc:
            report.add_issue(Issue("warn", f"Optional service not running: {svc}", "This service is optional; enable if needed."))

    # Dependency services
    for svc in DEPENDENCY_SERVICES:
        ok_svc, status = _service_status(backend, TARGET_HOST, svc)
        report.add_check(CheckResult(f"service_{svc}", ok_svc, f"Get-Service {svc}", status))
        if not ok_svc:
            if _service_missing(status):
                report.add_issue(Issue("warn", f"Dependency service missing: {svc}", "Service is not installed; install it if required by your configuration."))
            else:
                report.add_issue(Issue("crit", f"Dependency service not running: {svc}", "Ensure the service is installed and running."))

    # Logs scan
    rules = default_rules()
    for path in LOG_TARGETS:
        exists, content = _tail_file(backend, TARGET_HOST, path, file_tail)
        if exists and content:
            for i in scan_text(content, rules):
                report.add_issue(i)

    return finalize(report)
