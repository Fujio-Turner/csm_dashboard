from __future__ import annotations

import json
from dataclasses import dataclass, field

from csm_dashboard.compose.redact import redact
from csm_dashboard.config import load_settings


@dataclass
class ComposeContext:
    account_id: str
    payload: dict
    truncated: bool = False
    text: str = ""

    def serialized(self) -> str:
        return self.text or json.dumps(self.payload, default=str)


def _msg_slice(email: dict) -> dict:
    snippet = str(email.get("snippet") or "").strip()
    if snippet:
        body = snippet[:160]
    else:
        body = str(email.get("body_text") or "")[:500]
    return {
        "from_addr": email.get("from_addr") or "",
        "sent_at": email.get("sent_at") or "",
        "text": body,
    }


def build_compose_context(
    repo,
    account_id: str,
    *,
    thread_id: str | None = None,
    ticket_ids: list[str] | None = None,
    slack_refs: list[str] | None = None,
    calendar_days: int = 14,
    max_chars: int | None = None,
) -> ComposeContext:
    settings = load_settings()
    budget = int(max_chars or settings.max_context_chars)
    acct = repo.get_account(account_id) or {}
    slim = {
        "name": acct.get("name"),
        "abbr": acct.get("abbr"),
        "health": acct.get("health"),
        "contract": acct.get("contract"),
        "team": acct.get("team"),
    }

    tickets = []
    if ticket_ids:
        for tid in ticket_ids:
            t = repo.get_ticket(tid)
            if t:
                tickets.append(t)
    else:
        tickets, _ = repo.page_tickets(account_id, limit=5)
        tickets = [t for t in tickets if t.get("status") not in {"done", "cancelled"}][:5]
    ticket_slice = []
    for t in tickets:
        comments = []
        for c in (t.get("comments") or [])[-3:]:
            comments.append({"at": c.get("at"), "author": c.get("author"), "text": str(c.get("text") or "")[:500]})
        ticket_slice.append(
            {
                "key": t.get("key"),
                "summary": t.get("summary"),
                "status": t.get("status"),
                "priority": t.get("priority"),
                "updated_at": t.get("updated_at"),
                "comments": comments,
            }
        )

    emails, _ = repo.page_emails(account_id, thread_id=thread_id, limit=40, slim=True)
    emails.sort(key=lambda r: str(r.get("sent_at") or ""))
    tail_n = settings.thread_tail
    older = emails[:-tail_n] if len(emails) > tail_n else []
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
    actions = [
        {"title": a.get("title"), "due_on": a.get("due_on"), "status": a.get("status")}
        for a in repo.page_actions(account_id=account_id, status="open")
    ]
    people = [
        {"name": p.get("name"), "role": p.get("role"), "email": p.get("email")}
        for p in repo.list_people(account_id)
        if p.get("role") in {"champion", "ae", "csm", "tam", "ps_lead", "exec_sponsor"}
    ]

    payload: dict = {
        "account": slim,
        "tickets": ticket_slice,
        "thread": thread_recent,
        "thread_summary": thread_summary,
        "slack": slack_slice,
        "teams": teams_slice,
        "calendar": cal_slice,
        "actions": actions,
        "people": people,
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
    return ComposeContext(account_id=account_id, payload=payload, truncated=truncated, text=text[:budget])
