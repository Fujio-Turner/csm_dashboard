from __future__ import annotations

from csm_dashboard.chat.desk_answer import answer_desk
from csm_dashboard.chat.mentions import parse_customer_tokens, parse_person_handles, parse_slash_bounds, resolve_account


def test_parse_tokens():
    braced = "Is there any issue with #{ACME}? Did @bob from #{ customer xyz} reply?"
    assert parse_customer_tokens(braced) == ["ACME", "xyz"]
    assert parse_person_handles(braced) == ["bob"]
    bare = "Is there any issue with #ACME? Did @bob from #NWIN reply?"
    assert parse_customer_tokens(bare) == ["ACME", "NWIN"]
    assert parse_person_handles(bare) == ["bob"]
    mixed = "open #{ACME} then #GLX"
    assert parse_customer_tokens(mixed) == ["ACME", "GLX"]


def test_parse_skips_routes_colors_tickets():
    assert parse_customer_tokens("open #account/ACME and #help/foo") == []
    assert parse_customer_tokens("color #fff or #0B3D91") == []
    assert parse_customer_tokens("see ACME-12 and #ACME") == ["ACME"]
    assert parse_person_handles("mail bob.hale@acme.com and @bob") == ["bob"]


def test_resolve_and_issues(repo):
    from csm_dashboard.config import fixtures_dir
    from csm_dashboard.seed.load import apply_seed

    apply_seed(repo, fixtures_dir() / "seed")
    acct = resolve_account(repo, "issues with #ACME?")
    assert acct and acct["abbr"] == "ACME"
    legacy = resolve_account(repo, "issues with #{ACME}?")
    assert legacy and legacy["abbr"] == "ACME"
    text = answer_desk(repo, "Is there any issue with #ACME?", acct)
    assert "ACME-12" in text
    assert "#{ACME}" not in text
    assert "#ACME" in text


def test_bob_replied(repo):
    from csm_dashboard.config import fixtures_dir
    from csm_dashboard.seed.load import apply_seed

    apply_seed(repo, fixtures_dir() / "seed")
    acct = resolve_account(repo, "did @bob from #ACME reply to my last email?")
    text = answer_desk(repo, "did @bob from #ACME reply to my last email?", acct)
    assert "Yes" in text
    assert "Bob" in text or "bob" in text.lower()


def test_parse_slash_bounds():
    bounds = parse_slash_bounds("what was /people bob response to /ticket ACME-12?")
    assert bounds["people"] == ["bob"]
    assert bounds["ticket"] == ["ACME-12"]
    assert parse_person_handles("what was /people bob response to /ticket ACME-12?") == ["bob"]
    mixed = parse_slash_bounds("Did /people bob reply? Also @pat")
    assert mixed["people"] == ["bob"]
    assert parse_person_handles("Did /people bob reply? Also @pat") == ["pat", "bob"]


def test_person_ticket_bound(repo):
    from csm_dashboard.config import fixtures_dir
    from csm_dashboard.seed.load import apply_seed

    apply_seed(repo, fixtures_dir() / "seed")
    acct = resolve_account(repo, "x", "acct:acme")
    text = answer_desk(repo, "what was /people bob response to /ticket ACME-12?", acct)
    assert "ACME-12" in text
    assert "Bob" in text or "bob" in text.lower()
    assert "Which book?" not in text


def test_unique_person_implies_book(repo):
    from csm_dashboard.config import fixtures_dir
    from csm_dashboard.seed.load import apply_seed

    apply_seed(repo, fixtures_dir() / "seed")
    acct = resolve_account(repo, "did @bob reply to my last email?")
    assert acct and acct["abbr"] == "ACME"
    text = answer_desk(repo, "did @bob reply to my last email?", acct)
    assert "Bob" in text or "bob" in text.lower()
