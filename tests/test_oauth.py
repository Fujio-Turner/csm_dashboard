from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse


def test_gmail_form_has_no_refresh_token_field(client):
    items = client.get("/api/connectors").json()["items"]
    gmail = next(i for i in items if i["name"] == "google_mail")
    names = [f["name"] for f in gmail["fields"]]
    assert gmail["auth"] == "oauth"
    assert gmail["oauth_vendor"] == "google"
    assert "refresh_token" not in names
    assert "access_token" not in names
    assert "client_id" not in names
    assert gmail["redirect_uri"].startswith("http://localhost:")
    assert gmail["redirect_uri"].endswith("/oauth2callback")
    jira = next(i for i in items if i["name"] == "jira")
    assert jira["auth"] == "token"
    imap = next(i for i in items if i["name"] == "smtp_imap")
    assert imap["auth"] == "password"
    slack = next(i for i in items if i["name"] == "slack")
    assert slack["auth"] == "oauth"
    assert [f["name"] for f in slack["fields"]] == ["user_token"]
    teams = next(i for i in items if i["name"] == "teams")
    assert teams["auth"] == "oauth"
    assert teams["oauth_vendor"] == "microsoft"


def test_google_local_credentials_path_is_first_file(tmp_path, monkeypatch):
    from csm_dashboard.connectors import google_secrets

    monkeypatch.setattr(google_secrets, "_in_pytest", lambda: False)
    monkeypatch.setattr(google_secrets, "ROOT", tmp_path)
    monkeypatch.delenv("GOOGLE_CLIENT_SECRETS", raising=False)
    monkeypatch.delenv("CSM_GOOGLE_CREDENTIALS", raising=False)
    paths = google_secrets.candidate_paths()
    assert paths[0] == tmp_path / "__local" / "credentials.json"


def test_google_credentials_file_starts_oauth(client, tmp_path, monkeypatch):
    path = tmp_path / "credentials.json"
    path.write_text(
        json.dumps(
            {
                "web": {
                    "client_id": "from-file.apps.googleusercontent.com",
                    "client_secret": "file-secret-do-not-echo",
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("GOOGLE_CLIENT_SECRETS", str(path))
    status = client.get("/api/status").json()
    assert status["sso"]["google_file"] is True
    assert status["sso"]["clients"]["google"] is True
    assert "file-secret" not in json.dumps(status)
    res = client.get("/api/oauth/google/start", follow_redirects=False)
    assert res.status_code == 302
    qs = parse_qs(urlparse(res.headers["location"]).query)
    assert qs["client_id"] == ["from-file.apps.googleusercontent.com"]
    assert qs["redirect_uri"][0].endswith("/oauth2callback")


def test_oauth_start_requires_client_id(client):
    res = client.get("/api/oauth/google/start", follow_redirects=False)
    assert res.status_code == 400
    assert "Google client ID" in res.text
    assert "oauth_client_id_missing" not in res.text or "client ID" in res.text


def test_google_client_secret_saved_without_echo(client):
    secret = "GOCSPX-test-secret-do-not-echo"
    res = client.put(
        "/api/settings/keys",
        json={"connectors": {"google": {"client_id": "abc.apps.googleusercontent.com", "client_secret": secret}}},
    )
    assert res.status_code == 200
    blob = json.dumps(res.json())
    assert secret not in blob
    status = client.get("/api/status").json()
    assert status["sso"]["clients"]["google"] is True
    assert status["sso"]["clients"]["google_secret"] is True
    assert secret not in json.dumps(status)


def test_oauth_start_redirects_to_google(client):
    client.put(
        "/api/settings/keys",
        json={"connectors": {"google_mail": {"client_id": "abc.apps.googleusercontent.com"}}},
    )
    res = client.get("/api/oauth/google/start", follow_redirects=False)
    assert res.status_code == 302
    loc = res.headers["location"]
    assert loc.startswith("https://accounts.google.com/o/oauth2/v2/auth")
    qs = parse_qs(urlparse(loc).query)
    assert qs["client_id"] == ["abc.apps.googleusercontent.com"]
    assert "gmail.send" in qs.get("scope", [""])[0]
    assert "gmail.compose" in qs.get("scope", [""])[0]
    assert "gmail.readonly" in qs.get("scope", [""])[0]
    assert "code_challenge" in qs
    assert "access_type" in qs
    blob = json.dumps(qs)
    assert "refresh_token" not in blob or "access_type" in qs


def test_oauth_callback_stores_tokens_without_echo(client, monkeypatch):
    from csm_dashboard.connectors import oauth as oauth_flow

    client.put("/api/settings/keys", json={"connectors": {"google_mail": {"client_id": "abc"}}})
    start = client.get("/api/oauth/google/start", follow_redirects=False)
    state = parse_qs(urlparse(start.headers["location"]).query)["state"][0]

    def fake_post(url, data):
        assert "googleapis.com/token" in url
        assert data.get("code") == "code123"
        return {
            "access_token": "ya29-secret-access",
            "refresh_token": "1//secret-refresh",
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": "https://www.googleapis.com/auth/gmail.readonly",
        }

    monkeypatch.setattr(oauth_flow, "token_post", fake_post)
    cb = client.get("/api/oauth/google/callback", params={"code": "code123", "state": state})
    assert cb.status_code == 200
    assert "Connected" in cb.text
    assert "ya29-secret-access" not in cb.text
    assert "1//secret-refresh" not in cb.text
    items = client.get("/api/connectors").json()["items"]
    blob = json.dumps(items)
    assert "ya29-secret-access" not in blob
    assert "1//secret-refresh" not in blob
    gmail = next(i for i in items if i["name"] == "google_mail")
    cal = next(i for i in items if i["name"] == "google_cal")
    assert gmail["connected"] is True
    assert cal["connected"] is True
    assert gmail["mode"] == "live"
    assert cal["mode"] == "live"
    names = [f["name"] for f in gmail["fields"]]
    assert "refresh_token" not in names

    gone = client.post("/api/oauth/google/disconnect")
    assert gone.status_code == 200
    after = client.get("/api/connectors").json()["items"]
    gmail2 = next(i for i in after if i["name"] == "google_mail")
    assert gmail2["connected"] is False


def test_slack_oauth_requests_user_history_scopes(client):
    client.put("/api/settings/keys", json={"connectors": {"slack": {"client_id": "slack-client"}}})
    res = client.get("/api/oauth/slack/start", follow_redirects=False)
    assert res.status_code == 302
    loc = res.headers["location"]
    assert loc.startswith("https://slack.com/oauth/v2/authorize")
    qs = parse_qs(urlparse(loc).query)
    assert qs["client_id"] == ["slack-client"]
    user_scope = qs.get("user_scope", [""])[0]
    assert "channels:history" in user_scope
    assert "users:read" in user_scope


def test_google_redirect_uses_public_port(monkeypatch):
    from csm_dashboard.config import invalidate_settings, load_settings
    from csm_dashboard.connectors.oauth import redirect_uri

    monkeypatch.setenv("CSM_DASHBOARD_PORT", "5000")
    monkeypatch.setenv("CSM_DASHBOARD_PUBLIC_PORT", "5001")
    invalidate_settings()
    try:
        settings = load_settings(force=True)
        assert settings.port == 5000
        assert settings.public_port == 5001
        assert redirect_uri("google") == "http://localhost:5001/oauth2callback"
        assert redirect_uri("microsoft") == "http://127.0.0.1:5001/api/oauth/microsoft/callback"
    finally:
        invalidate_settings()
