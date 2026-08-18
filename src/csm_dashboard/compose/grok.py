from __future__ import annotations

import json
import logging

from csm_dashboard.compose.context import ComposeContext
from csm_dashboard.config import Settings
from csm_dashboard.prompts import prompt_system, prompt_user

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
