from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass

from .base import Backend, CmdResult


def _run(cmd: list[str], timeout_s: int) -> CmdResult:
    try:
        p = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_s,
            check=False,
        )
        return CmdResult(p.returncode, p.stdout.strip(), p.stderr.strip())
    except FileNotFoundError:
        return CmdResult(127, "", f"Command not found: {cmd[0]}")
    except subprocess.TimeoutExpired:
        return CmdResult(124, "", f"Timeout running: {' '.join(cmd)}")


@dataclass(frozen=True)
class DockerBackend(Backend):
    def check_available(self) -> tuple[bool, str]:
        r = _run(["docker", "version", "--format", "{{json .}}"], timeout_s=10)
        return (r.rc == 0, r.out or r.err)

    def exec(self, target: str, shell_cmd: str, timeout_s: int = 15) -> CmdResult:
        return _run(["docker", "exec", target, "sh", "-lc", shell_cmd], timeout_s=timeout_s)

    def inspect(self, target: str) -> dict:
        r = _run(["docker", "inspect", target], timeout_s=20)
        if r.rc != 0 or not r.out:
            return {"_error": r.err or r.out or f"inspect failed for {target}"}
        try:
            arr = json.loads(r.out)
            return arr[0] if arr else {}
        except json.JSONDecodeError:
            return {"_error": "invalid JSON from docker inspect", "_raw": r.out[:2000]}

    def logs(self, target: str, tail: int = 400) -> str:
        r = _run(["docker", "logs", "--tail", str(tail), target], timeout_s=20)
        if r.rc != 0:
            return f"[logs error] {r.err or r.out}"
        return r.out
