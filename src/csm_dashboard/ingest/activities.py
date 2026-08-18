from __future__ import annotations

from csm_dashboard.storage.repo import CsmRepo, utcnow


def emit_ticket_activity(repo: CsmRepo, ticket: dict, *, verb: str = "updated") -> dict:
    key = ticket.get("key") or ""
    at = ticket.get("updated_at") or utcnow()
    kind = "ticket_created" if verb == "created" else "ticket_updated"
    return repo.upsert_activity_by_source_ref(
        {
            "account_id": ticket.get("account_id") or "",
            "kind": kind,
            "at": at,
            "title": f"{key} {verb}",
            "ref": {"collection": "tickets", "id": ticket.get("_id") or f"tkt:jira:{key}"},
            "source_ref": f"jira:ticket:{key}:{verb}:{at}",
            "actor": "jira",
        }
    )


def emit_email_activity(repo: CsmRepo, email: dict) -> dict:
    direction = email.get("direction") or "inbound"
    kind = "email_in" if direction == "inbound" else "email_out"
    at = email.get("sent_at") or utcnow()
    mid = email.get("message_id") or email.get("_id") or at
    return repo.upsert_activity_by_source_ref(
        {
            "account_id": email.get("account_id") or "",
            "kind": kind,
            "at": at,
            "title": str(email.get("subject") or "")[:160],
            "ref": {"collection": "emails", "id": email.get("_id") or ""},
            "source_ref": f"mail:{mid}",
            "actor": email.get("from_addr") or "mail",
        }
    )


def emit_calendar_activity(repo: CsmRepo, event: dict) -> dict:
    ext = event.get("external_id") or ""
    at = event.get("start_at") or utcnow()
    return repo.upsert_activity_by_source_ref(
        {
            "account_id": event.get("account_id") or "",
            "kind": "meeting",
            "at": at,
            "title": str(event.get("title") or "")[:160],
            "ref": {"collection": "calendar_events", "id": event.get("_id") or ""},
            "source_ref": f"cal:{event.get('provider') or 'stub'}:{ext}",
            "actor": "calendar",
        }
    )
