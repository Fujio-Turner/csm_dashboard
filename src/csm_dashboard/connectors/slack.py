"""Slack read-only pull. User token (xoxp) or OAuth bot/user tokens."""

from __future__ import annotations

import logging

from csm_dashboard.connectors.base import NormalizedEvent
from csm_dashboard.connectors.http import json_get
from csm_dashboard.connectors.live import LiveConnector, since_unix
from csm_dashboard.credentials import oauth_connected
from csm_dashboard.storage.repo import utcnow

log = logging.getLogger(__name__)

SKIP_SUBTYPES = frozenset({"channel_join", "channel_leave", "channel_topic", "channel_purpose"})


def slack_token(secret: dict) -> str:
    for key in ("user_token", "bot_token", "access_token"):
        value = str(secret.get(key) or "").strip()
        if value:
            return value
    return ""


def map_channel(row: dict) -> dict:
    topic = row.get("topic") if isinstance(row.get("topic"), dict) else {}
    purpose = row.get("purpose") if isinstance(row.get("purpose"), dict) else {}
    return {
        "type": "slack_channel",
        "channel_id": str(row.get("id") or ""),
        "name": str(row.get("name") or ""),
        "is_private": bool(row.get("is_private")),
        "topic": str(topic.get("value") or purpose.get("value") or ""),
    }


def map_message(row: dict, *, channel_id: str, user_name: str = "") -> dict:
    ts = str(row.get("ts") or "")
    permalink = str(row.get("permalink") or "")
    if not permalink and channel_id and ts:
        permalink = f"https://slack.com/archives/{channel_id}/p{ts.replace('.', '')}"
    return {
        "type": "slack_message",
        "channel_id": channel_id,
        "ts": ts,
        "thread_ts": str(row.get("thread_ts") or ""),
        "user": str(row.get("user") or row.get("bot_id") or ""),
        "user_name": user_name or str(row.get("username") or row.get("user") or ""),
        "text": str(row.get("text") or ""),
        "permalink": permalink,
        "sources": {"slack": {"fetched_at": utcnow()}},
    }


def configured_channel_ids(accounts: list[dict]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for acct in accounts:
        for cid in ((acct.get("connectors") or {}).get("slack") or {}).get("channel_ids") or []:
            value = str(cid or "").strip()
            if value and value not in seen:
                seen.add(value)
                out.append(value)
    return out


class SlackConnector(LiveConnector):
    name = "slack"

    def ready(self) -> bool:
        return oauth_connected(self.secret()) or bool(slack_token(self.secret()))

    def _token(self) -> str:
        token = slack_token(self.secret())
        if not token:
            raise RuntimeError("not_connected")
        return token

    def _api(self, method: str, params: dict | None = None) -> dict:
        payload = json_get(
            f"https://slack.com/api/{method}",
            headers={"Authorization": f"Bearer {self._token()}"},
            params=params or {},
        )
        if not isinstance(payload, dict):
            raise RuntimeError("slack_bad_payload")
        if payload.get("ok") is False:
            raise RuntimeError(str(payload.get("error") or "slack_error"))
        return payload

    def probe(self) -> dict:
        health = self.health()
        if not health.get("ok"):
            return health
        try:
            data = self._api("auth.test")
            health["message"] = "ok"
            health["team"] = str(data.get("team") or "")
            health["last_ok_at"] = utcnow()
        except Exception as exc:
            health["ok"] = False
            health["message"] = str(exc)
            log.info("csm.connector.probe name=slack ok=false err=%s", exc)
        return health

    def _resolve_user(self, user_id: str, cache: dict[str, str]) -> str:
        if not user_id:
            return ""
        if user_id in cache:
            return cache[user_id]
        try:
            data = self._api("users.info", {"user": user_id})
            user = data.get("user") if isinstance(data.get("user"), dict) else {}
            profile = user.get("profile") if isinstance(user.get("profile"), dict) else {}
            name = str(profile.get("display_name") or profile.get("real_name") or user.get("name") or user_id)
        except Exception:
            name = user_id
        cache[user_id] = name
        return name

    def _list_channels(self) -> list[dict]:
        channels: list[dict] = []
        cursor = ""
        while len(channels) < 80:
            params = {
                "types": "public_channel,private_channel",
                "exclude_archived": "true",
                "limit": 200,
            }
            if cursor:
                params["cursor"] = cursor
            try:
                data = self._api("conversations.list", params)
            except RuntimeError as exc:
                if str(exc) in {"missing_scope", "not_allowed_token_type"}:
                    break
                raise
            batch = data.get("channels") if isinstance(data.get("channels"), list) else []
            channels.extend(row for row in batch if isinstance(row, dict))
            cursor = str(((data.get("response_metadata") or {}) if isinstance(data.get("response_metadata"), dict) else {}).get("next_cursor") or "")
            if not cursor or not batch:
                break
        return channels[:80]

    def _history(self, channel_id: str, oldest: str) -> list[dict]:
        messages: list[dict] = []
        cursor = ""
        while len(messages) < 200:
            params = {"channel": channel_id, "oldest": oldest, "limit": 200}
            if cursor:
                params["cursor"] = cursor
            try:
                data = self._api("conversations.history", params)
            except RuntimeError as exc:
                if str(exc) in {"not_in_channel", "channel_not_found", "missing_scope"}:
                    log.info("csm.connector.pull name=slack skip_channel err=%s", exc)
                    return []
                raise
            batch = data.get("messages") if isinstance(data.get("messages"), list) else []
            messages.extend(row for row in batch if isinstance(row, dict))
            meta = data.get("response_metadata") if isinstance(data.get("response_metadata"), dict) else {}
            cursor = str(meta.get("next_cursor") or "")
            if not data.get("has_more") or not cursor or not batch:
                break
        return messages[:200]

    def pull(self, since: str | None, account: dict | None) -> list[NormalizedEvent]:
        if not self.ready():
            raise RuntimeError("not_connected")
        accounts = self.account_rows(account)
        wanted = configured_channel_ids(accounts)
        listed = self._list_channels()
        by_id = {str(row.get("id") or ""): row for row in listed}
        channel_ids = wanted or [cid for cid in by_id if cid]
        oldest = since_unix(since)
        events: list[NormalizedEvent] = []
        users: dict[str, str] = {}
        seen_channels: set[str] = set()
        log.info("csm.connector.pull name=slack channels=%s", len(channel_ids))
        for cid in channel_ids:
            row = by_id.get(cid) or {"id": cid, "name": cid}
            if cid not in seen_channels:
                payload = map_channel(row)
                events.append(
                    NormalizedEvent(
                        connector="slack",
                        kind="slack_channel",
                        external_id=cid,
                        occurred_at=utcnow(),
                        account_hint={"channel_ids": [cid]},
                        payload=payload,
                    )
                )
                seen_channels.add(cid)
            for msg in self._history(cid, oldest):
                if str(msg.get("subtype") or "") in SKIP_SUBTYPES:
                    continue
                user_name = self._resolve_user(str(msg.get("user") or ""), users)
                payload = map_message(msg, channel_id=cid, user_name=user_name)
                events.append(
                    NormalizedEvent(
                        connector="slack",
                        kind="slack_message",
                        external_id=payload.get("ts") or "",
                        occurred_at=payload.get("ts") or utcnow(),
                        account_hint={"channel_ids": [cid]},
                        payload=payload,
                    )
                )
        return events


def connector(repo=None) -> SlackConnector:
    return SlackConnector(repo)
