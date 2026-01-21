from __future__ import annotations

import argparse
import sys

from dsutil.backends.docker import DockerBackend
from dsutil.collectors.docker_collect import collect_docker_report
from dsutil.output.jsonout import to_json
from dsutil.output.text import print_report


def main() -> None:
    ap = argparse.ArgumentParser(
        prog="dsutil",
        description="ONLYOFFICE DocumentServer diagnostics utility",
    )
    ap.add_argument(
        "--platform",
        default="docker",
        choices=["auto", "docker", "linux", "windows"],
        help="Execution platform",
    )
    ap.add_argument(
        "--ds",
        default="onlyoffice-documentserver",
        help="Target container name (docker)",
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
        help="How many docker log lines to scan",
    )
    ap.add_argument(
        "--file-tail",
        type=int,
        default=800,
        help="How many lines to tail from DS log files",
    )

    args = ap.parse_args()

    # Only docker is implemented for now
    if args.platform not in ("auto", "docker"):
        print(
            f"Platform '{args.platform}' is not implemented yet. "
            f"Use --platform docker.",
            file=sys.stderr,
        )
        sys.exit(2)

    backend = DockerBackend()
    report = collect_docker_report(
        backend=backend,
        container=args.ds,
        docker_tail=args.docker_tail,
        file_tail=args.file_tail,
    )

    if args.json:
        print(to_json(report))
    else:
        print_report(report)
