"""Parse #{customer} and @person tokens from desk chat."""

from __future__ import annotations

import re

HASH_RE = re.compile(r"#\{\s*(?:customer\s+)?([^}]+?)\}", re.I)
AT_RE = re.compile(r"@([A-Za-z][A-Za-z0-9._-]*)")


def parse_customer_tokens(message: str) -> list[str]:
    return [m.strip() for m in HASH_RE.findall(message or "") if m.strip()]


def parse_person_handles(message: str) -> list[str]:
    return [m.strip() for m in AT_RE.findall(message or "") if m.strip()]


def resolve_account(repo, message: str, account_id: str | None = None) -> dict | None:
    aid = str(account_id or "").strip()
    if aid and aid not in {"desk", "acct:_desk"}:
        return repo.get_account(aid) or repo.get_account_by_abbr(aid)
    for token in parse_customer_tokens(message):
        hit = _match_account(repo, token)
        if hit:
            return hit
    return None


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
        rows = repo.store.query_all("people")
    hits = []
    for person in rows:
        name = str(person.get("name") or "").lower()
        email = str(person.get("email") or "").lower()
        first = name.split()[0] if name else ""
        local = email.split("@", 1)[0] if email else ""
        if needle == first or needle in name.split() or needle in local or needle in name:
            hits.append(person)
    return hits
