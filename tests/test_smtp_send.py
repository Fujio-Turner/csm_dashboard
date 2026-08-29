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
    assert msg["Subject"] == "Hello"
    assert "Hi there" in msg.get_content()


def test_send_via_smtp_uses_client(monkeypatch):
    DummySMTP.sent = []
    DummySMTP.logins = []
    secret = {"host": "smtp.example.com", "port": "587", "username": "me@ex.com", "password": "pw"}
    msg = build_message(from_addr="me@ex.com", to_addrs=["you@ex.com"], subject="Ping", body="x")
    host = send_via_smtp(secret, msg, client_factory=DummySMTP)
    assert host == "smtp.example.com"
    assert DummySMTP.logins == [("me@ex.com", "pw")]
    assert DummySMTP.sent[0]["Subject"] == "Ping"


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
