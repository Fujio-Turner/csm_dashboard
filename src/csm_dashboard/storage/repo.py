from __future__ import annotations

import base64
import hashlib
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from csm_dashboard.ingest.identity import activity_doc_id, email_doc_id, thread_doc_id

from .cbl_store import COLLECTIONS
from .memory import MemoryStore

log = logging.getLogger(__name__)

TOKEN_RE = re.compile(r"^[a-z0-9-]{2,32}$")
ABBR_RE = re.compile(r"^[A-Z0-9]{2,6}$")
SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
DATA_IMAGE_RE = re.compile(r"^data:(image/(?:png|jpeg|jpg|webp));base64,(.+)$", re.I | re.S)
LOGO_MAX_BYTES = 1_500_000
OPEN_TICKET = {"open", "in_progress", "waiting"}
PERSON_FUNCTIONS = ("Ops", "Accounting", "DBA")
TASK_KINDS = ("Action item(s)", "Follow up(s)", "Review(s)", "More Detail(s)")
PROJECT_KINDS = ("implementation", "qbr", "training", "migration", "other")
PROJECT_STATUSES = ("planned", "active", "blocked", "done", "cancelled")
_FUNC_CANON = {name.lower(): name for name in PERSON_FUNCTIONS}
REF_PROJECT_COLLECTIONS = {
    "tickets",
    "emails",
    "slack_messages",
    "teams_messages",
    "calendar_events",
    "salesforce_opportunities",
    "salesforce_cases",
}


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _norm_timezone(value: str) -> str:
    tz = str(value or "").strip() or "UTC"
    try:
        from zoneinfo import ZoneInfo

        ZoneInfo(tz)
        return tz
    except Exception:
        return "UTC"


def _norm_timezone_list(values: Any) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    raw = values if isinstance(values, list) else []
    for item in raw:
        tz = _norm_timezone(str(item or ""))
        if tz in seen:
            continue
        seen.add(tz)
        out.append(tz)
    return out


_THEMES = ("auto", "day", "night")
_THEME_ALIAS = {"light": "day", "dark": "night"}


def _norm_week_start(value: Any) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return 0
    if n < 0 or n > 6:
        return 0
    return n


def _norm_hidden_weekdays(values: Any) -> list[int]:
    raw = values if isinstance(values, list) else []
    out: list[int] = []
    seen: set[int] = set()
    for item in raw:
        try:
            n = int(item)
        except (TypeError, ValueError):
            continue
        if n < 0 or n > 6 or n in seen:
            continue
        seen.add(n)
        out.append(n)
    if len(out) >= 7:
        return []
    out.sort()
    return out


def _norm_theme(value: Any) -> str:
    raw = str(value or "").strip().lower()
    raw = _THEME_ALIAS.get(raw, raw)
    return raw if raw in _THEMES else "auto"


def _norm_timeline_layout(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if raw in ("h", "horizon", "horizontal"):
        return "horizontal"
    return "vertical"


def _norm_timeline_days(value: Any) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return 7
    return 30 if n == 30 else 7


def _norm_preferences(incoming: dict | None, current: dict | None = None) -> dict:
    cur = current if isinstance(current, dict) else {}
    src = incoming if isinstance(incoming, dict) else {}
    merged = {**cur, **src}
    if "hidden_weekdays" in src:
        hidden = src.get("hidden_weekdays")
    else:
        hidden = cur.get("hidden_weekdays", [])
    return {
        "week_start": _norm_week_start(merged.get("week_start", 0)),
        "hidden_weekdays": _norm_hidden_weekdays(hidden),
        "theme": _norm_theme(merged.get("theme", "auto")),
        "timeline_layout": _norm_timeline_layout(merged.get("timeline_layout", "vertical")),
        "timeline_past_days": _norm_timeline_days(merged.get("timeline_past_days", 7)),
        "timeline_next_days": _norm_timeline_days(merged.get("timeline_next_days", 7)),
    }


def ts_to_iso(ts: str) -> str:
    raw = str(ts or "").strip()
    if not raw:
        return utcnow()
    if "T" in raw or raw.endswith("Z"):
        return raw
    try:
        sec = float(raw)
        if sec > 1e12:
            sec = sec / 1000.0
        return datetime.fromtimestamp(sec, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    except (TypeError, ValueError, OSError, OverflowError):
        return utcnow()


def hex12() -> str:
    return uuid.uuid4().hex[:12]


def sha16(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


class Store(Protocol):
    def ensure_collections(self, names: list[str]) -> None: ...
    def save(self, collection: str, doc_id: str, doc: dict) -> None: ...
    def get(self, collection: str, doc_id: str) -> dict | None: ...
    def purge(self, collection: str, doc_id: str) -> None: ...
    def count(self, collection: str) -> int: ...
    def query_all(self, collection: str) -> list[dict]: ...
    def close(self) -> None: ...


def open_store(db_path: str | None = None, *, memory: bool = False) -> Store:
    if memory or not db_path:
        store = MemoryStore()
        store.ensure_collections(list(COLLECTIONS))
        return store
    from .cbl_store import CBLStore

    return CBLStore(db_path)


def _attach(doc: dict | None, doc_id: str) -> dict | None:
    if doc is None:
        return None
    out = dict(doc)
    out["_id"] = doc_id
    return out


def _norm_abbr(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())[:6]


def _str_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [p.strip() for p in value.split(",") if p.strip()]
    out: list[str] = []
    for item in value:
        s = str(item or "").strip()
        if s and s not in out:
            out.append(s)
    return out


def _norm_emails(value: Any) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in _str_list(value):
        addr = item.strip()
        key = addr.lower()
        if not addr or key in seen:
            continue
        seen.add(key)
        out.append(addr)
    return out


AUDIENCE_ME = "me"
AUDIENCE_US = "us"
AUDIENCE_THEM = "them"
AUDIENCE_ALL = "all"
AUDIENCE_UNKNOWN = "unknown"
AUDIENCE_NA = "na"
AUDIENCE_VALUES = (AUDIENCE_ME, AUDIENCE_US, AUDIENCE_THEM, AUDIENCE_ALL, AUDIENCE_UNKNOWN, AUDIENCE_NA)


def _addr_domain(addr: str) -> str:
    raw = str(addr or "").strip().lower()
    if "@" not in raw:
        return ""
    return raw.rsplit("@", 1)[-1]


def _addr_side(
    addr: str,
    *,
    me: str,
    us_emails: set[str],
    them_emails: set[str],
    us_domains: set[str],
    them_domains: set[str],
) -> str:
    a = str(addr or "").strip().lower()
    if not a:
        return ""
    if me and a == me:
        return AUDIENCE_ME
    if a in us_emails:
        return AUDIENCE_US
    if a in them_emails:
        return AUDIENCE_THEM
    domain = _addr_domain(a)
    if domain and domain in us_domains:
        return AUDIENCE_US
    if domain and domain in them_domains:
        return AUDIENCE_THEM
    return AUDIENCE_UNKNOWN


def fold_audience_sides(sides: set[str]) -> str:
    known = {s for s in sides if s and s != AUDIENCE_UNKNOWN}
    if not known:
        return AUDIENCE_UNKNOWN
    has_me = AUDIENCE_ME in known
    has_us = AUDIENCE_US in known
    has_them = AUDIENCE_THEM in known
    if has_them and (has_me or has_us):
        return AUDIENCE_ALL
    if has_them:
        return AUDIENCE_THEM
    if has_us:
        return AUDIENCE_US
    if has_me:
        return AUDIENCE_ME
    return AUDIENCE_UNKNOWN


def inbox_audience(
    *,
    kind: str = "",
    to_addrs: list | None = None,
    cc_addrs: list | None = None,
    bcc_addrs: list | None = None,
    channel_id: str = "",
    is_im: bool = False,
    me: str = "",
    us_emails: set[str] | None = None,
    them_emails: set[str] | None = None,
    us_domains: set[str] | None = None,
    them_domains: set[str] | None = None,
) -> str:
    """Who this inbox row is to: me, us, them, all, unknown (??), or na."""
    kind = str(kind or "")
    if kind in {"slack", "teams"}:
        cid = str(channel_id or "")
        if is_im or cid.startswith("D"):
            return AUDIENCE_ME
        if cid:
            return AUDIENCE_ALL
        return AUDIENCE_UNKNOWN
    addrs = list(to_addrs or []) + list(cc_addrs or []) + list(bcc_addrs or [])
    if not addrs:
        if kind in {"email", "task"}:
            return AUDIENCE_UNKNOWN
        return AUDIENCE_NA
    sides = {
        _addr_side(
            addr,
            me=str(me or "").strip().lower(),
            us_emails=set(us_emails or ()),
            them_emails=set(them_emails or ()),
            us_domains=set(us_domains or ()),
            them_domains=set(them_domains or ()),
        )
        for addr in addrs
    }
    return fold_audience_sides(sides)


def _is_task_email(doc: dict) -> bool:
    if (doc.get("operator") or {}).get("task"):
        return True
    return str(doc.get("subject") or "").startswith("Tasks:")


def _task_subject(company: str, name: str, kind: str) -> str:
    return f"Tasks: {company} : {name} {{{kind}}}"


def _due_label(raw: str) -> str:
    s = str(raw or "").strip()
    if not s:
        return ""
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y %I:%M %p").replace(" 0", " ")
    except ValueError:
        return s


def _project_tags(value: Any) -> list[str]:
    raw: list[Any]
    if isinstance(value, list):
        raw = value
    else:
        raw = _str_list(value)
    out: list[str] = []
    for item in raw:
        if isinstance(item, dict):
            item = item.get("value") or item.get("name") or ""
        tag = str(item or "").strip()
        if tag and tag not in out:
            out.append(tag)
    return out


def _norm_project_kind(value: str) -> str:
    kind = str(value or "").strip().lower() or "other"
    return kind if kind in PROJECT_KINDS else "other"


def _norm_project_status(value: str) -> str:
    status = str(value or "").strip().lower() or "planned"
    return status if status in PROJECT_STATUSES else "planned"


def _task_body(content: str, due_at: str) -> str:
    text = str(content or "").strip()
    label = _due_label(due_at)
    if label:
        text = f"{text}\n\nWhen Due By: {label}".strip()
    return text


def _norm_domains(value: Any) -> list[str]:
    out: list[str] = []
    for item in _str_list(value):
        d = item.lower().lstrip("@").strip()
        if d and d not in out:
            out.append(d)
    return out


def _functions(value: Any) -> list[str]:
    out: list[str] = []
    for item in _str_list(value):
        name = _FUNC_CANON.get(item.lower())
        if name and name not in out:
            out.append(name)
    return out


def _person_blob(row: dict) -> str:
    bits = [
        row.get("name"),
        row.get("email"),
        row.get("title"),
        row.get("location"),
        row.get("role"),
        row.get("kind"),
        " ".join(row.get("project_ids") or []),
        " ".join(row.get("functions") or []),
        "all projects" if row.get("owns_all_projects") else "",
    ]
    return " ".join(str(b or "") for b in bits).lower()


def _is_open_ticket(row: dict) -> bool:
    return str(row.get("status") or "") in OPEN_TICKET and not (row.get("operator") or {}).get("ignore")


def _chat_title(messages: Any, fallback: str = "New chat") -> str:
    for item in messages or []:
        if not isinstance(item, dict):
            continue
        if item.get("role") != "user":
            continue
        text = " ".join(str(item.get("content") or "").split())
        if text:
            return text[:72]
    return fallback


def decode_logo_data_url(raw: str) -> tuple[bytes, str]:
    text = str(raw or "").strip()
    match = DATA_IMAGE_RE.match(text)
    if not match:
        raise ValueError("invalid image")
    mime = match.group(1).lower()
    if mime == "image/jpg":
        mime = "image/jpeg"
    try:
        blob = base64.b64decode(match.group(2), validate=False)
    except (ValueError, TypeError) as exc:
        raise ValueError("invalid image") from exc
    if not blob or len(blob) > LOGO_MAX_BYTES:
        raise ValueError("image too large")
    if mime == "image/png" and not blob.startswith(b"\x89PNG"):
        raise ValueError("invalid png")
    if mime == "image/jpeg" and blob[:2] != b"\xff\xd8":
        raise ValueError("invalid jpeg")
    if mime == "image/webp" and blob[:4] != b"RIFF":
        raise ValueError("invalid webp")
    return blob, mime


def _logo_stem(account_id: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", str(account_id or "").lower()).strip("-") or "acct"


class CsmRepo:
    def __init__(self, store: Store) -> None:
        self.store = store
        self.store.ensure_collections(list(COLLECTIONS))
        self._logos: dict[str, tuple[bytes, str]] = {}

    def close(self) -> None:
        self.store.close()

    def counts(self) -> dict[str, int]:
        return {name: self.store.count(name) for name in COLLECTIONS}

    def _account_rows(self, collection: str, account_id: str) -> list[dict]:
        fn = getattr(self.store, "query_by_account", None)
        if callable(fn):
            return fn(collection, account_id)
        return [r for r in self.store.query_all(collection) if r.get("account_id") == account_id]

    # -- settings ----------------------------------------------------------

    def get_settings(self) -> dict:
        return self.store.get("settings", "settings") or {"type": "settings"}

    def save_settings(self, doc: dict) -> dict:
        current = self.get_settings() or {"type": "settings"}
        incoming = dict(doc or {})
        if isinstance(incoming.get("operator"), dict):
            incoming_op = incoming["operator"]
            op = {**(current.get("operator") or {}), **incoming_op}
            op["timezone"] = _norm_timezone(str(op.get("timezone") or ""))
            if "timezones" in incoming_op:
                op["timezones"] = _norm_timezone_list(incoming_op.get("timezones"))
            incoming["operator"] = op
        wc_in = incoming.get("world_clock") if isinstance(incoming.get("world_clock"), dict) else None
        op_now = incoming.get("operator") if isinstance(incoming.get("operator"), dict) else current.get("operator") or {}
        wc = dict(current.get("world_clock") or {})
        if wc_in is not None:
            wc = {**wc, **wc_in}
            if "timezones" in wc_in:
                wc["timezones"] = _norm_timezone_list(wc_in.get("timezones"))
            if "hour24" in wc_in:
                wc["hour24"] = bool(wc_in.get("hour24"))
        elif "timezones" in op_now:
            wc["timezones"] = _norm_timezone_list(op_now.get("timezones"))
        if wc:
            incoming["world_clock"] = wc
            if wc.get("timezones") is not None:
                op_merged = incoming.get("operator") if isinstance(incoming.get("operator"), dict) else {}
                op_merged = {**(current.get("operator") or {}), **op_merged, "timezones": wc["timezones"]}
                op_merged["timezone"] = _norm_timezone(str(op_merged.get("timezone") or ""))
                incoming["operator"] = op_merged
        if isinstance(incoming.get("connectors"), dict):
            from csm_dashboard.connectors.registry import normalize_mode

            cur_conn = dict(current.get("connectors") or {})
            for name, row in incoming["connectors"].items():
                key = str(name or "").strip()
                if not key:
                    continue
                if not isinstance(row, dict):
                    continue
                merged_row = {**(cur_conn.get(key) or {}), **row}
                if "mode" in merged_row:
                    merged_row["mode"] = normalize_mode(str(merged_row.get("mode")))
                cur_conn[key] = merged_row
            incoming["connectors"] = cur_conn
        if isinstance(incoming.get("ai"), dict):
            incoming["ai"] = {**(current.get("ai") or {}), **incoming["ai"]}
        if isinstance(incoming.get("sso"), dict):
            incoming["sso"] = {**(current.get("sso") or {}), **incoming["sso"]}
        if isinstance(incoming.get("preferences"), dict):
            incoming["preferences"] = _norm_preferences(
                incoming["preferences"],
                current.get("preferences") if isinstance(current.get("preferences"), dict) else {},
            )
        merged = {**current, **incoming, "type": "settings"}
        self.store.save("settings", "settings", merged)
        saved = self.store.get("settings", "settings") or merged
        clock = saved.get("world_clock") or {}
        if clock:
            log.info(
                "csm.world_clock.saved count=%s hour24=%s",
                len(clock.get("timezones") or []),
                bool(clock.get("hour24")),
            )
        prefs = saved.get("preferences") or {}
        if prefs:
            log.info(
                "csm.preferences.saved week_start=%s hidden=%s theme=%s",
                prefs.get("week_start"),
                ",".join(str(d) for d in (prefs.get("hidden_weekdays") or [])),
                prefs.get("theme"),
            )
        return _attach(saved, "settings") or saved

    def credential_doc_id(self, kind: str, name: str) -> str:
        from csm_dashboard.credentials import credential_id

        return credential_id(kind, name)

    def get_credential_secret(self, kind: str, name: str) -> dict:
        """Internal. Never put this dict on an HTTP response."""
        doc = self.store.get("credentials", self.credential_doc_id(kind, name)) or {}
        secret = doc.get("secret")
        return dict(secret) if isinstance(secret, dict) else {}

    def put_credential_secret(self, kind: str, name: str, fields: dict) -> dict:
        from csm_dashboard.credentials import merge_secret, public_view

        doc_id = self.credential_doc_id(kind, name)
        existing = self.store.get("credentials", doc_id) or {}
        secret = merge_secret(existing.get("secret") if isinstance(existing.get("secret"), dict) else {}, fields)
        if not secret:
            if existing:
                self.store.purge("credentials", doc_id)
            log.info("csm.credential.cleared kind=%s name=%s", kind, name)
            return public_view(kind=kind, name=name, secret={}, field_names=tuple(fields.keys()))
        doc = {
            "type": "credential",
            "kind": kind,
            "name": name,
            "secret": secret,
            "updated_at": utcnow(),
        }
        self.store.save("credentials", doc_id, doc)
        log.info("csm.credential.saved kind=%s name=%s fields=%s", kind, name, ",".join(sorted(secret.keys())))
        return public_view(kind=kind, name=name, secret=secret, field_names=tuple(secret.keys()))

    def ai_api_key(self, provider: str) -> str:
        from csm_dashboard.credentials import normalize_ai_provider

        name = normalize_ai_provider(provider)
        secret = self.get_credential_secret("ai", name)
        return str(secret.get("api_key") or "").strip()

    def list_credentials_public(self) -> dict:
        from csm_dashboard.connectors.registry import PULL_CONNECTORS
        from csm_dashboard.credentials import AI_PROVIDERS, connector_cred_name, connector_ui_fields, public_view

        ai = {}
        for name in AI_PROVIDERS:
            ai[name] = public_view(
                kind="ai",
                name=name,
                secret=self.get_credential_secret("ai", name),
                field_names=("api_key",),
            )
        connectors = {}
        for name in PULL_CONNECTORS:
            fields = connector_ui_fields(name)
            connectors[name] = public_view(
                kind="connector",
                name=name,
                secret=self.get_credential_secret("connector", connector_cred_name(name)),
                field_names=fields,
            )
        return {"ai": ai, "connectors": connectors}

    def world_clock(self, doc: dict | None = None) -> dict:
        doc = doc if doc is not None else (self.get_settings() or {})
        stored = doc.get("world_clock") or {}
        op = doc.get("operator") or {}
        zones = _norm_timezone_list(stored.get("timezones") or op.get("timezones"))
        if not zones:
            zones = [_norm_timezone(str(op.get("timezone") or "UTC"))]
        return {"timezones": zones, "hour24": bool(stored.get("hour24"))}

    def preferences(self, doc: dict | None = None) -> dict:
        doc = doc if doc is not None else (self.get_settings() or {})
        stored = doc.get("preferences") if isinstance(doc.get("preferences"), dict) else {}
        return _norm_preferences(stored)

    # -- accounts ----------------------------------------------------------

    def create_account(self, body: dict) -> dict:
        slug = str(body.get("slug") or "").strip().lower()
        if not SLUG_RE.match(slug):
            raise ValueError("invalid slug")
        account_id = f"acct:{slug}"
        if self.store.get("accounts", account_id):
            raise ValueError("slug taken")
        abbr = _norm_abbr(str(body.get("abbr") or slug))
        if not ABBR_RE.match(abbr):
            raise ValueError("invalid abbr")
        if self.get_account_by_abbr(abbr):
            raise ValueError("abbr taken")
        color = str(body.get("color") or "#0B3D91")
        if not COLOR_RE.match(color):
            raise ValueError("invalid color")
        now = utcnow()
        doc = {
            "type": "account",
            "account_id": account_id,
            "name": str(body.get("name") or slug).strip(),
            "abbr": abbr,
            "slug": slug,
            "color": color.upper().replace("#", "#") if False else color,
            "domains": _norm_domains(body.get("domains")),
            "connectors": body.get("connectors") or {},
            "quiet": bool(body.get("quiet")),
            "removed": False,
            "has_logo": False,
            "health": body.get("health")
            or {
                "score": 50,
                "score_max": 100,
                "scored_by": "rules",
                "rules_score": 50,
                "status": "watch",
                "breakdown": [],
                "override": None,
            },
            "contract": body.get("contract") or {"source": "operator", "currency": "USD"},
            "team": body.get("team") or {"account": [], "ps": []},
            "next_action": body.get("next_action") or {},
            "stats": body.get("stats") or {},
            "sources": body.get("sources") or {},
            "created_at": now,
            "updated_at": now,
        }
        if COLOR_RE.match(color):
            doc["color"] = color if color.startswith("#") else f"#{color}"
        self.store.save("accounts", account_id, doc)
        return _attach(doc, account_id) or doc

    def get_account(self, account_id: str) -> dict | None:
        return _attach(self.store.get("accounts", account_id), account_id)

    def get_account_by_abbr(self, abbr: str) -> dict | None:
        want = _norm_abbr(abbr)
        fn = getattr(self.store, "query_eq", None)
        rows = fn("accounts", "abbr", want) if callable(fn) else self.store.query_all("accounts")
        for row in rows:
            if row.get("removed"):
                continue
            if _norm_abbr(str(row.get("abbr") or "")) == want:
                return row
        if callable(fn):
            for row in self.store.query_all("accounts"):
                if row.get("removed"):
                    continue
                if _norm_abbr(str(row.get("abbr") or "")) == want:
                    return row
        return None

    def patch_account(self, account_id: str, patch: dict) -> dict:
        doc = self.store.get("accounts", account_id)
        if not doc:
            raise KeyError(account_id)
        if "slug" in patch and str(patch.get("slug") or "") != doc.get("slug"):
            raise PermissionError("slug_immutable")
        if "abbr" in patch:
            abbr = _norm_abbr(str(patch.get("abbr") or ""))
            if not ABBR_RE.match(abbr):
                raise ValueError("invalid abbr")
            other = self.get_account_by_abbr(abbr)
            if other and other.get("_id") != account_id and other.get("account_id") != account_id:
                raise ValueError("abbr taken")
            doc["abbr"] = abbr
        for key in ("name", "color", "connectors", "team", "contract", "next_action"):
            if key in patch:
                doc[key] = patch[key]
        if "domains" in patch:
            doc["domains"] = _norm_domains(patch.get("domains"))
        if "quiet" in patch:
            doc["quiet"] = bool(patch.get("quiet"))
        if "removed" in patch:
            doc["removed"] = bool(patch.get("removed"))
            if doc["removed"]:
                doc["quiet"] = True
        if "health" in patch and isinstance(patch["health"], dict):
            health = dict(doc.get("health") or {})
            incoming = patch["health"]
            if "override" in incoming:
                health["override"] = incoming["override"]
            for extra in incoming:
                if extra != "override":
                    continue
            doc["health"] = health
        doc["updated_at"] = utcnow()
        self.store.save("accounts", account_id, doc)
        return _attach(doc, account_id) or doc

    def list_accounts(
        self,
        *,
        q: str | None = None,
        status: str | None = None,
        include_hidden: bool = False,
    ) -> list[dict]:
        rows = self.store.query_all("accounts")
        needle = (q or "").strip().lower()
        out = []
        for row in rows:
            if not include_hidden and (row.get("removed") or row.get("quiet")):
                continue
            if row.get("removed") and not include_hidden:
                continue
            if status and str((row.get("health") or {}).get("status") or "") != status:
                continue
            blob = f"{row.get('name','')} {row.get('abbr','')} {row.get('slug','')}".lower()
            if needle and needle not in blob:
                continue
            out.append(row)
        out.sort(
            key=lambda r: (
                int((r.get("health") or {}).get("score") or 100),
                str((r.get("contract") or {}).get("renewal_on") or "9999"),
            )
        )
        return out

    # -- people / projects / notes ----------------------------------------

    def create_person(self, body: dict) -> dict:
        token = str(body.get("_id") or "").removeprefix("person:") or hex12()
        if not TOKEN_RE.match(token):
            raise ValueError("invalid person id")
        doc_id = f"person:{token}"
        now = utcnow()
        name = str(body.get("name") or "").strip()
        if not name:
            raise ValueError("name required")
        doc = {
            "type": "person",
            "account_id": body.get("account_id") or "",
            "kind": body.get("kind") or "customer",
            "name": name,
            "email": str(body.get("email") or "").strip(),
            "title": str(body.get("title") or "").strip(),
            "location": str(body.get("location") or "").strip(),
            "role": body.get("role") or "other",
            "reports_to": str(body.get("reports_to") or "").strip(),
            "project_ids": _str_list(body.get("project_ids")),
            "functions": _functions(body.get("functions")),
            "owns_all_projects": bool(body.get("owns_all_projects")),
            "external_ids": body.get("external_ids") or {},
            "sources": body.get("sources") or {},
            "created_at": now,
            "updated_at": now,
        }
        self.store.save("people", doc_id, doc)
        return _attach(doc, doc_id) or doc

    def get_person(self, person_id: str) -> dict | None:
        return _attach(self.store.get("people", person_id), person_id)

    def patch_person(self, person_id: str, patch: dict) -> dict:
        doc = self.store.get("people", person_id)
        if not doc:
            raise KeyError(person_id)
        for key in ("name", "email", "title", "location", "role", "kind", "reports_to", "external_ids"):
            if key in patch:
                doc[key] = patch[key]
        if "project_ids" in patch:
            doc["project_ids"] = _str_list(patch.get("project_ids"))
        if "functions" in patch:
            doc["functions"] = _functions(patch.get("functions"))
        if "owns_all_projects" in patch:
            doc["owns_all_projects"] = bool(patch.get("owns_all_projects"))
        doc["updated_at"] = utcnow()
        self.store.save("people", person_id, doc)
        return _attach(doc, person_id) or doc

    def list_people(
        self,
        account_id: str,
        *,
        kind: str | None = None,
        q: str | None = None,
        project_id: str | None = None,
        function: str | None = None,
    ) -> list[dict]:
        rows = self._account_rows("people", account_id)
        if kind:
            rows = [r for r in rows if r.get("kind") == kind]
        if project_id:
            if project_id == "all":
                rows = [r for r in rows if r.get("owns_all_projects")]
            else:
                rows = [
                    r
                    for r in rows
                    if r.get("owns_all_projects") or project_id in (r.get("project_ids") or [])
                ]
        if function:
            want = _FUNC_CANON.get(function.strip().lower(), function.strip())
            rows = [r for r in rows if want in (r.get("functions") or [])]
        needle = (q or "").strip().lower()
        if needle:
            rows = [r for r in rows if needle in _person_blob(r)]
        rows.sort(key=lambda r: str(r.get("name") or ""))
        return rows

    def create_project(self, body: dict) -> dict:
        token = str(body.get("_id") or "").removeprefix("proj:") or hex12()
        doc_id = f"proj:{token}" if not str(body.get("_id") or "").startswith("proj:") else str(body["_id"])
        name = str(body.get("name") or "").strip()
        if not name:
            raise ValueError("name required")
        now = utcnow()
        doc = {
            "type": "project",
            "account_id": body.get("account_id") or "",
            "name": name,
            "kind": _norm_project_kind(str(body.get("kind") or "")),
            "status": _norm_project_status(str(body.get("status") or "")),
            "owner_person_id": str(body.get("owner_person_id") or "").strip(),
            "group_email": str(body.get("group_email") or "").strip(),
            "tags": _project_tags(body.get("tags")),
            "start_on": body.get("start_on") or "",
            "end_on": body.get("end_on") or "",
            "jira_epic": body.get("jira_epic") or "",
            "summary": body.get("summary") or "",
            "removed": False,
            "sources": body.get("sources") or {},
            "created_at": now,
            "updated_at": now,
        }
        self.store.save("projects", doc_id, doc)
        self._link_project_owner(doc_id, doc.get("owner_person_id") or "")
        return _attach(doc, doc_id) or doc

    def get_project(self, project_id: str) -> dict | None:
        return _attach(self.store.get("projects", project_id), project_id)

    def patch_project(self, project_id: str, patch: dict) -> dict:
        doc = self.store.get("projects", project_id)
        if not doc:
            raise KeyError(project_id)
        if "name" in patch:
            name = str(patch.get("name") or "").strip()
            if not name:
                raise ValueError("name required")
            doc["name"] = name
        if "kind" in patch:
            doc["kind"] = _norm_project_kind(str(patch.get("kind") or ""))
        if "status" in patch:
            doc["status"] = _norm_project_status(str(patch.get("status") or ""))
        if "owner_person_id" in patch:
            doc["owner_person_id"] = str(patch.get("owner_person_id") or "").strip()
        if "group_email" in patch:
            doc["group_email"] = str(patch.get("group_email") or "").strip()
        if "tags" in patch:
            doc["tags"] = _project_tags(patch.get("tags"))
        for key in ("start_on", "end_on", "jira_epic", "summary"):
            if key in patch:
                doc[key] = patch[key]
        doc["updated_at"] = utcnow()
        self.store.save("projects", project_id, doc)
        if "owner_person_id" in patch:
            self._link_project_owner(project_id, doc.get("owner_person_id") or "")
        return _attach(doc, project_id) or doc

    def delete_project(self, project_id: str) -> dict:
        doc = self.store.get("projects", project_id)
        if not doc:
            raise KeyError(project_id)
        doc["removed"] = True
        doc["updated_at"] = utcnow()
        self.store.save("projects", project_id, doc)
        return _attach(doc, project_id) or doc

    def _link_project_owner(self, project_id: str, person_id: str) -> None:
        if not person_id:
            return
        person = self.store.get("people", person_id)
        if not person:
            return
        ids = [str(x) for x in (person.get("project_ids") or []) if x]
        if project_id not in ids:
            ids.append(project_id)
            person["project_ids"] = ids
            person["updated_at"] = utcnow()
            self.store.save("people", person_id, person)

    def list_projects(
        self,
        account_id: str,
        *,
        q: str | None = None,
        status: str | None = None,
        kind: str | None = None,
    ) -> list[dict]:
        rows = [r for r in self._account_rows("projects", account_id) if not r.get("removed")]
        if status:
            rows = [r for r in rows if str(r.get("status") or "") == status]
        if kind:
            rows = [r for r in rows if str(r.get("kind") or "") == kind]
        needle = (q or "").strip().lower()
        if needle:
            filtered = []
            for row in rows:
                owner = str(row.get("owner_person_id") or "")
                blob = " ".join(
                    [
                        str(row.get("name") or ""),
                        str(row.get("kind") or ""),
                        str(row.get("status") or ""),
                        str(row.get("group_email") or ""),
                        str(row.get("summary") or ""),
                        str(row.get("jira_epic") or ""),
                        " ".join(row.get("tags") or []),
                        owner,
                    ]
                ).lower()
                if needle in blob:
                    filtered.append(row)
            rows = filtered
        rows.sort(key=lambda r: str(r.get("name") or ""))
        return rows

    def add_note(self, body: dict) -> dict:
        doc_id = f"note:{hex12()}"
        doc = {
            "type": "note",
            "account_id": body.get("account_id") or "",
            "ref": body.get("ref") or {"collection": "accounts", "id": body.get("account_id") or ""},
            "body": body.get("body") or "",
            "author": body.get("author") or "you",
            "created_at": utcnow(),
        }
        self.store.save("notes", doc_id, doc)
        return _attach(doc, doc_id) or doc

    def list_notes(
        self,
        account_id: str,
        *,
        ref_id: str | None = None,
        q: str | None = None,
    ) -> list[dict]:
        rows = self._account_rows("notes", account_id)
        if ref_id:
            rows = [r for r in rows if str((r.get("ref") or {}).get("id") or "") == ref_id]
        needle = (q or "").strip().lower()
        if needle:
            rows = [r for r in rows if needle in str(r.get("body") or "").lower()]
        rows.sort(key=lambda r: str(r.get("created_at") or ""), reverse=True)
        return rows

    # -- tickets -----------------------------------------------------------

    def upsert_ticket(self, doc: dict, *, doc_id: str | None = None) -> dict:
        key = str(doc.get("key") or "")
        source = str(doc.get("source") or "jira")
        tid = doc_id or str(doc.get("_id") or f"tkt:{source}:{key}")
        comments = list(doc.get("comments") or [])[-10:]
        for item in comments:
            if isinstance(item, dict) and item.get("text"):
                item["text"] = str(item["text"])[:2000]
        doc = dict(doc)
        doc["type"] = "ticket"
        doc["comments"] = comments
        existing = self.store.get("tickets", tid)
        if existing:
            op = existing.get("operator") or {}
            incoming_op = doc.get("operator") or {}
            doc["operator"] = {
                "triage": incoming_op.get("triage", op.get("triage", "")),
                "ignore": incoming_op.get("ignore", op.get("ignore", False)),
            }
            if existing.get("operator") and "triage" not in (doc.get("_force_operator") or {}):
                doc["operator"] = existing.get("operator") or doc["operator"]
        else:
            doc.setdefault("operator", {"triage": "", "ignore": False})
        self.store.save("tickets", tid, doc)
        return _attach(doc, tid) or doc

    def get_ticket(self, ticket_id: str) -> dict | None:
        return _attach(self.store.get("tickets", ticket_id), ticket_id)

    def patch_ticket_operator(self, ticket_id: str, patch: dict) -> dict:
        doc = self.store.get("tickets", ticket_id)
        if not doc:
            raise KeyError(ticket_id)
        op = dict(doc.get("operator") or {})
        if "triage" in patch:
            op["triage"] = patch["triage"]
        if "ignore" in patch:
            op["ignore"] = bool(patch["ignore"])
        doc["operator"] = op
        self.store.save("tickets", ticket_id, doc)
        return _attach(doc, ticket_id) or doc

    def page_tickets(
        self,
        account_id: str,
        *,
        status: str | None = None,
        priority: str | None = None,
        q: str | None = None,
        project_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        rows = self._account_rows("tickets", account_id)
        if status:
            rows = [r for r in rows if r.get("status") == status]
        if priority:
            rows = [r for r in rows if r.get("priority") == priority]
        if project_id:
            rows = [r for r in rows if str(r.get("project_id") or "") == project_id]
        if q:
            needle = q.lower()
            rows = [
                r
                for r in rows
                if needle in str(r.get("key") or "").lower() or needle in str(r.get("summary") or "").lower()
            ]
        rows.sort(key=lambda r: str(r.get("updated_at") or ""), reverse=True)
        total = len(rows)
        return rows[offset : offset + limit], total

    # -- mail --------------------------------------------------------------

    def upsert_email(self, doc: dict) -> dict:
        body = str(doc.get("body_text") or "")
        if len(body.encode("utf-8")) > 200 * 1024:
            body = body.encode("utf-8")[: 200 * 1024].decode("utf-8", "ignore")
            doc["body_text"] = body
        doc = dict(doc)
        doc["type"] = "email"
        doc["body_bytes"] = int(doc.get("body_bytes") or len(body.encode("utf-8")))
        eid = str(doc.get("_id") or email_doc_id(doc))
        thread_id = str(doc.get("thread_id") or thread_doc_id(doc))
        doc["thread_id"] = thread_id
        existing = self.store.get("emails", eid)
        if existing:
            op = existing.get("operator") or {}
            doc["operator"] = doc.get("operator") or op
            if existing.get("operator"):
                doc["operator"] = existing["operator"]
        else:
            doc.setdefault("operator", {"unread": True})
        self.store.save("emails", eid, doc)
        thread = self.get_thread(thread_id) or {
            "type": "thread",
            "account_id": doc.get("account_id") or "",
            "subject": doc.get("subject") or "",
            "last_at": doc.get("sent_at") or utcnow(),
            "message_count": 0,
            "participants": [],
            "operator": {"unread": True, "pinned": False},
        }
        parts = set(thread.get("participants") or [])
        if doc.get("from_addr"):
            parts.add(doc["from_addr"])
        for addr in doc.get("to_addrs") or []:
            parts.add(addr)
        thread["participants"] = sorted(parts)
        thread["account_id"] = doc.get("account_id") or thread.get("account_id") or ""
        thread["subject"] = thread.get("subject") or doc.get("subject") or ""
        sent = str(doc.get("sent_at") or "")
        if sent >= str(thread.get("last_at") or ""):
            thread["last_at"] = sent
        if not existing:
            thread["message_count"] = int(thread.get("message_count") or 0) + 1
        thread["type"] = "thread"
        self.store.save("threads", thread_id, thread)
        return _attach(doc, eid) or doc

    def save_task(self, body: dict, *, email_id: str | None = None) -> dict:
        aid = str(body.get("account_id") or "").strip()
        acct = self.get_account(aid)
        if not acct:
            raise ValueError("account required")
        task_name = str(body.get("task_name") or "").strip()
        if not task_name:
            raise ValueError("task name required")
        kind = str(body.get("task_kind") or "").strip() or TASK_KINDS[0]
        if kind not in TASK_KINDS:
            kind = kind or TASK_KINDS[0]
        company = str(acct.get("name") or acct.get("abbr") or "").strip()
        profile = self.operator_profile()
        me = str(profile.get("email") or "").strip() or "operator@local"
        cc = _norm_emails(body.get("cc_addrs"))
        bcc = _norm_emails(body.get("bcc_addrs"))
        due_at = str(body.get("due_at") or "").strip()
        content = str(body.get("body") or body.get("content") or "")
        now = utcnow()
        existing = self.get_email(email_id) if email_id else None
        if email_id and not existing:
            raise KeyError(email_id)
        eid = str((existing or {}).get("_id") or email_id or f"em:task:{hex12()}")
        thread_id = str((existing or {}).get("thread_id") or f"thr:task:{hex12()}")
        message_id = str((existing or {}).get("message_id") or f"<task.{eid.split(':')[-1]}@csm.local>")
        doc = {
            "type": "email",
            "account_id": aid,
            "subject": _task_subject(company, task_name, kind),
            "from_addr": me,
            "to_addrs": [me],
            "cc_addrs": cc,
            "bcc_addrs": bcc,
            "body_text": _task_body(content, due_at),
            "snippet": content.strip()[:180],
            "sent_at": now if not existing else (existing.get("sent_at") or now),
            "updated_at": now,
            "direction": "internal",
            "message_id": message_id,
            "thread_id": thread_id,
            "operator": {
                "unread": True,
                "task": True,
                "task_name": task_name,
                "task_kind": kind,
                "due_at": due_at,
            },
        }
        self.store.save("emails", eid, doc)
        thread = self.get_thread(thread_id) or {
            "type": "thread",
            "account_id": aid,
            "subject": doc["subject"],
            "last_at": doc["sent_at"],
            "message_count": 0,
            "participants": [],
            "operator": {"unread": True, "pinned": False},
        }
        parts = set(thread.get("participants") or [])
        parts.add(me)
        parts.update(cc)
        thread["participants"] = sorted(parts)
        thread["account_id"] = aid
        thread["subject"] = doc["subject"]
        thread["last_at"] = now
        thread["type"] = "thread"
        if not existing:
            thread["message_count"] = int(thread.get("message_count") or 0) + 1
        op = dict(thread.get("operator") or {})
        op["unread"] = True
        thread["operator"] = op
        self.store.save("threads", thread_id, thread)
        return self.task_public(eid) or _attach(doc, eid) or doc

    def task_public(self, email_id: str) -> dict | None:
        doc = self.get_email(email_id)
        if not doc or not _is_task_email(doc):
            return None
        op = doc.get("operator") or {}
        body = str(doc.get("body_text") or "")
        content = body
        marker = "\n\nWhen Due By:"
        if marker in body:
            content = body.split(marker, 1)[0]
        out = dict(doc)
        out["task_name"] = str(op.get("task_name") or "")
        out["task_kind"] = str(op.get("task_kind") or "")
        out["due_at"] = str(op.get("due_at") or "")
        out["mailbox_sent_at"] = str(op.get("mailbox_sent_at") or "")
        out["content"] = content
        out["cc_addrs"] = list(doc.get("cc_addrs") or [])
        out["bcc_addrs"] = list(doc.get("bcc_addrs") or [])
        return out

    def get_email(self, email_id: str) -> dict | None:
        return _attach(self.store.get("emails", email_id), email_id)

    def patch_email_operator(self, email_id: str, patch: dict) -> dict:
        doc = self.store.get("emails", email_id)
        if not doc:
            raise KeyError(email_id)
        op = dict(doc.get("operator") or {})
        if "unread" in patch:
            op["unread"] = bool(patch["unread"])
        doc["operator"] = op
        self.store.save("emails", email_id, doc)
        return _attach(doc, email_id) or doc

    def page_emails(self, account_id: str, *, thread_id: str | None = None, limit: int = 50, offset: int = 0):
        rows = self._account_rows("emails", account_id)
        if thread_id:
            rows = [r for r in rows if r.get("thread_id") == thread_id]
        rows.sort(key=lambda r: str(r.get("sent_at") or ""))
        return rows[offset : offset + limit], len(rows)

    def upsert_thread(self, doc: dict, *, doc_id: str | None = None) -> dict:
        tid = doc_id or str(doc.get("_id") or thread_doc_id(doc))
        existing = self.store.get("threads", tid)
        merged = {**(existing or {}), **doc, "type": "thread"}
        if existing and existing.get("operator"):
            merged["operator"] = existing["operator"]
        else:
            merged.setdefault("operator", {"unread": True, "pinned": False})
        self.store.save("threads", tid, merged)
        return _attach(merged, tid) or merged

    def get_thread(self, thread_id: str) -> dict | None:
        return _attach(self.store.get("threads", thread_id), thread_id)

    def patch_thread_operator(self, thread_id: str, patch: dict) -> dict:
        doc = self.store.get("threads", thread_id)
        if not doc:
            raise KeyError(thread_id)
        op = dict(doc.get("operator") or {})
        if "unread" in patch:
            op["unread"] = bool(patch["unread"])
        if "pinned" in patch:
            op["pinned"] = bool(patch["pinned"])
        doc["operator"] = op
        self.store.save("threads", thread_id, doc)
        return _attach(doc, thread_id) or doc

    def page_threads(self, account_id: str, *, limit: int = 50, offset: int = 0):
        rows = self._account_rows("threads", account_id)
        rows.sort(key=lambda r: str(r.get("last_at") or ""), reverse=True)
        return rows[offset : offset + limit], len(rows)

    # -- slack / calendar --------------------------------------------------

    def upsert_slack_channel(self, doc: dict) -> dict:
        cid = str(doc.get("channel_id") or "")
        doc_id = f"slc:{cid}"
        doc = {**doc, "type": "slack_channel"}
        self.store.save("slack_channels", doc_id, doc)
        return _attach(doc, doc_id) or doc

    def upsert_slack_message(self, doc: dict, *, emit_activity: bool = True) -> dict:
        channel_id = str(doc.get("channel_id") or "")
        ts = str(doc.get("ts") or "")
        ts_safe = ts.replace(".", "_")
        doc_id = f"slm:{channel_id}:{ts_safe}"
        existing = self.store.get("slack_messages", doc_id)
        merged = {**(existing or {}), **doc, "type": "slack_message"}
        if existing and existing.get("operator"):
            op = dict(existing["operator"])
            incoming = doc.get("operator") or {}
            if "unread" in incoming:
                op["unread"] = bool(incoming["unread"])
            if "pin" in incoming:
                op["pin"] = bool(incoming["pin"])
            merged["operator"] = op
        else:
            merged.setdefault("operator", {"pin": False, "unread": True})
        self.store.save("slack_messages", doc_id, merged)
        if emit_activity:
            thread_ts = str(merged.get("thread_ts") or "")
            is_root = not thread_ts or thread_ts == ts
            pinned = bool((merged.get("operator") or {}).get("pin"))
            mention = "@" in str(merged.get("text") or "")
            if is_root or pinned or mention:
                self.upsert_activity_by_source_ref(
                    {
                        "account_id": merged.get("account_id") or "",
                        "kind": "slack",
                        "at": ts_to_iso(ts),
                        "title": (str(merged.get("text") or "")[:160]),
                        "ref": {"collection": "slack_messages", "id": doc_id},
                        "source_ref": f"slack:{channel_id}:{ts}",
                        "actor": merged.get("user_name") or "slack",
                    }
                )
        return _attach(merged, doc_id) or merged

    def get_slack_message(self, message_id: str) -> dict | None:
        return _attach(self.store.get("slack_messages", message_id), message_id)

    def patch_slack_operator(self, message_id: str, patch: dict) -> dict:
        doc = self.store.get("slack_messages", message_id)
        if not doc:
            raise KeyError(message_id)
        op = dict(doc.get("operator") or {})
        if "pin" in patch:
            op["pin"] = bool(patch["pin"])
        doc["operator"] = op
        self.store.save("slack_messages", message_id, doc)
        return _attach(doc, message_id) or doc

    def page_slack(self, account_id: str, *, channel_id: str | None = None, limit: int = 50, before_ts: str | None = None):
        rows = self._account_rows("slack_messages", account_id)
        if channel_id:
            rows = [r for r in rows if r.get("channel_id") == channel_id]
        if before_ts:
            rows = [r for r in rows if str(r.get("ts") or "") < before_ts]
        rows.sort(key=lambda r: str(r.get("ts") or ""))
        return rows[-limit:], len(rows)

    def list_slack_channels(self, account_id: str) -> list[dict]:
        return self._account_rows("slack_channels", account_id)

    def upsert_teams_channel(self, doc: dict) -> dict:
        cid = str(doc.get("channel_id") or "")
        doc_id = f"tmc:{cid}"
        payload = {**doc, "type": "teams_channel"}
        self.store.save("teams_channels", doc_id, payload)
        return _attach(payload, doc_id) or payload

    def upsert_teams_message(self, doc: dict, *, emit_activity: bool = True) -> dict:
        channel_id = str(doc.get("channel_id") or "")
        ts = str(doc.get("ts") or "")
        ts_safe = ts.replace(".", "_")
        doc_id = f"tmm:{channel_id}:{ts_safe}"
        existing = self.store.get("teams_messages", doc_id)
        merged = {**(existing or {}), **doc, "type": "teams_message"}
        if existing and existing.get("operator"):
            op = dict(existing["operator"])
            incoming = doc.get("operator") or {}
            if "unread" in incoming:
                op["unread"] = bool(incoming["unread"])
            if "pin" in incoming:
                op["pin"] = bool(incoming["pin"])
            merged["operator"] = op
        else:
            merged.setdefault("operator", {"pin": False, "unread": True})
        self.store.save("teams_messages", doc_id, merged)
        if emit_activity:
            thread_id = str(merged.get("thread_id") or "")
            is_root = not thread_id
            pinned = bool((merged.get("operator") or {}).get("pin"))
            mention = "@" in str(merged.get("text") or "")
            if is_root or pinned or mention:
                self.upsert_activity_by_source_ref(
                    {
                        "account_id": merged.get("account_id") or "",
                        "kind": "teams",
                        "at": ts_to_iso(ts),
                        "title": (str(merged.get("text") or "")[:160]),
                        "ref": {"collection": "teams_messages", "id": doc_id},
                        "source_ref": f"teams:{channel_id}:{ts}",
                        "actor": merged.get("user_name") or "teams",
                    }
                )
        return _attach(merged, doc_id) or merged

    def get_teams_message(self, message_id: str) -> dict | None:
        return _attach(self.store.get("teams_messages", message_id), message_id)

    def patch_teams_operator(self, message_id: str, patch: dict) -> dict:
        doc = self.store.get("teams_messages", message_id)
        if not doc:
            raise KeyError(message_id)
        op = dict(doc.get("operator") or {})
        if "pin" in patch:
            op["pin"] = bool(patch["pin"])
        doc["operator"] = op
        self.store.save("teams_messages", message_id, doc)
        return _attach(doc, message_id) or doc

    def page_teams(self, account_id: str, *, channel_id: str | None = None, limit: int = 50, before_ts: str | None = None):
        rows = self._account_rows("teams_messages", account_id)
        if channel_id:
            rows = [r for r in rows if r.get("channel_id") == channel_id]
        if before_ts:
            rows = [r for r in rows if str(r.get("ts") or "") < before_ts]
        rows.sort(key=lambda r: str(r.get("ts") or ""))
        return rows[-limit:], len(rows)

    def list_teams_channels(self, account_id: str) -> list[dict]:
        return self._account_rows("teams_channels", account_id)

    def upsert_salesforce_opportunity(self, doc: dict, *, emit_activity: bool = True) -> dict:
        ext = str(doc.get("external_id") or doc.get("_id") or "").removeprefix("sfo:") or hex12()
        doc_id = f"sfo:{ext}"
        existing = self.store.get("salesforce_opportunities", doc_id)
        merged = {**(existing or {}), **doc, "type": "salesforce_opportunity"}
        if existing and existing.get("operator"):
            merged["operator"] = existing["operator"]
        else:
            merged.setdefault("operator", {"pin": False})
        self.store.save("salesforce_opportunities", doc_id, merged)
        if emit_activity:
            at = merged.get("updated_at") or utcnow()
            self.upsert_activity_by_source_ref(
                {
                    "account_id": merged.get("account_id") or "",
                    "kind": "salesforce",
                    "at": at,
                    "title": f"{merged.get('name') or ext} · {merged.get('stage') or ''}".strip(" ·"),
                    "ref": {"collection": "salesforce_opportunities", "id": doc_id},
                    "source_ref": f"sfdc:opp:{ext}:{merged.get('stage') or ''}:{at}",
                    "actor": "salesforce",
                    "project_id": merged.get("project_id") or "",
                }
            )
        return _attach(merged, doc_id) or merged

    def get_salesforce_opportunity(self, opp_id: str) -> dict | None:
        return _attach(self.store.get("salesforce_opportunities", opp_id), opp_id)

    def page_salesforce_opportunities(self, account_id: str, *, q: str | None = None) -> list[dict]:
        rows = self._account_rows("salesforce_opportunities", account_id)
        needle = (q or "").strip().lower()
        if needle:
            rows = [
                r
                for r in rows
                if needle in " ".join([str(r.get("name") or ""), str(r.get("stage") or ""), str(r.get("kind") or "")]).lower()
            ]
        rows.sort(key=lambda r: str(r.get("close_on") or ""), reverse=True)
        return rows

    def upsert_salesforce_case(self, doc: dict, *, emit_activity: bool = True) -> dict:
        num = str(doc.get("case_number") or doc.get("external_id") or "").removeprefix("sfc:") or hex12()
        doc_id = f"sfc:{num}"
        existing = self.store.get("salesforce_cases", doc_id)
        merged = {**(existing or {}), **doc, "type": "salesforce_case"}
        if existing and existing.get("operator"):
            merged["operator"] = existing["operator"]
        else:
            merged.setdefault("operator", {"pin": False})
        self.store.save("salesforce_cases", doc_id, merged)
        if emit_activity:
            at = merged.get("updated_at") or utcnow()
            self.upsert_activity_by_source_ref(
                {
                    "account_id": merged.get("account_id") or "",
                    "kind": "salesforce",
                    "at": at,
                    "title": f"Case {num} · {merged.get('subject') or ''}".strip(" ·"),
                    "ref": {"collection": "salesforce_cases", "id": doc_id},
                    "source_ref": f"sfdc:case:{num}:{merged.get('status') or ''}:{at}",
                    "actor": "salesforce",
                    "project_id": merged.get("project_id") or "",
                }
            )
        return _attach(merged, doc_id) or merged

    def get_salesforce_case(self, case_id: str) -> dict | None:
        return _attach(self.store.get("salesforce_cases", case_id), case_id)

    def page_salesforce_cases(self, account_id: str, *, q: str | None = None) -> list[dict]:
        rows = self._account_rows("salesforce_cases", account_id)
        needle = (q or "").strip().lower()
        if needle:
            rows = [
                r
                for r in rows
                if needle
                in " ".join(
                    [str(r.get("case_number") or ""), str(r.get("subject") or ""), str(r.get("status") or "")]
                ).lower()
            ]
        rows.sort(key=lambda r: str(r.get("updated_at") or ""), reverse=True)
        return rows

    def upsert_calendar(self, doc: dict) -> dict:
        provider = str(doc.get("provider") or "stub")
        ext = str(doc.get("external_id") or "").replace("/", "_")
        doc_id = f"cal:{provider}:{ext}"
        existing = self.store.get("calendar_events", doc_id)
        merged = {**(existing or {}), **doc, "type": "calendar_event"}
        if existing and existing.get("operator"):
            op = dict(existing["operator"])
            incoming = doc.get("operator") or {}
            if "unread" in incoming:
                op["unread"] = bool(incoming["unread"])
            if "prep_note" in incoming:
                op["prep_note"] = incoming["prep_note"]
            merged["operator"] = op
        else:
            merged.setdefault("operator", {"prep_note": "", "unread": True})
        self.store.save("calendar_events", doc_id, merged)
        return _attach(merged, doc_id) or merged

    def get_calendar(self, event_id: str) -> dict | None:
        return _attach(self.store.get("calendar_events", event_id), event_id)

    def patch_calendar_operator(self, event_id: str, patch: dict) -> dict:
        doc = self.store.get("calendar_events", event_id)
        if not doc:
            raise KeyError(event_id)
        op = dict(doc.get("operator") or {})
        if "prep_note" in patch:
            op["prep_note"] = str(patch["prep_note"] or "")
        doc["operator"] = op
        self.store.save("calendar_events", event_id, doc)
        return _attach(doc, event_id) or doc

    def page_calendar(self, account_id: str, *, start: str | None = None, end: str | None = None):
        rows = self._account_rows("calendar_events", account_id)
        if start:
            rows = [r for r in rows if str(r.get("start_at") or "") >= start]
        if end:
            rows = [r for r in rows if str(r.get("start_at") or "") <= end]
        rows.sort(key=lambda r: str(r.get("start_at") or ""))
        return rows

    # -- actions / drafts / reports / chats / jobs -------------------------

    def create_action(self, body: dict) -> dict:
        token = str(body.get("_id") or "").removeprefix("actn:") or hex12()
        doc_id = body.get("_id") if str(body.get("_id") or "").startswith("actn:") else f"actn:{token}"
        now = utcnow()
        doc = {
            "type": "action_item",
            "account_id": body.get("account_id") or "",
            "title": body.get("title") or "",
            "kind": body.get("kind") or "other",
            "status": body.get("status") or "open",
            "due_on": body.get("due_on") or "",
            "owner_person_id": body.get("owner_person_id") or "",
            "owner_label": body.get("owner_label") or "",
            "source": body.get("source") or "operator",
            "linked": body.get("linked") or {},
            "created_by": body.get("created_by") or "you",
            "created_at": now,
            "completed_at": body.get("completed_at") or "",
        }
        self.store.save("action_items", doc_id, doc)
        if doc.get("account_id"):
            self.touch_next_action(doc["account_id"])
        return _attach(doc, doc_id) or doc

    def get_action(self, action_id: str) -> dict | None:
        return _attach(self.store.get("action_items", action_id), action_id)

    def patch_action(self, action_id: str, patch: dict) -> dict:
        doc = self.store.get("action_items", action_id)
        if not doc:
            raise KeyError(action_id)
        for key in ("title", "kind", "status", "due_on", "owner_person_id", "owner_label"):
            if key in patch:
                doc[key] = patch[key]
        if doc.get("status") == "done" and not doc.get("completed_at"):
            doc["completed_at"] = utcnow()
        self.store.save("action_items", action_id, doc)
        if doc.get("account_id"):
            self.touch_next_action(doc["account_id"])
        return _attach(doc, action_id) or doc

    def page_actions(
        self,
        *,
        account_id: str | None = None,
        status: str | None = None,
        due: str = "all",
        today: str | None = None,
    ) -> list[dict]:
        rows = self._account_rows("action_items", account_id) if account_id else self.store.query_all("action_items")
        if status:
            rows = [r for r in rows if r.get("status") == status]
        day = today or utcnow()[:10]
        if due == "overdue":
            rows = [r for r in rows if r.get("status") == "open" and str(r.get("due_on") or "") and r["due_on"] < day]
        elif due == "today":
            rows = [r for r in rows if str(r.get("due_on") or "") == day]
        rows.sort(key=lambda r: (str(r.get("due_on") or "9999"), str(r.get("title") or "")))
        return rows

    def touch_next_action(self, account_id: str) -> None:
        acct = self.store.get("accounts", account_id)
        if not acct:
            return
        open_items = self.page_actions(account_id=account_id, status="open")
        if not open_items:
            acct["next_action"] = {}
        else:
            first = open_items[0]
            acct["next_action"] = {
                "kind": first.get("kind") or "other",
                "due_on": first.get("due_on") or "",
                "title": first.get("title") or "",
                "action_id": first.get("_id") or "",
            }
        acct["updated_at"] = utcnow()
        self.store.save("accounts", account_id, acct)

    def create_draft(self, body: dict) -> dict:
        token = hex12()
        doc_id = f"draft:{token}"
        now = utcnow()
        doc = {
            "type": "draft",
            "account_id": body.get("account_id") or "",
            "status": body.get("status") or "ready",
            "channel": body.get("channel") or "email",
            "to_addrs": body.get("to_addrs") or [],
            "cc_addrs": body.get("cc_addrs") or [],
            "bcc_addrs": body.get("bcc_addrs") or [],
            "attachment_names": body.get("attachment_names") or [],
            "subject": body.get("subject") or "",
            "body": body.get("body") or "",
            "prompt_name": body.get("prompt_name") or "",
            "model": body.get("model") or "",
            "context_ref": body.get("context_ref") or {},
            "created_by": body.get("created_by") or "you",
            "created_at": now,
            "updated_at": now,
            "sent_at": "",
            "send_error": "",
        }
        self.store.save("drafts", doc_id, doc)
        return _attach(doc, doc_id) or doc

    def get_draft(self, draft_id: str) -> dict | None:
        return _attach(self.store.get("drafts", draft_id), draft_id)

    def patch_draft(self, draft_id: str, patch: dict) -> dict:
        doc = self.store.get("drafts", draft_id)
        if not doc:
            raise KeyError(draft_id)
        for key in ("subject", "body", "to_addrs", "cc_addrs", "bcc_addrs", "attachment_names", "status"):
            if key in patch:
                doc[key] = patch[key]
        doc["updated_at"] = utcnow()
        self.store.save("drafts", draft_id, doc)
        return _attach(doc, draft_id) or doc

    def mark_draft_sent(self, draft_id: str, *, error: str = "") -> dict:
        doc = self.store.get("drafts", draft_id)
        if not doc:
            raise KeyError(draft_id)
        now = utcnow()
        if error:
            doc["status"] = "failed"
            doc["send_error"] = error
        else:
            doc["status"] = "sent"
            doc["sent_at"] = now
            doc["send_error"] = ""
        doc["updated_at"] = now
        self.store.save("drafts", draft_id, doc)
        return _attach(doc, draft_id) or doc

    def mark_task_sent(self, email_id: str) -> dict:
        doc = self.get_email(email_id)
        if not doc or not _is_task_email(doc):
            raise KeyError(email_id)
        op = dict(doc.get("operator") or {})
        op["mailbox_sent_at"] = utcnow()
        doc["operator"] = op
        doc["updated_at"] = utcnow()
        self.store.save("emails", email_id, doc)
        return self.task_public(email_id) or _attach(doc, email_id) or doc

    def list_drafts(self, account_id: str) -> list[dict]:
        rows = self._account_rows("drafts", account_id)
        rows.sort(key=lambda r: str(r.get("updated_at") or ""), reverse=True)
        return rows

    def create_report(self, body: dict) -> dict:
        doc_id = f"rpt:{hex12()}"
        doc = {
            "type": "report",
            "account_id": body.get("account_id") or "",
            "kind": body.get("kind") or "weekly",
            "period_start": body.get("period_start") or "",
            "period_end": body.get("period_end") or "",
            "title": body.get("title") or "",
            "body_md": body.get("body_md") or "",
            "model": body.get("model") or "",
            "prompt_name": body.get("prompt_name") or "weekly_report",
            "created_at": utcnow(),
        }
        self.store.save("reports", doc_id, doc)
        return _attach(doc, doc_id) or doc

    def get_report(self, report_id: str) -> dict | None:
        return _attach(self.store.get("reports", report_id), report_id)

    def list_reports(self, account_id: str | None = None) -> list[dict]:
        rows = self.store.query_all("reports")
        if account_id:
            rows = [r for r in rows if r.get("account_id") == account_id]
        rows.sort(key=lambda r: str(r.get("created_at") or ""), reverse=True)
        return rows

    def save_chat(self, doc: dict, *, chat_id: str | None = None) -> dict:
        cid = chat_id or doc.get("_id") or f"chat:{hex12()}"
        prev = self.store.get("chats", cid)
        payload = {**(prev or {}), **doc, "type": "chat", "updated_at": utcnow()}
        if prev and prev.get("created_at"):
            payload["created_at"] = prev["created_at"]
        else:
            payload.setdefault("created_at", utcnow())
        if "bookmarked" not in doc and prev is not None:
            payload["bookmarked"] = bool(prev.get("bookmarked"))
        else:
            payload["bookmarked"] = bool(payload.get("bookmarked"))
        title = str(payload.get("title") or "").strip()
        if not title or title in {"Desk chat", "Account coach", "New chat"}:
            payload["title"] = _chat_title(payload.get("messages"), title or "New chat")
        self.store.save("chats", cid, payload)
        return _attach(payload, cid) or payload

    def get_chat(self, chat_id: str) -> dict | None:
        return _attach(self.store.get("chats", chat_id), chat_id)

    def patch_chat(self, chat_id: str, patch: dict) -> dict:
        doc = self.store.get("chats", chat_id)
        if not doc:
            raise KeyError(chat_id)
        if "bookmarked" in patch:
            doc["bookmarked"] = bool(patch.get("bookmarked"))
        if "title" in patch:
            doc["title"] = str(patch.get("title") or "").strip()[:120]
        return self.save_chat(doc, chat_id=chat_id)

    def list_chats(self, account_id: str) -> list[dict]:
        rows = self._account_rows("chats", account_id)
        rows.sort(key=lambda r: str(r.get("updated_at") or ""), reverse=True)
        rows.sort(key=lambda r: 0 if r.get("bookmarked") else 1)
        return rows

    def save_job(self, doc: dict, *, job_id: str | None = None) -> dict:
        jid = job_id or doc.get("_id") or f"job:{hex12()}"
        doc = {**doc, "type": "sync_job", "updated_at": utcnow()}
        doc.setdefault("created_at", utcnow())
        self.store.save("sync_jobs", jid, doc)
        return _attach(doc, jid) or doc

    def get_job(self, job_id: str) -> dict | None:
        return _attach(self.store.get("sync_jobs", job_id), job_id)

    def list_jobs(self) -> list[dict]:
        rows = self.store.query_all("sync_jobs")
        rows.sort(key=lambda r: str(r.get("updated_at") or ""), reverse=True)
        return rows

    # -- activities --------------------------------------------------------

    def upsert_activity_by_source_ref(self, doc: dict) -> dict:
        source_ref = str(doc.get("source_ref") or "").strip()
        if not source_ref:
            raise ValueError("source_ref required")
        doc_id = activity_doc_id(source_ref)
        existing = self.store.get("activities", doc_id)
        merged = {
            "type": "activity",
            "account_id": doc.get("account_id") or "",
            "kind": doc.get("kind") or "note",
            "at": doc.get("at") or utcnow(),
            "title": str(doc.get("title") or "")[:160],
            "ref": doc.get("ref") or {},
            "source_ref": source_ref,
            "actor": doc.get("actor") or "",
            "body": "",
            "project_id": str(doc.get("project_id") or (existing or {}).get("project_id") or ""),
        }
        if existing and existing.get("created_at"):
            merged["created_at"] = existing["created_at"]
        else:
            merged["created_at"] = utcnow()
        self.store.save("activities", doc_id, merged)
        return _attach(merged, doc_id) or merged

    def add_operator_activity(self, doc: dict) -> dict:
        doc_id = f"act:{hex12()}"
        payload = {
            "type": "activity",
            "account_id": doc.get("account_id") or "",
            "kind": doc.get("kind") or "note",
            "at": doc.get("at") or utcnow(),
            "title": str(doc.get("title") or "")[:160],
            "ref": doc.get("ref") or {},
            "source_ref": "",
            "actor": doc.get("actor") or "you",
            "body": "",
            "project_id": str(doc.get("project_id") or ""),
            "created_at": utcnow(),
        }
        self.store.save("activities", doc_id, payload)
        return _attach(payload, doc_id) or payload

    def get_activity(self, activity_id: str) -> dict | None:
        return _attach(self.store.get("activities", activity_id), activity_id)

    def patch_activity(self, activity_id: str, patch: dict) -> dict:
        doc = self.store.get("activities", activity_id)
        if not doc:
            raise KeyError(activity_id)
        if "project_id" in patch:
            pid = str(patch.get("project_id") or "").strip()
            if pid and not self.store.get("projects", pid):
                raise ValueError("unknown project")
            doc["project_id"] = pid
            self._stamp_ref_project(doc.get("ref") or {}, pid)
        doc["updated_at"] = utcnow()
        self.store.save("activities", activity_id, doc)
        return _attach(doc, activity_id) or doc

    def _stamp_ref_project(self, ref: dict, project_id: str) -> None:
        col = str(ref.get("collection") or "")
        rid = str(ref.get("id") or "")
        if col not in REF_PROJECT_COLLECTIONS or not rid:
            return
        related = self.store.get(col, rid)
        if not related:
            return
        related["project_id"] = project_id
        self.store.save(col, rid, related)

    def page_timeline(
        self,
        account_id: str,
        *,
        since: str | None = None,
        until: str | None = None,
        kind: str | None = None,
        project_id: str | None = None,
        q: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        filtered = bool(project_id or q or since or until)
        fetch_limit = 200 if filtered else limit
        fetch_offset = 0 if filtered else offset
        fn = getattr(self.store, "page_timeline", None)
        if callable(fn):
            try:
                rows = fn(
                    account_id,
                    since=since,
                    until=until,
                    kind=kind,
                    limit=fetch_limit,
                    offset=fetch_offset,
                )
            except TypeError:
                rows = fn(account_id, since=since, kind=kind, limit=fetch_limit, offset=fetch_offset)
                if until:
                    rows = [r for r in rows if str(r.get("at") or "") <= until]
        else:
            rows = self._account_rows("activities", account_id)
            if since:
                rows = [r for r in rows if str(r.get("at") or "") >= since]
            if until:
                rows = [r for r in rows if str(r.get("at") or "") <= until]
            if kind:
                rows = [r for r in rows if r.get("kind") == kind]
            rows.sort(key=lambda r: str(r.get("at") or ""), reverse=True)
            rows = rows[fetch_offset : fetch_offset + fetch_limit]
        if project_id:
            rows = [r for r in rows if self._activity_on_project(r, project_id)]
        needle = (q or "").strip().lower()
        if needle:
            rows = [
                r
                for r in rows
                if needle in " ".join(
                    [str(r.get("title") or ""), str(r.get("kind") or ""), str(r.get("actor") or "")]
                ).lower()
            ]
        if filtered:
            rows = rows[offset : offset + limit]
        return self._stamp_note_counts(account_id, rows)

    def _stamp_note_counts(self, account_id: str, rows: list[dict]) -> list[dict]:
        counts: dict[str, int] = {}
        for note in self.list_notes(account_id):
            rid = str((note.get("ref") or {}).get("id") or "")
            if rid:
                counts[rid] = counts.get(rid, 0) + 1
        for row in rows:
            row["note_count"] = int(counts.get(str(row.get("_id") or ""), 0))
        return rows

    def _activity_on_project(self, row: dict, project_id: str) -> bool:
        if str(row.get("project_id") or "") == project_id:
            return True
        ref = row.get("ref") or {}
        if ref.get("collection") == "tickets" and ref.get("id"):
            ticket = self.get_ticket(str(ref["id"]))
            if ticket and str(ticket.get("project_id") or "") == project_id:
                return True
        return False

    # -- stats / health / seed ---------------------------------------------

    def next_meeting(self, account_id: str) -> dict | None:
        now = utcnow()
        upcoming: list[dict] = []
        for ev in self.page_calendar(account_id):
            start = str(ev.get("start_at") or "")
            if start < now:
                continue
            raw = str(ev.get("status") or ev.get("response") or "").lower().replace(" ", "_")
            if raw in {"cancelled", "canceled", "declined"}:
                continue
            proposed = raw in {"proposed", "tentative", "needsaction", "needs_action"} or bool(
                (ev.get("operator") or {}).get("proposed")
            )
            upcoming.append(
                {
                    "title": ev.get("title") or "",
                    "start_at": start,
                    "status": "proposed" if proposed else "scheduled",
                    "location": ev.get("location") or "",
                }
            )
        upcoming.sort(key=lambda r: r["start_at"])
        return upcoming[0] if upcoming else None

    def _audience_book(self, acct: dict, *, me: str, us_domains: set[str]) -> dict:
        aid = acct.get("account_id") or acct.get("_id") or ""
        us_emails: set[str] = set()
        them_emails: set[str] = set()
        for person in self.list_people(aid):
            email = str(person.get("email") or "").strip().lower()
            if not email or email == me:
                continue
            if person.get("kind") in {"account_team", "ps_team"}:
                us_emails.add(email)
            else:
                them_emails.add(email)
        slack_im = {
            str(ch.get("channel_id") or "")
            for ch in self.list_slack_channels(aid)
            if ch.get("is_im") or ch.get("is_mpim")
        }
        teams_im = {
            str(ch.get("channel_id") or "")
            for ch in self.list_teams_channels(aid)
            if ch.get("is_im") or str(ch.get("chat_type") or "").lower() in {"oneonone", "dm"}
        }
        return {
            "me": me,
            "us_emails": us_emails,
            "them_emails": them_emails,
            "us_domains": us_domains,
            "them_domains": set(_norm_domains(acct.get("domains") or [])),
            "slack_im": slack_im,
            "teams_im": teams_im,
        }

    def home_agenda(self, day: str, *, start: str | None = None, end: str | None = None, inbox_limit: int = 50) -> dict:
        def _day(value: str, fallback: str) -> str:
            raw = str(value or "")[:10]
            return raw if re.match(r"^\d{4}-\d{2}-\d{2}$", raw) else fallback

        inbox_day = _day(day, utcnow()[:10])
        meet_start = _day(start, inbox_day)
        meet_end = _day(end, inbox_day)
        if meet_end < meet_start:
            meet_end = meet_start
        raw = inbox_day
        meetings: list[dict] = []
        inbox: list[dict] = []
        project_filters: list[dict] = []
        profile = self.operator_profile()
        me = str(profile.get("email") or "").strip().lower()
        us_domains = set(_norm_domains(profile.get("domains") or []))
        for acct in self.list_accounts():
            aid = acct.get("account_id") or acct.get("_id") or ""
            slim = {
                "account_id": aid,
                "name": acct.get("name") or "",
                "abbr": acct.get("abbr") or "",
                "color": acct.get("color") or "",
                "has_logo": self.account_has_logo(aid, acct),
                "logo_updated_at": acct.get("logo_updated_at") or "",
            }
            company_label = slim["name"] or slim["abbr"] or aid
            project_filters.append(
                {
                    "key": aid,
                    "account_id": aid,
                    "project_id": "",
                    "label": company_label,
                }
            )
            proj_names: dict[str, str] = {}
            for proj in self.list_projects(aid):
                pid = str(proj.get("_id") or "")
                pname = str(proj.get("name") or pid)
                if not pid:
                    continue
                proj_names[pid] = pname
                project_filters.append(
                    {
                        "key": aid + "|" + pid,
                        "account_id": aid,
                        "project_id": pid,
                        "label": company_label + ":" + pname,
                    }
                )
            for ev in self.page_calendar(aid):
                start = str(ev.get("start_at") or "")
                ev_day = start[:10]
                if ev_day < meet_start or ev_day > meet_end:
                    continue
                status = str(ev.get("status") or ev.get("response") or "").lower().replace(" ", "_")
                if status in {"cancelled", "canceled", "declined"}:
                    continue
                proposed = status in {"proposed", "tentative", "needsaction", "needs_action"} or bool(
                    (ev.get("operator") or {}).get("proposed")
                )
                meetings.append(
                    {
                        "_id": ev.get("_id") or "",
                        "title": ev.get("title") or "",
                        "start_at": start,
                        "end_at": ev.get("end_at") or "",
                        "location": ev.get("location") or "",
                        "status": "proposed" if proposed else "scheduled",
                        "attendees": ev.get("attendees") or [],
                        "account": slim,
                    }
                )
            book = self._audience_book(acct, me=me, us_domains=us_domains)
            mail_kw = {
                "me": book["me"],
                "us_emails": book["us_emails"],
                "them_emails": book["them_emails"],
                "us_domains": book["us_domains"],
                "them_domains": book["them_domains"],
            }
            emails, _ = self.page_emails(aid, limit=200)
            for mail in emails:
                op = mail.get("operator") or {}
                is_task = _is_task_email(mail)
                if is_task:
                    if op.get("ignore"):
                        continue
                elif not op.get("unread"):
                    continue
                mail_pid = str(mail.get("project_id") or "")
                mail_kind = "task" if is_task else "email"
                inbox.append(
                    {
                        "kind": mail_kind,
                        "at": str(mail.get("updated_at") or mail.get("sent_at") or ""),
                        "title": mail.get("subject") or "(no subject)",
                        "body": str(mail.get("snippet") or mail.get("body_text") or "")[:220],
                        "from_name": mail.get("from_addr") or "",
                        "due_at": str(op.get("due_at") or ""),
                        "task_kind": str(op.get("task_kind") or ""),
                        "project_id": mail_pid,
                        "project_name": proj_names.get(mail_pid) or "",
                        "account": slim,
                        "audience": inbox_audience(
                            kind=mail_kind,
                            to_addrs=mail.get("to_addrs") or [],
                            cc_addrs=mail.get("cc_addrs") or [],
                            bcc_addrs=mail.get("bcc_addrs") or [],
                            **mail_kw,
                        ),
                        "ref": {"collection": "emails", "id": mail.get("_id") or "", "thread_id": mail.get("thread_id") or ""},
                    }
                )
            slack, _ = self.page_slack(aid, limit=200)
            for msg in slack:
                if not (msg.get("operator") or {}).get("unread"):
                    continue
                slack_pid = str(msg.get("project_id") or "")
                slack_cid = str(msg.get("channel_id") or "")
                inbox.append(
                    {
                        "kind": "slack",
                        "at": ts_to_iso(str(msg.get("ts") or "")),
                        "title": msg.get("user_name") or msg.get("user") or "Slack",
                        "body": str(msg.get("text") or "")[:220],
                        "from_name": msg.get("user_name") or "",
                        "project_id": slack_pid,
                        "project_name": proj_names.get(slack_pid) or "",
                        "account": slim,
                        "audience": inbox_audience(
                            kind="slack",
                            channel_id=slack_cid,
                            is_im=slack_cid in book["slack_im"],
                        ),
                        "ref": {"collection": "slack_messages", "id": msg.get("_id") or ""},
                    }
                )
            teams, _ = self.page_teams(aid, limit=200)
            for msg in teams:
                if not (msg.get("operator") or {}).get("unread"):
                    continue
                teams_pid = str(msg.get("project_id") or "")
                teams_cid = str(msg.get("channel_id") or "")
                inbox.append(
                    {
                        "kind": "teams",
                        "at": ts_to_iso(str(msg.get("ts") or "")),
                        "title": msg.get("user_name") or msg.get("user") or "Teams",
                        "body": str(msg.get("text") or "")[:220],
                        "from_name": msg.get("user_name") or "",
                        "project_id": teams_pid,
                        "project_name": proj_names.get(teams_pid) or "",
                        "account": slim,
                        "audience": inbox_audience(
                            kind="teams",
                            channel_id=teams_cid,
                            is_im=teams_cid in book["teams_im"],
                        ),
                        "ref": {"collection": "teams_messages", "id": msg.get("_id") or ""},
                    }
                )
        meetings.sort(key=lambda r: str(r.get("start_at") or ""))
        inbox.sort(key=lambda r: str(r.get("at") or ""), reverse=True)
        return {
            "date": raw,
            "start": meet_start,
            "end": meet_end,
            "meetings": meetings,
            "inbox": inbox[:inbox_limit],
            "project_filters": project_filters,
        }

    def account_inbox_stats(self, account_id: str) -> dict:
        tickets, _ = self.page_tickets(account_id, limit=500)
        open_t = [t for t in tickets if _is_open_ticket(t)]
        new_tickets = [t for t in open_t if not str((t.get("operator") or {}).get("triage") or "").strip()]
        threads, _ = self.page_threads(account_id, limit=500)
        new_email = [t for t in threads if (t.get("operator") or {}).get("unread")]
        slack, _ = self.page_slack(account_id, limit=500)
        new_slack = [m for m in slack if (m.get("operator") or {}).get("unread")]
        teams, _ = self.page_teams(account_id, limit=500)
        new_teams = [m for m in teams if (m.get("operator") or {}).get("unread")]
        now = utcnow()
        cal = self.page_calendar(account_id)
        new_cal = []
        for ev in cal:
            start = str(ev.get("start_at") or "")
            if start < now:
                continue
            op = ev.get("operator") or {}
            raw = str(ev.get("status") or "").lower()
            if raw in {"cancelled", "canceled", "declined"}:
                continue
            if op.get("unread") or raw in {"proposed", "tentative", "needsaction", "needs_action"}:
                new_cal.append(ev)
        overdue = self.page_actions(account_id=account_id, due="overdue")
        return {
            "open_tickets": len(open_t),
            "open_p1": len([t for t in open_t if t.get("priority") == "p1"]),
            "new_tickets": len(new_tickets),
            "new_email": len(new_email),
            "new_slack": len(new_slack),
            "new_teams": len(new_teams),
            "new_chat": len(new_slack) + len(new_teams),
            "new_calendar": len(new_cal),
            "overdue_actions": len(overdue),
            "unread_threads": len(new_email),
            "refreshed_at": utcnow(),
        }

    def refresh_account_stats(self, account_id: str) -> dict:
        acct = self.store.get("accounts", account_id)
        if not acct:
            raise KeyError(account_id)
        stats = self.account_inbox_stats(account_id)
        acct["stats"] = stats
        self.store.save("accounts", account_id, acct)
        return stats

    def score_account(self, account_id: str) -> dict:
        from csm_dashboard.health.engine import score_account

        return score_account(self, account_id)

    def reset_store(self) -> None:
        settings = self.get_settings()
        creds = list(self.store.query_all("credentials"))
        for name in COLLECTIONS:
            if name in {"settings", "credentials"}:
                continue
            for row in list(self.store.query_all(name)):
                rid = row.get("_id")
                if rid:
                    self.store.purge(name, rid)
        self.store.save("settings", "settings", settings)
        for row in creds:
            rid = row.get("_id")
            if not rid:
                continue
            clean = {k: v for k, v in row.items() if k != "_id"}
            self.store.save("credentials", rid, clean)

    def seed_from_dir(self, seed_dir) -> dict[str, int]:
        from csm_dashboard.seed.load import apply_seed

        return apply_seed(self, seed_dir)

    def expand_account(self, account: dict) -> dict:
        out = dict(account)
        team = out.get("team") or {}
        needed: set[str] = set()
        for row in (team.get("account") or []) + (team.get("ps") or []):
            pid = row.get("person_id")
            if pid:
                needed.add(pid)
        people = {}
        for pid in needed:
            person = self.get_person(pid)
            if person:
                people[pid] = person

        def _expand(rows: list) -> list:
            expanded = []
            for row in rows or []:
                pid = row.get("person_id")
                person = people.get(pid) or {}
                expanded.append({**row, "name": person.get("name") or "", "email": person.get("email") or ""})
            return expanded

        out["team"] = {"account": _expand(team.get("account")), "ps": _expand(team.get("ps"))}
        out["input_counts"] = self.account_input_counts(out.get("account_id") or out.get("_id") or "")
        return out

    def account_input_counts(self, account_id: str) -> dict[str, int]:
        def n(collection: str) -> int:
            return len(self._account_rows(collection, account_id))

        people = self._account_rows("people", account_id)
        return {
            "timeline": n("activities"),
            "tickets": n("tickets"),
            "email": n("threads"),
            "slack": n("slack_messages"),
            "teams": n("teams_messages"),
            "chat": n("slack_messages") + n("teams_messages"),
            "salesforce": n("salesforce_opportunities") + n("salesforce_cases"),
            "calendar": n("calendar_events"),
            "projects": n("projects"),
            "people": len(people),
            "orgchart": sum(1 for p in people if p.get("kind") == "customer"),
            "accountteam": sum(1 for p in people if p.get("kind") in {"account_team", "ps_team"}),
        }

    def operator_profile(self, doc: dict | None = None) -> dict:
        stored = ((doc if doc is not None else self.get_settings()) or {}).get("operator") or {}
        from csm_dashboard.config import load_settings

        cfg = load_settings()
        email = str(stored.get("email") or cfg.operator_email or "").strip()
        home = _norm_timezone(str(stored.get("timezone") or ""))
        zones = _norm_timezone_list(stored.get("timezones"))
        if not zones:
            zones = [home]
        return {
            "name": str(stored.get("name") or cfg.operator_name or "").strip(),
            "phone": str(stored.get("phone") or "").strip(),
            "email": email,
            "timezone": home,
            "timezones": zones,
            "role": str(stored.get("role") or cfg.operator_role or "csm").strip(),
            "domains": _norm_domains(stored.get("domains") or ([email.rsplit("@", 1)[-1]] if "@" in email else [])),
        }

    def operator_domains(self) -> set[str]:
        return set(self.operator_profile().get("domains") or [])

    def _logo_file(self, account_id: str, mime: str | None = None) -> tuple[Path, str] | None:
        stem = _logo_stem(account_id)
        wanted = []
        if mime == "image/jpeg":
            wanted.append(("jpg", "image/jpeg"))
        elif mime == "image/webp":
            wanted.append(("webp", "image/webp"))
        elif mime:
            wanted.append(("png", "image/png"))
        wanted.extend([("png", "image/png"), ("jpg", "image/jpeg"), ("jpeg", "image/jpeg"), ("webp", "image/webp")])
        seen: set[str] = set()
        for ext, kind in wanted:
            if ext in seen:
                continue
            seen.add(ext)
            path = self.logo_dir() / f"{stem}.{ext}"
            if path.is_file():
                return path, kind
        return None

    def account_has_logo(self, account_id: str, doc: dict | None = None) -> bool:
        if account_id in self._logos:
            return True
        mime = str((doc or {}).get("logo_mime") or "") or None
        return self._logo_file(account_id, mime) is not None

    def logo_dir(self) -> Path:
        from csm_dashboard.config import ROOT, load_settings

        try:
            db = Path(load_settings().db_path)
            return db.parent / "logos"
        except Exception:
            return ROOT / "data" / "logos"

    def save_account_logo(self, account_id: str, data_url: str) -> dict:
        doc = self.store.get("accounts", account_id)
        if not doc:
            raise KeyError(account_id)
        blob, mime = decode_logo_data_url(data_url)
        self._logos[account_id] = (blob, mime)
        ext = "jpg" if mime == "image/jpeg" else "webp" if mime == "image/webp" else "png"
        path = self.logo_dir() / f"{_logo_stem(account_id)}.{ext}"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(blob)
        except OSError as exc:
            log.warning("csm.account.logo_disk_failed account_id=%s err=%s", account_id, exc)
        doc["has_logo"] = True
        doc["logo_mime"] = mime
        doc["logo_updated_at"] = utcnow()
        doc["updated_at"] = doc["logo_updated_at"]
        self.store.save("accounts", account_id, doc)
        return _attach(doc, account_id) or doc

    def get_account_logo(self, account_id: str) -> tuple[bytes, str] | None:
        if account_id in self._logos:
            return self._logos[account_id]
        doc = self.store.get("accounts", account_id) or {}
        found = self._logo_file(account_id, str(doc.get("logo_mime") or "") or None)
        if found:
            return found[0].read_bytes(), found[1]
        return None

    def delete_account_logo(self, account_id: str) -> dict:
        doc = self.store.get("accounts", account_id)
        if not doc:
            raise KeyError(account_id)
        self._logos.pop(account_id, None)
        stem = _logo_stem(account_id)
        for ext in ("png", "jpg", "jpeg", "webp"):
            path = self.logo_dir() / f"{stem}.{ext}"
            if path.is_file():
                try:
                    path.unlink()
                except OSError:
                    pass
        doc["has_logo"] = False
        doc["logo_mime"] = ""
        doc["logo_updated_at"] = utcnow()
        doc["updated_at"] = doc["logo_updated_at"]
        self.store.save("accounts", account_id, doc)
        return _attach(doc, account_id) or doc

    def remove_account(self, account_id: str) -> dict:
        doc = self.store.get("accounts", account_id)
        if not doc:
            raise KeyError(account_id)
        doc["removed"] = True
        doc["quiet"] = True
        doc["updated_at"] = utcnow()
        self.store.save("accounts", account_id, doc)
        return _attach(doc, account_id) or doc
