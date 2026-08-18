from __future__ import annotations

from typing import Protocol


class NormalizedEvent(dict):
    """Keys: connector, kind, external_id, occurred_at, account_hint, payload."""


class ConnectorHealth(dict):
    """Keys: name, ok, mode, last_ok_at, message. Never include tokens."""


class Connector(Protocol):
    name: str

    def pull(self, since: str | None, account: dict | None) -> list[NormalizedEvent]:
        """Incremental fetch. Stub ignores since and returns fixtures for account."""

    def health(self) -> ConnectorHealth:
        ...
