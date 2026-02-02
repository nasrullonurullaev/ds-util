from __future__ import annotations

import subprocess
from dataclasses import dataclass

from dsutil.backends.base import Backend, CmdResult


def _run_powershell(command: str, timeout_s: int) -> CmdResult:
    try:
        p = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_s,
            check=False,
        )
        return CmdResult(p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip())
    except FileNotFoundError:
        return CmdResult(127, "", "PowerShell is not available")
    except subprocess.TimeoutExpired:
        return CmdResult(124, "", f"Timeout running: {command}")


@dataclass(frozen=True)
class WindowsBackend(Backend):
    def check_available(self) -> tuple[bool, str]:
        r = _run_powershell("$PSVersionTable.PSVersion.ToString()", timeout_s=5)
        return (r.rc == 0, r.out or r.err)

    def exec(self, target: str, shell_cmd: str, timeout_s: int = 15) -> CmdResult:
        return _run_powershell(shell_cmd, timeout_s=timeout_s)

    def inspect(self, target: str) -> dict:
        return {"target": target, "kind": "host"}

    def logs(self, target: str, tail: int = 400) -> str:
        r = _run_powershell(
            f"Get-EventLog -LogName Application -Newest {int(tail)} | "
            "Select-Object -ExpandProperty Message",
            timeout_s=10,
        )
        return r.out or r.err
