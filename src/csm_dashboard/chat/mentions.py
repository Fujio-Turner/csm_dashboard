"""Parse #customer and @person tokens from desk chat."""

from __future__ import annotations

import re

# Legacy braces: #{ACME}  #{ customer Northwind }
HASH_BRACE_RE = re.compile(r"#\{\s*(?:customer\s+)?([^}]+?)\}", re.I)
# Bare #ACME — letter-first so #333 drops out. Skip desk routes (#account/…).
# Do not swallow ticket keys (#ACME-12).
HASH_BARE_RE = re.compile(
    r"(?<![A-Za-z0-9])#(?!\{)"
    r"(?!(?:account|compose|help|home|settings|actions|reports)(?:/|\b))"
    r"([A-Za-z][A-Za-z0-9_]{1,31})"
    r"(?!-\d)(?![A-Za-z0-9_])",
    re.I,
)
AT_RE = re.compile(r"(?<![A-Za-z0-9._])@([A-Za-z][A-Za-z0-9._-]*)")
SLASH_CMDS = (
    "people",
    "ticket",
    "project",
    "email",
    "chat",
    "slack",
    "teams",
    "calendar",
    "sf",
    "note",
)
SLASH_BOUND_RE = re.compile(
    r"(?<![A-Za-z0-9])/(" + "|".join(SLASH_CMDS) + r")(?:\s+([^\s/?#]+))?",
    re.I,
)
_HEX_TOKEN = re.compile(r"^(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{4}|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})$")
_RESERVED = frozenset(
    {"account", "compose", "help", "home", "settings", "actions", "reports"}
)

# Back-compat alias used by older imports/tests.
HASH_RE = HASH_BRACE_RE


def parse_customer_tokens(message: str) -> list[str]:
    text = message or ""
    found: list[str] = []
    seen: set[str] = set()

    def add(raw: str) -> None:
        token = (raw or "").strip()
        if not token:
            return
        if _HEX_TOKEN.match(token):
            return
        if token.lower() in _RESERVED:
            return
        key = token.lower()
        if key in seen:
            return
        seen.add(key)
        found.append(token)

    for m in HASH_BRACE_RE.findall(text):
        add(m)
    stripped = HASH_BRACE_RE.sub(" ", text)
    for m in HASH_BARE_RE.findall(stripped):
        add(m)
    return found


def parse_slash_bounds(message: str) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for cmd, rest in SLASH_BOUND_RE.findall(message or ""):
        key = cmd.lower()
        val = (rest or "").strip().strip(".,;:!?)]}\"")
        if not val:
            continue
        bucket = found.setdefault(key, [])
        if val not in bucket:
            bucket.append(val)
    return found


def parse_person_handles(message: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()

    def add(raw: str) -> None:
        handle = (raw or "").strip().lstrip("@")
        if not handle:
            return
        key = handle.lower()
        if key in seen:
            return
        seen.add(key)
        found.append(handle)

    for m in AT_RE.findall(message or ""):
        add(m)
    for handle in parse_slash_bounds(message).get("people") or []:
        add(handle)
    return found


def resolve_account(repo, message: str, account_id: str | None = None) -> dict | None:
    aid = str(account_id or "").strip()
    if aid and aid not in {"desk", "acct:_desk"}:
        return repo.get_account(aid) or repo.get_account_by_abbr(aid)
    for token in parse_customer_tokens(message):
        hit = _match_account(repo, token)
        if hit:
            return hit
    return _account_from_unique_person(repo, message)


def _account_from_unique_person(repo, message: str) -> dict | None:
    handles = parse_person_handles(message)
    if len(handles) != 1:
        return None
    people = find_people(repo, handles[0], None)
    ids: list[str] = []
    for person in people:
        pid = str(person.get("account_id") or "")
        if pid and pid not in ids:
            ids.append(pid)
    if len(ids) != 1:
        return None
    return repo.get_account(ids[0])


def _match_account(repo, token: str) -> dict | None:
    raw = (token or "").strip()
    if not raw:
        return None
    by_abbr = repo.get_account_by_abbr(raw)
    if by_abbr:
        return by_abbr
    slug = re.sub(r"[^a-z0-9]+", "-", raw.lower()).strip("-")
    by_id = repo.get_account(f"acct:{slug}")
    if by_id:
        return by_id
    needle = raw.lower()
    for acct in repo.list_accounts():
        name = str(acct.get("name") or "").lower()
        abbr = str(acct.get("abbr") or "").lower()
        slug_v = str(acct.get("slug") or "").lower()
        if needle in name or needle == abbr or needle == slug_v:
            return acct
    return None


def find_people(repo, handle: str, account_id: str | None = None) -> list[dict]:
    needle = (handle or "").lower().lstrip("@")
    if not needle:
        return []
    if account_id:
        rows = repo.list_people(account_id)
    else:
        rows = repo.list_people(None)
    hits = []
    for person in rows:
        name = str(person.get("name") or "").lower()
        email = str(person.get("email") or "").lower()
        first = name.split()[0] if name else ""
        local = email.split("@", 1)[0] if email else ""
        if needle == first or needle in name.split() or needle in local or needle in name:
            hits.append(person)
    return hits
