"""Auto-draft Grok replies for inbound mail addressed To the operator."""

from __future__ import annotations

import logging
import threading

from csm_dashboard.chat.providers import resolve_ai_client, selected_provider
from csm_dashboard.compose.context import build_compose_context
from csm_dashboard.compose.gmail_draft import sync_gmail_draft
from csm_dashboard.compose.grok import as_addr_list, compose_with_grok, fallback_reply
from csm_dashboard.config import load_settings
from csm_dashboard.ingest.people import skip_local

log = logging.getLogger(__name__)

MAX_PER_RUN = 8
_lock = threading.Lock()


def _norm(addr: str) -> str:
    return str(addr or "").strip().lower()


def account_auto_drafts(account: dict | None) -> bool:
    return bool(((account or {}).get("coverage") or {}).get("auto_draft_replies"))


def addressed_to_operator(email: dict, me: str) -> bool:
    want = _norm(me)
    if not want or "@" not in want:
        return False
    return any(_norm(a) == want for a in (email.get("to_addrs") or []))


def skip_reason(repo, email: dict, *, me: str = "") -> str:
    """Empty string means draft it. Otherwise a skip reason."""
    if not email:
        return "no_email"
    aid = str(email.get("account_id") or "")
    acct = repo.get_account(aid) if aid else None
    if not aid or not acct:
        return "no_account"
    if not account_auto_drafts(acct):
        return "off"
    if str(email.get("direction") or "inbound") == "outbound":
        return "outbound"
    me = _norm(me or (repo.operator_profile() or {}).get("email") or "")
    if not me:
        return "no_operator_email"
    if _norm(email.get("from_addr") or "") == me:
        return "from_self"
    if not addressed_to_operator(email, me):
        return "not_to_me"
    local = _norm(email.get("from_addr") or "").split("@", 1)[0]
    if skip_local(local):
        return "noreply"
    op = email.get("operator") or {}
    if op.get("auto_draft_id"):
        return "already"
    if op.get("task"):
        return "task"
    return ""


def draft_reply_for_email(repo, email: dict) -> dict | None:
    reason = skip_reason(repo, email)
    if reason:
        log.info("csm.auto_draft.skipped reason=%s", reason)
        return None
    aid = str(email.get("account_id") or "")
    acct = repo.get_account(aid) or {}
    thread_id = str(email.get("thread_id") or "")
    settings = load_settings()
    operator = repo.operator_profile()
    client = resolve_ai_client(repo, settings)
    if not client:
        log.info("csm.auto_draft.skipped reason=no_ai account_id=%s", aid)
        return None
    ctx = build_compose_context(
        repo, aid, thread_id=thread_id or None, inbound=email, operator=operator, mode="reply"
    )
    thread = repo.get_thread(thread_id) if thread_id else {"subject": email.get("subject")}
    draft_body = fallback_reply(acct, thread, email)
    result = "fallback"
    model = ""
    try:
        drafted, model = compose_with_grok(client, ctx, settings, operator=operator)
        draft_body = {**draft_body, **drafted}
        result = selected_provider(repo.get_settings())
    except Exception as exc:
        log.warning("csm.auto_draft.failed err=%s", exc)
        return None
    to_addrs = as_addr_list(draft_body.get("to"))
    from_addr = str(email.get("from_addr") or "")
    if from_addr and from_addr not in to_addrs:
        to_addrs = [from_addr, *to_addrs]
    saved = repo.create_draft(
        {
            "account_id": aid,
            "subject": draft_body.get("subject") or "",
            "body": draft_body.get("body") or "",
            "to_addrs": to_addrs,
            "cc_addrs": as_addr_list(draft_body.get("cc")),
            "prompt_name": "email_draft",
            "model": model,
            "created_by": "grok" if result != "fallback" else "you",
            "context_ref": {"thread_id": thread_id, "email_id": str(email.get("_id") or "")},
            "status": "ready",
            "channel": "email",
        }
    )
    saved = sync_gmail_draft(repo, saved)
    eid = str(email.get("_id") or "")
    if eid:
        try:
            repo.patch_email_operator(eid, {"auto_draft_id": saved.get("_id") or ""})
        except KeyError:
            pass
    log.info(
        "csm.auto_draft.created account_id=%s result=%s gmail=%s",
        aid,
        result,
        (saved.get("gmail") or {}).get("ok"),
    )
    return saved


def process_new_emails(repo, emails: list | None) -> dict:
    created = 0
    skipped = 0
    with _lock:
        for email in emails or []:
            if created >= MAX_PER_RUN:
                skipped += 1
                continue
            if not email.get("_new"):
                skipped += 1
                continue
            if draft_reply_for_email(repo, email):
                created += 1
            else:
                skipped += 1
    if created or skipped:
        log.info("csm.auto_draft.batch created=%s skipped=%s", created, skipped)
    return {"created": created, "skipped": skipped}


def backfill_account(repo, account_id: str) -> dict:
    acct = repo.get_account(account_id)
    if not account_auto_drafts(acct):
        return {"created": 0, "skipped": 0}
    rows, _ = repo.page_emails(account_id, limit=40, slim=False, desc=True)
    created = 0
    skipped = 0
    with _lock:
        for email in rows:
            if created >= MAX_PER_RUN:
                break
            if draft_reply_for_email(repo, email):
                created += 1
            else:
                skipped += 1
    log.info("csm.auto_draft.backfill account_id=%s created=%s skipped=%s", account_id, created, skipped)
    return {"created": created, "skipped": skipped}
