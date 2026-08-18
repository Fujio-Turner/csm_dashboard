from __future__ import annotations

import json
import logging

from datetime import datetime, timedelta, timezone

from csm_dashboard.compose.context import ComposeContext
from csm_dashboard.config import Settings
from csm_dashboard.prompts import prompt_system, prompt_user
from csm_dashboard.storage.repo import TASK_KINDS

log = logging.getLogger(__name__)


def fallback_reply(account: dict, thread: dict, last: dict | None = None) -> dict:
    abbr = account.get("abbr") or "ACCT"
    name = account.get("name") or abbr
    subj = str((thread or {}).get("subject") or f"{abbr} follow-up")
    if not subj.lower().startswith("re:"):
        subj = "Re: " + subj
    to_addr = str((last or {}).get("from_addr") or "")
    body = (
        f"Hi,\n\nThanks for the note on {name}. I have the account context "
        f"(tickets, people, and recent thread) and will come back with next steps.\n\nThanks,\n"
    )
    return {"subject": subj, "body": body, "to": [to_addr] if to_addr else [], "cc": [], "next_steps": [], "risks": []}


def fallback_draft(account: dict, ctx: ComposeContext) -> dict:
    abbr = account.get("abbr") or "ACCT"
    keys = [t.get("key") for t in (ctx.payload.get("tickets") or []) if t.get("key")]
    subject = f"{abbr} follow-up"
    if keys:
        subject = f"{abbr} — {keys[0]} update"
    body = (
        f"Hi,\n\nFollowing up on {abbr}"
        + (f" ({', '.join(keys)})" if keys else "")
        + ".\n\nI will send a fuller note once Grok is configured in Settings.\n\nThanks,\n"
    )
    return {
        "subject": subject,
        "body": body,
        "to": [],
        "cc": [],
        "next_steps": ["Add an xAI key to draft with Grok"],
        "risks": [],
    }


def fallback_task_assist(account: dict, *, kind: str = "", name: str = "", body: str = "", people: list | None = None) -> dict:
    abbr = account.get("abbr") or "ACCT"
    company = account.get("name") or abbr
    use_kind = kind if kind in TASK_KINDS else TASK_KINDS[0]
    title = (name or "").strip() or f"{use_kind.split('(')[0].strip()} — {abbr}"
    note = (body or "").strip() or (
        f"{use_kind} for {company}. Review open tickets and recent mail, then close this when the next step is booked."
    )
    cc: list[str] = []
    for person in people or []:
        if person.get("role") == "champion" and person.get("email"):
            cc.append(str(person["email"]))
            break
    due = (datetime.now(timezone.utc) + timedelta(days=3)).strftime("%Y-%m-%dT15:00")
    return {
        "task_name": title,
        "task_kind": use_kind,
        "due_at": due,
        "cc_addrs": cc,
        "body": note,
    }


def assist_task_with_grok(client, payload: dict, settings: Settings) -> tuple[dict, str]:
    messages = [
        {"role": "system", "content": prompt_system("task_assist")},
        {"role": "user", "content": prompt_user("task_assist", json.dumps(payload, default=str))},
    ]
    data, model = client.complete_json(messages)
    log.info(
        "csm.ai.complete account_id=%s prompt_name=task_assist model=%s",
        payload.get("account_id") or "",
        model,
    )
    return data, model


def compose_with_grok(client, ctx: ComposeContext, settings: Settings) -> tuple[dict, str]:
    messages = [
        {"role": "system", "content": prompt_system("email_draft")},
        {"role": "user", "content": prompt_user("email_draft", ctx.serialized())},
    ]
    data, model = client.complete_json(messages)
    log.info(
        "csm.ai.complete account_id=%s prompt_name=email_draft model=%s truncated=%s",
        ctx.account_id,
        model,
        ctx.truncated,
    )
    return data, model
