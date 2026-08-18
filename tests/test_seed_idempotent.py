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
    assert nwin and glx
    assert int((nwin.get("health") or {}).get("score") or 100) < int((glx.get("health") or {}).get("score") or 0)
