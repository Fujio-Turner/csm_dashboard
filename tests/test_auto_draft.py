from __future__ import annotations

from csm_dashboard.compose.grok import as_addr_list, normalize_draft_fields
from csm_dashboard.compose.auto_draft import (
    addressed_to_operator,
    draft_reply_for_email,
    process_new_emails,
    skip_reason,
)
from csm_dashboard.storage.repo import normalize_coverage


def _mail(**kwargs):
    row = {
        "_id": "em:test1",
        "account_id": "acct:acme",
        "direction": "inbound",
        "from_addr": "pat@acme.com",
        "to_addrs": ["jordan@example.com"],
        "cc_addrs": [],
        "subject": "Help",
        "thread_id": "thr:1",
        "operator": {"unread": True},
        "_new": True,
    }
    row.update(kwargs)
    return row


def test_as_addr_list_accepts_string_object_and_list():
    assert as_addr_list("pat@acme.com") == ["pat@acme.com"]
    assert as_addr_list("a@x.com, b@y.com") == ["a@x.com", "b@y.com"]
    assert as_addr_list({"email": "pat@acme.com"}) == ["pat@acme.com"]
    assert as_addr_list(["pat@acme.com", {"value": "sam@acme.com"}]) == ["pat@acme.com", "sam@acme.com"]
    assert as_addr_list(None) == []
    out = normalize_draft_fields({"to": "pat@acme.com", "cc": "sam@acme.com, riley@example.com", "subject": "Hi"})
    assert out["to"] == ["pat@acme.com"]
    assert out["cc"] == ["sam@acme.com", "riley@example.com"]


def test_coverage_auto_draft_default_off():
    cov = normalize_coverage({})
    assert cov["auto_draft_replies"] is False
    on = normalize_coverage({"auto_draft_replies": True})
    assert on["auto_draft_replies"] is True


def test_addressed_to_operator_uses_to_not_cc():
    me = "jordan@example.com"
    assert addressed_to_operator(_mail(to_addrs=["jordan@example.com"]), me)
    assert not addressed_to_operator(_mail(to_addrs=["pat@acme.com"], cc_addrs=["jordan@example.com"]), me)
    assert not addressed_to_operator(_mail(to_addrs=["other@acme.com"]), me)


def test_skip_reason_gates(repo):
    repo.create_account({"name": "Acme", "slug": "acme", "abbr": "ACME", "color": "#0B3D91"})
    repo.save_settings({"operator": {"email": "jordan@example.com"}})
    mail = _mail()
    assert skip_reason(repo, mail) == "off"
    repo.patch_account("acct:acme", {"coverage": {"auto_draft_replies": True}})
    assert skip_reason(repo, mail) == ""
    assert skip_reason(repo, _mail(direction="outbound")) == "outbound"
    assert skip_reason(repo, _mail(from_addr="jordan@example.com")) == "from_self"
    assert skip_reason(repo, _mail(to_addrs=["pat@acme.com"], cc_addrs=["jordan@example.com"])) == "not_to_me"
    assert skip_reason(repo, _mail(from_addr="noreply@acme.com")) == "noreply"
    assert skip_reason(repo, _mail(operator={"auto_draft_id": "draft:x"})) == "already"


def test_process_new_emails_drafts_when_on(repo, monkeypatch):
    repo.create_account(
        {
            "name": "Acme",
            "slug": "acme",
            "abbr": "ACME",
            "color": "#0B3D91",
            "coverage": {"auto_draft_replies": True},
        }
    )
    repo.save_settings({"operator": {"email": "jordan@example.com"}})
    saved = repo.upsert_email(
        {
            "account_id": "acct:acme",
            "message_id": "<in@acme.com>",
            "direction": "inbound",
            "from_addr": "pat@acme.com",
            "to_addrs": ["jordan@example.com"],
            "subject": "Need a date",
            "sent_at": "2026-09-03T15:00:00Z",
            "snippet": "When can we talk?",
            "body_text": "When can we talk?",
        }
    )
    monkeypatch.setattr(
        "csm_dashboard.compose.auto_draft.resolve_ai_client",
        lambda *a, **k: object(),
    )
    monkeypatch.setattr(
        "csm_dashboard.compose.auto_draft.compose_with_grok",
        lambda *a, **k: ({"subject": "Re: Need a date", "body": "Tuesday works.", "to": ["pat@acme.com"], "cc": []}, "grok-4.6"),
    )
    monkeypatch.setattr(
        "csm_dashboard.compose.auto_draft.sync_gmail_draft",
        lambda repo, doc: {**doc, "gmail": {"ok": True, "gmail_draft_id": "r1"}},
    )
    monkeypatch.setattr("csm_dashboard.compose.auto_draft.selected_provider", lambda *a, **k: "grok")
    out = process_new_emails(repo, [saved])
    assert out["created"] == 1
    drafts = repo.list_drafts("acct:acme")
    assert len(drafts) == 1
    assert drafts[0]["subject"].startswith("Re:")
    mail = repo.get_email(saved["_id"])
    assert (mail.get("operator") or {}).get("auto_draft_id") == drafts[0]["_id"]
    again = process_new_emails(repo, [{**saved, "_new": True, "operator": mail.get("operator")}])
    assert again["created"] == 0


def test_draft_reply_skips_without_ai(repo):
    repo.create_account(
        {
            "name": "Acme",
            "slug": "acme",
            "abbr": "ACME",
            "color": "#0B3D91",
            "coverage": {"auto_draft_replies": True},
        }
    )
    repo.save_settings({"operator": {"email": "jordan@example.com"}})
    mail = repo.upsert_email(
        {
            "account_id": "acct:acme",
            "message_id": "<noai@acme.com>",
            "direction": "inbound",
            "from_addr": "pat@acme.com",
            "to_addrs": ["jordan@example.com"],
            "subject": "Ping",
            "sent_at": "2026-09-03T16:00:00Z",
        }
    )
    assert draft_reply_for_email(repo, mail) is None
    assert repo.list_drafts("acct:acme") == []
