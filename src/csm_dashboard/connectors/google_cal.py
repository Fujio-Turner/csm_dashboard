"""Google Calendar read-only pull. Shares the Gmail Google OAuth tokens."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone

import httpx

from csm_dashboard.connectors.base import NormalizedEvent
from csm_dashboard.connectors.http import HttpError, _verify, json_get
from csm_dashboard.connectors.live import LiveConnector, lookback_days, since_iso
from csm_dashboard.credentials import oauth_connected
from csm_dashboard.storage.repo import utcnow

log = logging.getLogger(__name__)

CAL = "https://www.googleapis.com/calendar/v3"
LIST_CAP = 250
LIST_PAGE = 100
SEED_PAGES = 80
LIST_FIELDS = (
    "nextPageToken,nextSyncToken,"
    "items(id,status,summary,start,end,attendees(email,displayName),location,hangoutLink)"
)


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
        "status": str(ev.get("status") or "").lower(),
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

    def _get(self, url: str, params: dict | None = None, *, client: httpx.Client | None = None) -> dict:
        last: Exception | None = None
        http = client
        for attempt in range(3):
            try:
                payload = json_get(url, headers=self._headers(), params=params, timeout=60.0, client=http)
            except HttpError as exc:
                if exc.status != 401:
                    raise
                from csm_dashboard.connectors import oauth as oauth_flow

                oauth_flow.ensure_access_token("google", self.repo, force=True)
                payload = json_get(url, headers=self._headers(), params=params, timeout=60.0, client=http)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last = exc
                log.info("csm.connector.retry name=google_cal attempt=%s err=%s", attempt + 1, exc)
                http = None
                if attempt < 2:
                    time.sleep(0.3)
                continue
            return payload if isinstance(payload, dict) else {}
        assert last is not None
        raise last

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
        with httpx.Client(timeout=60.0, verify=_verify()) as client:
            return self._pull(since, account, client)

    def _pull(self, since: str | None, account: dict | None, client: httpx.Client) -> list[NormalizedEvent]:
        if account:
            rows, _ignored = self._list_bounded(since, account, client)
            events = self._events_from_rows(rows)
            log.info("csm.connector.pull name=google_cal listed=%s", len(events))
            return events
        token = ""
        if self.repo:
            token = str((self.repo.get_sync_cursor("google_cal") or {}).get("sync_token") or "")
        if token:
            try:
                rows, new_token = self._list_sync(token, client)
                events = self._events_from_rows(rows)
                self._store_sync_token(new_token or token)
                log.info("csm.connector.pull name=google_cal mode=sync listed=%s", len(events))
                return events
            except HttpError as exc:
                if exc.status not in {410, 404}:
                    raise
                log.info("csm.connector.cursor_stale name=google_cal status=%s", exc.status)
        try:
            rows, new_token = self._list_initial(since, client)
            events = self._events_from_rows(rows)
            self._store_sync_token(new_token)
            log.info("csm.connector.pull name=google_cal listed=%s token=%s", len(events), bool(new_token))
            return events
        except (HttpError, httpx.TimeoutException, httpx.TransportError) as exc:
            log.info("csm.connector.cursor_seed_failed name=google_cal err=%s", exc)
            self._store_sync_token("")
            raise

    def _window_days(self, account: dict | None) -> int:
        if account:
            return lookback_days(account)
        days = [lookback_days(row) for row in self.account_rows(None)]
        return max(days) if days else 14

    def _list_bounded(self, since: str | None, account: dict | None, client: httpx.Client | None = None) -> tuple[list[dict], str]:
        time_min = since_iso(since, days=self._window_days(account))
        time_max = (datetime.now(timezone.utc) + timedelta(days=14)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        rows: list[dict] = []
        page = ""
        while len(rows) < LIST_CAP:
            params: dict[str, str | int] = {
                "timeMin": time_min,
                "timeMax": time_max,
                "singleEvents": "true",
                "orderBy": "startTime",
                "maxResults": min(LIST_PAGE, LIST_CAP - len(rows)),
                "fields": LIST_FIELDS,
            }
            if page:
                params["pageToken"] = page
            data = self._get(f"{CAL}/calendars/primary/events", params, client=client)
            items = data.get("items") if isinstance(data.get("items"), list) else []
            for row in items:
                if isinstance(row, dict):
                    rows.append(row)
                    if len(rows) >= LIST_CAP:
                        break
            page = str(data.get("nextPageToken") or "")
            if not page:
                break
        return rows, ""

    def _list_initial(self, since: str | None, client: httpx.Client | None = None) -> tuple[list[dict], str]:
        """Lookback window, paginated to the last page so Google returns nextSyncToken."""
        time_min = since_iso(since, days=self._window_days(None))
        rows: list[dict] = []
        page = ""
        token = ""
        pages = 0
        while pages < SEED_PAGES:
            pages += 1
            params: dict[str, str | int] = {
                "timeMin": time_min,
                "singleEvents": "true",
                "showDeleted": "true",
                "maxResults": LIST_PAGE,
                "fields": LIST_FIELDS,
            }
            if page:
                params["pageToken"] = page
            data = self._get(f"{CAL}/calendars/primary/events", params, client=client)
            items = data.get("items") if isinstance(data.get("items"), list) else []
            for row in items:
                if isinstance(row, dict) and len(rows) < LIST_CAP:
                    rows.append(row)
            page = str(data.get("nextPageToken") or "")
            token = str(data.get("nextSyncToken") or token)
            if not page:
                break
        log.info("csm.connector.pull name=google_cal mode=seed pages=%s token=%s", pages, bool(token))
        return rows, token

    def _list_sync(self, sync_token: str, client: httpx.Client | None = None) -> tuple[list[dict], str]:
        rows: list[dict] = []
        page = ""
        new_token = sync_token
        while len(rows) < LIST_CAP:
            params: dict[str, str | int] = {
                "maxResults": min(LIST_PAGE, LIST_CAP - len(rows)),
                "singleEvents": "true",
                "showDeleted": "true",
                "fields": LIST_FIELDS,
            }
            if page:
                params["pageToken"] = page
            else:
                params["syncToken"] = sync_token
            data = self._get(f"{CAL}/calendars/primary/events", params, client=client)
            items = data.get("items") if isinstance(data.get("items"), list) else []
            for row in items:
                if isinstance(row, dict):
                    rows.append(row)
                    if len(rows) >= LIST_CAP:
                        break
            page = str(data.get("nextPageToken") or "")
            new_token = str(data.get("nextSyncToken") or new_token)
            if not page:
                break
        return rows, new_token

    def _events_from_rows(self, rows: list[dict]) -> list[NormalizedEvent]:
        events: list[NormalizedEvent] = []
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

    def _store_sync_token(self, token: str) -> None:
        if self.repo is None:
            return
        patch: dict = {"pulled_at": utcnow()}
        value = str(token or "").strip()
        if value:
            patch["sync_token"] = value
        self.repo.put_sync_cursor("google_cal", patch)


def connector(repo=None) -> GoogleCalConnector:
    return GoogleCalConnector(repo)
