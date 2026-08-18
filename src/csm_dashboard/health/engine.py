from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from csm_dashboard.config import load_settings
from csm_dashboard.storage.repo import utcnow

log = logging.getLogger(__name__)

OPEN = {"open", "in_progress", "waiting"}


def status_for(score: int) -> str:
    if score >= 75:
        return "healthy"
    if score >= 50:
        return "watch"
    if score >= 25:
        return "at_risk"
    return "critical"


def _parse(ts: str) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def score_account(repo, account_id: str) -> dict:
    acct = repo.get_account(account_id)
    if not acct:
        raise KeyError(account_id)
    settings = load_settings()
    weights = settings.health or {}
    ticket_max = int(weights.get("ticket_max") or 25)
    resp_max = int(weights.get("responsiveness_max") or 20)
    eng_max = int(weights.get("engagement_max") or 20)
    act_max = int(weights.get("actions_max") or 15)
    ren_max = int(weights.get("renewal_max") or 20)

    now = datetime.now(timezone.utc)
    today = utcnow()[:10]

    tickets, _ = repo.page_tickets(account_id, limit=500)
    open_t = [t for t in tickets if t.get("status") in OPEN and not (t.get("operator") or {}).get("ignore")]
    p1 = sum(1 for t in open_t if t.get("priority") == "p1")
    p2 = sum(1 for t in open_t if t.get("priority") == "p2")
    ticket_pts = max(0, ticket_max - 12 * p1 - 6 * p2)

    threads, _ = repo.page_threads(account_id, limit=200)
    hits = 0
    for th in threads:
        if not (th.get("operator") or {}).get("unread"):
            continue
        at = _parse(str(th.get("last_at") or ""))
        if at and now - at > timedelta(days=3):
            hits += 1
    for t in open_t:
        if t.get("status") != "waiting":
            continue
        at = _parse(str(t.get("updated_at") or ""))
        if at and now - at > timedelta(days=5):
            hits += 1
    resp_pts = max(0, resp_max - 10 * hits)

    events = repo.page_calendar(account_id)
    last_meet: datetime | None = None
    for ev in events:
        start = _parse(str(ev.get("start_at") or ""))
        if not start or start > now:
            continue
        attendees = ev.get("attendees") or []
        if attendees and (last_meet is None or start > last_meet):
            last_meet = start
    if last_meet is None:
        eng_pts = 0
    else:
        days = (now - last_meet).days
        if days <= 14:
            eng_pts = eng_max
        elif days <= 30:
            eng_pts = 10
        elif days <= 45:
            eng_pts = 5
        else:
            eng_pts = 0

    overdue = repo.page_actions(account_id=account_id, due="overdue", today=today)
    act_pts = max(0, act_max - 5 * len(overdue))

    renewal = str((acct.get("contract") or {}).get("renewal_on") or "")
    other = ticket_pts + resp_pts + eng_pts + act_pts
    if not renewal:
        ren_pts = 10
    else:
        try:
            days_left = (datetime.fromisoformat(renewal) - now.replace(tzinfo=None)).days
        except ValueError:
            days_left = 999
        if days_left > 90:
            ren_pts = ren_max
        elif days_left > 30:
            ren_pts = 12
        elif other >= 40:
            ren_pts = 8
        else:
            ren_pts = 0

    rules = ticket_pts + resp_pts + eng_pts + act_pts + ren_pts
    breakdown = [
        {"id": "tickets", "points": ticket_pts, "max": ticket_max, "reason": f"{p1} P1, {p2} P2"},
        {"id": "responsiveness", "points": resp_pts, "max": resp_max, "reason": f"{hits} stale unread/waiting"},
        {"id": "engagement", "points": eng_pts, "max": eng_max, "reason": "last customer meeting"},
        {"id": "actions", "points": act_pts, "max": act_max, "reason": f"{len(overdue)} overdue"},
        {"id": "renewal", "points": ren_pts, "max": ren_max, "reason": renewal or "unknown"},
    ]

    health = dict(acct.get("health") or {})
    override = health.get("override")
    health["rules_score"] = rules
    health["breakdown"] = breakdown
    health["score_max"] = 100
    if isinstance(override, int):
        health["score"] = override
        health["status"] = status_for(override)
        health["scored_by"] = "override"
        scored_by = "override"
    else:
        health["score"] = rules
        health["status"] = status_for(rules)
        health["scored_by"] = "rules"
        scored_by = "rules"
    acct["health"] = health
    acct["updated_at"] = utcnow()
    repo.store.save("accounts", account_id, {k: v for k, v in acct.items() if k != "_id"})
    log.info("csm.health.updated account_id=%s score=%s scored_by=%s", account_id, health["score"], scored_by)
    return repo.get_account(account_id) or acct
