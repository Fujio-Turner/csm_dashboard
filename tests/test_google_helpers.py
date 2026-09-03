from __future__ import annotations

import json

from csm_dashboard.connectors.google_cal import cal_time, map_event
from csm_dashboard.connectors.google_mail import (
    gmail_body,
    gmail_search_query,
    google_draft_ready,
    google_send_ready,
    header_time,
    map_gmail_message,
)
from csm_dashboard.connectors.google_secrets import hydrate_google, load_google_client
from csm_dashboard.connectors.http import HttpError
from csm_dashboard.storage.memory import MemoryStore
from csm_dashboard.storage.repo import CsmRepo


def test_gmail_search_query_scopes_customer_domains():
    q = gmail_search_query("2026-08-01T00:00:00Z", ["acme.com", "@acme.com"])
    assert "after:2026/08/01" in q
    assert "-in:chats" in q
    assert "from:acme.com" in q
    assert "to:acme.com" in q
    assert "cc:acme.com" in q
    assert q.count("from:acme.com") == 1
    bare = gmail_search_query("2026-08-19T00:00:00Z", [])
    assert "after:2026/08/19" in bare
    assert "from:" not in bare
    windowed = gmail_search_query(None, ["acme.com"], days=90)
    assert "from:acme.com" in windowed
    assert "after:" in windowed


def test_gmail_scope_gates_send_and_drafts(repo):
    repo.put_credential_secret("connector", "google", {"access_token": "ya29", "refresh_token": "1//r", "scope": "https://www.googleapis.com/auth/gmail.send"})
    assert google_send_ready(repo) is True
    assert google_draft_ready(repo) is False
    repo.put_credential_secret("connector", "google", {"access_token": "ya29", "refresh_token": "1//r", "scope": "https://www.googleapis.com/auth/gmail.compose"})
    assert google_send_ready(repo) is True
    assert google_draft_ready(repo) is True


def test_gmail_multipart_plain_and_sent_direction():
    payload = {
        "mimeType": "multipart/alternative",
        "parts": [
            {
                "mimeType": "text/plain",
                "body": {"data": "UGxhaW4gYm9keQ=="},
            },
            {
                "mimeType": "text/html",
                "body": {"data": "PHA+SFRNTDwvcD4="},
            },
        ],
    }
    assert "Plain body" in gmail_body(payload)
    mapped = map_gmail_message(
        {
            "id": "abc",
            "threadId": "t",
            "labelIds": ["SENT"],
            "snippet": "hi",
            "payload": {
                "headers": [
                    {"name": "From", "value": "me@example.com"},
                    {"name": "To", "value": "pat@acme.com"},
                    {"name": "Subject", "value": ""},
                ],
                "parts": payload["parts"],
            },
        }
    )
    assert mapped["direction"] == "outbound"
    assert mapped["subject"] == "(No subject)"
    assert mapped["message_id"].startswith("<gmail.abc@")
    named = map_gmail_message(
        {
            "id": "named",
            "threadId": "t",
            "snippet": "hi",
            "payload": {
                "headers": [
                    {"name": "From", "value": '"Moyerman, Joshua" <joshua.moyerman@acme.com>'},
                    {"name": "To", "value": "you@example.com"},
                    {"name": "Subject", "value": "Hello"},
                ]
            },
        }
    )
    assert named["from_addr"] == "joshua.moyerman@acme.com"
    assert named["from_name"] == "Moyerman, Joshua"


def test_gmail_header_time_and_html_only():
    assert header_time("").endswith("Z")
    assert header_time("not a date").endswith("Z")
    iso = header_time("Thu, 20 Aug 2026 12:00:00 +0000")
    assert iso.startswith("2026-08-20T12:00:00")
    html = gmail_body({"mimeType": "text/html", "body": {"data": "PHA+SGk8L3A+"}})
    assert html == "Hi"
    assert gmail_body(None) == ""
    assert gmail_body({"mimeType": "text/plain"}) == ""


def test_cal_time_all_day_and_skip_blank_attendees():
    assert cal_time({}) == ""
    assert cal_time({"date": "2026-08-20"}) == "2026-08-20T00:00:00Z"
    assert cal_time({"dateTime": "2026-08-20T16:00:00+00:00"}).endswith("Z")
    payload = map_event(
        {
            "id": "e1",
            "summary": "Standup",
            "start": {"date": "2026-08-21"},
            "end": {"date": "2026-08-21"},
            "attendees": [{"displayName": "No email"}, {"email": "pat@acme.com"}],
            "hangoutLink": "https://meet.google.com/x",
        }
    )
    assert payload["start_at"].startswith("2026-08-21")
    assert payload["attendees"] == [{"email": "pat@acme.com", "name": ""}]
    assert "meet.google.com" in payload["location"]


def test_load_installed_client_and_skip_bad_files(tmp_path, monkeypatch):
    from csm_dashboard.connectors import google_secrets

    bad = tmp_path / "bad.json"
    bad.write_text("{not-json", encoding="utf-8")
    good = tmp_path / "ok.json"
    good.write_text(
        json.dumps({"installed": {"client_id": "installed-id", "client_secret": "sec"}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("GOOGLE_CLIENT_SECRETS", str(bad))
    assert load_google_client() == {}
    monkeypatch.setenv("GOOGLE_CLIENT_SECRETS", str(good))
    loaded = load_google_client()
    assert loaded["client_id"] == "installed-id"
    assert loaded["label"] == good.name


def test_hydrate_keeps_existing_client_id(tmp_path, monkeypatch):
    path = tmp_path / "credentials.json"
    path.write_text(json.dumps({"web": {"client_id": "file-id", "client_secret": "file-sec"}}), encoding="utf-8")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRETS", str(path))
    repo = CsmRepo(MemoryStore())
    repo.put_credential_secret("connector", "google", {"client_id": "already", "client_secret": "kept"})
    out = hydrate_google(repo)
    assert out["found"] is True
    secret = repo.get_credential_secret("connector", "google")
    assert secret["client_id"] == "already"
    assert secret["client_secret"] == "kept"


def test_google_cal_sync_mocked(client, repo, monkeypatch):
    client.post("/api/settings/seed")
    repo.put_credential_secret("connector", "google", {"access_token": "ya29", "refresh_token": "1//r"})
    client.put("/api/settings", json={"connectors": {"google_cal": {"mode": "live"}}})

    def fake_token(vendor, repo, force=False):
        return "ya29"

    def fake_get(url, headers=None, params=None, **kwargs):
        if "calendarList" in url:
            return {"items": [{"id": "primary"}]}
        if url.endswith("/events"):
            return {
                "items": [
                    {
                        "id": "evt-live",
                        "summary": "ACME live cal",
                        "start": {"dateTime": "2026-08-28T16:00:00Z"},
                        "end": {"dateTime": "2026-08-28T17:00:00Z"},
                        "attendees": [{"email": "pat.nguyen@acme.com", "displayName": "Pat"}],
                    }
                ]
            }
        return {"items": []}

    monkeypatch.setattr("csm_dashboard.connectors.oauth.ensure_access_token", fake_token)
    monkeypatch.setattr("csm_dashboard.connectors.google_cal.json_get", fake_get)
    job = client.post("/api/connectors/google_cal/sync", json={})
    assert job.json()["status"] == "done"
    rows = client.get("/api/calendar", params={"account_id": "acct:acme"}).json()["items"]
    assert any(r.get("external_id") == "evt-live" for r in rows)


def test_gmail_probe_401_retries(monkeypatch, repo):
    from csm_dashboard.connectors.google_mail import GmailConnector

    repo.put_credential_secret("connector", "google", {"access_token": "old", "refresh_token": "rt"})
    calls = {"n": 0}

    def fake_get(url, headers=None, params=None, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise HttpError(401)
        return {"emailAddress": "ada@example.com"}

    monkeypatch.setattr("csm_dashboard.connectors.google_mail.json_get", fake_get)
    monkeypatch.setattr("csm_dashboard.connectors.oauth.ensure_access_token", lambda *a, **k: "new")
    health = GmailConnector(repo).probe()
    assert health["ok"] is True
    assert health["email"] == "ada@example.com"


def test_gmail_pull_uses_metadata_format(monkeypatch, repo):
    from csm_dashboard.connectors.google_mail import GmailConnector

    repo.put_credential_secret("connector", "google", {"access_token": "ya29", "refresh_token": "rt"})
    calls = []

    def fake_get(url, headers=None, params=None, **kwargs):
        calls.append((url, params))
        if str(url).endswith("/messages"):
            return {"messages": [{"id": "m1"}]}
        return {
            "id": "m1",
            "threadId": "t",
            "snippet": "hi from acme",
            "payload": {
                "headers": [
                    {"name": "From", "value": "pat@acme.com"},
                    {"name": "To", "value": "you@example.com"},
                    {"name": "Subject", "value": "Hello"},
                    {"name": "Date", "value": "Tue, 1 Sep 2026 12:00:00 +0000"},
                    {"name": "Message-ID", "value": "<m1@acme.com>"},
                ]
            },
        }

    monkeypatch.setattr("csm_dashboard.connectors.google_mail.json_get", fake_get)
    monkeypatch.setattr("csm_dashboard.connectors.oauth.ensure_access_token", lambda *a, **k: "ya29")
    events = GmailConnector(repo).pull(
        None, {"domains": ["acme.com"], "coverage": {"lookback_days": 14}}
    )
    assert len(events) == 1
    assert events[0]["payload"]["from_addr"] == "pat@acme.com"
    meta = [p for _url, p in calls if isinstance(p, dict) and p.get("format") == "metadata"]
    assert meta
    assert "From" in (meta[0].get("metadataHeaders") or [])
