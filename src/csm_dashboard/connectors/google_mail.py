"""Gmail read-only pull. Uses the Google OAuth tokens from Sign in with Google."""

from __future__ import annotations

import base64
import logging
import re
from datetime import timezone
from email.utils import getaddresses, parsedate_to_datetime

from csm_dashboard.connectors.base import NormalizedEvent
from csm_dashboard.connectors.http import HttpError, json_get
from csm_dashboard.connectors.live import LiveConnector, since_iso
from csm_dashboard.credentials import oauth_connected
from csm_dashboard.storage.repo import utcnow

log = logging.getLogger(__name__)

GMAIL = "https://gmail.googleapis.com/gmail/v1/users/me"
_TAG = re.compile(r"<[^>]+>")


def _b64url(raw: str) -> str:
    pad = "=" * ((4 - len(raw) % 4) % 4)
    try:
        return base64.urlsafe_b64decode((raw + pad).encode("ascii")).decode("utf-8", "ignore")
    except Exception:
        return ""


def strip_html(raw: str) -> str:
    return " ".join(_TAG.sub(" ", str(raw or "")).split())


def header_map(payload: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for row in payload.get("headers") or []:
        if isinstance(row, dict) and row.get("name"):
            out[str(row["name"]).lower()] = str(row.get("value") or "")
    return out


def parse_addrs(raw: str) -> list[str]:
    return [addr.strip() for _, addr in getaddresses([str(raw or "")]) if addr and "@" in addr]


def header_time(raw: str) -> str:
    text = str(raw or "").strip()
    if not text:
        return utcnow()
    try:
        dt = parsedate_to_datetime(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    except Exception:
        return utcnow()


def gmail_body(payload: dict | None) -> str:
    if not isinstance(payload, dict):
        return ""
    mime = str(payload.get("mimeType") or "")
    data = str(((payload.get("body") or {}) if isinstance(payload.get("body"), dict) else {}).get("data") or "")
    if data and mime.startswith("text/plain"):
        return _b64url(data)
    parts = payload.get("parts") if isinstance(payload.get("parts"), list) else []
    if parts:
        texts = [gmail_body(part) for part in parts if isinstance(part, dict)]
        plain = [t for t in texts if t]
        return "\n".join(plain)
    if data and mime.startswith("text/html"):
        return strip_html(_b64url(data))
    if data:
        return _b64url(data)
    return ""


def map_gmail_message(msg: dict) -> dict:
    payload = msg.get("payload") if isinstance(msg.get("payload"), dict) else {}
    headers = header_map(payload)
    labels = [str(item) for item in (msg.get("labelIds") or [])]
    from_addr = (parse_addrs(headers.get("from") or "") or [""])[0]
    to_addrs = parse_addrs(headers.get("to") or "")
    cc_addrs = parse_addrs(headers.get("cc") or "")
    mid = str(headers.get("message-id") or "").strip() or f"<gmail.{msg.get('id')}@gmail.internal>"
    body = gmail_body(payload)
    snippet = str(msg.get("snippet") or "")
    sent = header_time(headers.get("date") or "")
    return {
        "type": "email",
        "direction": "outbound" if "SENT" in labels else "inbound",
        "message_id": mid,
        "in_reply_to": str(headers.get("in-reply-to") or ""),
        "references": str(headers.get("references") or ""),
        "from_addr": from_addr,
        "to_addrs": to_addrs,
        "cc_addrs": cc_addrs,
        "subject": str(headers.get("subject") or "(No subject)"),
        "sent_at": sent,
        "snippet": snippet,
        "body_text": body or snippet,
        "has_attachments": any(
            bool(part.get("filename"))
            for part in (payload.get("parts") or [])
            if isinstance(part, dict)
        ),
        "sources": {
            "google_mail": {
                "fetched_at": utcnow(),
                "gmail_id": str(msg.get("id") or ""),
                "gmail_thread": str(msg.get("threadId") or ""),
            }
        },
    }


class GmailConnector(LiveConnector):
    name = "google_mail"

    def ready(self) -> bool:
        return oauth_connected(self.secret())

    def _headers(self) -> dict[str, str]:
        from csm_dashboard.connectors import oauth as oauth_flow

        token = oauth_flow.ensure_access_token("google", self.repo)
        if not token:
            raise RuntimeError("not_connected")
        return {"Authorization": f"Bearer {token}"}

    def _get(self, url: str, params: dict | None = None) -> dict:
        try:
            payload = json_get(url, headers=self._headers(), params=params)
        except HttpError as exc:
            if exc.status != 401:
                raise
            from csm_dashboard.connectors import oauth as oauth_flow

            oauth_flow.ensure_access_token("google", self.repo, force=True)
            payload = json_get(url, headers=self._headers(), params=params)
        return payload if isinstance(payload, dict) else {}

    def probe(self) -> dict:
        health = self.health()
        if not health.get("ok"):
            return health
        try:
            me = self._get(f"{GMAIL}/profile")
            health["message"] = "ok"
            health["last_ok_at"] = utcnow()
            health["email"] = str(me.get("emailAddress") or "")
        except Exception as exc:
            health["ok"] = False
            health["message"] = str(exc)
            log.info("csm.connector.probe name=google_mail ok=false err=%s", exc)
        return health

    def pull(self, since: str | None, account: dict | None) -> list[NormalizedEvent]:
        if not self.ready():
            raise RuntimeError("not_connected")
        day = since_iso(since)[:10].replace("-", "/")
        query = f"after:{day}"
        listed = self._get(f"{GMAIL}/messages", {"q": query, "maxResults": 40})
        rows = listed.get("messages") if isinstance(listed.get("messages"), list) else []
        events: list[NormalizedEvent] = []
        log.info("csm.connector.pull name=google_mail listed=%s", len(rows))
        for row in rows[:40]:
            if not isinstance(row, dict) or not row.get("id"):
                continue
            try:
                msg = self._get(f"{GMAIL}/messages/{row['id']}", {"format": "full"})
            except HttpError:
                continue
            payload = map_gmail_message(msg)
            events.append(
                NormalizedEvent(
                    connector="google_mail",
                    kind="email",
                    external_id=payload.get("message_id") or "",
                    occurred_at=payload.get("sent_at") or utcnow(),
                    account_hint={"domains": []},
                    payload=payload,
                )
            )
        return events


def connector(repo=None) -> GmailConnector:
    return GmailConnector(repo)
