from __future__ import annotations

from csm_dashboard.compose.context import REPLY_MAX_CHARS, build_compose_context


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


def test_reply_context_is_this_thread_not_the_mailbox(repo):
    repo.create_account(
        {
            "name": "Acme",
            "slug": "acme",
            "abbr": "ACME",
            "color": "#0B3D91",
            "health": {"score": 72, "status": "watch", "notes": "SECRET_HEALTH_DUMP"},
            "contract": {"renewal_on": "2027-01-01", "secret": "SECRET_CONTRACT"},
            "team": {"account": [{"person_id": "person:csm01", "name": "Jordan Lee"}]},
        }
    )
    repo.save_settings({"operator": {"name": "Alex Rivera", "email": "alex@acme.com"}})
    inbound = repo.upsert_email(
        {
            "account_id": "acct:acme",
            "message_id": "<in@acme.com>",
            "thread_id": "thr:keep",
            "from_addr": "pat@acme.com",
            "to_addrs": ["alex@acme.com"],
            "subject": "Need a date",
            "sent_at": "2026-09-03T15:00:00Z",
            "snippet": "When can we talk?",
            "body_text": "When can we talk about the rollout?",
        }
    )
    for i in range(12):
        repo.upsert_email(
            {
                "account_id": "acct:acme",
                "message_id": f"<other-{i}@acme.com>",
                "thread_id": "thr:other",
                "from_addr": "other@acme.com",
                "to_addrs": ["alex@acme.com"],
                "subject": "Noise",
                "sent_at": f"2026-08-0{(i % 9) + 1}T10:00:00Z",
                "snippet": "SECRET_OTHER_THREAD",
                "body_text": "SECRET_OTHER_THREAD body",
            }
        )
    op = repo.operator_profile()
    ctx = build_compose_context(
        repo,
        "acct:acme",
        thread_id="thr:keep",
        inbound=inbound,
        operator=op,
        mode="reply",
    )
    blob = ctx.serialized()
    assert "SECRET_OTHER_THREAD" not in blob
    assert "SECRET_HEALTH_DUMP" not in blob
    assert "SECRET_CONTRACT" not in blob
    assert "Jordan Lee" not in blob
    assert ctx.payload["operator"]["name"] == "Alex Rivera"
    assert ctx.payload["operator"]["email"] == "alex@acme.com"
    assert ctx.payload["account"].get("team") is None
    assert "contract" not in ctx.payload["account"]
    assert ctx.payload["slack"] == []
    assert ctx.payload["teams"] == []
    assert ctx.payload["calendar"] == []
    assert ctx.payload["inbound"]["from_addr"] == "pat@acme.com"
    assert len(blob) <= REPLY_MAX_CHARS
    assert len(ctx.payload["thread"]) <= 8


def test_operator_profile_prefers_settings_over_seed(repo):
    repo.save_settings({"operator": {"name": "Alex Rivera", "email": "alex@acme.com"}})
    op = repo.operator_profile()
    assert op["name"] == "Alex Rivera"
    assert op["email"] == "alex@acme.com"
    repo.save_settings({"operator": {"name": "", "email": "alex.rivera@acme.com"}})
    op = repo.operator_profile()
    assert op["email"] == "alex.rivera@acme.com"
    assert "Alex" in op["name"]
    assert op["name"] != "Jordan Lee"
