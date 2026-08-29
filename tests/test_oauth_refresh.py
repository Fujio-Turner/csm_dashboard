from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from csm_dashboard.connectors import oauth as oauth_flow
from csm_dashboard.storage.memory import MemoryStore
from csm_dashboard.storage.repo import CsmRepo


class _Repo:
    def __init__(self, secret: dict):
        self.secret = dict(secret)

    def get_credential_secret(self, kind, name):
        return dict(self.secret)

    def put_credential_secret(self, kind, name, fields):
        self.secret.update(fields)
        return self.secret


def test_ensure_access_token_uses_fresh_and_refreshes_google(monkeypatch):
    repo = _Repo(
        {
            "client_id": "abc",
            "client_secret": "sec",
            "access_token": "old",
            "refresh_token": "1//r",
            "expiry": "3600",
        }
    )

    def fake_post(url, data):
        assert "googleapis.com/token" in url
        assert data["grant_type"] == "refresh_token"
        return {"access_token": "new-access", "expires_in": 3600, "refresh_token": "1//r2", "scope": "gmail"}

    monkeypatch.setattr(oauth_flow, "token_post", fake_post)
    token = oauth_flow.ensure_access_token("google", repo, force=True)
    assert token == "new-access"
    assert repo.secret["access_token"] == "new-access"

    slack = _Repo({"user_token": "xoxp-live"})
    assert oauth_flow.ensure_access_token("slack", slack) == "xoxp-live"


def test_ensure_access_token_microsoft_refresh(monkeypatch):
    repo = _Repo(
        {
            "client_id": "ms",
            "access_token": "stale",
            "refresh_token": "rt",
            "expiry": "1",
        }
    )

    def fake_post(url, data):
        assert "microsoftonline.com" in url
        return {"access_token": "ms-new", "expires_in": 3600}

    monkeypatch.setattr(oauth_flow, "token_post", fake_post)
    assert oauth_flow.ensure_access_token("microsoft", repo) == "ms-new"


def test_microsoft_oauth_start(client):
    client.put(
        "/api/settings/keys",
        json={"connectors": {"microsoft": {"client_id": "ms-app", "tenant_id": "common"}}},
    )
    res = client.get("/api/oauth/microsoft/start", follow_redirects=False)
    assert res.status_code == 302
    loc = res.headers["location"]
    assert "login.microsoftonline.com" in loc
    qs = parse_qs(urlparse(loc).query)
    assert qs["client_id"] == ["ms-app"]
    assert "Chat.Read" in qs["scope"][0]


def test_oauth2callback_alias_finishes_google(client, monkeypatch):
    client.put("/api/settings/keys", json={"connectors": {"google": {"client_id": "abc"}}})
    start = client.get("/api/oauth/google/start", follow_redirects=False)
    state = parse_qs(urlparse(start.headers["location"]).query)["state"][0]

    def fake_post(url, data):
        return {
            "access_token": "ya29-alias",
            "refresh_token": "1//alias",
            "token_type": "Bearer",
            "expires_in": 3600,
        }

    monkeypatch.setattr(oauth_flow, "token_post", fake_post)
    cb = client.get("/oauth2callback", params={"code": "code123", "state": state})
    assert cb.status_code == 200
    assert "Connected" in cb.text
    gmail = next(i for i in client.get("/api/connectors").json()["items"] if i["name"] == "google_mail")
    assert gmail["connected"] is True


def test_oauth_callback_invalid_state(client):
    res = client.get("/api/oauth/google/callback", params={"code": "x", "state": "nope"})
    assert res.status_code == 400
    denied = client.get("/api/oauth/google/callback", params={"error": "access_denied"})
    assert denied.status_code == 400


def test_expiry_helpers():
    assert oauth_flow._expiry_unix("0") == ""
    assert oauth_flow._expiry_unix("nope") == ""
    assert oauth_flow._expiry_passed("3600") is True
    future = str(2_000_000_000)
    assert oauth_flow._expiry_passed(future) is False
