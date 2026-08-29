from __future__ import annotations

from csm_dashboard.storage.paging import row_matches
from csm_dashboard.storage.repo import EMAIL_LIST_OMIT, TICKET_LIST_OMIT


def test_row_matches_nested_and_or():
    row = {"operator": {"unread": True, "task": False}, "status": "open", "priority": "p1"}
    assert row_matches(row, {"truthy": ["operator.unread"]})
    assert row_matches(row, {"in": {"status": ["open", "waiting"]}})
    assert row_matches(row, {"or_truthy": [["operator.unread", "operator.task"]]})
    assert not row_matches(row, {"eq": {"priority": "p2"}})
    ignored = {"operator": {"unread": True, "ignore": True}}
    assert not row_matches(ignored, {"not_true": ["operator.ignore"]})


def test_email_list_is_slim(client):
    client.post("/api/settings/seed")
    emails = client.get("/api/emails", params={"account_id": "acct:acme"}).json()["items"]
    assert emails
    assert "body_text" not in emails[0]
    for key in EMAIL_LIST_OMIT:
        assert key not in emails[0]
    tickets = client.get("/api/tickets", params={"account_id": "acct:acme"}).json()["items"]
    assert tickets
    for key in TICKET_LIST_OMIT:
        assert key not in tickets[0]
    thread_id = emails[0].get("thread_id")
    assert thread_id
    full = client.get(f"/api/threads/{thread_id}", params={"include": "messages"}).json()
    msgs = full.get("messages") or []
    assert msgs
    assert any(m.get("body_text") or m.get("snippet") for m in msgs)


def test_account_counts_are_cached_and_positive(client):
    client.post("/api/settings/seed")
    acct = client.get("/api/accounts/by-abbr/acme").json()
    counts = acct.get("input_counts") or {}
    assert counts.get("tickets", 0) >= 1
    assert counts.get("email", 0) >= 1
    assert counts.get("people", 0) >= 1
    assert counts.get("refreshed_at")
    agenda = client.get("/api/home/agenda", params={"date": "2026-08-18"}).json()
    inbox = agenda.get("inbox") or []
    assert inbox
    assert all(item.get("audience") in {"me", "us", "them", "all", "unknown", "na"} for item in inbox)
