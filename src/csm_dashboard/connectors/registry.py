from __future__ import annotations

from csm_dashboard.config import load_settings
from csm_dashboard.connectors.base import Connector
from csm_dashboard.connectors.oauth import redirect_uri
from csm_dashboard.connectors.stub import StubConnector
from csm_dashboard.credentials import PASSWORD_FIELDS, connector_auth, connector_ui_fields, connector_vendor

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

def get_connector(name: str, repo=None) -> Connector:
    if name not in PULL_CONNECTORS:
        raise KeyError(name)
    if name == "jira":
        from csm_dashboard.connectors.jira import connector as factory

        return factory(repo)
    if name == "slack":
        from csm_dashboard.connectors.slack import connector as factory

        return factory(repo)
    if name == "teams":
        from csm_dashboard.connectors.teams import connector as factory

        return factory(repo)
    if name == "google_mail":
        from csm_dashboard.connectors.google_mail import connector as factory

        return factory(repo)
    if name == "google_cal":
        from csm_dashboard.connectors.google_cal import connector as factory

        return factory(repo)
    return StubConnector(name)


def normalize_mode(mode: str) -> str:
    """User-facing modes are live | disabled. Legacy stub/off become disabled."""
    value = str(mode or "").strip().lower()
    if value == "live":
        return "live"
    return "disabled"


def connector_mode(name: str, settings_doc: dict | None = None) -> str:
    overlay = ((settings_doc or {}).get("connectors") or {}).get(name) or {}
    if overlay.get("mode"):
        return normalize_mode(str(overlay.get("mode")))
    cfg = load_settings().connectors.get(name) or {}
    return normalize_mode(str(cfg.get("mode") or "disabled"))


def list_connectors(settings_doc: dict | None = None, creds_public: dict | None = None, repo=None) -> list[dict]:
    out = []
    creds = creds_public or {}
    for name in PULL_CONNECTORS:
        health = get_connector(name, repo).health()
        health["mode"] = connector_mode(name, settings_doc)
        public = creds.get(name) or {}
        kind = connector_auth(name)
        vendor = connector_vendor(name)
        health["auth"] = kind
        health["oauth_vendor"] = vendor
        health["connected"] = bool(public.get("connected"))
        health["present"] = bool(public.get("present"))
        if kind == "oauth" and vendor:
            health["redirect_uri"] = redirect_uri(vendor)
        health["fields"] = public.get("fields") or [
            {"name": field, "present": False, "secret": field in PASSWORD_FIELDS}
            for field in connector_ui_fields(name)
        ]
        out.append(health)
    return out
