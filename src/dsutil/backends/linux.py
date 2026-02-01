from __future__ import annotations

import os
import shlex
import subprocess
from dataclasses import dataclass

from dsutil.backends.base import Backend, CmdResult


class LinuxBackend(Backend):
    """Backend for native Linux installations (systemd).
    The 'target' argument is ignored; commands run on the local host.
    """

    def check_available(self) -> tuple[bool, str]:
        # Minimal sanity: we need a shell and systemctl for service checks.
        ok = (self.exec("host", "command -v systemctl >/dev/null 2>&1").rc == 0)
        return (ok, "systemctl found" if ok else "systemctl not found (systemd required)")

    def exec(self, target: str, shell_cmd: str, timeout_s: int = 15) -> CmdResult:
        try:
            p = subprocess.run(
                shell_cmd,
                shell=True,
                text=True,
                capture_output=True,
                timeout=timeout_s,
                env=os.environ.copy(),
            )
            return CmdResult(p.returncode, p.stdout or "", p.stderr or "")
        except subprocess.TimeoutExpired as e:
            return CmdResult(124, e.stdout or "", e.stderr or "timeout")
        except Exception as e:
            return CmdResult(1, "", str(e))

    def inspect(self, target: str) -> dict:
        # No container metadata on native Linux.
        return {
            "target": target,
            "kind": "host",
        }

    def logs(self, target: str, tail: int = 400) -> str:
        # Generic system logs hint (not DS logs). Keep it simple.
        # Collector should read DS log files directly.
        r = self.exec("host", f"journalctl -n {int(tail)} --no-pager 2>/dev/null || true", timeout_s=10)
        return r.out or r.err
