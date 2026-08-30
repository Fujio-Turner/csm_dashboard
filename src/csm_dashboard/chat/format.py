"""Turn model/tool JSON into a short operator-facing chat reply."""

from __future__ import annotations

import json
import re
from typing import Any

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.I)


def humanize_chat_text(text: str) -> str:
    raw = (text or "").strip()
    if not raw:
        return ""
    data = _parse_json(raw)
    if data is None:
        return text
    prose = _json_to_prose(data)
    return prose or text


def _parse_json(raw: str) -> Any:
    blob = _FENCE.sub("", raw).strip()
    try:
        return json.loads(blob)
    except json.JSONDecodeError:
        pass
    for start_ch, end_ch in (("[", "]"), ("{", "}")):
        start = blob.find(start_ch)
        end = blob.rfind(end_ch)
        if start >= 0 and end > start:
            try:
                return json.loads(blob[start : end + 1])
            except json.JSONDecodeError:
                continue
    return None


def _json_to_prose(data: Any) -> str:
    if isinstance(data, list):
        if not data:
            return "Nothing to show."
        if all(isinstance(row, dict) for row in data):
            if any(row.get("key") for row in data):
                return _tickets_prose(data)
            if any(row.get("subject") or row.get("from_addr") for row in data):
                return _mail_prose(data)
            if any(row.get("title") or row.get("due_on") or row.get("due_at") for row in data):
                return _actions_prose(data)
            return "\n".join("- " + _dict_line(row) for row in data[:12])
        return "\n".join(f"- {item}" for item in data[:12])
    if isinstance(data, dict):
        if data.get("error"):
            return str(data.get("error"))
        if data.get("ok") is True and len(data) <= 2:
            return "Done."
        if data.get("key"):
            return _tickets_prose([data])
        return _dict_line(data)
    return str(data)


def _pri(row: dict) -> str:
    raw = str(row.get("priority") or "").strip()
    if raw.lower().startswith("p") and raw[1:].isdigit():
        return raw.upper()
    return raw or "—"


def _status(row: dict) -> str:
    return str(row.get("status") or "").replace("_", " ") or "—"


def _tickets_prose(rows: list[dict]) -> str:
    open_rows = [r for r in rows if str(r.get("status") or "") not in {"done", "cancelled"}]
    closed = [r for r in rows if r not in open_rows]
    lines = []
    if open_rows:
        lines.append(f"{len(open_rows)} open ticket" + ("s" if len(open_rows) != 1 else "") + ":")
        for row in open_rows[:12]:
            lines.append(
                f"- {row.get('key') or '—'}: {row.get('summary') or row.get('title') or '—'} "
                f"({_pri(row)} · {_status(row)})"
            )
    if closed:
        lines.append("Recently closed:")
        for row in closed[:4]:
            lines.append(f"- {row.get('key')}: {row.get('summary') or '—'} ({_status(row)})")
    return "\n".join(lines) if lines else "No tickets."


def _mail_prose(rows: list[dict]) -> str:
    lines = [f"{len(rows)} recent mail:"]
    for row in rows[:8]:
        who = row.get("from_addr") or ",".join(row.get("to_addrs") or []) or "—"
        lines.append(f"- {row.get('subject') or '—'} · {who} · {row.get('sent_at') or ''}".strip(" ·"))
    return "\n".join(lines)


def _actions_prose(rows: list[dict]) -> str:
    lines = [f"{len(rows)} open follow-up" + ("s" if len(rows) != 1 else "") + ":"]
    for row in rows[:10]:
        due = row.get("due_on") or row.get("due_at") or "no due date"
        lines.append(f"- {row.get('title') or row.get('task_name') or '—'} (due {due})")
    return "\n".join(lines)


def _dict_line(row: dict) -> str:
    bits = []
    for key in ("key", "name", "title", "summary", "subject", "status", "priority", "stage"):
        val = row.get(key)
        if val not in (None, ""):
            bits.append(str(val))
    return " · ".join(bits) if bits else json.dumps(row, ensure_ascii=False)
