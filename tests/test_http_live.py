from __future__ import annotations

from csm_dashboard.connectors.http import HttpError, json_get, json_post, request
from csm_dashboard.connectors.live import LiveConnector, jira_day, since_iso, since_unix


class _Resp:
    def __init__(self, status=200, content=b'{"ok":true}', payload=None):
        self.status_code = status
        self.content = content
        self._payload = payload if payload is not None else {"ok": True}

    def json(self):
        if self._payload == "bad":
            raise ValueError("not json")
        return self._payload


class _Client:
    def __init__(self, resp):
        self._resp = resp

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def request(self, *args, **kwargs):
        return self._resp


def test_http_error_code():
    err = HttpError(401)
    assert err.status == 401
    assert str(err) == "http_401"
    err2 = HttpError(200, "http_not_json")
    assert str(err2) == "http_not_json"


def test_request_ok_and_errors(monkeypatch):
    import csm_dashboard.connectors.http as http_mod

    monkeypatch.setattr(http_mod.httpx, "Client", lambda **kw: _Client(_Resp()))
    assert request("GET", "https://example.test") == {"ok": True}

    monkeypatch.setattr(http_mod.httpx, "Client", lambda **kw: _Client(_Resp(status=404, content=b"no")))
    try:
        request("GET", "https://example.test/missing")
        assert False, "expected HttpError"
    except HttpError as exc:
        assert exc.status == 404

    monkeypatch.setattr(http_mod.httpx, "Client", lambda **kw: _Client(_Resp(content=b"", payload={})))
    assert json_get("https://example.test/empty") == {}

    monkeypatch.setattr(
        http_mod.httpx,
        "Client",
        lambda **kw: _Client(_Resp(content=b"not-json", payload="bad")),
    )
    try:
        json_post("https://example.test/bad", json={})
        assert False, "expected not json"
    except HttpError as exc:
        assert exc.code == "http_not_json"

    monkeypatch.setattr(http_mod.httpx, "Client", lambda **kw: _Client(_Resp(payload=["a"])))
    assert request("GET", "https://example.test/list") == ["a"]

    monkeypatch.setattr(http_mod.httpx, "Client", lambda **kw: _Client(_Resp(payload=3)))
    assert request("GET", "https://example.test/num") == {}


def test_request_reuses_passed_client(monkeypatch):
    import csm_dashboard.connectors.http as http_mod

    created = {"n": 0}

    class Factory:
        def __init__(self, **kw):
            created["n"] += 1

        def __enter__(self):
            return _Client(_Resp())

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(http_mod.httpx, "Client", Factory)
    existing = _Client(_Resp())
    assert request("GET", "https://example.test", client=existing) == {"ok": True}
    assert created["n"] == 0


def test_since_helpers_use_provided_or_default():
    assert since_iso("2026-08-01T00:00:00Z").startswith("2026-08-01")
    assert since_iso("").endswith("Z")
    assert since_unix("2026-08-01T00:00:00Z").isdigit()
    assert since_unix("not-a-date").isdigit()
    assert "2026-08-01 00:00" in jira_day("2026-08-01T00:00:00Z")


def test_live_connector_without_repo():
    conn = LiveConnector(None)
    conn.name = "jira"
    assert conn.secret() == {}
    assert conn.account_rows(None) == []
    assert conn.account_rows({"account_id": "acct:x"}) == [{"account_id": "acct:x"}]
    assert conn.ready() is False
    health = conn.health()
    assert health["ok"] is False
    assert health["message"] == "not_connected"
    assert conn.probe()["name"] == "jira"
