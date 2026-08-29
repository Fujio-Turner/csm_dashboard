from __future__ import annotations

import json


def test_put_keys_stores_in_cbl_and_never_echoes_secret(client):
    secret = "xai-test-secret-do-not-echo"
    res = client.put("/api/settings/keys", json={"xai_api_key": secret, "openai_api_key": "sk-test-openai"})
    assert res.status_code == 200
    payload = res.json()
    blob = json.dumps(payload)
    assert secret not in blob
    assert "sk-test-openai" not in blob
    assert payload["credentials"]["ai"]["grok"]["present"] is True
    assert payload["credentials"]["ai"]["openai"]["present"] is True

    status = client.get("/api/status").json()
    assert secret not in json.dumps(status)
    assert status["keys"]["xai"] is True
    assert status["keys"]["grok"] is True
    assert status["keys"]["openai"] is True
    assert status["ai"]["provider"] == "grok"

    listed = client.get("/api/settings/keys").json()
    assert secret not in json.dumps(listed)
    assert listed["ai"]["grok"]["present"] is True
    assert "secret" not in listed["ai"]["grok"]
    assert listed["ai"]["grok"].get("secret") is None


def test_select_provider_and_connector_mode(client):
    client.put("/api/settings/keys", json={"ai": {"gemini": "gem-key-123"}})
    saved = client.put("/api/settings", json={"ai": {"provider": "gemini", "model": "gemini-2.5-flash"}})
    assert saved.status_code == 200
    status = client.get("/api/status").json()
    assert status["ai"]["provider"] == "gemini"
    assert status["keys"]["gemini"] is True
    assert "gem-key-123" not in json.dumps(status)

    conn = client.put(
        "/api/settings/keys",
        json={"connectors": {"jira": {"base_url": "https://ex.atlassian.net", "email": "me@ex.com", "api_token": "jira-token"}}},
    )
    assert conn.status_code == 200
    client.put("/api/settings", json={"connectors": {"jira": {"mode": "live"}}})
    items = client.get("/api/connectors").json()["items"]
    jira = next(i for i in items if i["name"] == "jira")
    assert jira["mode"] == "live"
    assert jira["present"] is True
    assert "jira-token" not in json.dumps(items)
    fields = {f["name"]: f for f in jira["fields"]}
    assert fields["api_token"]["present"] is True
    assert fields["api_token"]["secret"] is True
    assert fields["base_url"]["present"] is True


def test_reset_keeps_credentials(client):
    client.put("/api/settings/keys", json={"xai_api_key": "keep-me-key"})
    client.post("/api/settings/seed")
    reset = client.post("/api/settings/reset", json={"confirm": "RESET"})
    assert reset.status_code == 200
    status = client.get("/api/status").json()
    assert status["keys"]["xai"] is True
    assert "keep-me-key" not in json.dumps(status)
    home = client.get("/api/home").json()
    assert home["items"] == []


def test_merge_secret_deletes_blank_and_skips_none():
    from csm_dashboard.credentials import merge_secret, oauth_connected, public_view

    merged = merge_secret({"api_token": "keep", "extra": "x"}, {"api_token": "", "other": None, "new": "y"})
    assert "api_token" not in merged
    assert merged["new"] == "y"
    assert "extra" in merged
    assert oauth_connected(None) is False
    view = public_view(kind="ai", name="grok", secret={"api_key": "k"}, field_names=("api_key",))
    assert view["present"] is True
    assert view["connected"] is False


def test_empty_ai_key_clears(client):
    client.put("/api/settings/keys", json={"openai_api_key": "sk-temp"})
    assert client.get("/api/status").json()["keys"]["openai"] is True
    client.put("/api/settings/keys", json={"openai_api_key": ""})
    assert client.get("/api/status").json()["keys"]["openai"] is False
