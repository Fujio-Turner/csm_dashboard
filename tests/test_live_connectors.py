from __future__ import annotations

import json

from csm_dashboard.connectors.google_cal import map_event
from csm_dashboard.connectors.google_mail import map_gmail_message, parse_addrs
from csm_dashboard.connectors.jira import build_jql, map_issue, map_status
from csm_dashboard.connectors.slack import map_channel, map_message
from csm_dashboard.connectors.teams import map_message as map_teams_message
from csm_dashboard.connectors.teams import strip_html


SAMPLE_ISSUE = {
    "id": "10099",
    "key": "ACME-99",
    "fields": {
        "summary": "Live pull works",
        "status": {"name": "Canceled", "statusCategory": {"key": "done"}},
        "priority": {"name": "Highest"},
        "issuetype": {"name": "Bug"},
        "assignee": {"emailAddress": "tam@acme.com", "displayName": "Tam"},
        "reporter": {"emailAddress": "pat@acme.com", "displayName": "Pat"},
        "labels": ["fw"],
        "created": "2026-08-01T12:00:00.000+0000",
        "updated": "2026-08-20T12:00:00.000+0000",
        "resolutiondate": "2026-08-20T12:30:00.000+0000",
        "project": {"key": "ACME"},
        "comment": {
            "total": 1,
            "comments": [
                {
                    "created": "2026-08-20T11:00:00.000+0000",
                    "author": {"emailAddress": "pat@acme.com"},
                    "body": {
                        "type": "doc",
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [{"type": "text", "text": "Still dying after 20 minutes."}],
                            }
                        ],
                    },
                }
            ],
        },
    },
}


def test_jira_maps_cancelled_and_caps_comments():
    status, raw = map_status(SAMPLE_ISSUE["fields"])
    assert status == "cancelled"
    assert raw == "Canceled"
    payload = map_issue(SAMPLE_ISSUE, base_url="https://ex.atlassian.net")
    assert payload["key"] == "ACME-99"
    assert payload["status"] == "cancelled"
    assert payload["priority"] == "p1"
    assert payload["project_key"] == "ACME"
    assert payload["url"] == "https://ex.atlassian.net/browse/ACME-99"
    assert payload["comments"][0]["text"] == "Still dying after 20 minutes."
    assert "canceled" not in payload["status"]


def test_jira_jql_uses_project_keys_and_since():
    from csm_dashboard.connectors.jira import adf_text, jira_time, project_keys

    jql = build_jql(keys=["ACME", "NWIN"], since="2026-08-01T00:00:00Z")
    assert "project in (ACME, NWIN)" in jql
    assert "updated >=" in jql
    assert "ORDER BY updated DESC" in jql
    custom = build_jql(keys=[], custom="assignee = currentUser()", since="2026-08-01T00:00:00Z")
    assert "assignee = currentUser()" in custom
    empty = build_jql(keys=[], since="2026-08-01T00:00:00Z")
    assert "reporter = currentUser()" in empty
    assert adf_text(None) == ""
    assert adf_text("plain") == "plain"
    assert adf_text([{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]) == "a b"
    assert jira_time("") == ""
    assert jira_time("2026-08-01T12:00:00.000+0000").endswith("Z")
    assert project_keys([{"connectors": {"jira": {"project_keys": ["ACME", "ACME", ""]}}}]) == ["ACME"]


def test_slack_and_teams_message_shapes():
    ch = map_channel({"id": "C0ACME1", "name": "acme-success", "topic": {"value": "prod"}})
    assert ch["channel_id"] == "C0ACME1"
    assert ch["topic"] == "prod"
    msg = map_message({"ts": "1723900000.000100", "user": "U0PAT", "text": "hi"}, channel_id="C0ACME1", user_name="pat")
    assert msg["type"] == "slack_message"
    assert "C0ACME1" in msg["permalink"]
    html = map_teams_message(
        {
            "id": "m1",
            "createdDateTime": "2026-08-20T12:00:00Z",
            "from": {"user": {"id": "u1", "displayName": "Bob"}},
            "body": {"content": "<p>Tried the <b>pin</b></p>"},
            "webUrl": "https://teams.microsoft.com/l/message/1",
        },
        channel_id="19:chat",
    )
    assert html["user_name"] == "Bob"
    assert "pin" in html["text"]
    assert "<p>" not in html["text"]
    assert strip_html("<div>a</div>") == "a"


def test_slack_user_token_saved_without_echo(client):
    secret = "xoxp-secret-do-not-echo"
    res = client.put("/api/settings/keys", json={"connectors": {"slack": {"user_token": secret}}})
    assert res.status_code == 200
    blob = json.dumps(res.json())
    assert secret not in blob
    items = client.get("/api/connectors").json()["items"]
    slack = next(i for i in items if i["name"] == "slack")
    assert slack["connected"] is True
    assert slack["auth"] == "oauth"
    names = [f["name"] for f in slack["fields"]]
    assert names == ["user_token"]
    assert "xoxp-secret" not in json.dumps(items)
    field = next(f for f in slack["fields"] if f["name"] == "user_token")
    assert field["present"] is True
    assert field["secret"] is True


def test_jira_test_and_sync_mocked(client, monkeypatch):
    client.post("/api/settings/seed")
    client.put(
        "/api/settings/keys",
        json={
            "connectors": {
                "jira": {
                    "base_url": "https://ex.atlassian.net",
                    "email": "me@ex.com",
                    "api_token": "jira-secret-token",
                }
            }
        },
    )

    def fake_get(url, **kwargs):
        assert "myself" in url
        return {"accountId": "abc"}

    def fake_post(url, json=None, **kwargs):
        assert "search/jql" in url
        assert "ACME" in (json or {}).get("jql", "")
        return {"issues": [SAMPLE_ISSUE], "isLast": True}

    monkeypatch.setattr("csm_dashboard.connectors.jira.json_get", fake_get)
    monkeypatch.setattr("csm_dashboard.connectors.jira.json_post", fake_post)
    probed = client.post("/api/connectors/jira/test")
    assert probed.status_code == 200
    assert probed.json()["ok"] is True
    assert probed.json()["mode"] == "live"
    assert "jira-secret-token" not in json.dumps(probed.json())
    job = client.post("/api/connectors/jira/sync", json={})
    assert job.status_code == 200
    assert job.json()["status"] == "done"
    assert job.json()["fetched"] == 1
    tickets = client.get("/api/tickets", params={"account_id": "acct:acme", "q": "ACME-99"}).json()["items"]
    assert any(t.get("key") == "ACME-99" and t.get("status") == "cancelled" for t in tickets)


def test_slack_sync_mocked(client, monkeypatch):
    client.post("/api/settings/seed")
    client.put("/api/settings/keys", json={"connectors": {"slack": {"user_token": "xoxp-test"}}})
    client.put("/api/settings", json={"connectors": {"slack": {"mode": "live"}}})

    def fake_get(url, headers=None, params=None, **kwargs):
        method = url.rsplit("/", 1)[-1]
        if method == "auth.test":
            return {"ok": True, "user_id": "U0JOR", "team": "T1"}
        if method == "conversations.list":
            return {"ok": True, "channels": [{"id": "C0ACME1", "name": "acme-success", "topic": {"value": "prod"}}]}
        if method == "conversations.history":
            return {
                "ok": True,
                "messages": [{"ts": "1723900999.000100", "user": "U0PAT", "text": "live slack hi"}],
                "has_more": False,
            }
        if method == "users.info":
            return {"ok": True, "user": {"name": "pat", "profile": {"display_name": "pat.nguyen"}}}
        return {"ok": True}

    monkeypatch.setattr("csm_dashboard.connectors.slack.json_get", fake_get)
    job = client.post("/api/connectors/slack/sync", json={})
    assert job.json()["status"] == "done"
    assert job.json()["fetched"] >= 1
    msgs = client.get("/api/slack/messages", params={"account_id": "acct:acme"}).json()["items"]
    assert any("live slack hi" in (m.get("text") or "") for m in msgs)


def test_teams_sync_mocked(client, repo, monkeypatch):
    client.post("/api/settings/seed")
    repo.put_credential_secret("connector", "microsoft", {"client_id": "ms-app", "access_token": "at", "refresh_token": "rt"})
    client.put("/api/settings", json={"connectors": {"teams": {"mode": "live"}}})

    def fake_token(vendor, repo, force=False):
        assert vendor == "microsoft"
        return "ms-access"

    def fake_get(url, headers=None, params=None, **kwargs):
        assert (headers or {}).get("Authorization") == "Bearer ms-access"
        if url.endswith("/me"):
            return {"userPrincipalName": "ada@example.com"}
        if url.endswith("/me/chats"):
            return {
                "value": [
                    {
                        "id": "19:acme-success",
                        "topic": "ACME Success",
                        "members": [{"displayName": "Bob"}],
                    }
                ]
            }
        if "/messages" in url:
            return {
                "value": [
                    {
                        "id": "m1",
                        "messageType": "message",
                        "createdDateTime": "2026-08-28T12:00:00Z",
                        "from": {"user": {"id": "u1", "displayName": "Bob Hale"}},
                        "body": {"content": "<p>Tried the pin</p>"},
                        "webUrl": "https://teams.microsoft.com/l/message/1",
                    }
                ]
            }
        if "joinedTeams" in url:
            return {"value": []}
        return {"value": []}

    monkeypatch.setattr("csm_dashboard.connectors.oauth.ensure_access_token", fake_token)
    monkeypatch.setattr("csm_dashboard.connectors.teams.json_get", fake_get)
    job = client.post("/api/connectors/teams/sync", json={})
    assert job.json()["status"] == "done"
    assert job.json()["fetched"] >= 1
    msgs = client.get("/api/teams/messages", params={"account_id": "acct:acme"}).json()["items"]
    assert any("pin" in (m.get("text") or "") for m in msgs)


def test_jira_search_falls_back_to_legacy_get(client, monkeypatch):
    from csm_dashboard.connectors.http import HttpError

    client.post("/api/settings/seed")
    client.put(
        "/api/settings/keys",
        json={"connectors": {"jira": {"base_url": "https://ex.atlassian.net", "email": "me@ex.com", "api_token": "tok"}}},
    )
    client.put("/api/settings", json={"connectors": {"jira": {"mode": "live"}}})
    posts = {"n": 0}

    def fake_post(url, json=None, **kwargs):
        posts["n"] += 1
        raise HttpError(410)

    def fake_get(url, **kwargs):
        if "myself" in url:
            return {"accountId": "1"}
        assert "search" in url
        return {"issues": [SAMPLE_ISSUE], "total": 1}

    monkeypatch.setattr("csm_dashboard.connectors.jira.json_post", fake_post)
    monkeypatch.setattr("csm_dashboard.connectors.jira.json_get", fake_get)
    job = client.post("/api/connectors/jira/sync", json={})
    assert job.json()["status"] == "done"
    assert posts["n"] >= 1


def test_slack_probe_and_skip_join(client, monkeypatch):
    client.put("/api/settings/keys", json={"connectors": {"slack": {"user_token": "xoxp-test"}}})
    calls = []

    def fake_get(url, headers=None, params=None, **kwargs):
        method = url.rsplit("/", 1)[-1]
        calls.append(method)
        if method == "auth.test":
            return {"ok": True, "team": "T1"}
        if method == "conversations.list":
            return {"ok": True, "channels": [{"id": "C0SKIP", "name": "noise"}]}
        if method == "conversations.history":
            return {
                "ok": True,
                "messages": [
                    {"ts": "1.0", "subtype": "channel_join", "user": "U1", "text": "joined"},
                    {"ts": "2.0", "user": "U1", "text": "real"},
                ],
                "has_more": False,
            }
        if method == "users.info":
            return {"ok": True, "user": {"name": "pat", "profile": {"display_name": "pat"}}}
        return {"ok": True}

    monkeypatch.setattr("csm_dashboard.connectors.slack.json_get", fake_get)
    probed = client.post("/api/connectors/slack/test")
    assert probed.json()["ok"] is True
    client.put("/api/settings", json={"connectors": {"slack": {"mode": "live"}}})
    job = client.post("/api/connectors/slack/sync", json={})
    assert job.json()["status"] == "done"


def test_get_connector_unknown():
    from csm_dashboard.connectors.registry import get_connector
    from csm_dashboard.connectors.stub import StubConnector

    try:
        get_connector("nope")
        assert False, "expected KeyError"
    except KeyError:
        pass
    stub = get_connector("smtp_imap")
    assert isinstance(stub, StubConnector)
    assert stub.pull(None, None) == []


def test_live_sync_without_credentials_records_error(client):
    client.put("/api/settings", json={"connectors": {"jira": {"mode": "live"}}})
    job = client.post("/api/connectors/jira/sync", json={})
    assert job.status_code == 200
    assert job.json()["status"] == "error"
    assert job.json()["error"] == "not_connected"


def test_gmail_maps_headers_and_html_body():
    assert parse_addrs("Pat Nguyen <pat@acme.com>, other@x.com") == ["pat@acme.com", "other@x.com"]
    payload = map_gmail_message(
        {
            "id": "g1",
            "threadId": "t1",
            "labelIds": ["INBOX"],
            "snippet": "Scanner died",
            "payload": {
                "mimeType": "text/html",
                "headers": [
                    {"name": "From", "value": "Pat Nguyen <pat@acme.com>"},
                    {"name": "To", "value": "jordan@example.com"},
                    {"name": "Subject", "value": "ACME-12 workaround"},
                    {"name": "Date", "value": "Thu, 20 Aug 2026 12:00:00 +0000"},
                    {"name": "Message-ID", "value": "<acme-live@acme.com>"},
                ],
                "body": {"data": "PHA+U2Nhbm5lciBkaWVkPC9wPg=="},
            },
        }
    )
    assert payload["from_addr"] == "pat@acme.com"
    assert payload["direction"] == "inbound"
    assert payload["message_id"] == "<acme-live@acme.com>"
    assert "Scanner died" in payload["body_text"]
    assert "<p>" not in payload["body_text"]


def test_google_cal_maps_event():
    payload = map_event(
        {
            "id": "evt-1",
            "summary": "ACME QBR",
            "start": {"dateTime": "2026-08-20T16:00:00Z"},
            "end": {"dateTime": "2026-08-20T17:00:00Z"},
            "attendees": [{"email": "pat@acme.com", "displayName": "Pat"}],
            "location": "Meet",
        }
    )
    assert payload["provider"] == "google"
    assert payload["external_id"] == "evt-1"
    assert payload["attendees"][0]["email"] == "pat@acme.com"


def test_gmail_sync_mocked(client, repo, monkeypatch):
    client.post("/api/settings/seed")
    repo.put_credential_secret("connector", "google", {"access_token": "ya29", "refresh_token": "1//r"})
    client.put("/api/settings", json={"connectors": {"google_mail": {"mode": "live"}}})

    def fake_token(vendor, repo, force=False):
        return "ya29"

    def fake_get(url, headers=None, params=None, **kwargs):
        if url.endswith("/profile"):
            return {"emailAddress": "jordan@example.com"}
        if url.endswith("/messages"):
            return {"messages": [{"id": "g1"}]}
        if url.endswith("/messages/g1"):
            return {
                "id": "g1",
                "threadId": "t1",
                "labelIds": ["INBOX"],
                "snippet": "Scanner died again.",
                "payload": {
                    "mimeType": "text/plain",
                    "headers": [
                        {"name": "From", "value": "pat.nguyen@acme.com"},
                        {"name": "To", "value": "jordan@example.com"},
                        {"name": "Subject", "value": "Live gmail"},
                        {"name": "Date", "value": "Thu, 20 Aug 2026 12:00:00 +0000"},
                        {"name": "Message-ID", "value": "<live-gmail@acme.com>"},
                    ],
                    "body": {"data": "U2Nhbm5lciBkaWVkIGFnYWluLg=="},
                },
            }
        return {}

    monkeypatch.setattr("csm_dashboard.connectors.oauth.ensure_access_token", fake_token)
    monkeypatch.setattr("csm_dashboard.connectors.google_mail.json_get", fake_get)
    job = client.post("/api/connectors/google_mail/sync", json={})
    assert job.json()["status"] == "done"
    mail = client.get("/api/emails", params={"account_id": "acct:acme"}).json()["items"]
    assert any("Live gmail" in (m.get("subject") or "") for m in mail)
