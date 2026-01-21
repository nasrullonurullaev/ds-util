from __future__ import annotations

from dsutil.core.models import Report

def print_report(report: Report) -> None:
    print(f"dsutil report @ {report.timestamp_utc}")
    print(f"Platform: {report.platform} | Target: {report.target}")
    worst = "info"
    for i in report.issues:
        if i.severity == "crit":
            worst = "crit"
            break
        if i.severity == "warn":
            worst = "warn"
    print(f"Issues: {len(report.issues)} (worst: {worst})\n")

    print("Checks:")
    for c in report.checks:
        tag = "OK" if c.ok else "FAIL"
        print(f"- [{tag}] {c.name}: {c.command}")
        if not c.ok and c.output:
            txt = str(c.output)
            print(f"  output: {txt[:400]}")

    print("\nIssues:")
    if not report.issues:
        print("- none ✅")
        return
    for i in report.issues:
        print(f"- [{i.severity}] {i.title}")
        print(f"  hint: {i.hint}")
