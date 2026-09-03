"""Shared bits for live pull connectors."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from csm_dashboard.connectors.base import ConnectorHealth
from csm_dashboard.credentials import connector_auth, connector_cred_name, oauth_connected
from csm_dashboard.storage.repo import utcnow


LOOKBACK_CHOICES = (14, 90, 365)


def lookback_days(account: dict | None, *, default: int = 14) -> int:
    raw = ((account or {}).get("coverage") or {}).get("lookback_days")
    try:
        days = int(raw)
    except (TypeError, ValueError):
        days = default
    return days if days in LOOKBACK_CHOICES else default


def since_iso(since: str | None, *, days: int = 14) -> str:
    raw = str(since or "").strip()
    if raw:
        return raw
    start = datetime.now(timezone.utc) - timedelta(days=days)
    return start.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def since_unix(since: str | None, *, days: int = 14) -> str:
    raw = since_iso(since, days=days)
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return str(int(dt.timestamp()))
    except ValueError:
        start = datetime.now(timezone.utc) - timedelta(days=days)
        return str(int(start.timestamp()))


def jira_day(since: str | None, *, days: int = 14) -> str:
    raw = since_iso(since, days=days)
    return raw[:16].replace("T", " ")


class LiveConnector:
    name = ""

    def __init__(self, repo=None) -> None:
        self.repo = repo

    def cred_name(self) -> str:
        return connector_cred_name(self.name)

    def secret(self) -> dict:
        if self.repo is None:
            return {}
        return self.repo.get_credential_secret("connector", self.cred_name())

    def account_rows(self, account: dict | None) -> list[dict]:
        if account:
            return [account]
        if self.repo is None:
            return []
        return [row for row in self.repo.list_accounts(include_hidden=True) if not row.get("removed")]

    def ready(self) -> bool:
        secret = self.secret()
        if connector_auth(self.name) == "oauth":
            return oauth_connected(secret)
        return any(str(secret.get(key) or "").strip() for key in ("api_token", "password", "user_token"))

    def health(self) -> ConnectorHealth:
        ok = self.ready()
        return ConnectorHealth(
            name=self.name,
            ok=ok,
            mode="disabled",
            last_ok_at=utcnow() if ok else "",
            message="ready" if ok else "not_connected",
        )

    def probe(self) -> ConnectorHealth:
        return self.health()
