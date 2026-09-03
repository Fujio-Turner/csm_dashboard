from __future__ import annotations

import httpx
import pytest

from csm_dashboard.connectors.http import HttpError
from csm_dashboard.connectors.refresh import min_refresh_minutes, refresh_due, run_google_refresh
from csm_dashboard.storage.repo import refresh_minutes


def test_refresh_minutes_default_and_clamp(repo):
    bare = repo.create_account({"name": "Acme", "slug": "acme", "abbr": "ACME", "color": "#0B3D91"})
    assert bare["coverage"]["refresh_minutes"] == 5
    assert refresh_minutes(bare) == 5
    tight = repo.create_account(
        {
            "name": "North",
            "slug": "nwin",
            "abbr": "NWIN",
            "color": "#14532d",
            "coverage": {"mode": "new", "refresh_minutes": 0, "feeds": ["google_mail"]},
        }
    )
    assert refresh_minutes(tight) == 1
    wide = repo.patch_account("acct:acme", {"coverage": {"refresh_minutes": 2000}})
    assert wide["coverage"]["refresh_minutes"] == 1440
    assert wide["coverage"]["mode"] == "view"


def test_min_refresh_minutes_uses_shortest_gmail_or_cal_book(repo):
    repo.create_account(
        {
            "name": "Acme",
            "slug": "acme",
            "abbr": "ACME",
            "color": "#0B3D91",
            "domains": ["acme.com"],
            "coverage": {"mode": "new", "feeds": ["google_mail"], "refresh_minutes": 15},
        }
    )
    repo.create_account(
        {
            "name": "Globex",
            "slug": "globex",
            "abbr": "GLX",
            "color": "#7B1E3A",
            "domains": ["globex.test"],
            "coverage": {"mode": "new", "feeds": ["google_cal"], "refresh_minutes": 5},
        }
    )
    repo.create_account(
        {
            "name": "Skip",
            "slug": "skip",
            "abbr": "SKIP",
            "color": "#333333",
            "coverage": {"mode": "new", "feeds": ["jira"], "refresh_minutes": 1},
        }
    )
    assert min_refresh_minutes(repo) == 5


def test_refresh_due_without_live_google_is_false(repo):
    repo.create_account(
        {
            "name": "Acme",
            "slug": "acme",
            "abbr": "ACME",
            "color": "#0B3D91",
            "domains": ["acme.com"],
            "coverage": {"mode": "new", "feeds": ["google_mail"], "refresh_minutes": 5},
        }
    )
    assert refresh_due(repo) is False


def test_refresh_endpoint_empty_when_connectors_disabled(client):
    res = client.post("/api/sync/refresh")
    assert res.status_code == 200
    assert res.json()["jobs"] == []
    assert run_google_refresh(client.app.state.repo) == []


def test_gmail_history_incremental_and_stale_fallback(monkeypatch, repo):
    from csm_dashboard.connectors.google_mail import GmailConnector

    repo.put_credential_secret("connector", "google", {"access_token": "ya29", "refresh_token": "rt"})
    repo.put_sync_cursor("google_mail", {"history_id": "10", "pulled_at": "2026-09-01T00:00:00Z"})
    repo.create_account(
        {
            "name": "Acme",
            "slug": "acme",
            "abbr": "ACME",
            "color": "#0B3D91",
            "domains": ["acme.com"],
        }
    )
    calls = []

    def fake_get(url, headers=None, params=None, **kwargs):
        calls.append((url, params))
        if "/history" in str(url):
            return {
                "historyId": "11",
                "history": [{"messagesAdded": [{"message": {"id": "m2"}}]}],
            }
        if str(url).endswith("/m2") or "/messages/m2" in str(url):
            return {
                "id": "m2",
                "threadId": "t",
                "snippet": "hi",
                "payload": {
                    "headers": [
                        {"name": "From", "value": "pat@acme.com"},
                        {"name": "To", "value": "you@example.com"},
                        {"name": "Subject", "value": "Later"},
                        {"name": "Message-ID", "value": "<m2@acme.com>"},
                    ]
                },
            }
        return {}

    monkeypatch.setattr("csm_dashboard.connectors.google_mail.json_get", fake_get)
    monkeypatch.setattr("csm_dashboard.connectors.oauth.ensure_access_token", lambda *a, **k: "ya29")
    events = GmailConnector(repo).pull(None, None)
    assert len(events) == 1
    assert events[0]["payload"]["subject"] == "Later"
    assert repo.get_sync_cursor("google_mail")["history_id"] == "11"
    assert any("/history" in str(u) for u, _p in calls)

    def stale_get(url, headers=None, params=None, **kwargs):
        if "/history" in str(url):
            raise HttpError(404)
        if str(url).endswith("/messages"):
            return {"messages": [{"id": "m3"}]}
        if "/profile" in str(url):
            return {"historyId": "30"}
        return {
            "id": "m3",
            "threadId": "t",
            "snippet": "backfill",
            "payload": {
                "headers": [
                    {"name": "From", "value": "pat@acme.com"},
                    {"name": "To", "value": "you@example.com"},
                    {"name": "Subject", "value": "Backfill"},
                    {"name": "Message-ID", "value": "<m3@acme.com>"},
                ]
            },
        }

    monkeypatch.setattr("csm_dashboard.connectors.google_mail.json_get", stale_get)
    again = GmailConnector(repo).pull(None, None)
    assert any(e["payload"]["subject"] == "Backfill" for e in again)
    assert repo.get_sync_cursor("google_mail")["history_id"] == "30"


def test_calendar_sync_token_and_410_fallback(monkeypatch, repo):
    from csm_dashboard.connectors.google_cal import GoogleCalConnector

    repo.put_credential_secret("connector", "google", {"access_token": "ya29", "refresh_token": "rt"})
    repo.put_sync_cursor("google_cal", {"sync_token": "abc", "pulled_at": "2026-09-01T00:00:00Z"})

    def fake_get(url, headers=None, params=None, **kwargs):
        params = params or {}
        if params.get("syncToken") == "abc":
            return {
                "nextSyncToken": "def",
                "items": [
                    {
                        "id": "evt-2",
                        "status": "cancelled",
                        "summary": "Cancelled",
                        "start": {"dateTime": "2026-09-03T16:00:00Z"},
                        "end": {"dateTime": "2026-09-03T17:00:00Z"},
                        "attendees": [{"email": "pat@acme.com"}],
                    }
                ],
            }
        return {"items": []}

    monkeypatch.setattr("csm_dashboard.connectors.google_cal.json_get", fake_get)
    monkeypatch.setattr("csm_dashboard.connectors.oauth.ensure_access_token", lambda *a, **k: "ya29")
    events = GoogleCalConnector(repo).pull(None, None)
    assert len(events) == 1
    assert events[0]["payload"]["status"] == "cancelled"
    assert repo.get_sync_cursor("google_cal")["sync_token"] == "def"

    def gone(url, headers=None, params=None, **kwargs):
        params = params or {}
        if params.get("syncToken"):
            raise HttpError(410)
        return {
            "nextSyncToken": "ghi",
            "items": [
                {
                    "id": "evt-3",
                    "status": "confirmed",
                    "summary": "Fresh",
                    "start": {"dateTime": "2026-09-04T16:00:00Z"},
                    "end": {"dateTime": "2026-09-04T17:00:00Z"},
                    "attendees": [{"email": "pat@acme.com"}],
                }
            ],
        }

    monkeypatch.setattr("csm_dashboard.connectors.google_cal.json_get", gone)
    fresh = GoogleCalConnector(repo).pull(None, None)
    assert any(e["payload"].get("title") == "Fresh" for e in fresh)
    assert repo.get_sync_cursor("google_cal")["sync_token"] == "ghi"


def test_calendar_mailbox_seeds_token_and_window(monkeypatch, repo):
    from csm_dashboard.connectors.google_cal import GoogleCalConnector

    repo.put_credential_secret("connector", "google", {"access_token": "ya29", "refresh_token": "rt"})
    calls = []

    def fake_get(url, headers=None, params=None, **kwargs):
        params = dict(params or {})
        calls.append(params)
        return {
            "nextSyncToken": "seed-tok",
            "items": [
                {
                    "id": "evt-win",
                    "status": "confirmed",
                    "summary": "Windowed",
                    "start": {"dateTime": "2026-09-03T16:00:00Z"},
                    "end": {"dateTime": "2026-09-03T17:00:00Z"},
                    "attendees": [{"email": "pat@acme.com"}],
                }
            ],
        }

    monkeypatch.setattr("csm_dashboard.connectors.google_cal.json_get", fake_get)
    monkeypatch.setattr("csm_dashboard.connectors.oauth.ensure_access_token", lambda *a, **k: "ya29")
    events = GoogleCalConnector(repo).pull(None, None)
    assert any(e["payload"].get("title") == "Windowed" for e in events)
    assert repo.get_sync_cursor("google_cal")["sync_token"] == "seed-tok"
    assert calls
    assert calls[0].get("timeMin")
    assert calls[0].get("singleEvents") == "true"
    assert "timeMax" not in calls[0]
    assert "nextSyncToken" in str(calls[0].get("fields") or "")

    def boom(url, headers=None, params=None, **kwargs):
        raise httpx.RemoteProtocolError("Server disconnected without sending a response.")

    repo.put_sync_cursor("google_cal", {"sync_token": "", "pulled_at": ""})
    monkeypatch.setattr("csm_dashboard.connectors.google_cal.json_get", boom)
    monkeypatch.setattr("csm_dashboard.connectors.google_cal.time.sleep", lambda *_a, **_k: None)
    with pytest.raises(httpx.RemoteProtocolError):
        GoogleCalConnector(repo).pull(None, None)
    cursor = repo.get_sync_cursor("google_cal")
    assert cursor.get("pulled_at")
    assert not cursor.get("sync_token")
