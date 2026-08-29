from __future__ import annotations

from csm_dashboard.config import load_settings
from csm_dashboard.connectors.base import ConnectorHealth, NormalizedEvent
from csm_dashboard.storage.repo import utcnow


class StubConnector:
    def __init__(self, name: str) -> None:
        self.name = name

    def _mode(self) -> str:
        cfg = load_settings().connectors.get(self.name) or {}
        return str(cfg.get("mode") or "disabled")

    def health(self) -> ConnectorHealth:
        return ConnectorHealth(
            name=self.name,
            ok=True,
            mode=self._mode(),
            last_ok_at=utcnow(),
            message="pull_not_shipped",
        )

    def pull(self, since: str | None, account: dict | None) -> list[NormalizedEvent]:
        # Seed is POST /api/settings/seed. Live sync must not replay fixtures.
        return []
