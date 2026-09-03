from __future__ import annotations

import json
from dataclasses import dataclass

from csm_dashboard.compose.redact import redact
from csm_dashboard.config import load_settings
from csm_dashboard.prompts import operator_identity

REPLY_MAX_CHARS = 8000
KEY_ROLES = {"champion", "ae", "csm", "tam", "ps_lead", "exec_sponsor"}


@dataclass
class ComposeContext:
    account_id: str
    payload: dict
    truncated: bool = False
    text: str = ""
    mode: str = "full"

    def serialized(self) -> str:
        return self.text or json.dumps(self.payload, default=str)


def _msg_slice(email: dict, *, n: int = 160) -> dict:
    snippet = str(email.get("snippet") or "").strip()
    if snippet:
        body = snippet[:n]
    else:
        body = str(email.get("body_text") or "")[: max(n, 500)]
    return {
        "from_addr": email.get("from_addr") or "",
        "sent_at": email.get("sent_at") or "",
        "text": body,
    }


def _health_slim(health) -> dict:
    if not isinstance(health, dict):
        return {}
    return {k: health[k] for k in ("score", "status") if k in health}


def _account_slim(acct: dict, *, reply: bool) -> dict:
    slim = {
        "name": acct.get("name"),
        "abbr": acct.get("abbr"),
        "health": _health_slim(acct.get("health") or {}),
    }
    if reply:
        return slim
    contract = acct.get("contract") if isinstance(acct.get("contract"), dict) else {}
    slim["contract"] = {
        k: contract[k] for k in ("renewal_on", "arr", "plan", "status") if k in contract
    }
    return slim


def _operator_payload(operator: dict | None) -> dict:
    ident = operator_identity(operator)
    return {"name": ident["name"], "email": ident["email"], "role": ident["role"]}


def build_compose_context(
    repo,
    account_id: str,
    *,
    thread_id: str | None = None,
    ticket_ids: list[str] | None = None,
    slack_refs: list[str] | None = None,
    calendar_days: int = 14,
    max_chars: int | None = None,
    inbound: dict | None = None,
    operator: dict | None = None,
    mode: str = "full",
) -> ComposeContext:
    settings = load_settings()
    reply = str(mode or "full") == "reply"
    if max_chars is None:
        budget = REPLY_MAX_CHARS if reply else int(settings.max_context_chars)
    else:
        budget = int(max_chars)
    acct = repo.get_account(account_id) or {}
    slim = _account_slim(acct, reply=reply)

    ticket_limit = 3 if reply else 5
    tickets = []
    if ticket_ids:
        for tid in ticket_ids:
            t = repo.get_ticket(tid)
            if t:
                tickets.append(t)
    else:
        tickets, _ = repo.page_tickets(account_id, limit=ticket_limit)
        tickets = [t for t in tickets if t.get("status") not in {"done", "cancelled"}][:ticket_limit]
    ticket_slice = []
    comment_n = 0 if reply else 3
    comment_chars = 200 if reply else 500
    for t in tickets:
        comments = []
        for c in (t.get("comments") or [])[-comment_n:]:
            comments.append(
                {"at": c.get("at"), "author": c.get("author"), "text": str(c.get("text") or "")[:comment_chars]}
            )
        row = {
            "key": t.get("key"),
            "summary": t.get("summary"),
            "status": t.get("status"),
            "priority": t.get("priority"),
            "updated_at": t.get("updated_at"),
        }
        if comments:
            row["comments"] = comments
        ticket_slice.append(row)

    tail_n = min(int(settings.thread_tail or 8), 8 if reply else int(settings.thread_tail or 8))
    email_limit = tail_n if reply else 40
    emails, _ = repo.page_emails(
        account_id, thread_id=thread_id, limit=email_limit, slim=True, desc=True
    )
    emails.sort(key=lambda r: str(r.get("sent_at") or ""))
    older = [] if reply else (emails[:-tail_n] if len(emails) > tail_n else [])
    recent = emails[-tail_n:]
    thread_recent = [_msg_slice(e) for e in recent]
    thread_summary = [
        {
            "from_addr": e.get("from_addr"),
            "sent_at": e.get("sent_at"),
            "text": str(e.get("snippet") or e.get("body_text") or "")[:160],
        }
        for e in older
    ]

    slack_slice: list[dict] = []
    teams_slice: list[dict] = []
    cal_slice: list[dict] = []
    if not reply:
        slack_rows = []
        if slack_refs:
            for ref in slack_refs:
                row = repo.store.get("slack_messages", ref)
                if row:
                    slack_rows.append(row)
        else:
            slack_rows, _ = repo.page_slack(account_id, limit=settings.slack_tail, slim=True)
        slack_slice = [
            {"ts": r.get("ts"), "user_name": r.get("user_name"), "text": str(r.get("text") or "")[:500]}
            for r in slack_rows[-settings.slack_tail :]
        ]
        teams_tail = int(getattr(settings, "teams_tail", None) or settings.slack_tail)
        teams_rows, _ = repo.page_teams(account_id, limit=teams_tail, slim=True)
        teams_slice = [
            {"ts": r.get("ts"), "user_name": r.get("user_name"), "text": str(r.get("text") or "")[:500]}
            for r in teams_rows[-teams_tail :]
        ]
        cal = repo.page_calendar(account_id, limit=20, slim=True)
        cal_slice = [
            {
                "title": e.get("title"),
                "start_at": e.get("start_at"),
                "attendees": [a.get("email") for a in (e.get("attendees") or [])],
            }
            for e in cal
        ]
    elif slack_refs:
        slack_rows = []
        for ref in slack_refs:
            row = repo.store.get("slack_messages", ref)
            if row:
                slack_rows.append(row)
        slack_slice = [
            {"ts": r.get("ts"), "user_name": r.get("user_name"), "text": str(r.get("text") or "")[:200]}
            for r in slack_rows[-8:]
        ]

    actions = [
        {"title": a.get("title"), "due_on": a.get("due_on"), "status": a.get("status")}
        for a in repo.page_actions(account_id=account_id, status="open")
    ]
    if reply:
        actions = actions[:5]
    people = [
        {"name": p.get("name"), "role": p.get("role"), "email": p.get("email")}
        for p in repo.list_people(account_id)
        if p.get("role") in KEY_ROLES
    ]

    payload: dict = {
        "account": slim,
        "operator": _operator_payload(operator),
        "tickets": ticket_slice,
        "thread": thread_recent,
        "thread_summary": thread_summary,
        "slack": slack_slice,
        "teams": teams_slice,
        "calendar": cal_slice,
        "actions": actions,
        "people": people,
    }
    if inbound:
        payload["inbound"] = {
            "from_addr": inbound.get("from_addr") or "",
            "from_name": inbound.get("from_name") or "",
            "to_addrs": inbound.get("to_addrs") or [],
            "cc_addrs": inbound.get("cc_addrs") or [],
            "subject": inbound.get("subject") or "",
            "sent_at": inbound.get("sent_at") or "",
            "text": str(inbound.get("body_text") or inbound.get("snippet") or "")[:1500],
        }
    truncated = False
    text = redact(json.dumps(payload, default=str))
    drop_order = ["teams", "slack", "thread_summary", "calendar", "tickets"]
    while len(text) > budget and drop_order:
        key = drop_order.pop(0)
        if key == "tickets" and len(payload["tickets"]) > 1:
            payload["tickets"] = payload["tickets"][:1]
        elif key == "calendar" and payload["calendar"]:
            payload["calendar"] = payload["calendar"][:2]
        else:
            payload[key] = []
        truncated = True
        text = redact(json.dumps(payload, default=str))
    if len(text) > budget:
        for item in payload.get("thread") or []:
            item["text"] = str(item.get("text") or "")[:160]
        truncated = True
        text = redact(json.dumps(payload, default=str))
    return ComposeContext(
        account_id=account_id,
        payload=payload,
        truncated=truncated,
        text=text[:budget],
        mode="reply" if reply else "full",
    )
