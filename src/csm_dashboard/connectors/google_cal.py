"""Google Calendar read-only pull. Shares the Gmail Google OAuth tokens."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from csm_dashboard.connectors.base import NormalizedEvent
from csm_dashboard.connectors.http import HttpError, json_get
from csm_dashboard.connectors.live import LiveConnector, since_iso
from csm_dashboard.credentials import oauth_connected
from csm_dashboard.storage.repo import utcnow

log = logging.getLogger(__name__)

CAL = "https://www.googleapis.com/calendar/v3"


def cal_time(blob) -> str:
    if not isinstance(blob, dict):
        return ""
    raw = str(blob.get("dateTime") or blob.get("date") or "").strip()
    if not raw:
        return ""
    if "T" not in raw:
        return raw + "T00:00:00Z"
    text = raw.replace("+00:00", "Z")
    if text.endswith("Z") and len(text) >= 19:
        return text[:19] + "Z"
    return text


def map_event(ev: dict) -> dict:
    attendees = []
    for row in ev.get("attendees") or []:
        if not isinstance(row, dict) or not row.get("email"):
            continue
        attendees.append({"email": str(row.get("email") or ""), "name": str(row.get("displayName") or "")})
    return {
        "type": "calendar_event",
        "provider": "google",
        "external_id": str(ev.get("id") or ""),
        "title": str(ev.get("summary") or ""),
        "start_at": cal_time(ev.get("start") if isinstance(ev.get("start"), dict) else {}),
        "end_at": cal_time(ev.get("end") if isinstance(ev.get("end"), dict) else {}),
        "attendees": attendees,
        "location": str(ev.get("location") or ev.get("hangoutLink") or ""),
        "sources": {"google_cal": {"fetched_at": utcnow()}},
    }


class GoogleCalConnector(LiveConnector):
    name = "google_cal"

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
            self._get(f"{CAL}/users/me/calendarList", {"maxResults": 1})
            health["message"] = "ok"
            health["last_ok_at"] = utcnow()
        except Exception as exc:
            health["ok"] = False
            health["message"] = str(exc)
            log.info("csm.connector.probe name=google_cal ok=false err=%s", exc)
        return health

    def pull(self, since: str | None, account: dict | None) -> list[NormalizedEvent]:
        if not self.ready():
            raise RuntimeError("not_connected")
        time_min = since_iso(since)
        time_max = (datetime.now(timezone.utc) + timedelta(days=14)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        data = self._get(
            f"{CAL}/calendars/primary/events",
            {
                "timeMin": time_min,
                "timeMax": time_max,
                "singleEvents": "true",
                "orderBy": "startTime",
                "maxResults": 100,
            },
        )
        rows = data.get("items") if isinstance(data.get("items"), list) else []
        events: list[NormalizedEvent] = []
        log.info("csm.connector.pull name=google_cal listed=%s", len(rows))
        for row in rows:
            if not isinstance(row, dict):
                continue
            payload = map_event(row)
            if not payload.get("external_id"):
                continue
            events.append(
                NormalizedEvent(
                    connector="google_cal",
                    kind="calendar_event",
                    external_id=payload.get("external_id") or "",
                    occurred_at=payload.get("start_at") or utcnow(),
                    account_hint={"domains": [a.get("email") for a in payload.get("attendees") or [] if a.get("email")]},
                    payload=payload,
                )
            )
        return events


def connector(repo=None) -> GoogleCalConnector:
    return GoogleCalConnector(repo)
