from __future__ import annotations

from urllib.parse import parse_qs, urlparse


def test_default_sso_empty_and_disabled_mode(client):
    status = client.get("/api/status").json()
    assert status["sso"]["org_url"] == ""
    assert status["sso"]["signed_in"] is False
    assert status["sso"]["configured"] is False
    assert status["sso"]["clients"]["google"] is False
    assert status["sso"]["google_redirect"].endswith("/oauth2callback")
    assert status["sso"]["google_file"] is False
    assert "UserHome" not in str(status["sso"].get("dashboard_url") or "")
    gmail = next(i for i in status["connectors"] if i["name"] == "google_mail")
    assert gmail["mode"] == "disabled"
    client.put("/api/settings", json={"connectors": {"jira": {"mode": "stub"}}})
    jira = next(i for i in client.get("/api/connectors").json()["items"] if i["name"] == "jira")
    assert jira["mode"] == "disabled"
    sync = client.post("/api/connectors/jira/sync", json={})
    assert sync.status_code == 409
    assert "connector_disabled" in sync.json()["detail"]


def test_okta_sign_in_redirects_to_authorize_not_userhome(client, monkeypatch):
    from csm_dashboard.connectors import oauth as oauth_flow

    def fake_disc(org):
        return {
            "authorization_endpoint": "https://idp.example.com/oauth2/v1/authorize",
            "token_endpoint": "https://idp.example.com/oauth2/v1/token",
            "userinfo_endpoint": "https://idp.example.com/oauth2/v1/userinfo",
            "issuer": "https://idp.example.com",
        }

    monkeypatch.setattr(oauth_flow, "discover_oidc", fake_disc)
    client.put("/api/settings", json={"sso": {"org_url": "https://idp.example.com"}})
    client.put(
        "/api/settings/keys",
        json={"connectors": {"okta": {"client_id": "0oaTEST", "org_url": "https://idp.example.com"}}},
    )
    res = client.get("/api/oauth/okta/start", follow_redirects=False)
    assert res.status_code == 302
    loc = res.headers["location"]
    assert loc.startswith("https://idp.example.com/oauth2/v1/authorize")
    assert "UserHome" not in loc
    qs = parse_qs(urlparse(loc).query)
    assert qs["client_id"] == ["0oaTEST"]
    assert qs["response_type"] == ["code"]
    assert "openid" in qs["scope"][0]


def test_okta_callback_signs_in_without_echoing_token(client, monkeypatch):
    from csm_dashboard.connectors import oauth as oauth_flow

    monkeypatch.setattr(
        oauth_flow,
        "discover_oidc",
        lambda org: {
            "authorization_endpoint": "https://idp.example.com/oauth2/v1/authorize",
            "token_endpoint": "https://idp.example.com/oauth2/v1/token",
            "userinfo_endpoint": "https://idp.example.com/oauth2/v1/userinfo",
            "issuer": "https://idp.example.com",
        },
    )
    client.put("/api/settings/keys", json={"connectors": {"okta": {"client_id": "0oaTEST", "org_url": "https://idp.example.com"}}})
    start = client.get("/api/oauth/okta/start", follow_redirects=False)
    state = parse_qs(urlparse(start.headers["location"]).query)["state"][0]

    def fake_post(url, data):
        assert "token" in url
        return {"access_token": "okta-access-secret", "refresh_token": "okta-refresh-secret", "token_type": "Bearer"}

    def fake_get(url, headers=None):
        assert "userinfo" in url
        return {"email": "ada@example.com", "name": "Ada Example", "sub": "00u1"}

    monkeypatch.setattr(oauth_flow, "token_post", fake_post)
    monkeypatch.setattr(oauth_flow, "http_get", fake_get)
    cb = client.get("/api/oauth/okta/callback", params={"code": "code123", "state": state})
    assert cb.status_code == 200
    assert "okta-access-secret" not in cb.text
    status = client.get("/api/status").json()
    assert status["sso"]["signed_in"] is True
    assert status["sso"]["email"] == "ada@example.com"
    assert "okta-access-secret" not in str(status)


def test_oauth_uses_operator_email_as_login_hint(client):
    client.put("/api/settings", json={"operator": {"email": "ada@example.com"}})
    client.put("/api/settings/keys", json={"connectors": {"google_mail": {"client_id": "abc.apps.googleusercontent.com"}}})
    res = client.get("/api/oauth/google/start", follow_redirects=False)
    assert res.status_code == 302
    qs = parse_qs(urlparse(res.headers["location"]).query)
    assert qs["login_hint"] == ["ada@example.com"]
    assert qs["hd"] == ["example.com"]
