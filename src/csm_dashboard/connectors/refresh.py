"""Mailbox-level Gmail/Calendar refresh: one-shot incremental + optional poller.

Cursors (Gmail historyId, Calendar syncToken) live in Couchbase Lite.
The timer is a one-shot every N minutes, not a long-poll or websocket.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone

from csm_dashboard.connectors.registry import PULL_CONNECTORS, connector_mode, get_connector
from csm_dashboard.ingest.route import route_event
from csm_dashboard.seed.load import apply_sync_event
from csm_dashboard.storage.repo import refresh_minutes, utcnow

log = logging.getLogger(__name__)

GOOGLE_REFRESH = ("google_mail", "google_cal")
_lock = threading.Lock()


def min_refresh_minutes(repo) -> int:
    """How often to hit Google: the smallest per-company interval that uses Gmail or Calendar."""
    vals: list[int] = []
    for acct in repo.list_accounts():
        if acct.get("removed"):
            continue
        feeds = list(((acct.get("coverage") or {}).get("feeds") or []))
        if feeds and "google_mail" not in feeds and "google_cal" not in feeds:
            continue
        if not feeds and not (acct.get("domains") or []):
            continue
        vals.append(refresh_minutes(acct))
    return min(vals) if vals else 0


def cursor_age_seconds(cursor: dict | None) -> float | None:
    raw = str((cursor or {}).get("pulled_at") or "")
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds()


def refresh_due(repo) -> bool:
    minutes = min_refresh_minutes(repo)
    if minutes <= 0:
        return False
    ages: list[float] = []
    for name in GOOGLE_REFRESH:
        if connector_mode(name, repo.get_settings()) != "live":
            continue
        conn = get_connector(name, repo)
        if not conn.ready():
            continue
        age = cursor_age_seconds(repo.get_sync_cursor(name))
        if age is None:
            return True
        ages.append(age)
    if not ages:
        return False
    return min(ages) >= minutes * 60


def run_connector_sync(repo, name: str, *, account_id: str = "", since: str = "") -> dict:
    if name not in PULL_CONNECTORS:
        raise KeyError(name)
    if connector_mode(name, repo.get_settings()) != "live":
        raise RuntimeError("connector_disabled")
    account = repo.get_account(account_id) if account_id else None
    job = repo.save_job(
        {
            "connector": name,
            "account_id": account_id or "",
            "status": "running",
            "since": since or "",
            "fetched": 0,
            "upserted": 0,
            "skipped": 0,
            "error": "",
        }
    )
    log.info("csm.sync.started connector=%s", name)
    try:
        events = get_connector(name, repo).pull(since or None, account)
        accounts = repo.list_accounts(include_hidden=True)
        upserted = 0
        routed = 0
        unassigned = 0
        touched: set[str] = set()
        ours = repo.operator_domains()
        new_mail: list[dict] = []
        for event in events:
            aid = route_event(accounts, event, operator_domains=ours)
            event["account_id"] = aid
            if aid:
                payload = dict(event.get("payload") or {})
                payload["account_id"] = aid
                event["payload"] = payload
                routed += 1
                touched.add(aid)
            else:
                unassigned += 1
            saved = apply_sync_event(repo, event)
            upserted += 1
            if name == "google_mail" and isinstance(saved, dict) and saved.get("_new"):
                new_mail.append(saved)
        if new_mail:
            from csm_dashboard.compose.auto_draft import process_new_emails

            process_new_emails(repo, new_mail)
        if account_id:
            repo.reattach_unassigned(account_id)
            touched.add(account_id)
        for aid in touched:
            try:
                repo.refresh_account_stats(aid)
                repo.score_account(aid)
            except KeyError:
                pass
        job = repo.save_job(
            {
                **job,
                "status": "done",
                "fetched": len(events),
                "upserted": upserted,
                "routed": routed,
                "unassigned": unassigned,
            },
            job_id=job["_id"],
        )
        log.info(
            "csm.sync.finished connector=%s fetched=%s upserted=%s routed=%s unassigned=%s",
            name,
            len(events),
            upserted,
            routed,
            unassigned,
        )
        return job
    except Exception as exc:
        job = repo.save_job({**job, "status": "error", "error": str(exc)}, job_id=job["_id"])
        log.error("csm.sync.failed connector=%s err=%s", name, exc)
        return job


def run_google_refresh(repo, *, connectors: list[str] | None = None) -> list[dict]:
    want = [n for n in (connectors or list(GOOGLE_REFRESH)) if n in GOOGLE_REFRESH]
    jobs: list[dict] = []
    with _lock:
        for name in want:
            if connector_mode(name, repo.get_settings()) != "live":
                continue
            conn = get_connector(name, repo)
            if not conn.ready():
                continue
            jobs.append(run_connector_sync(repo, name))
    return jobs


def tick_google_refresh(repo) -> list[dict]:
    if not refresh_due(repo):
        return []
    log.info("csm.refresh.poll minutes=%s", min_refresh_minutes(repo))
    return run_google_refresh(repo)


def start_poller(repo_fn, *, interval_sec: float = 30.0):
    stop = threading.Event()

    def loop() -> None:
        while not stop.wait(interval_sec):
            try:
                repo = repo_fn()
                if repo is None:
                    continue
                tick_google_refresh(repo)
            except Exception:
                log.exception("csm.refresh.poll_failed")

    thread = threading.Thread(target=loop, name="csm-google-refresh", daemon=True)
    thread.start()
    log.info("csm.refresh.poller_started interval_sec=%s", interval_sec)

    def shutdown() -> None:
        stop.set()
        thread.join(timeout=2.0)
        log.info("csm.refresh.poller_stopped")

    return shutdown
