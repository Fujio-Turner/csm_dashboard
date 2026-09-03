"""Push desk drafts into Gmail Drafts."""

from __future__ import annotations

import logging

from csm_dashboard.connectors.google_mail import google_draft_ready, save_gmail_draft
from csm_dashboard.connectors.smtp_imap import SendFailed, SendNotConfigured, build_message
from csm_dashboard.credentials import oauth_connected

log = logging.getLogger(__name__)


def sync_gmail_draft(repo, doc: dict) -> dict:
    out = dict(doc)
    secret = repo.get_credential_secret("connector", "google")
    if not oauth_connected(secret):
        out["gmail"] = {"ok": False, "reason": "not_connected"}
        return out
    if not google_draft_ready(repo):
        out["gmail"] = {"ok": False, "reason": "google_draft_reconnect"}
        return out
    me = str(repo.operator_profile().get("email") or "").strip()
    if not me:
        out["gmail"] = {"ok": False, "reason": "operator_email_required"}
        return out
    msg = build_message(
        from_addr=me,
        to_addrs=list(doc.get("to_addrs") or []),
        cc_addrs=list(doc.get("cc_addrs") or []),
        bcc_addrs=list(doc.get("bcc_addrs") or []),
        subject=str(doc.get("subject") or ""),
        body=str(doc.get("body") or ""),
    )
    try:
        saved = save_gmail_draft(
            repo,
            msg,
            draft_id=str(doc.get("gmail_draft_id") or ""),
            from_addr=me,
            to_addrs=list(doc.get("to_addrs") or []),
        )
    except SendNotConfigured as exc:
        out["gmail"] = {"ok": False, "reason": str(exc) or "google_draft_reconnect"}
        return out
    except SendFailed as exc:
        log.warning("csm.mail.draft_failed err=%s", exc.message)
        out["gmail"] = {"ok": False, "reason": "send_failed"}
        return out
    gid = str(saved.get("gmail_draft_id") or "")
    doc_id = str(doc.get("_id") or "")
    if gid and doc_id and gid != str(doc.get("gmail_draft_id") or ""):
        try:
            out = repo.patch_draft(doc_id, {"gmail_draft_id": gid})
        except KeyError:
            out["gmail_draft_id"] = gid
    elif gid:
        out["gmail_draft_id"] = gid
    out["gmail"] = {"ok": True, "gmail_draft_id": gid}
    return out
