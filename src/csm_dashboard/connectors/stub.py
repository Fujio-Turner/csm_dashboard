from __future__ import annotations

import json
from pathlib import Path

from csm_dashboard.config import fixtures_dir, load_settings
from csm_dashboard.connectors.base import ConnectorHealth, NormalizedEvent
from csm_dashboard.storage.repo import utcnow

KIND_FILES = {
    "jira": ("tickets.json", "ticket"),
    "smtp_imap": ("emails.json", "email"),
    "google_mail": ("emails.json", "email"),
    "microsoft365": ("emails.json", "email"),
    "slack": ("slack_messages.json", "slack_message"),
    "teams": ("teams_messages.json", "teams_message"),
    "salesforce": ("salesforce_opportunities.json", "salesforce_opportunity"),
    "google_cal": ("calendar_events.json", "calendar_event"),
    "m365_cal": ("calendar_events.json", "calendar_event"),
}


class StubConnector:
    def __init__(self, name: str) -> None:
        self.name = name

    def _mode(self) -> str:
        cfg = (load_settings().connectors.get(self.name) or {})
        return str(cfg.get("mode") or "stub")

    def health(self) -> ConnectorHealth:
        try:
            seed = fixtures_dir() / "seed"
            ok = seed.is_dir()
            msg = "stub" if ok else "fixtures missing"
        except FileNotFoundError:
            ok = False
            msg = "fixtures missing"
        return ConnectorHealth(name=self.name, ok=ok, mode=self._mode(), last_ok_at=utcnow(), message=msg)

    def pull(self, since: str | None, account: dict | None) -> list[NormalizedEvent]:
        filename, kind = KIND_FILES[self.name]
        path = Path(fixtures_dir()) / "seed" / filename
        if not path.is_file():
            return []
        rows = json.loads(path.read_text(encoding="utf-8"))
        events: list[NormalizedEvent] = []
        aid = (account or {}).get("account_id") or (account or {}).get("_id")
        extra_file = None
        if kind == "slack_message":
            extra_file = Path(fixtures_dir()) / "seed" / "slack_channels.json"
        if kind == "teams_message":
            extra_file = Path(fixtures_dir()) / "seed" / "teams_channels.json"
        if kind == "salesforce_opportunity":
            extra_file = Path(fixtures_dir()) / "seed" / "salesforce_cases.json"
        if extra_file and extra_file.is_file():
            for row in json.loads(extra_file.read_text(encoding="utf-8")):
                if aid and row.get("account_id") != aid:
                    continue
                extra_kind = "slack_channel"
                if kind == "teams_message":
                    extra_kind = "teams_channel"
                elif kind == "salesforce_opportunity":
                    extra_kind = "salesforce_case"
                events.append(
                    NormalizedEvent(
                        connector=self.name,
                        kind=extra_kind,
                        external_id=row.get("channel_id") or "",
                        occurred_at=row.get("updated_at") or utcnow(),
                        account_hint={},
                        payload=row,
                    )
                )
        for row in rows:
            if aid and row.get("account_id") != aid:
                continue
            events.append(
                NormalizedEvent(
                    connector=self.name,
                    kind=kind,
                    external_id=row.get("key")
                    or row.get("message_id")
                    or row.get("ts")
                    or row.get("case_number")
                    or row.get("external_id")
                    or "",
                    occurred_at=row.get("updated_at") or row.get("sent_at") or row.get("start_at") or utcnow(),
                    account_hint={},
                    payload=row,
                )
            )
        return events
