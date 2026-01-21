from __future__ import annotations

import json
from dataclasses import asdict

from dsutil.core.models import Report

def to_json(report: Report) -> str:
    return json.dumps(asdict(report), indent=2, ensure_ascii=False)
