from __future__ import annotations

from email.message import EmailMessage

from csm_dashboard.connectors.smtp_imap import build_message, send_via_smtp


class DummySMTP:
    sent: list[EmailMessage] = []
    logins: list[tuple[str, str]] = []

    def __init__(self, host, port, timeout=30):
        self.host = host
        self.port = port

    def starttls(self):
        return None

    def login(self, user, password):
        DummySMTP.logins.append((user, password))

    def send_message(self, msg):
        DummySMTP.sent.append(msg)

    def quit(self):
        return None


def _enable_smtp(client):
    client.put(
        "/api/settings",
        json={"operator": {"name": "Jordan", "email": "jordan@example.com", "timezone": "UTC"}},
    )
    client.put(
        "/api/settings/keys",
        json={
            "connectors": {
                "smtp_imap": {
                    "host": "smtp.example.com",
                    "port": "587",
                    "username": "jordan@example.com",
                    "password": "app-pass",
                }
            }
        },
    )
    client.put("/api/settings", json={"connectors": {"smtp_imap": {"mode": "live"}}})


def test_build_message_sets_headers():
    msg = build_message(
        from_addr="me@ex.com",
        to_addrs=["you@ex.com"],
        cc_addrs=["cc@ex.com"],
        subject="Hello",
        body="Hi there",
    )
    assert msg["From"] == "me@ex.com"
    assert msg["To"] == "you@ex.com"
    assert msg["Cc"] == "cc@ex.com"
    assert msg["Bcc"] is None
    msg2 = build_message(
        from_addr="me@ex.com",
        to_addrs=["you@ex.com"],
        cc_addrs=["cc@ex.com"],
        bcc_addrs=["bcc@ex.com"],
        subject="Hello",
        body="Hi there",
        attachments=[("note.txt", "text/plain", b"hi")],
    )
    assert msg2["Bcc"] == "bcc@ex.com"
    names = [part.get_filename() for part in msg2.iter_attachments()]
    assert "note.txt" in names


def test_send_via_smtp_uses_client(monkeypatch):
    DummySMTP.sent = []
    DummySMTP.logins = []
    secret = {"host": "smtp.example.com", "port": "587", "username": "me@ex.com", "password": "pw"}
    msg = build_message(from_addr="me@ex.com", to_addrs=["you@ex.com"], subject="Ping", body="x")
    host = send_via_smtp(secret, msg, client_factory=DummySMTP)
    assert host == "smtp.example.com"
    assert DummySMTP.logins == [("me@ex.com", "pw")]
    assert DummySMTP.sent[0]["Subject"] == "Ping"


def test_draft_send_uses_gmail_when_send_scope(client, repo, monkeypatch):
    client.post("/api/settings/seed")
    client.put("/api/settings", json={"operator": {"email": "jordan@example.com"}})
    repo.put_credential_secret(
        "connector",
        "google",
        {
            "access_token": "ya29",
            "refresh_token": "1//r",
            "scope": "https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/gmail.send",
        },
    )

    def fake_post(url, headers=None, json=None, **kwargs):
        assert "messages/send" in url
        assert json and json.get("raw")
        return {"id": "gmail-sent-1", "threadId": "t1", "labelIds": ["SENT"]}

    monkeypatch.setattr("csm_dashboard.connectors.google_mail.json_post", fake_post)
    monkeypatch.setattr("csm_dashboard.connectors.oauth.ensure_access_token", lambda *a, **k: "ya29")
    composed = client.post("/api/drafts/compose", json={"account_id": "acct:acme"})
    sent = client.post(
        "/api/drafts/" + composed.json()["_id"] + "/send",
        json={"to_addrs": ["jordan@example.com"], "subject": "Ping me", "body": "desk test"},
    )
    assert sent.status_code == 200
    assert sent.json()["sent"]["via"] == "gmail"
    assert sent.json()["sent"]["gmail_id"] == "gmail-sent-1"


def test_save_draft_pushes_gmail_when_compose_scope(client, repo, monkeypatch):
    client.post("/api/settings/seed")
    client.put("/api/settings", json={"operator": {"email": "jordan@example.com"}})
    repo.put_credential_secret(
        "connector",
        "google",
        {
            "access_token": "ya29",
            "refresh_token": "1//r",
            "scope": (
                "https://www.googleapis.com/auth/gmail.readonly "
                "https://www.googleapis.com/auth/gmail.send "
                "https://www.googleapis.com/auth/gmail.compose"
            ),
        },
    )
    calls: list[tuple[str, str]] = []

    def fake_post(url, headers=None, json=None, **kwargs):
        calls.append(("POST", str(url)))
        if str(url).endswith("/drafts"):
            return {"id": "r-draft-1", "message": {"id": "m-draft-1"}}
        if str(url).endswith("/drafts/send"):
            return {"id": "m-sent-1", "threadId": "t1", "labelIds": ["SENT"]}
        raise AssertionError(url)

    def fake_put(url, headers=None, json=None, **kwargs):
        calls.append(("PUT", str(url)))
        return {"id": "r-draft-1", "message": {"id": "m-draft-1"}}

    monkeypatch.setattr("csm_dashboard.connectors.google_mail.json_post", fake_post)
    monkeypatch.setattr("csm_dashboard.connectors.google_mail.json_put", fake_put)
    monkeypatch.setattr("csm_dashboard.connectors.oauth.ensure_access_token", lambda *a, **k: "ya29")
    created = client.post(
        "/api/drafts",
        json={
            "account_id": "acct:acme",
            "to_addrs": ["pat@acme.com"],
            "subject": "Hi",
            "body": "Hello",
        },
    )
    assert created.status_code == 200
    body = created.json()
    assert body["gmail"]["ok"] is True
    assert body["gmail_draft_id"] == "r-draft-1"
    patched = client.patch(
        "/api/drafts/" + body["_id"],
        json={"subject": "Hi again", "body": "Hello 2", "to_addrs": ["pat@acme.com"]},
    )
    assert patched.status_code == 200
    assert any(method == "PUT" and "/drafts/r-draft-1" in url for method, url in calls)
    sent = client.post("/api/drafts/" + body["_id"] + "/send")
    assert sent.status_code == 200
    assert sent.json()["sent"]["via"] == "gmail"
    assert any(method == "POST" and url.endswith("/drafts/send") for method, url in calls)


def test_save_draft_without_compose_scope_stays_local(client, repo):
    client.post("/api/settings/seed")
    client.put("/api/settings", json={"operator": {"email": "jordan@example.com"}})
    repo.put_credential_secret(
        "connector",
        "google",
        {
            "access_token": "ya29",
            "refresh_token": "1//r",
            "scope": "https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/gmail.send",
        },
    )
    created = client.post(
        "/api/drafts",
        json={
            "account_id": "acct:acme",
            "to_addrs": ["pat@acme.com"],
            "subject": "Hi",
            "body": "Hello",
        },
    )
    assert created.status_code == 200
    assert created.json()["_id"].startswith("draft:")
    assert created.json()["gmail"]["ok"] is False
    assert created.json()["gmail"]["reason"] == "google_draft_reconnect"


def test_gmail_connected_without_send_scope_asks_reconnect(client, repo):
    client.post("/api/settings/seed")
    repo.put_credential_secret(
        "connector",
        "google",
        {
            "access_token": "ya29",
            "refresh_token": "1//r",
            "scope": "https://www.googleapis.com/auth/gmail.readonly",
        },
    )
    composed = client.post("/api/drafts/compose", json={"account_id": "acct:acme"})
    res = client.post(
        "/api/drafts/" + composed.json()["_id"] + "/send",
        json={"to_addrs": ["me@ex.com"]},
    )
    assert res.status_code == 409
    assert "google_send_reconnect" in res.json()["detail"]


def test_draft_send_without_smtp_is_conflict(client):
    client.post("/api/settings/seed")
    composed = client.post("/api/drafts/compose", json={"account_id": "acct:acme"})
    res = client.post("/api/drafts/" + composed.json()["_id"] + "/send")
    assert res.status_code == 409
    assert "send_not_configured" in res.json()["detail"]


def test_draft_and_task_send_after_confirm(client, monkeypatch):
    DummySMTP.sent = []
    DummySMTP.logins = []
    monkeypatch.setattr("csm_dashboard.connectors.smtp_imap.smtp_client", DummySMTP)
    client.post("/api/settings/seed")
    _enable_smtp(client)
    composed = client.post("/api/drafts/compose", json={"account_id": "acct:acme"})
    draft_id = composed.json()["_id"]
    sent = client.post(f"/api/drafts/{draft_id}/send")
    assert sent.status_code == 200
    assert sent.json()["status"] == "sent"
    assert sent.json()["sent"]["via"] == "smtp"
    assert DummySMTP.sent
    assert DummySMTP.sent[0]["From"] == "jordan@example.com"

    task = client.post(
        "/api/tasks",
        json={
            "account_id": "acct:acme",
            "task_name": "Ping Pat",
            "task_kind": "Follow up(s)",
            "due_at": "2026-08-29T15:00",
            "body": "Call after QBR.",
        },
    )
    assert task.status_code == 200
    tid = task.json()["_id"]
    mailed = client.post(f"/api/tasks/{tid}/send")
    assert mailed.status_code == 200
    assert mailed.json()["mailbox_sent_at"]
    assert mailed.json()["sent"]["via"] == "smtp"
    subjects = [m["Subject"] for m in DummySMTP.sent]
    assert any("Ping Pat" in s for s in subjects)
