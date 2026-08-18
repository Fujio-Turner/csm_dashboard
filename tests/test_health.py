from __future__ import annotations

from csm_dashboard.health.engine import score_account, status_for


def test_status_bands():
    assert status_for(80) == "healthy"
    assert status_for(60) == "watch"
    assert status_for(30) == "at_risk"
    assert status_for(10) == "critical"


def test_override_is_lock(repo):
    repo.create_account(
        {
            "name": "Acme",
            "slug": "acme",
            "abbr": "ACME",
            "color": "#0B3D91",
            "health": {"score": 10, "override": 90, "status": "critical"},
        }
    )
    scored = score_account(repo, "acct:acme")
    assert scored["health"]["score"] == 90
    assert scored["health"]["status"] == "healthy"
    assert scored["health"]["scored_by"] == "override"
    assert "rules_score" in scored["health"]
