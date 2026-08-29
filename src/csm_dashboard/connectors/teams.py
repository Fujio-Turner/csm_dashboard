"""Microsoft Teams read-only pull via Graph (Chat.Read). Shares Microsoft OAuth tokens."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from urllib.parse import quote

from csm_dashboard.connectors.base import NormalizedEvent
from csm_dashboard.connectors.http import HttpError, json_get
from csm_dashboard.connectors.live import LiveConnector, since_iso
from csm_dashboard.credentials import oauth_connected
from csm_dashboard.storage.repo import utcnow

log = logging.getLogger(__name__)

GRAPH = "https://graph.microsoft.com/v1.0"
_TAG = re.compile(r"<[^>]+>")


def strip_html(raw: str) -> str:
    text = _TAG.sub(" ", str(raw or ""))
    return " ".join(text.split())


def graph_ts(raw: str) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return f"{dt.timestamp():.6f}"
    except ValueError:
        return text


def chat_title(chat: dict) -> str:
    topic = chat.get("topic")
    if isinstance(topic, dict):
        source = str(topic.get("source") or "").strip()
        if source:
            return source[:80]
    if isinstance(topic, str) and topic.strip():
        return topic.strip()[:80]
    names: list[str] = []
    for member in chat.get("members") or []:
        if not isinstance(member, dict):
            continue
        name = str(member.get("displayName") or "").strip()
        if name:
            names.append(name)
    return ", ".join(names)[:80]


def map_channel(row: dict, *, team_name: str = "") -> dict:
    cid = str(row.get("id") or "")
    return {
        "type": "teams_channel",
        "channel_id": cid,
        "name": str(row.get("displayName") or chat_title(row) or cid),
        "team_name": team_name,
        "topic": str(row.get("description") or chat_title(row) or ""),
    }


def map_message(row: dict, *, channel_id: str) -> dict:
    from_blob = row.get("from") if isinstance(row.get("from"), dict) else {}
    user = from_blob.get("user") if isinstance(from_blob.get("user"), dict) else {}
    app = from_blob.get("application") if isinstance(from_blob.get("application"), dict) else {}
    name = str(user.get("displayName") or app.get("displayName") or "")
    body = row.get("body") if isinstance(row.get("body"), dict) else {}
    created = str(row.get("createdDateTime") or "")
    web = str(row.get("webUrl") or "")
    return {
        "type": "teams_message",
        "channel_id": channel_id,
        "ts": graph_ts(created) or created,
        "thread_id": str(row.get("replyToId") or ""),
        "user": str(user.get("id") or app.get("id") or ""),
        "user_name": name,
        "text": strip_html(str(body.get("content") or "")),
        "permalink": web,
        "sources": {"teams": {"fetched_at": utcnow()}},
    }


def configured_channel_ids(accounts: list[dict]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for acct in accounts:
        for cid in ((acct.get("connectors") or {}).get("teams") or {}).get("channel_ids") or []:
            value = str(cid or "").strip()
            if value and value not in seen:
                seen.add(value)
                out.append(value)
    return out


class TeamsConnector(LiveConnector):
    name = "teams"

    def ready(self) -> bool:
        return oauth_connected(self.secret())

    def _headers(self) -> dict[str, str]:
        from csm_dashboard.connectors import oauth as oauth_flow

        token = oauth_flow.ensure_access_token("microsoft", self.repo)
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

            oauth_flow.ensure_access_token("microsoft", self.repo, force=True)
            payload = json_get(url, headers=self._headers(), params=params)
        return payload if isinstance(payload, dict) else {}

    def _pages(self, url: str, params: dict | None = None, *, cap: int = 50) -> list[dict]:
        items: list[dict] = []
        next_url = url
        query = params
        while next_url and len(items) < cap:
            try:
                data = self._get(next_url, query)
            except HttpError as exc:
                if exc.status in {403, 404}:
                    break
                raise
            batch = data.get("value") if isinstance(data.get("value"), list) else []
            items.extend(row for row in batch if isinstance(row, dict))
            next_url = str(data.get("@odata.nextLink") or "")
            query = None
        return items[:cap]

    def probe(self) -> dict:
        health = self.health()
        if not health.get("ok"):
            return health
        try:
            me = self._get(f"{GRAPH}/me")
            health["message"] = "ok"
            health["last_ok_at"] = utcnow()
            health["upn"] = str(me.get("userPrincipalName") or me.get("mail") or "")
        except Exception as exc:
            health["ok"] = False
            health["message"] = str(exc)
            log.info("csm.connector.probe name=teams ok=false err=%s", exc)
        return health

    def pull(self, since: str | None, account: dict | None) -> list[NormalizedEvent]:
        if not self.ready():
            raise RuntimeError("not_connected")
        accounts = self.account_rows(account)
        wanted = set(configured_channel_ids(accounts))
        cutoff = since_iso(since)
        events: list[NormalizedEvent] = []
        try:
            chats = self._pages(f"{GRAPH}/me/chats", {"$top": "50", "$expand": "members"}, cap=50)
        except HttpError as exc:
            if exc.status not in {400, 501}:
                raise
            chats = self._pages(f"{GRAPH}/me/chats", {"$top": "50"}, cap=50)
        log.info("csm.connector.pull name=teams chats=%s", len(chats))
        for chat in chats:
            cid = str(chat.get("id") or "")
            if not cid:
                continue
            if wanted and cid not in wanted:
                continue
            encoded = quote(cid, safe="")
            channel_payload = map_channel(chat)
            events.append(
                NormalizedEvent(
                    connector="teams",
                    kind="teams_channel",
                    external_id=cid,
                    occurred_at=utcnow(),
                    account_hint={"channel_ids": [cid]},
                    payload=channel_payload,
                )
            )
            messages = self._pages(f"{GRAPH}/me/chats/{encoded}/messages", {"$top": "50"}, cap=50)
            for msg in messages:
                if str(msg.get("messageType") or "") not in {"", "message"}:
                    continue
                created = str(msg.get("createdDateTime") or "")
                if cutoff and created and created < cutoff:
                    continue
                payload = map_message(msg, channel_id=cid)
                events.append(
                    NormalizedEvent(
                        connector="teams",
                        kind="teams_message",
                        external_id=payload.get("ts") or "",
                        occurred_at=payload.get("ts") or utcnow(),
                        account_hint={"channel_ids": [cid]},
                        payload=payload,
                    )
                )
        try:
            teams = self._pages(f"{GRAPH}/me/joinedTeams", cap=20)
        except HttpError:
            teams = []
        for team in teams:
            tid = str(team.get("id") or "")
            team_name = str(team.get("displayName") or "")
            if not tid:
                continue
            try:
                channels = self._pages(f"{GRAPH}/teams/{tid}/channels", cap=30)
            except HttpError:
                continue
            for ch in channels:
                cid = str(ch.get("id") or "")
                if not cid:
                    continue
                if wanted and cid not in wanted:
                    continue
                events.append(
                    NormalizedEvent(
                        connector="teams",
                        kind="teams_channel",
                        external_id=cid,
                        occurred_at=utcnow(),
                        account_hint={"channel_ids": [cid]},
                        payload=map_channel(ch, team_name=team_name),
                    )
                )
                try:
                    messages = self._pages(
                        f"{GRAPH}/teams/{quote(tid, safe='')}/channels/{quote(cid, safe='')}/messages",
                        {"$top": "50"},
                        cap=50,
                    )
                except HttpError:
                    continue
                for msg in messages:
                    created = str(msg.get("createdDateTime") or "")
                    if cutoff and created and created < cutoff:
                        continue
                    payload = map_message(msg, channel_id=cid)
                    events.append(
                        NormalizedEvent(
                            connector="teams",
                            kind="teams_message",
                            external_id=payload.get("ts") or "",
                            occurred_at=payload.get("ts") or utcnow(),
                            account_hint={"channel_ids": [cid]},
                            payload=payload,
                        )
                    )
        return events


def connector(repo=None) -> TeamsConnector:
    return TeamsConnector(repo)
