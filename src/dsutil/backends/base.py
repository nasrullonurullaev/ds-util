from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class CmdResult:
    rc: int
    out: str
    err: str


class Backend(ABC):
    @abstractmethod
    def check_available(self) -> tuple[bool, str]:
        ...

    @abstractmethod
    def exec(self, target: str, shell_cmd: str, timeout_s: int = 15) -> CmdResult:
        """Run a shell command *inside* the target (container/host)."""
        ...

    @abstractmethod
    def inspect(self, target: str) -> dict:
        ...

    @abstractmethod
    def logs(self, target: str, tail: int = 400) -> str:
        ...
