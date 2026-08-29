"""Credential catalog and public (no-secret) views.

Secrets live in the CBL ``credentials`` collection, one doc per AI provider
or pull connector. HTTP responses and logs must use :func:`public_view` only.
"""

from __future__ import annotations

from typing import Any

AI_PROVIDERS = ("grok", "openai", "gemini")

AI_KEY_ALIASES = {
    "grok": "grok",
    "xai": "grok",
    "xai_api_key": "grok",
    "openai": "openai",
    "openai_api_key": "openai",
    "gemini": "gemini",
    "gemini_api_key": "gemini",
}

CONNECTOR_AUTH: dict[str, str] = {
    "jira": "token",
    "smtp_imap": "password",
    "google_mail": "oauth",
    "google_cal": "oauth",
    "microsoft365": "oauth",
    "m365_cal": "oauth",
    "teams": "oauth",
    "slack": "oauth",
    "salesforce": "oauth",
}

CONNECTOR_VENDOR: dict[str, str] = {
    "google_mail": "google",
    "google_cal": "google",
    "microsoft365": "microsoft",
    "m365_cal": "microsoft",
    "teams": "microsoft",
    "slack": "slack",
    "salesforce": "salesforce",
}

VENDOR_CONNECTORS: dict[str, tuple[str, ...]] = {
    "google": ("google_mail", "google_cal"),
    "microsoft": ("microsoft365", "m365_cal", "teams"),
    "slack": ("slack",),
    "salesforce": ("salesforce",),
}

VENDOR_CLIENT_FIELDS: dict[str, tuple[str, ...]] = {
    "google": ("client_id", "client_secret"),
    "microsoft": ("tenant_id", "client_id", "client_secret"),
    "slack": ("client_id", "client_secret", "user_token", "bot_token"),
    "salesforce": ("instance_url", "client_id", "client_secret"),
}

CONNECTOR_FORM_FIELDS: dict[str, tuple[str, ...]] = {
    "jira": ("base_url", "email", "api_token"),
    "smtp_imap": ("host", "port", "username", "password"),
    "google_mail": ("client_id", "client_secret"),
    "google_cal": ("client_id", "client_secret"),
    "microsoft365": ("tenant_id", "client_id", "client_secret"),
    "m365_cal": ("tenant_id", "client_id", "client_secret"),
    "teams": ("tenant_id", "client_id", "client_secret"),
    "slack": ("client_id", "client_secret", "user_token"),
    "salesforce": ("instance_url", "client_id", "client_secret"),
}

OAUTH_TOKEN_FIELDS = (
    "refresh_token",
    "access_token",
    "token_type",
    "expiry",
    "bot_token",
    "user_token",
    "scope",
    "team_id",
)

PASSWORD_FIELDS = frozenset(
    {
        "api_key",
        "api_token",
        "password",
        "bot_token",
        "user_token",
        "access_token",
        "refresh_token",
        "client_secret",
    }
)


def normalize_ai_provider(name: str) -> str:
    key = str(name or "").strip().lower()
    return AI_KEY_ALIASES.get(key, key)


def credential_id(kind: str, name: str) -> str:
    return f"cred:{kind}:{name}"


def connector_fields(name: str) -> tuple[str, ...]:
    """Fields Settings may write. OAuth tokens are callback-only."""
    if name == "okta":
        return ("client_id", "client_secret", "org_url")
    return CONNECTOR_FORM_FIELDS.get(name, ())


def connector_ui_fields(name: str) -> tuple[str, ...]:
    """Fields shown on a connector card. OAuth services are Connect-only except Slack's paste token."""
    if name == "slack":
        return ("user_token",)
    if CONNECTOR_AUTH.get(name) == "oauth":
        return ()
    return CONNECTOR_FORM_FIELDS.get(name, ())


def connector_auth(name: str) -> str:
    return CONNECTOR_AUTH.get(name, "token")


def connector_vendor(name: str) -> str | None:
    return CONNECTOR_VENDOR.get(name)


def connector_cred_name(name: str) -> str:
    return CONNECTOR_VENDOR.get(name) or name


def oauth_connected(secret: dict | None) -> bool:
    stored = secret if isinstance(secret, dict) else {}
    for key in ("refresh_token", "access_token", "bot_token", "user_token"):
        if str(stored.get(key) or "").strip():
            return True
    return False


def public_fields(secret: dict | None, field_names: tuple[str, ...]) -> list[dict[str, Any]]:
    stored = secret if isinstance(secret, dict) else {}
    out = []
    for field in field_names:
        value = stored.get(field)
        present = bool(str(value).strip()) if value is not None else False
        out.append(
            {
                "name": field,
                "present": present,
                "secret": field in PASSWORD_FIELDS,
            }
        )
    return out


def public_view(*, kind: str, name: str, secret: dict | None, field_names: tuple[str, ...]) -> dict[str, Any]:
    fields = public_fields(secret, field_names)
    connected = oauth_connected(secret) if kind == "connector" else False
    present = connected if connector_auth(name) == "oauth" else any(row["present"] for row in fields)
    if kind == "ai":
        present = any(row["present"] for row in fields)
        connected = False
    return {
        "kind": kind,
        "name": name,
        "present": present,
        "connected": connected,
        "auth": connector_auth(name) if kind == "connector" else "key",
        "fields": fields,
    }


def merge_secret(existing: dict | None, incoming: dict) -> dict:
    """Apply incoming fields. Empty string deletes a field."""
    out = dict(existing or {})
    for key, value in incoming.items():
        if value is None:
            continue
        text = value if isinstance(value, str) else str(value)
        if text.strip() == "":
            out.pop(str(key), None)
        else:
            out[str(key)] = text.strip() if isinstance(value, str) else value
    return out
