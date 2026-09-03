from __future__ import annotations

from datetime import datetime
from pathlib import Path

from csm_dashboard.seed.load import apply_seed

SEED = Path(__file__).resolve().parents[1] / "fixtures" / "seed"


def _at(iso: str) -> datetime:
    return datetime.fromisoformat(str(iso or "").replace("Z", "+00:00"))


def test_seed_twice_same_counts(repo):
    first = apply_seed(repo, SEED)
    second = apply_seed(repo, SEED)
    for key in ("accounts", "tickets", "emails", "threads", "activities", "people"):
        assert first[key] == second[key] == repo.counts()[key]
    assert first["accounts"] == 3
    nwin = repo.get_account_by_abbr("NWIN")
    glx = repo.get_account_by_abbr("GLX")
    acme = repo.get_account_by_abbr("ACME")
    assert nwin and glx and acme
    assert int((nwin.get("health") or {}).get("score") or 100) < int((glx.get("health") or {}).get("score") or 0)
    assert first["people"] >= 50
    customers = repo.list_people("acct:acme", kind="customer")
    assert len(customers) >= 18
    assert any(p.get("_id") == "person:acme-dana" for p in customers)
    assert any(p.get("reports_to") == "person:acme-dana" for p in customers)
    assert any(p.get("_id") == "person:acme-bob" for p in customers)
    assert any(p.get("owns_all_projects") for p in customers)
    nwin_people = repo.list_people("acct:northwind", kind="customer")
    glx_people = repo.list_people("acct:globex", kind="customer")
    assert len(nwin_people) >= 14
    assert len(glx_people) >= 14
    assert any(p.get("reports_to") == "person:nwin-helen" for p in nwin_people)
    assert any(p.get("reports_to") == "person:glx-eleanor" for p in glx_people)
    day = repo.home_agenda("2026-08-28")
    titles = [m.get("title") or "" for m in day["meetings"]]
    abbrs = [((m.get("account") or {}).get("abbr") or "") for m in day["meetings"]]
    assert len(day["meetings"]) >= 8
    assert abbrs.count("ACME") >= 3
    assert abbrs.count("NWIN") >= 2
    assert abbrs.count("GLX") >= 2
    assert any("standup" in t.lower() or "QBR" in t or "renewal" in t.lower() for t in titles)
    ordered = sorted(day["meetings"], key=lambda m: str(m.get("start_at") or ""))
    gaps = []
    for prev, nxt in zip(ordered, ordered[1:]):
        gap = (_at(nxt["start_at"]) - _at(prev["end_at"])).total_seconds() / 60
        assert gap >= -1
        gaps.append(gap)
    assert sum(1 for g in gaps if -1 <= g <= 5) >= 1
    assert sum(1 for g in gaps if g >= 25) >= 3
    today = repo.home_agenda("")
    assert len(today["meetings"]) >= 8
    week = repo.home_agenda("2026-08-28", start="2026-08-24", end="2026-08-30")
    assert week["start"] == "2026-08-24"
    assert week["end"] == "2026-08-30"
    assert len(week["meetings"]) >= len(day["meetings"])
    assert (week["meetings"][0].get("title") or "").strip()
    tasks = []
    for aid in ("acct:acme", "acct:northwind", "acct:globex"):
        rows, _ = repo.page_emails(aid, limit=80, slim=True, desc=True)
        tasks.extend(r for r in rows if (r.get("operator") or {}).get("task"))
    assert len(tasks) >= 12
    by_acct = {aid: 0 for aid in ("acct:acme", "acct:northwind", "acct:globex")}
    by_proj: dict[str, int] = {}
    for row in tasks:
        aid = str(row.get("account_id") or "")
        if aid in by_acct:
            by_acct[aid] += 1
        pid = str(row.get("project_id") or "")
        if pid:
            by_proj[pid] = by_proj.get(pid, 0) + 1
    assert by_acct["acct:acme"] >= 3
    assert by_acct["acct:northwind"] >= 2
    assert by_acct["acct:globex"] >= 2
    assert by_proj.get("proj:acme-scan", 0) >= 2
    assert by_proj.get("proj:acme-sso", 0) >= 2
    assert by_proj.get("proj:nwin-renew", 0) >= 2
    assert by_proj.get("proj:glx-onboard", 0) >= 2
    inbox = day["inbox"]
    top_kinds = [str(i.get("kind") or "") for i in inbox[:15]]
    assert "email" in top_kinds[:8]
    assert "slack" in top_kinds[:8]
    assert "teams" in top_kinds[:8]
    assert top_kinds.count("email") >= 2
    run = 1
    max_run = 1
    for prev, nxt in zip(top_kinds, top_kinds[1:]):
        if prev == nxt:
            run += 1
            max_run = max(max_run, run)
        else:
            run = 1
    assert max_run <= 3
    assert repo.account_has_logo("acct:acme", acme)
    assert repo.account_has_logo("acct:northwind", nwin)
    assert repo.account_has_logo("acct:globex", glx)
