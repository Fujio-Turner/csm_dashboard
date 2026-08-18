from __future__ import annotations

from csm_dashboard.compose.redact import redact


def test_redact_key_patterns():
    text = "token sk-abcdefghijk and xai-zzzzzzzz Bearer abc api_key=secret password=hunter2"
    out = redact(text)
    assert "sk-abcdefghijk" not in out
    assert "Bearer abc" not in out
    assert "[REDACTED]" in out
