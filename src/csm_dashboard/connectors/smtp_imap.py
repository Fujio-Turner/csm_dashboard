"""SMTP send for drafts and self-email tasks. IMAP pull stays a later slice."""

from __future__ import annotations

import base64
import logging
import smtplib
from email.message import EmailMessage

from csm_dashboard.connectors.base import ConnectorHealth, NormalizedEvent
from csm_dashboard.connectors.live import LiveConnector
from csm_dashboard.credentials import connector_cred_name
from csm_dashboard.storage.repo import utcnow

log = logging.getLogger(__name__)


class SendNotConfigured(Exception):
    """SMTP is disabled or missing host / username / password."""


class SendFailed(Exception):
    def __init__(self, message: str = "send_failed") -> None:
        super().__init__(message)
        self.message = message


def connector(repo=None) -> "SmtpImapConnector":
    return SmtpImapConnector(repo)


class SmtpImapConnector(LiveConnector):
    name = "smtp_imap"

    def ready(self) -> bool:
        secret = self.secret()
        return bool(
            str(secret.get("host") or "").strip()
            and str(secret.get("username") or "").strip()
            and str(secret.get("password") or "").strip()
        )

    def health(self) -> ConnectorHealth:
        ok = self.ready()
        return ConnectorHealth(
            name=self.name,
            ok=ok,
            mode="disabled",
            last_ok_at=utcnow() if ok else "",
            message="send_ready" if ok else "not_connected",
        )

    def pull(self, since: str | None, account: dict | None) -> list[NormalizedEvent]:
        return []


def smtp_secret(repo) -> dict:
    if repo is None:
        return {}
    from csm_dashboard.connectors.registry import connector_mode

    if connector_mode("smtp_imap", repo.get_settings()) != "live":
        return {}
    return repo.get_credential_secret("connector", connector_cred_name("smtp_imap")) or {}


def send_configured(repo) -> bool:
    secret = smtp_secret(repo)
    return bool(
        str(secret.get("host") or "").strip()
        and str(secret.get("username") or "").strip()
        and str(secret.get("password") or "").strip()
    )


_MAX_ATTACH_BYTES = 5 * 1024 * 1024
_MAX_ATTACH_COUNT = 8


def parse_attachments(items: list | None) -> list[tuple[str, str, bytes]]:
    out: list[tuple[str, str, bytes]] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("filename") or "file")[:180] or "file"
        ctype = str(item.get("content_type") or "application/octet-stream")
        raw = str(item.get("content_b64") or "")
        if not raw:
            continue
        try:
            data = base64.b64decode(raw, validate=False)
        except Exception as exc:
            raise ValueError("attachment_invalid") from exc
        if len(data) > _MAX_ATTACH_BYTES:
            raise ValueError("attachment_too_large")
        out.append((name, ctype, data))
        if len(out) > _MAX_ATTACH_COUNT:
            raise ValueError("too_many_attachments")
    return out


def add_attachments(msg: EmailMessage, attachments: list | None) -> None:
    for item in attachments or []:
        name, ctype, data = item
        main, _, sub = str(ctype or "application/octet-stream").partition("/")
        msg.add_attachment(
            data,
            maintype=main or "application",
            subtype=sub or "octet-stream",
            filename=str(name or "file"),
        )


def build_message(
    *,
    from_addr: str,
    to_addrs: list[str],
    cc_addrs: list[str] | None = None,
    bcc_addrs: list[str] | None = None,
    subject: str,
    body: str,
    attachments: list | None = None,
) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = ", ".join(to_addrs)
    cc = [addr for addr in (cc_addrs or []) if addr]
    if cc:
        msg["Cc"] = ", ".join(cc)
    bcc = [addr for addr in (bcc_addrs or []) if addr]
    if bcc:
        msg["Bcc"] = ", ".join(bcc)
    msg["Subject"] = subject or ""
    msg.set_content(body or "")
    add_attachments(msg, attachments)
    return msg


def smtp_client(host: str, port: int, *, timeout: float = 30.0):
    if int(port) == 465:
        return smtplib.SMTP_SSL(host, port, timeout=timeout)
    return smtplib.SMTP(host, port, timeout=timeout)


def send_via_smtp(secret: dict, message: EmailMessage, *, client_factory=None) -> str:
    host = str(secret.get("smtp_host") or secret.get("host") or "").strip()
    user = str(secret.get("username") or "").strip()
    password = str(secret.get("password") or "")
    try:
        port = int(str(secret.get("smtp_port") or secret.get("port") or 587) or 587)
    except (TypeError, ValueError):
        port = 587
    if not host or not user or not password:
        raise SendNotConfigured("send_not_configured")
    factory = client_factory or smtp_client
    client = factory(host, port)
    try:
        if port != 465:
            try:
                client.starttls()
            except smtplib.SMTPNotSupportedError:
                pass
        client.login(user, password)
        client.send_message(message)
    except SendNotConfigured:
        raise
    except Exception as exc:
        raise SendFailed(str(exc) or "send_failed") from exc
    finally:
        try:
            client.quit()
        except Exception:
            pass
    return host


def deliver_mail(
    repo,
    *,
    from_addr: str,
    to_addrs: list[str],
    cc_addrs: list[str] | None = None,
    bcc_addrs: list[str] | None = None,
    subject: str,
    body: str,
    attachments: list | None = None,
    gmail_draft_id: str = "",
) -> dict:
    from csm_dashboard.connectors.google_mail import google_send_ready, send_via_gmail

    secret = smtp_secret(repo)
    gmail_ok = google_send_ready(repo)
    smtp_ok = send_configured(repo)
    if not gmail_ok and not smtp_ok:
        if repo is not None:
            from csm_dashboard.credentials import oauth_connected

            google = repo.get_credential_secret("connector", "google")
            if oauth_connected(google):
                raise SendNotConfigured("google_send_reconnect")
        raise SendNotConfigured("send_not_configured")
    sender = str(from_addr or secret.get("username") or "").strip()
    to = [addr for addr in to_addrs if addr]
    if not sender:
        raise SendNotConfigured("operator_email_required")
    if not to:
        raise ValueError("to_addrs required")
    raw = list(attachments or [])
    files = parse_attachments(raw) if raw and isinstance(raw[0], dict) else raw
    msg = build_message(
        from_addr=sender,
        to_addrs=to,
        cc_addrs=cc_addrs,
        bcc_addrs=bcc_addrs,
        subject=subject,
        body=body,
        attachments=files,
    )
    if gmail_ok:
        return send_via_gmail(
            repo,
            msg,
            from_addr=sender,
            to_addrs=to,
            attach_count=len(files),
            gmail_draft_id=gmail_draft_id,
        )
    host = send_via_smtp(secret, msg)
    log.info(
        "csm.mail.sent via=smtp host=%s to_count=%s attach_count=%s",
        host,
        len(to),
        len(files),
    )
    return {"via": "smtp", "host": host, "from_addr": sender, "to_addrs": to, "attach_count": len(files)}
