from __future__ import annotations

from pathlib import Path

from csm_dashboard.seed.load import apply_seed

SEED = Path(__file__).resolve().parents[1] / "fixtures" / "seed"


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
    assert len(day["meetings"]) >= 18
    assert abbrs.count("ACME") >= 5
    assert abbrs.count("NWIN") >= 5
    assert abbrs.count("GLX") >= 5
    assert any("standup" in t.lower() or "QBR" in t or "renewal" in t.lower() for t in titles)
    today = repo.home_agenda("")
    assert len(today["meetings"]) >= 18
    assert repo.account_has_logo("acct:acme", acme)
    assert repo.account_has_logo("acct:northwind", nwin)
    assert repo.account_has_logo("acct:globex", glx)
