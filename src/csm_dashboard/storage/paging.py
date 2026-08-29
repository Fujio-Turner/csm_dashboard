"""Account-scoped paging filters shared by MemoryStore and CBLStore."""

from __future__ import annotations

import re
from typing import Any

_PATH = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$")
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_ORDER = {
    "sent_at",
    "updated_at",
    "last_at",
    "ts",
    "start_at",
    "at",
    "close_on",
    "due_on",
    "name",
    "key",
}
_COLLECTIONS = {
    "accounts",
    "people",
    "projects",
    "tickets",
    "emails",
    "threads",
    "slack_channels",
    "slack_messages",
    "teams_channels",
    "teams_messages",
    "salesforce_opportunities",
    "salesforce_cases",
    "calendar_events",
    "action_items",
    "drafts",
    "reports",
    "chats",
    "sync_jobs",
    "activities",
    "notes",
}


def safe_collection(name: str) -> str:
    if name not in _COLLECTIONS:
        raise ValueError("bad_collection")
    return name


def safe_path(path: str) -> str:
    raw = str(path or "")
    if not _PATH.match(raw):
        raise ValueError("bad_path")
    return raw


def safe_order(field: str, default: str = "updated_at") -> str:
    raw = str(field or default)
    if raw not in _ORDER:
        return default if default in _ORDER else "updated_at"
    return raw


def dot_get(row: dict, path: str) -> Any:
    cur: Any = row
    for part in str(path).split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _as_bool(value: Any) -> bool:
    return value is True or value == 1 or str(value).lower() == "true"


def row_matches(row: dict, filters: dict | None) -> bool:
    if not filters:
        return True
    for path, want in (filters.get("eq") or {}).items():
        if dot_get(row, path) != want:
            return False
    for path, want in (filters.get("neq") or {}).items():
        if dot_get(row, path) == want:
            return False
    for path, want in (filters.get("gte") or {}).items():
        if str(dot_get(row, path) or "") < str(want):
            return False
    for path, want in (filters.get("lte") or {}).items():
        if str(dot_get(row, path) or "") > str(want):
            return False
    for path, want in (filters.get("lt") or {}).items():
        if str(dot_get(row, path) or "") >= str(want):
            return False
    for path, values in (filters.get("in") or {}).items():
        if dot_get(row, path) not in list(values):
            return False
    for path in filters.get("truthy") or []:
        if not _as_bool(dot_get(row, path)):
            return False
    for path in filters.get("not_true") or []:
        if _as_bool(dot_get(row, path)):
            return False
    groups = filters.get("or_truthy") or []
    for group in groups:
        if not any(_as_bool(dot_get(row, path)) for path in group):
            return False
    return True


def sort_rows(rows: list[dict], order: str, *, desc: bool) -> list[dict]:
    field = safe_order(order)
    rows.sort(key=lambda r: str(r.get(field) or ""), reverse=desc)
    return rows


def omit_fields(row: dict, keys: tuple[str, ...] | list[str] | None) -> dict:
    if not keys:
        return row
    drop = set(keys)
    return {k: v for k, v in row.items() if k not in drop}


def sql_string_list(values: list) -> str:
    out: list[str] = []
    for item in values:
        raw = str(item)
        if not re.match(r"^[A-Za-z0-9_.:-]+$", raw):
            continue
        out.append("'" + raw.replace("'", "") + "'")
    if not out:
        return "('')"
    return "(" + ",".join(out) + ")"


def compile_filters(filters: dict | None, params: dict) -> list[str]:
    """Append SQL fragments; mutates params with unique keys."""
    clauses: list[str] = []
    if not filters:
        return clauses
    n = 0

    def pname() -> str:
        nonlocal n
        n += 1
        return f"f{n}"

    for path, want in (filters.get("eq") or {}).items():
        key = pname()
        clauses.append(f"{safe_path(path)} = ${key}")
        params[key] = want
    for path, want in (filters.get("neq") or {}).items():
        key = pname()
        clauses.append(f"({safe_path(path)} IS MISSING OR {safe_path(path)} != ${key})")
        params[key] = want
    for path, want in (filters.get("gte") or {}).items():
        key = pname()
        clauses.append(f"{safe_path(path)} >= ${key}")
        params[key] = want
    for path, want in (filters.get("lte") or {}).items():
        key = pname()
        clauses.append(f"{safe_path(path)} <= ${key}")
        params[key] = want
    for path, want in (filters.get("lt") or {}).items():
        key = pname()
        clauses.append(f"{safe_path(path)} < ${key}")
        params[key] = want
    for path, values in (filters.get("in") or {}).items():
        clauses.append(f"{safe_path(path)} IN {sql_string_list(list(values))}")
    for path in filters.get("truthy") or []:
        clauses.append(f"{safe_path(path)} = true")
    for path in filters.get("not_true") or []:
        p = safe_path(path)
        clauses.append(f"({p} IS MISSING OR {p} = false)")
    for group in filters.get("or_truthy") or []:
        parts = [f"{safe_path(path)} = true" for path in group]
        if parts:
            clauses.append("(" + " OR ".join(parts) + ")")
    return clauses


def sql_select_list(fields: tuple[str, ...] | list[str] | None) -> str:
    if not fields:
        return "META().id AS _id, *"
    cols = ["META().id AS _id"]
    for name in fields:
        if not _IDENT.match(str(name)):
            continue
        cols.append(str(name))
    return ", ".join(cols)


def count_from_row(row: dict | None) -> int:
    if not row:
        return 0
    for key in ("n", "count", "$1"):
        if key in row and row[key] is not None:
            try:
                return int(row[key])
            except (TypeError, ValueError):
                continue
    for value in row.values():
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return int(value)
    return 0
