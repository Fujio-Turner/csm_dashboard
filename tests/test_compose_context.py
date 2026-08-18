from __future__ import annotations

from csm_dashboard.compose.context import build_compose_context


def test_huge_body_never_reaches_context(repo):
    repo.create_account({"name": "Acme", "slug": "acme", "abbr": "ACME", "color": "#0B3D91"})
    huge = "X" * (200 * 1024)
    repo.upsert_email(
        {
            "account_id": "acct:acme",
            "message_id": "<huge@acme.com>",
            "from_addr": "pat@acme.com",
            "to_addrs": ["jordan@example.com"],
            "subject": "Huge",
            "sent_at": "2026-08-17T10:00:00Z",
            "snippet": "short snippet only",
            "body_text": huge,
            "body_bytes": len(huge),
        }
    )
    ctx = build_compose_context(repo, "acct:acme", max_chars=24000)
    blob = ctx.serialized()
    assert huge not in blob
    assert "X" * 600 not in blob
    assert len(blob) <= 24000
