from __future__ import annotations

import argparse
import sys

from dsutil.backends.docker import DockerBackend
from dsutil.collectors.docker_collect import collect_docker_report
from dsutil.collectors.linux_collect import collect_linux_report
from dsutil.output.jsonout import to_json
from dsutil.output.text import print_report


def main() -> None:
    ap = argparse.ArgumentParser(
        prog="dsutil",
        description="ONLYOFFICE DocumentServer diagnostics utility",
    )
    ap.add_argument(
        "--platform",
        required=True,
        choices=["docker", "linux", "windows"],
        help="Execution platform",
    )
    ap.add_argument(
        "--ds",
        default="onlyoffice-documentserver",
        help="Target container name (docker only)",
    )
    ap.add_argument(
        "--json",
        action="store_true",
        help="Print JSON report",
    )
    ap.add_argument(
        "--docker-tail",
        type=int,
        default=400,
        help="How many docker log lines to scan (docker only)",
    )
    ap.add_argument(
        "--file-tail",
        type=int,
        default=800,
        help="How many lines to tail from DS log files",
    )

    args = ap.parse_args()

    if args.platform == "docker":
        backend = DockerBackend()
        report = collect_docker_report(
            backend=backend,
            container=args.ds,
            docker_tail=args.docker_tail,
            file_tail=args.file_tail,
        )

    elif args.platform == "linux":
        # docker-specific args are intentionally ignored
        report = collect_linux_report(file_tail=args.file_tail)

    elif args.platform == "windows":
        print(
            "Windows platform is not implemented yet.\n"
            "Planned support: native DocumentServer for Windows.",
            file=sys.stderr,
        )
        sys.exit(2)

    else:
        # Should never happen because of argparse choices
        print(f"Unknown platform: {args.platform}", file=sys.stderr)
        sys.exit(2)

    if args.json:
        print(to_json(report))
    else:
        print_report(report)
