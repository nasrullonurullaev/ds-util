from __future__ import annotations

import re

REDACT_KEYS = ("JWT_SECRET", "SECRET", "PASSWORD", "PASS", "TOKEN", "KEY")


def redact_env(env_list: list[str]) -> list[str]:
    redacted: list[str] = []
    for item in env_list:
        if "=" not in item:
            redacted.append(item)
            continue
        k, v = item.split("=", 1)
        if any(key in k.upper() for key in REDACT_KEYS):
            redacted.append(f"{k}=***REDACTED***")
        else:
            # redact creds in URLs like amqp://user:pass@host
            v2 = re.sub(r"(://[^:/\s]+:)([^@/\s]+)(@)", r"\1***REDACTED***\3", v)
            redacted.append(f"{k}={v2}")
    return redacted
