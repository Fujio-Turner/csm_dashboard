from __future__ import annotations

from csm_dashboard.chat.desk_answer import answer_desk
from csm_dashboard.chat.mentions import parse_customer_tokens, parse_person_handles, resolve_account


def test_parse_tokens():
    msg = "Is there any issue with #{ACME}? Did @bob from #{ customer xyz} reply?"
    assert parse_customer_tokens(msg) == ["ACME", "xyz"]
    assert parse_person_handles(msg) == ["bob"]


def test_resolve_and_issues(repo):
    from csm_dashboard.config import fixtures_dir
    from csm_dashboard.seed.load import apply_seed

    apply_seed(repo, fixtures_dir() / "seed")
    acct = resolve_account(repo, "issues with #{ACME}?")
    assert acct and acct["abbr"] == "ACME"
    text = answer_desk(repo, "Is there any issue with #{ACME}?", acct)
    assert "ACME-12" in text


def test_bob_replied(repo):
    from csm_dashboard.config import fixtures_dir
    from csm_dashboard.seed.load import apply_seed

    apply_seed(repo, fixtures_dir() / "seed")
    acct = resolve_account(repo, "did @bob from #{ACME} reply to my last email?")
    text = answer_desk(repo, "did @bob from #{ACME} reply to my last email?", acct)
    assert "Yes" in text
    assert "Bob" in text or "bob" in text.lower()
