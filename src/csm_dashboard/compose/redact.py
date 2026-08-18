from __future__ import annotations

import re

_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9]{8,}"),
    re.compile(r"xai-[A-Za-z0-9]{8,}"),
    re.compile(r"Bearer\s+\S+", re.I),
    re.compile(r"api_key=\S+", re.I),
    re.compile(r"password=\S+", re.I),
)


def redact(text: str) -> str:
    out = text or ""
    for pat in _PATTERNS:
        out = pat.sub("[REDACTED]", out)
    return out
