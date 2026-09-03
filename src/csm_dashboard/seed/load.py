from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

from csm_dashboard.ingest.activities import emit_calendar_activity, emit_email_activity, emit_ticket_activity
from csm_dashboard.storage.repo import CsmRepo, utcnow

log = logging.getLogger(__name__)

SEED_DEMO_DAY = "2026-08-28"

COLLECTION_FILES = (
    ("accounts.json", "accounts"),
    ("people.json", "people"),
    ("projects.json", "projects"),
    ("tickets.json", "tickets"),
    ("threads.json", "threads"),
    ("emails.json", "emails"),
    ("slack_channels.json", "slack_channels"),
    ("slack_messages.json", "slack_messages"),
    ("teams_channels.json", "teams_channels"),
    ("teams_messages.json", "teams_messages"),
    ("salesforce_opportunities.json", "salesforce_opportunities"),
    ("salesforce_cases.json", "salesforce_cases"),
    ("calendar_events.json", "calendar_events"),
    ("action_items.json", "action_items"),
    ("notes.json", "notes"),
    ("activities.json", "activities"),
)


def _rows(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    return []


def apply_seed_logos(repo: CsmRepo, seed_dir: str | Path) -> int:
    src_dir = Path(seed_dir) / "logos"
    if not src_dir.is_dir():
        return 0
    dest = repo.logo_dir()
    dest.mkdir(parents=True, exist_ok=True)
    applied = 0
    for path in sorted(src_dir.iterdir()):
        suffix = path.suffix.lower()
        if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
            continue
        dest_path = dest / path.name
        shutil.copy2(path, dest_path)
        stem = path.stem
        account_id = stem if stem.startswith("acct:") else "acct:" + stem.removeprefix("acct-")
        doc = repo.get_account(account_id)
        if not doc:
            continue
        mime = "image/jpeg" if suffix in {".jpg", ".jpeg"} else "image/webp" if suffix == ".webp" else "image/png"
        repo._logos[account_id] = (path.read_bytes(), mime)
        doc["has_logo"] = True
        doc["logo_mime"] = mime
        doc["logo_updated_at"] = doc.get("updated_at") or ""
        repo.store.save("accounts", doc["_id"], {**doc, "type": "account"})
        applied += 1
        log.info("csm.seed.logo account_id=%s", account_id)
    return applied


def apply_seed_today_meetings(repo: CsmRepo, seed_dir: str | Path) -> int:
    """Copy the demo-day calendar onto today so Lab seed fills Home agenda."""
    today = utcnow()[:10]
    if today == SEED_DEMO_DAY:
        return 0
    cloned = 0
    for row in _rows(Path(seed_dir) / "calendar_events.json"):
        start = str(row.get("start_at") or "")
        if start[:10] != SEED_DEMO_DAY:
            continue
        new = dict(row)
        ext = str(row.get("external_id") or f"evt-{cloned}")
        new["external_id"] = ext if ext.endswith("-today") else f"{ext}-today"
        new["start_at"] = today + start[10:]
        end = str(row.get("end_at") or "")
        if len(end) >= 10:
            new["end_at"] = today + end[10:]
        saved = repo.upsert_calendar(new)
        emit_calendar_activity(repo, saved)
        cloned += 1
    if cloned:
        log.info("csm.seed.today_meetings day=%s cloned=%s", today, cloned)
    return cloned


def apply_seed(repo: CsmRepo, seed_dir: str | Path) -> dict[str, int]:
    root = Path(seed_dir)
    repo.begin_bulk()
    try:
        for filename, collection in COLLECTION_FILES:
            for row in _rows(root / filename):
                _upsert(repo, collection, row)
        apply_seed_logos(repo, root)
        apply_seed_today_meetings(repo, root)
    finally:
        repo.end_bulk()
    for acct in repo.list_accounts():
        aid = acct.get("account_id") or acct.get("_id")
        if aid:
            repo.touch_next_action(aid)
            repo.score_account(aid)
    counts = repo.counts()
    log.info("csm.seed.applied counts=%s", counts)
    return counts


def apply_sync_event(repo: CsmRepo, event: dict) -> dict | None:
    kind = event.get("kind")
    payload = dict(event.get("payload") or {})
    if event.get("account_id") and not payload.get("account_id"):
        payload["account_id"] = event["account_id"]
    saved = None
    if kind == "ticket":
        saved = repo.upsert_ticket(payload)
        emit_ticket_activity(repo, saved, verb="updated")
    elif kind == "email":
        saved = repo.upsert_email(payload)
        emit_email_activity(repo, saved)
    elif kind == "slack_channel":
        repo.upsert_slack_channel(payload)
    elif kind == "slack_message":
        repo.upsert_slack_message(payload)
    elif kind == "teams_channel":
        repo.upsert_teams_channel(payload)
    elif kind == "teams_message":
        repo.upsert_teams_message(payload)
    elif kind == "salesforce_opportunity":
        repo.upsert_salesforce_opportunity(payload)
    elif kind == "salesforce_case":
        repo.upsert_salesforce_case(payload)
    elif kind == "calendar_event":
        saved = repo.upsert_calendar(payload)
        emit_calendar_activity(repo, saved)
    return saved


def _upsert(repo: CsmRepo, collection: str, row: dict) -> None:
    row = dict(row)
    doc_id = row.pop("_id", None)
    if collection == "accounts":
        existing = repo.get_account(doc_id or f"acct:{row.get('slug')}")
        if existing:
            keep = {
                k: existing[k]
                for k in ("has_logo", "logo_mime", "logo_updated_at", "quiet", "removed")
                if k in existing
            }
            repo.store.save("accounts", existing["_id"], {**row, **keep, "type": "account"})
        else:
            if doc_id:
                row["_id"] = doc_id
            created = repo.create_account(row)
            if doc_id and created.get("_id") != doc_id:
                pass
        return
    if collection == "people":
        if doc_id:
            row["_id"] = doc_id
        if doc_id and repo.get_person(doc_id):
            repo.store.save("people", doc_id, {**row, "type": "person"})
        else:
            repo.create_person(row)
        return
    if collection == "projects":
        if doc_id:
            row["_id"] = doc_id
        if doc_id and repo.get_project(doc_id):
            repo.store.save("projects", doc_id, {**row, "type": "project"})
        else:
            repo.create_project(row)
        return
    if collection == "tickets":
        if doc_id:
            row["_id"] = doc_id
        repo.upsert_ticket(row, doc_id=doc_id)
        return
    if collection == "threads":
        repo.upsert_thread(row, doc_id=doc_id)
        return
    if collection == "emails":
        if doc_id:
            row["_id"] = doc_id
        repo.upsert_email(row)
        return
    if collection == "slack_channels":
        repo.upsert_slack_channel(row)
        return
    if collection == "slack_messages":
        repo.upsert_slack_message(row, emit_activity=False)
        return
    if collection == "teams_channels":
        repo.upsert_teams_channel(row)
        return
    if collection == "teams_messages":
        repo.upsert_teams_message(row, emit_activity=False)
        return
    if collection == "salesforce_opportunities":
        if doc_id:
            row["_id"] = doc_id
        repo.upsert_salesforce_opportunity(row, emit_activity=False)
        return
    if collection == "salesforce_cases":
        if doc_id:
            row["_id"] = doc_id
        repo.upsert_salesforce_case(row, emit_activity=False)
        return
    if collection == "calendar_events":
        repo.upsert_calendar(row)
        return
    if collection == "action_items":
        if doc_id:
            row["_id"] = doc_id
        if doc_id and repo.get_action(doc_id):
            repo.store.save("action_items", doc_id, {**row, "type": "action_item"})
        else:
            repo.create_action(row)
        return
    if collection == "notes":
        if doc_id:
            repo.store.save("notes", doc_id, {**row, "type": "note"})
        else:
            repo.add_note(row)
        return
    if collection == "activities":
        if row.get("source_ref"):
            repo.upsert_activity_by_source_ref(row)
        elif doc_id:
            repo.store.save("activities", doc_id, {**row, "type": "activity"})
        else:
            repo.add_operator_activity(row)
