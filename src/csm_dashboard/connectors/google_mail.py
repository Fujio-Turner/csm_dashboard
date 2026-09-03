"""Gmail read-only pull. Uses the Google OAuth tokens from Sign in with Google."""

from __future__ import annotations

import base64
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import timezone
from email.utils import getaddresses, parsedate_to_datetime

import httpx

from csm_dashboard.connectors.base import NormalizedEvent
from csm_dashboard.connectors.http import HttpError, _verify, json_get, json_post, json_put
from csm_dashboard.connectors.live import LiveConnector, lookback_days, since_iso
from csm_dashboard.credentials import oauth_connected
from csm_dashboard.storage.repo import utcnow

log = logging.getLogger(__name__)

GMAIL = "https://gmail.googleapis.com/gmail/v1/users/me"
GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
GMAIL_COMPOSE_SCOPE = "https://www.googleapis.com/auth/gmail.compose"
_TAG = re.compile(r"<[^>]+>")
LIST_CAP = 200
LIST_PAGE = 100
PULL_WORKERS = 8
METADATA_HEADERS = [
    "From",
    "To",
    "Cc",
    "Bcc",
    "Subject",
    "Date",
    "Message-ID",
    "In-Reply-To",
    "References",
]


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


def parse_named_addrs(raw: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for name, addr in getaddresses([str(raw or "")]):
        if addr and "@" in addr:
            out.append((str(name or "").strip(), addr.strip()))
    return out


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
    named_from = parse_named_addrs(headers.get("from") or "")
    from_name = named_from[0][0] if named_from else ""
    from_addr = named_from[0][1] if named_from else ((parse_addrs(headers.get("from") or "") or [""])[0])
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
        "from_name": from_name,
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


def clean_domains(raw) -> list[str]:
    out: list[str] = []
    for item in raw or []:
        domain = str(item or "").strip().lower().lstrip("@")
        if domain and domain not in out:
            out.append(domain)
    return out


def _google_scope(repo) -> str:
    if repo is None:
        return ""
    secret = repo.get_credential_secret("connector", "google")
    if not oauth_connected(secret):
        return ""
    return str(secret.get("scope") or "")


def google_send_ready(repo) -> bool:
    scope = _google_scope(repo)
    return bool(
        scope
        and (
            GMAIL_SEND_SCOPE in scope
            or GMAIL_COMPOSE_SCOPE in scope
            or "mail.google.com" in scope
        )
    )


def google_draft_ready(repo) -> bool:
    scope = _google_scope(repo)
    return bool(
        scope
        and (
            GMAIL_COMPOSE_SCOPE in scope
            or "gmail.modify" in scope
            or "mail.google.com" in scope
        )
    )


def rfc822_b64(message) -> str:
    raw = message.as_bytes()
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def send_via_gmail(
    repo,
    message,
    *,
    from_addr: str,
    to_addrs: list[str],
    attach_count: int = 0,
    gmail_draft_id: str = "",
) -> dict:
    if not google_send_ready(repo):
        from csm_dashboard.connectors.smtp_imap import SendNotConfigured

        raise SendNotConfigured("google_send_reconnect")
    conn = GmailConnector(repo)
    hid = str(gmail_draft_id or "").strip()
    try:
        if hid and google_draft_ready(repo):
            try:
                data = conn._post(f"{GMAIL}/drafts/send", {"id": hid})
            except HttpError as exc:
                if exc.status != 404:
                    raise
                data = conn._post(f"{GMAIL}/messages/send", {"raw": rfc822_b64(message)})
        else:
            data = conn._post(f"{GMAIL}/messages/send", {"raw": rfc822_b64(message)})
    except HttpError as exc:
        from csm_dashboard.connectors.smtp_imap import SendFailed, SendNotConfigured

        if exc.status in {401, 403}:
            raise SendNotConfigured("google_send_reconnect") from exc
        raise SendFailed(str(exc) or "send_failed") from exc
    msg = (data or {}).get("message") if isinstance((data or {}).get("message"), dict) else data
    log.info("csm.mail.sent via=gmail to_count=%s attach_count=%s", len(to_addrs), attach_count)
    return {
        "via": "gmail",
        "from_addr": from_addr,
        "to_addrs": list(to_addrs),
        "attach_count": attach_count,
        "gmail_id": str((msg or {}).get("id") or (data or {}).get("id") or ""),
    }


def save_gmail_draft(
    repo,
    message,
    *,
    draft_id: str = "",
    from_addr: str = "",
    to_addrs: list[str] | None = None,
) -> dict:
    if not google_draft_ready(repo):
        from csm_dashboard.connectors.smtp_imap import SendNotConfigured

        raise SendNotConfigured("google_draft_reconnect")
    conn = GmailConnector(repo)
    hid = str(draft_id or "").strip()
    payload = {"message": {"raw": rfc822_b64(message)}}
    try:
        if hid:
            payload["id"] = hid
            try:
                data = conn._put(f"{GMAIL}/drafts/{hid}", payload)
            except HttpError as exc:
                if exc.status != 404:
                    raise
                payload.pop("id", None)
                data = conn._post(f"{GMAIL}/drafts", payload)
        else:
            data = conn._post(f"{GMAIL}/drafts", payload)
    except HttpError as exc:
        from csm_dashboard.connectors.smtp_imap import SendFailed, SendNotConfigured

        if exc.status in {401, 403}:
            raise SendNotConfigured("google_draft_reconnect") from exc
        raise SendFailed(str(exc) or "send_failed") from exc
    log.info("csm.mail.draft_saved via=gmail")
    msg = (data or {}).get("message") if isinstance((data or {}).get("message"), dict) else {}
    return {
        "via": "gmail",
        "from_addr": from_addr,
        "to_addrs": list(to_addrs or []),
        "gmail_draft_id": str((data or {}).get("id") or ""),
        "gmail_id": str((msg or {}).get("id") or ""),
    }


def gmail_search_query(since: str | None, domains: list[str] | None = None, *, days: int = 14) -> str:
    """Gmail `q` for a time window, optionally restricted to customer domains."""
    day = since_iso(since, days=days)[:10].replace("-", "/")
    bits = [f"after:{day}", "-in:chats"]
    cleaned = clean_domains(domains)
    if cleaned:
        inner = " OR ".join(f"from:{d} OR to:{d} OR cc:{d}" for d in cleaned)
        bits.append(f"({inner})")
    return " ".join(bits)


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

    def _get(self, url: str, params: dict | None = None, *, client: httpx.Client | None = None) -> dict:
        try:
            payload = json_get(url, headers=self._headers(), params=params, timeout=60.0, client=client)
        except HttpError as exc:
            if exc.status != 401:
                raise
            from csm_dashboard.connectors import oauth as oauth_flow

            oauth_flow.ensure_access_token("google", self.repo, force=True)
            payload = json_get(url, headers=self._headers(), params=params, timeout=60.0, client=client)
        return payload if isinstance(payload, dict) else {}

    def _post(self, url: str, body: dict | None = None) -> dict:
        try:
            payload = json_post(url, headers=self._headers(), json=body)
        except HttpError as exc:
            if exc.status != 401:
                raise
            from csm_dashboard.connectors import oauth as oauth_flow

            oauth_flow.ensure_access_token("google", self.repo, force=True)
            payload = json_post(url, headers=self._headers(), json=body)
        return payload if isinstance(payload, dict) else {}

    def _put(self, url: str, body: dict | None = None) -> dict:
        try:
            payload = json_put(url, headers=self._headers(), json=body, timeout=60.0)
        except HttpError as exc:
            if exc.status != 401:
                raise
            from csm_dashboard.connectors import oauth as oauth_flow

            oauth_flow.ensure_access_token("google", self.repo, force=True)
            payload = json_put(url, headers=self._headers(), json=body, timeout=60.0)
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

    def _list_ids(self, query: str, *, cap: int = LIST_CAP, client: httpx.Client | None = None) -> list[str]:
        ids: list[str] = []
        token = ""
        while len(ids) < cap:
            params: dict[str, str | int] = {"q": query, "maxResults": min(LIST_PAGE, cap - len(ids))}
            if token:
                params["pageToken"] = token
            listed = self._get(f"{GMAIL}/messages", params, client=client)
            rows = listed.get("messages") if isinstance(listed.get("messages"), list) else []
            for row in rows:
                if isinstance(row, dict) and row.get("id"):
                    ids.append(str(row["id"]))
                    if len(ids) >= cap:
                        break
            token = str(listed.get("nextPageToken") or "")
            if not token:
                break
        return ids

    def _domain_groups(self, account: dict | None) -> list[tuple[list[str], int]]:
        if account:
            domains = clean_domains(account.get("domains"))
            return [(domains, lookback_days(account))]
        groups: list[tuple[list[str], int]] = []
        for row in self.account_rows(None):
            domains = clean_domains(row.get("domains"))
            if domains:
                groups.append((domains, lookback_days(row)))
        return groups or [([], 14)]

    def pull(self, since: str | None, account: dict | None) -> list[NormalizedEvent]:
        if not self.ready():
            raise RuntimeError("not_connected")
        self._headers()
        hid = ""
        if self.repo and not account:
            hid = str((self.repo.get_sync_cursor("google_mail") or {}).get("history_id") or "")
        with httpx.Client(timeout=60.0, verify=_verify()) as client:
            if hid:
                try:
                    events, new_hid = self._pull_history(hid, client)
                    self._store_history_id(new_hid or hid)
                    log.info("csm.connector.pull name=google_mail mode=history listed=%s", len(events))
                    return events
                except HttpError as exc:
                    if exc.status not in {404, 410}:
                        raise
                    log.info("csm.connector.cursor_stale name=google_mail status=%s", exc.status)
            events = self._pull_query(since, account, client)
            self._remember_history_id(client)
            return events

    def _pull_query(self, since: str | None, account: dict | None, client: httpx.Client) -> list[NormalizedEvent]:
        seen: set[str] = set()
        ids: list[str] = []
        for domains, days in self._domain_groups(account):
            query = gmail_search_query(since, domains, days=days)
            log.info("csm.connector.pull name=google_mail q=%s", query)
            for mid in self._list_ids(query, client=client):
                if mid not in seen:
                    seen.add(mid)
                    ids.append(mid)
        log.info("csm.connector.pull name=google_mail listed=%s", len(ids))
        return self._events_from_ids(ids, client)

    def _pull_history(self, history_id: str, client: httpx.Client) -> tuple[list[NormalizedEvent], str]:
        ids: list[str] = []
        seen: set[str] = set()
        token = ""
        new_hid = history_id
        while len(ids) < LIST_CAP:
            params: dict[str, str | int] = {
                "startHistoryId": str(history_id),
                "maxResults": min(LIST_PAGE, LIST_CAP - len(ids)),
            }
            if token:
                params["pageToken"] = token
            listed = self._get(f"{GMAIL}/history", params, client=client)
            new_hid = str(listed.get("historyId") or new_hid)
            rows = listed.get("history") if isinstance(listed.get("history"), list) else []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                for added in row.get("messagesAdded") or []:
                    msg = added.get("message") if isinstance(added, dict) else None
                    mid = str((msg or {}).get("id") or "")
                    if mid and mid not in seen:
                        seen.add(mid)
                        ids.append(mid)
                for msg in row.get("messages") or []:
                    if not isinstance(msg, dict):
                        continue
                    mid = str(msg.get("id") or "")
                    if mid and mid not in seen:
                        seen.add(mid)
                        ids.append(mid)
            token = str(listed.get("nextPageToken") or "")
            if not token:
                break
        return self._events_from_ids(ids, client), new_hid

    def _events_from_ids(self, ids: list[str], client: httpx.Client) -> list[NormalizedEvent]:
        events: list[NormalizedEvent] = []
        if not ids:
            return events
        workers = min(PULL_WORKERS, len(ids))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            messages = list(pool.map(lambda mid: self._fetch_message(mid, client), ids))
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            payload = map_gmail_message(msg)
            addrs = [payload.get("from_addr") or ""]
            addrs.extend(payload.get("to_addrs") or [])
            addrs.extend(payload.get("cc_addrs") or [])
            events.append(
                NormalizedEvent(
                    connector="google_mail",
                    kind="email",
                    external_id=payload.get("message_id") or "",
                    occurred_at=payload.get("sent_at") or utcnow(),
                    account_hint={"domains": [a for a in addrs if a]},
                    payload=payload,
                )
            )
        return events

    def _remember_history_id(self, client: httpx.Client) -> None:
        try:
            me = self._get(f"{GMAIL}/profile", client=client)
        except (HttpError, httpx.TimeoutException, httpx.TransportError):
            return
        hid = str((me or {}).get("historyId") or "")
        self._store_history_id(hid)

    def _store_history_id(self, history_id: str) -> None:
        if self.repo is None:
            return
        patch: dict = {"pulled_at": utcnow()}
        hid = str(history_id or "").strip()
        if hid:
            patch["history_id"] = hid
        self.repo.put_sync_cursor("google_mail", patch)

    def _fetch_message(self, mid: str, client: httpx.Client) -> dict | None:
        try:
            msg = self._get(
                f"{GMAIL}/messages/{mid}",
                {"format": "metadata", "metadataHeaders": METADATA_HEADERS},
                client=client,
            )
        except (HttpError, httpx.TimeoutException, httpx.TransportError):
            return None
        return msg if isinstance(msg, dict) else None


def connector(repo=None) -> GmailConnector:
    return GmailConnector(repo)
