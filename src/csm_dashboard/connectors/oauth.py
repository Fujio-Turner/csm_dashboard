"""Loopback OAuth for Google, Microsoft, Slack, and Salesforce.

The browser opens the vendor SSO page, lands on the loopback callback,
and we store refresh/access (or Slack bot/user) tokens in the
``credentials`` collection. Never return those values on GET.

Google uses ``http://localhost:<port>/oauth2callback``. Other vendors stay on
``/api/oauth/<vendor>/callback``.
"""

from __future__ import annotations

import base64
import hashlib
import html
import logging
import os
import secrets
import threading
import time
from urllib.parse import urlencode

import httpx

from csm_dashboard.config import load_settings
from csm_dashboard.credentials import VENDOR_CONNECTORS, connector_cred_name, oauth_connected
from csm_dashboard.sso import normalize_org_url

log = logging.getLogger(__name__)

TTL_SEC = 600
_pending: dict[str, dict] = {}
_lock = threading.Lock()

VENDORS = ("okta", "google", "microsoft", "slack", "salesforce")


def redirect_uri(vendor: str, port: int | None = None) -> str:
    settings = load_settings()
    use_port = int(port or settings.port or 8788)
    if vendor == "google":
        return f"http://localhost:{use_port}/oauth2callback"
    return f"http://127.0.0.1:{use_port}/api/oauth/{vendor}/callback"


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _expiry_unix(expires_in) -> str:
    try:
        seconds = int(expires_in)
    except (TypeError, ValueError):
        return ""
    if seconds <= 0:
        return ""
    return str(int(time.time()) + seconds - 60)


def _expiry_passed(raw) -> bool:
    try:
        exp = int(float(raw))
    except (TypeError, ValueError):
        return True
    # Old docs stored expires_in (e.g. 3600) instead of unix seconds.
    if exp < 1_000_000_000:
        return True
    return exp <= int(time.time())


def ensure_access_token(vendor: str, repo, *, force: bool = False) -> str:
    """Return a usable access token, refreshing Google/Microsoft when needed."""
    if vendor not in VENDORS:
        raise KeyError(vendor)
    secret = _secret(repo, vendor)
    if vendor == "slack":
        return str(secret.get("user_token") or secret.get("bot_token") or secret.get("access_token") or "").strip()
    access = str(secret.get("access_token") or "").strip()
    refresh = str(secret.get("refresh_token") or "").strip()
    if access and not force and not _expiry_passed(secret.get("expiry")):
        return access
    if vendor == "okta":
        return access
    if not refresh:
        return access
    client_id = str(secret.get("client_id") or "").strip()
    # Client id/secret live on the same credential doc as tokens after Settings save.
    # OAuth finish only writes tokens; merge keeps client_id.
    if not client_id:
        return access
    client_secret = str(secret.get("client_secret") or "").strip()
    if vendor == "google":
        data = {
            "client_id": client_id,
            "refresh_token": refresh,
            "grant_type": "refresh_token",
        }
        if client_secret:
            data["client_secret"] = client_secret
        payload = token_post("https://oauth2.googleapis.com/token", data)
    elif vendor == "microsoft":
        tenant = str(secret.get("tenant_id") or "common").strip() or "common"
        data = {
            "client_id": client_id,
            "refresh_token": refresh,
            "grant_type": "refresh_token",
            "scope": "offline_access Mail.Read Calendars.Read User.Read Chat.Read",
        }
        if client_secret:
            data["client_secret"] = client_secret
        payload = token_post(f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token", data)
    else:
        return access
    new_access = str(payload.get("access_token") or "").strip()
    if not new_access:
        return access
    stored = {
        "access_token": new_access,
        "token_type": payload.get("token_type") or "Bearer",
        "expiry": _expiry_unix(payload.get("expires_in")),
    }
    if payload.get("refresh_token"):
        stored["refresh_token"] = payload.get("refresh_token")
    if payload.get("scope"):
        stored["scope"] = payload.get("scope")
    repo.put_credential_secret("connector", vendor, stored)
    log.info("csm.oauth.refreshed vendor=%s", vendor)
    return new_access


def _pkce() -> tuple[str, str]:
    verifier = _b64(secrets.token_bytes(32))
    challenge = _b64(hashlib.sha256(verifier.encode("ascii")).digest())
    return verifier, challenge


def _purge_locked() -> None:
    now = time.time()
    for key in [k for k, row in _pending.items() if now - float(row.get("at") or 0) > TTL_SEC]:
        _pending.pop(key, None)


def http_get(url: str, headers: dict | None = None) -> dict:
    verify: str | bool = os.environ.get("SSL_CERT_FILE") or True
    with httpx.Client(timeout=30.0, verify=verify) as client:
        resp = client.get(url, headers=headers or {})
        resp.raise_for_status()
        payload = resp.json()
        return payload if isinstance(payload, dict) else {}


def discover_oidc(org_url: str) -> dict:
    org = normalize_org_url(org_url)
    if not org:
        raise ValueError("sso_org_missing")
    errors: list[str] = []
    for path in ("/oauth2/default/.well-known/openid-configuration", "/.well-known/openid-configuration"):
        url = org + path
        try:
            data = http_get(url)
            if data.get("authorization_endpoint") and data.get("token_endpoint"):
                return data
            errors.append(url + ": missing endpoints")
        except Exception as exc:
            errors.append(f"{url}: {exc}")
    raise ValueError("sso_discovery_failed")


def token_post(url: str, data: dict) -> dict:
    verify: str | bool = os.environ.get("SSL_CERT_FILE") or True
    with httpx.Client(timeout=30.0, verify=verify) as client:
        resp = client.post(url, data=data)
        resp.raise_for_status()
        payload = resp.json()
        if isinstance(payload, dict) and payload.get("ok") is False:
            raise RuntimeError(str(payload.get("error") or "oauth_denied"))
        return payload if isinstance(payload, dict) else {}


def _secret(repo, vendor: str) -> dict:
    stored = repo.get_credential_secret("connector", vendor)
    if vendor != "google":
        return stored
    from csm_dashboard.connectors.google_secrets import load_google_client

    file_creds = load_google_client()
    if not file_creds.get("client_id"):
        return stored
    out = dict(stored)
    if not str(out.get("client_id") or "").strip():
        out["client_id"] = file_creds["client_id"]
    if file_creds.get("client_secret") and not str(out.get("client_secret") or "").strip():
        out["client_secret"] = file_creds["client_secret"]
    return out


def start_url(vendor: str, repo, *, login_hint: str = "", org_url: str = "") -> str:
    if vendor not in VENDORS:
        raise KeyError(vendor)
    secret = _secret(repo, vendor)
    if vendor == "okta":
        secret = _secret(repo, "okta")
    client_id = str(secret.get("client_id") or "").strip()
    if not client_id:
        raise ValueError("oauth_client_id_missing")
    verifier, challenge = _pkce()
    state = secrets.token_urlsafe(24)
    redirect = redirect_uri(vendor)
    pending = {"vendor": vendor, "verifier": verifier, "at": time.time(), "redirect": redirect}
    hint = str(login_hint or "").strip()
    if vendor == "okta":
        org = normalize_org_url(str(secret.get("org_url") or org_url or ""))
        if not org:
            raise ValueError("sso_org_missing")
        disc = discover_oidc(org)
        pending["token_endpoint"] = disc.get("token_endpoint") or ""
        pending["userinfo_endpoint"] = disc.get("userinfo_endpoint") or ""
        pending["issuer"] = disc.get("issuer") or org
        with _lock:
            _purge_locked()
            _pending[state] = pending
        query = {
            "client_id": client_id,
            "redirect_uri": redirect,
            "response_type": "code",
            "scope": "openid profile email offline_access",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
        }
        if hint:
            query["login_hint"] = hint
        return str(disc.get("authorization_endpoint") or "") + "?" + urlencode(query)
    with _lock:
        _purge_locked()
        _pending[state] = pending
    if vendor == "google":
        query = {
            "client_id": client_id,
            "redirect_uri": redirect,
            "response_type": "code",
            "scope": "https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/calendar.readonly",
            "access_type": "offline",
            "prompt": "consent",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
        }
        if hint:
            query["login_hint"] = hint
            domain = hint.rsplit("@", 1)[-1].lower() if "@" in hint else ""
            if domain and domain not in {"gmail.com", "googlemail.com"}:
                query["hd"] = domain
        return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(query)
    if vendor == "microsoft":
        tenant = str(secret.get("tenant_id") or "common").strip() or "common"
        query = {
            "client_id": client_id,
            "redirect_uri": redirect,
            "response_type": "code",
            "response_mode": "query",
            "scope": "offline_access Mail.Read Calendars.Read User.Read Chat.Read",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
        }
        if hint:
            query["login_hint"] = hint
            query["domain_hint"] = "organizations"
        return f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize?" + urlencode(query)
    if vendor == "slack":
        query = {
            "client_id": client_id,
            "redirect_uri": redirect,
            "scope": "channels:history,groups:history,channels:read,users:read",
            "user_scope": "channels:history,groups:history,im:history,mpim:history,channels:read,groups:read,users:read",
            "state": state,
        }
        return "https://slack.com/oauth/v2/authorize?" + urlencode(query)
    instance = str(secret.get("instance_url") or "https://login.salesforce.com").rstrip("/")
    query = {
        "client_id": client_id,
        "redirect_uri": redirect,
        "response_type": "code",
        "scope": "refresh_token api",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state,
    }
    return f"{instance}/services/oauth2/authorize?" + urlencode(query)


def _exchange(vendor: str, code: str, pending: dict, secret: dict) -> dict:
    client_id = str(secret.get("client_id") or "").strip()
    client_secret = str(secret.get("client_secret") or "").strip()
    redirect = pending.get("redirect") or redirect_uri(vendor)
    verifier = pending.get("verifier") or ""
    if vendor == "okta":
        token_url = str(pending.get("token_endpoint") or "")
        if not token_url:
            raise ValueError("sso_discovery_failed")
        data = {
            "code": code,
            "client_id": client_id,
            "redirect_uri": redirect,
            "grant_type": "authorization_code",
            "code_verifier": verifier,
        }
        if client_secret:
            data["client_secret"] = client_secret
        payload = token_post(token_url, data)
        info: dict = {}
        access = str(payload.get("access_token") or "")
        userinfo = str(pending.get("userinfo_endpoint") or "")
        if access and userinfo:
            try:
                info = http_get(userinfo, {"Authorization": f"Bearer {access}"})
            except Exception:
                info = {}
        email = str(info.get("email") or info.get("preferred_username") or "").strip()
        name = str(info.get("name") or "").strip()
        return {
            "access_token": access,
            "refresh_token": payload.get("refresh_token") or "",
            "token_type": payload.get("token_type") or "Bearer",
            "expiry": payload.get("expires_in") or "",
            "email": email,
            "name": name,
            "sub": info.get("sub") or "",
            "org_url": secret.get("org_url") or "",
        }
    if vendor == "google":
        data = {
            "code": code,
            "client_id": client_id,
            "redirect_uri": redirect,
            "grant_type": "authorization_code",
            "code_verifier": verifier,
        }
        if client_secret:
            data["client_secret"] = client_secret
        payload = token_post("https://oauth2.googleapis.com/token", data)
        return {
            "access_token": payload.get("access_token") or "",
            "refresh_token": payload.get("refresh_token") or "",
            "token_type": payload.get("token_type") or "Bearer",
            "expiry": _expiry_unix(payload.get("expires_in")),
            "scope": payload.get("scope") or "",
        }
    if vendor == "microsoft":
        tenant = str(secret.get("tenant_id") or "common").strip() or "common"
        data = {
            "code": code,
            "client_id": client_id,
            "redirect_uri": redirect,
            "grant_type": "authorization_code",
            "code_verifier": verifier,
            "scope": "offline_access Mail.Read Calendars.Read User.Read Chat.Read",
        }
        if client_secret:
            data["client_secret"] = client_secret
        payload = token_post(f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token", data)
        return {
            "access_token": payload.get("access_token") or "",
            "refresh_token": payload.get("refresh_token") or "",
            "token_type": payload.get("token_type") or "Bearer",
            "expiry": _expiry_unix(payload.get("expires_in")),
            "scope": payload.get("scope") or "",
        }
    if vendor == "slack":
        data = {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect,
        }
        payload = token_post("https://slack.com/api/oauth.v2.access", data)
        authed = payload.get("authed_user") if isinstance(payload.get("authed_user"), dict) else {}
        return {
            "bot_token": payload.get("access_token") or "",
            "user_token": authed.get("access_token") or "",
            "refresh_token": payload.get("refresh_token") or authed.get("refresh_token") or "",
            "access_token": payload.get("access_token") or "",
            "token_type": "Bearer",
            "team_id": ((payload.get("team") or {}) if isinstance(payload.get("team"), dict) else {}).get("id") or "",
            "scope": payload.get("scope") or "",
        }
    instance = str(secret.get("instance_url") or "https://login.salesforce.com").rstrip("/")
    data = {
        "code": code,
        "client_id": client_id,
        "redirect_uri": redirect,
        "grant_type": "authorization_code",
        "code_verifier": verifier,
    }
    if client_secret:
        data["client_secret"] = client_secret
    payload = token_post(f"{instance}/services/oauth2/token", data)
    return {
        "access_token": payload.get("access_token") or "",
        "refresh_token": payload.get("refresh_token") or "",
        "token_type": payload.get("token_type") or "Bearer",
        "instance_url": payload.get("instance_url") or instance,
    }


def finish(vendor: str, code: str, state: str, repo) -> None:
    if vendor not in VENDORS:
        raise KeyError(vendor)
    with _lock:
        _purge_locked()
        pending = _pending.pop(state, None)
    if not pending or pending.get("vendor") != vendor:
        raise ValueError("oauth_state_invalid")
    if not str(code or "").strip():
        raise ValueError("oauth_code_missing")
    secret = _secret(repo, vendor)
    tokens = _exchange(vendor, code, pending, secret)
    repo.put_credential_secret("connector", vendor, tokens)
    if vendor == "okta":
        op = {}
        if tokens.get("email"):
            op["email"] = tokens["email"]
        if tokens.get("name"):
            op["name"] = tokens["name"]
        if op:
            repo.save_settings({"operator": op})
        log.info("csm.oauth.connected vendor=okta email_set=%s", bool(tokens.get("email")))
        return
    modes = {name: {"mode": "live"} for name in VENDOR_CONNECTORS.get(vendor, ())}
    if modes:
        repo.save_settings({"connectors": modes})
    log.info("csm.oauth.connected vendor=%s fields=%s", vendor, ",".join(sorted(k for k, v in tokens.items() if v)))


def disconnect(vendor: str, repo) -> None:
    if vendor not in VENDORS:
        raise KeyError(vendor)
    blanks = {
        key: ""
        for key in (
            "refresh_token",
            "access_token",
            "bot_token",
            "user_token",
            "expiry",
            "scope",
            "team_id",
            "email",
            "name",
            "sub",
        )
    }
    repo.put_credential_secret("connector", vendor, blanks)
    log.info("csm.oauth.disconnected vendor=%s", vendor)


def callback_html(*, ok: bool, message: str) -> str:
    title = "Connected" if ok else "Not connected"
    body = html.escape(message)
    flag = "ok" if ok else "error"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<style>
body {{ font-family: Source Sans 3, Segoe UI, sans-serif; background: #eef2f6; color: #1c2430; margin: 0; display: grid; min-height: 100vh; place-items: center; }}
main {{ background: #fff; padding: 1.5rem 1.75rem; border-radius: 16px; width: min(28rem, calc(100% - 2rem)); }}
h1 {{ font-size: 1.15rem; margin: 0 0 0.4rem; }}
p {{ margin: 0; color: #667085; }}
</style></head><body><main>
<h1>{html.escape(title)}</h1>
<p>{body}</p>
</main>
<script>
try {{
  if (window.opener) window.opener.postMessage({{ csm_oauth: "{flag}" }}, window.location.origin);
}} catch (err) {{}}
setTimeout(function () {{ window.close(); }}, 800);
</script>
</body></html>
"""


def is_connected(repo, name: str) -> bool:
    return oauth_connected(repo.get_credential_secret("connector", connector_cred_name(name)))
