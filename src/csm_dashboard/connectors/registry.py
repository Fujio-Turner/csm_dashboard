from __future__ import annotations

from csm_dashboard.config import load_settings
from csm_dashboard.connectors.stub import StubConnector

PULL_CONNECTORS = (
    "smtp_imap",
    "google_mail",
    "microsoft365",
    "jira",
    "slack",
    "teams",
    "salesforce",
    "google_cal",
    "m365_cal",
)


def get_connector(name: str) -> StubConnector:
    if name not in PULL_CONNECTORS:
        raise KeyError(name)
    return StubConnector(name)


def connector_mode(name: str) -> str:
    cfg = load_settings().connectors.get(name) or {}
    return str(cfg.get("mode") or "stub")


def list_connectors() -> list[dict]:
    out = []
    for name in PULL_CONNECTORS:
        health = get_connector(name).health()
        health["mode"] = connector_mode(name)
        out.append(health)
    return out
