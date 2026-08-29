"""Corporate SSO portal for the operator's browser session.

The portal URL is whatever IdP the operator uses (Okta, Entra, Google, …).
It does not mint Gmail/Slack API tokens. It signs the browser in so Connect
(OAuth) can federate through that session instead of a personal login.
"""

from __future__ import annotations

from urllib.parse import urlparse


def normalize_org_url(url: str) -> str:
    text = str(url or "").strip()
    if not text:
        return ""
    if "://" not in text:
        text = "https://" + text
    return text.rstrip("/")


def infer_provider(org_url: str) -> str:
    host = (urlparse(org_url).netloc or "").lower()
    if host.endswith(".okta.com") or host.endswith(".oktapreview.com") or host.endswith(".okta-emea.com"):
        return "okta"
    if "microsoftonline.com" in host or host in {"myapps.microsoft.com", "myapplications.microsoft.com"}:
        return "microsoft"
    if host.endswith(".google.com") or host == "accounts.google.com":
        return "google"
    return "custom"


def dashboard_url(org_url: str) -> str:
    url = normalize_org_url(org_url)
    if not url:
        return ""
    parsed = urlparse(url)
    path = parsed.path or ""
    if path not in {"", "/"}:
        return url
    if infer_provider(url) == "okta":
        return url + "/app/UserHome"
    return url


def public_sso(
    settings_doc: dict | None,
    *,
    operator_email: str = "",
    identity: dict | None = None,
    okta_redirect: str = "",
) -> dict:
    raw = (settings_doc or {}).get("sso") if isinstance((settings_doc or {}).get("sso"), dict) else {}
    ident = identity if isinstance(identity, dict) else {}
    org = normalize_org_url(str(ident.get("org_url") or raw.get("org_url") or raw.get("portal_url") or ""))
    provider = str(raw.get("provider") or "").strip() or (infer_provider(org) if org else "")
    email = str(ident.get("email") or operator_email or "").strip()
    name = str(ident.get("name") or "").strip()
    signed_in = bool(ident.get("signed_in") or ident.get("access_token") or ident.get("refresh_token"))
    return {
        "provider": provider,
        "org_url": org,
        "dashboard_url": dashboard_url(org),
        "redirect_uri": okta_redirect,
        "login_hint": email,
        "configured": bool(org and ident.get("client_id")),
        "client_present": bool(ident.get("client_id")),
        "signed_in": signed_in,
        "email": email if signed_in else "",
        "name": name if signed_in else "",
    }
