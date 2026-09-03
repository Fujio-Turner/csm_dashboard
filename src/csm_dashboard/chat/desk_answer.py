"""Local desk-chat answers so Home works without an xAI key."""

from __future__ import annotations

from datetime import datetime, timedelta

from csm_dashboard.chat.mentions import find_people, parse_person_handles, parse_slash_bounds, resolve_account
from csm_dashboard.storage.repo import utcnow


def answer_desk(repo, message: str, account: dict | None) -> str:
    text = (message or "").strip()
    low = text.lower()
    handles = parse_person_handles(text)
    bounds = parse_slash_bounds(text)
    ticket_tokens = bounds.get("ticket") or []

    if _is_tasks_question(low) and not account:
        return _tasks_due(repo, None, low)

    if _is_desk_wide(low) and not account:
        return _desk_wide(repo, low)

    if not account:
        books = repo.list_accounts()
        if not books:
            return "No accounts loaded. Open Settings and load seed data, then ask again with #ACME."
        names = ", ".join("#" + str(b.get("abbr") or "?") for b in books[:8])
        return (
            "Which book? Tag a customer like #ACME or #Northwind. "
            f"On the desk now: {names}. "
            "Or ask across every book: “What tasks are due this week?”"
        )

    abbr = account.get("abbr") or "?"
    name = account.get("name") or abbr
    aid = account.get("account_id") or account.get("_id") or ""

    if handles and ticket_tokens:
        return _person_ticket(repo, aid, abbr, handles[0], ticket_tokens[0])
    if ticket_tokens:
        return _one_ticket(repo, aid, abbr, ticket_tokens[0])

    if handles and any(k in low for k in ("reply", "replied", "email", "mail", "inbox", "response")):
        return _email_reply(repo, aid, abbr, handles[0])

    if any(k in low for k in ("issue", "ticket", "p1", "outage", "problem", "incident", "fire")):
        return _issues(repo, account, aid, abbr, name)

    if any(k in low for k in ("team", "slack", "teams")):
        return _streams(repo, aid, abbr)

    if any(k in low for k in ("salesforce", "sfdc", "opportunity", "renewal", "case")):
        return _salesforce(repo, aid, abbr)

    if _is_tasks_question(low) or _is_desk_wide(low):
        return _tasks_due(repo, account, low)
    return _status(repo, account, aid, abbr, name)


def _is_tasks_question(low: str) -> bool:
    if "task" not in low:
        return False
    return any(
        n in low
        for n in (
            "due",
            "today",
            "this week",
            "need to",
            "to do",
            "be done",
            "been done",
            "overdue",
            "what tasks",
            "which tasks",
            "any tasks",
            "my tasks",
        )
    )


def _is_desk_wide(low: str) -> bool:
    needles = (
        "opening next",
        "free next",
        "all accounts",
        "across accounts",
        "every book",
    )
    return any(n in low for n in needles)


def _week_end(day: str) -> str:
    start = datetime.fromisoformat(day + "T00:00:00+00:00")
    return (start + timedelta(days=6)).date().isoformat()


def _tasks_due(repo, account: dict | None, low: str = "") -> str:
    day = utcnow()[:10]
    today_only = "today" in low and "week" not in low
    end = day if today_only else _week_end(day)
    label = "today" if today_only else "this week"
    books = [account] if account else repo.list_accounts()
    lines = []
    for acct in books:
        aid = acct.get("account_id") or acct.get("_id") or ""
        abbr = acct.get("abbr") or "?"
        items, _ = repo.page_emails(aid, tasks=True, limit=80, slim=True, desc=True)
        due = []
        for row in items:
            op = row.get("operator") or {}
            if not op.get("task"):
                continue
            due_at = str(op.get("due_at") or "")[:10]
            if due_at and due_at <= end:
                due.append((due_at, op.get("task_name") or row.get("subject") or "Task", abbr))
        due.sort()
        for due_at, name, tag in due[:8]:
            stamp = "overdue" if due_at < day else ("today" if due_at == day else due_at)
            lines.append(f"- #{tag} {name} ({stamp})")
    if not lines:
        scope = (account or {}).get("abbr") if account else "every book"
        return f"No tasks due {label} on {scope}. Tag a book like #ACME to narrow, or leave it off for all books."
    if account:
        head = f"Tasks due {label} on #{account.get('abbr')}:"
    else:
        head = f"Tasks due {label} (every book):"
    return head + "\n" + "\n".join(lines[:12])


def _desk_wide(repo, low: str) -> str:
    if _is_tasks_question(low):
        return _tasks_due(repo, None, low)
    if "opening" in low or "free next" in low or "meeting" in low:
        return (
            "Desk-wide meeting fit: open the book (#ACME) and World clock, "
            "or tag the project like ACME:SSO hardening. "
            "I will not send an invite — I can only suggest a window."
        )
    return _tasks_due(repo, None, low)


def _resolve_ticket(repo, account_id: str, token: str) -> dict | None:
    raw = (token or "").strip()
    if not raw:
        return None
    rows, _ = repo.page_tickets(account_id, limit=80)
    needle = raw.lower()
    exact = None
    suffix = None
    for row in rows:
        key = str(row.get("key") or "")
        ext = str(row.get("external_id") or "")
        low = key.lower()
        if low == needle or ext.lower() == needle:
            exact = row
            break
        if needle.isdigit() and (low.endswith("-" + needle) or ext == raw):
            suffix = suffix or row
    hit = exact or suffix
    if not hit:
        return None
    full = repo.get_ticket(hit.get("_id") or "")
    return full or hit


def _one_ticket(repo, aid: str, abbr: str, token: str) -> str:
    ticket = _resolve_ticket(repo, aid, token)
    if not ticket:
        return f"No ticket matching /ticket {token} on #{abbr}."
    key = ticket.get("key") or token
    lines = [
        f"{key} on #{abbr}: {ticket.get('summary')} "
        f"({ticket.get('priority')} · {ticket.get('status')})."
    ]
    comments = ticket.get("comments") or []
    if comments:
        last = comments[-1]
        lines.append(
            f"Last comment {last.get('at')}: {last.get('author')} — {(last.get('text') or '')[:160]}"
        )
    return "\n".join(lines)


def _person_ticket(repo, aid: str, abbr: str, handle: str, token: str) -> str:
    people = find_people(repo, handle, aid) or find_people(repo, handle, None)
    if not people:
        return f"No person matching /people {handle} on #{abbr}."
    person = people[0]
    email = str(person.get("email") or "").lower()
    pname = person.get("name") or handle
    ticket = _resolve_ticket(repo, aid, token)
    if not ticket:
        return f"No ticket matching /ticket {token} on #{abbr}."
    key = str(ticket.get("key") or token)
    key_l = key.lower()
    bits: list[str] = []
    for row in ticket.get("comments") or []:
        author = str(row.get("author") or "").lower()
        if (email and email in author) or handle.lower() in author:
            bits.append(
                f"Ticket comment {row.get('at')}: {(row.get('text') or '')[:180]}"
            )
    emails, _ = repo.page_emails(aid, limit=50, slim=True, desc=True)
    for row in emails:
        blob = " ".join(
            [
                str(row.get("subject") or ""),
                str(row.get("snippet") or ""),
                str(row.get("from_addr") or ""),
            ]
        ).lower()
        if key_l not in blob:
            continue
        from_addr = str(row.get("from_addr") or "").lower()
        addrs = [a.lower() for a in (row.get("to_addrs") or []) + (row.get("cc_addrs") or [])]
        if email and (from_addr == email or email in addrs):
            who = "from" if from_addr == email else "on"
            bits.append(
                f"Mail {who} {pname} {row.get('sent_at')}: {row.get('subject')} — "
                f"{(row.get('snippet') or '')[:140]}"
            )
    for kind, page in (("Slack", repo.page_slack), ("Teams", repo.page_teams)):
        rows, _ = page(aid, limit=40, slim=True)
        for row in rows:
            user = str(row.get("user_name") or row.get("user") or "").lower()
            text = str(row.get("text") or "")
            if key_l not in text.lower():
                continue
            if handle.lower() in user or (email and email.split("@")[0] in user):
                bits.append(f"{kind} {row.get('ts') or row.get('at') or ''}: {text[:160]}")
    if not bits:
        return (
            f"No mail, Slack, Teams, or ticket comment from {pname} on {key} (#{abbr}). "
            f"{key}: {ticket.get('summary')} ({ticket.get('status')})."
        )
    head = f"{pname} on {key} (#{abbr}):"
    return head + "\n" + "\n".join(f"- {b}" for b in bits[:8])


def _issues(repo, account: dict, aid: str, abbr: str, name: str) -> str:
    tickets, _ = repo.page_tickets(aid, limit=40)
    open_t = [t for t in tickets if t.get("status") not in {"done", "cancelled"}]
    p1 = [t for t in open_t if t.get("priority") == "p1"]
    health = account.get("health") or {}
    lines = [
        f"{name} (#{abbr}) health {health.get('score')} {health.get('status')}."
    ]
    if not open_t:
        lines.append("No open tickets.")
        return " ".join(lines)
    lines.append(f"{len(open_t)} open tickets ({len(p1)} P1).")
    for t in (p1 + [x for x in open_t if x not in p1])[:6]:
        lines.append(f"- {t.get('key')}: {t.get('summary')} ({t.get('priority')} · {t.get('status')})")
    overdue = repo.page_actions(account_id=aid, due="overdue")
    if overdue:
        lines.append(f"{len(overdue)} overdue actions, next: {overdue[0].get('title')}.")
    return "\n".join(lines)


def _email_reply(repo, aid: str, abbr: str, handle: str) -> str:
    people = find_people(repo, handle, aid) or find_people(repo, handle, None)
    if not people:
        return f"No person matching @{handle} on #{abbr} (or any book)."
    person = people[0]
    email = str(person.get("email") or "").lower()
    pname = person.get("name") or handle
    if person.get("account_id") and person.get("account_id") != aid:
        return f"@{handle} ({pname}) is on {person.get('account_id')}, not #{abbr}."
    emails, _ = repo.page_emails(aid, limit=40, slim=True, desc=True)
    outbound = [
        e
        for e in emails
        if e.get("direction") == "outbound"
        and email
        and email in [a.lower() for a in (e.get("to_addrs") or []) + (e.get("cc_addrs") or [])]
    ]
    inbound = [
        e
        for e in emails
        if e.get("direction") == "inbound" and email and str(e.get("from_addr") or "").lower() == email
    ]
    outbound.sort(key=lambda e: str(e.get("sent_at") or ""))
    inbound.sort(key=lambda e: str(e.get("sent_at") or ""))
    if not outbound:
        if inbound:
            last_in = inbound[-1]
            return (
                f"You have not emailed {pname} ({email}) on #{abbr}. "
                f"Their last inbound was {last_in.get('sent_at')} — {last_in.get('subject')}."
            )
        return f"No mail with {pname} ({email}) on #{abbr}."
    last_out = outbound[-1]
    later = [e for e in inbound if str(e.get("sent_at") or "") > str(last_out.get("sent_at") or "")]
    if later:
        last_in = later[-1]
        return (
            f"Yes. {pname} replied after your last mail on #{abbr}. "
            f"You sent {last_out.get('sent_at')} ({last_out.get('subject')}). "
            f"They replied {last_in.get('sent_at')} — {last_in.get('snippet') or last_in.get('subject')}."
        )
    last_in = inbound[-1] if inbound else None
    extra = f" Last inbound from them: {last_in.get('sent_at')}." if last_in else ""
    return (
        f"No. {pname} has not replied since your last outbound on #{abbr} "
        f"({last_out.get('sent_at')} — {last_out.get('subject')}).{extra}"
    )


def _streams(repo, aid: str, abbr: str) -> str:
    slack, _ = repo.page_slack(aid, limit=5, slim=True)
    teams, _ = repo.page_teams(aid, limit=5, slim=True)
    bits = [f"Recent streams on #{abbr}:"]
    if slack:
        bits.append("Slack: " + "; ".join(f"{s.get('user_name')}: {(s.get('text') or '')[:80]}" for s in slack[-3:]))
    if teams:
        bits.append("Teams: " + "; ".join(f"{s.get('user_name')}: {(s.get('text') or '')[:80]}" for s in teams[-3:]))
    if len(bits) == 1:
        return f"No Slack or Teams messages stored for #{abbr}."
    return "\n".join(bits)


def _salesforce(repo, aid: str, abbr: str) -> str:
    opps = repo.page_salesforce_opportunities(aid)
    cases = repo.page_salesforce_cases(aid)
    bits = [f"Salesforce on #{abbr}:"]
    if opps:
        bits.append(
            "Opportunities: "
            + "; ".join(f"{o.get('name')} ({o.get('stage')}, {o.get('amount')})" for o in opps[:4])
        )
    if cases:
        bits.append(
            "Cases: "
            + "; ".join(f"{c.get('case_number')} {c.get('subject')} ({c.get('status')})" for c in cases[:4])
        )
    if len(bits) == 1:
        return f"No Salesforce opportunities or cases stored for #{abbr}."
    return "\n".join(bits)


def _status(repo, account: dict, aid: str, abbr: str, name: str) -> str:
    health = account.get("health") or {}
    stats = account.get("stats") or {}
    nxt = account.get("next_action") or {}
    lines = [
        f"{name} #{abbr} — health {health.get('score')} {health.get('status')}.",
        f"Open tickets {stats.get('open_tickets') or 0} (P1 {stats.get('open_p1') or 0}), "
        f"overdue actions {stats.get('overdue_actions') or 0}, unread threads {stats.get('unread_threads') or 0}.",
    ]
    if nxt.get("title"):
        lines.append(f"Next: {nxt.get('title')} due {nxt.get('due_on') or '—'}.")
    return " ".join(lines)
