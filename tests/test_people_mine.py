from __future__ import annotations

from csm_dashboard.ingest.people import (
    mine_account_people,
    name_from_local,
    parse_display_name,
    skip_email,
)


def test_parse_last_comma_first_and_email_local():
    last_first = parse_display_name("Moyerman, Joshua")
    assert last_first["name"] == "Joshua Moyerman"
    nd = parse_display_name("Zotov, Alexander -ND")
    assert nd["name"] == "Alexander Zotov"
    titled = parse_display_name("Joshua Moyerman, Engineering Manager")
    assert titled["name"] == "Joshua Moyerman"
    assert titled["title"] == "Engineering Manager"
    group = parse_display_name("Pat Nguyen, DBA, Platform")
    assert group["name"] == "Pat Nguyen"
    assert group["title"] == "DBA"
    assert group["group"] == "Platform"
    assert name_from_local("pat.nguyen") == "Pat Nguyen"
    assert name_from_local("alexander.x.rico.-nd") == "Alexander X Rico"
    assert skip_email("noreply@acme.com") is True
    assert skip_email("pat@acme.com") is False
    assert skip_email("pat@acme.com", operator_email="you@example.com", operator_domains={"example.com"}) is False
    assert skip_email("you@example.com", operator_email="you@example.com") is True


def test_mine_people_dedupes_mail_calendar_ticket(repo):
    repo.create_account(
        {
            "name": "Acme",
            "slug": "acme",
            "abbr": "ACME",
            "color": "#0B3D91",
            "domains": ["acme.com"],
        }
    )
    repo.save_settings({"operator": {"email": "you@example.com"}})
    repo.upsert_email(
        {
            "account_id": "acct:acme",
            "from_addr": "pat.nguyen@acme.com",
            "from_name": "Nguyen, Pat",
            "to_addrs": ["you@example.com"],
            "subject": "Hello",
            "snippet": "Pat Nguyen\nDBA\n+1 312-555-0199",
            "message_id": "<mine-1@test>",
            "sent_at": "2026-09-01T12:00:00Z",
        }
    )
    repo.upsert_email(
        {
            "account_id": "acct:acme",
            "from_addr": "noreply@acme.com",
            "to_addrs": ["you@example.com"],
            "subject": "Do not add",
            "message_id": "<mine-noreply@test>",
            "sent_at": "2026-09-01T13:00:00Z",
        }
    )
    repo.upsert_calendar(
        {
            "account_id": "acct:acme",
            "title": "Standup",
            "start_at": "2026-09-02T16:00:00Z",
            "end_at": "2026-09-02T16:30:00Z",
            "attendees": [{"email": "pat.nguyen@acme.com", "name": "Pat Nguyen"}],
            "external_id": "cal-mine-1",
            "provider": "google",
        }
    )
    repo.upsert_ticket(
        {
            "account_id": "acct:acme",
            "key": "ACME-1",
            "summary": "Capella",
            "status": "open",
            "priority": "p3",
            "reporter_email": "pat.nguyen@acme.com",
            "assignee_email": "kim.lee@acme.com",
        }
    )
    items = mine_account_people(repo, repo.get_account("acct:acme"))
    emails = {row["email"]: row for row in items}
    assert "noreply@acme.com" not in emails
    assert "you@example.com" not in emails
    pat = emails["pat.nguyen@acme.com"]
    assert pat["name"] == "Pat Nguyen"
    assert "email" in pat["sources"]
    assert "calendar" in pat["sources"]
    assert "ticket" in pat["sources"]
    assert pat["hits"] >= 3
    assert emails["kim.lee@acme.com"]["name"] == "Kim Lee"
    assert pat["phone"]


def test_create_person_dedupes_email_and_keeps_phone(client, repo):
    repo.create_account({"name": "Acme", "slug": "acme", "abbr": "ACME", "color": "#0B3D91"})
    first = client.post(
        "/api/people",
        json={
            "account_id": "acct:acme",
            "name": "Pat Nguyen",
            "email": "pat@acme.com",
            "kind": "customer",
        },
    )
    assert first.status_code == 200
    pid = first.json()["_id"]
    again = client.post(
        "/api/people",
        json={
            "account_id": "acct:acme",
            "name": "Pat Nguyen",
            "email": "pat@acme.com",
            "phone": "312-555-0100",
            "title": "DBA",
            "group": "Platform",
            "job_description": "Owns the clusters.",
        },
    )
    assert again.status_code == 200
    assert again.json()["_id"] == pid
    assert again.json()["phone"] == "312-555-0100"
    assert again.json()["title"] == "DBA"
    people = client.get("/api/people", params={"account_id": "acct:acme"}).json()["items"]
    assert len(people) == 1
    mined = client.get("/api/accounts/acct:acme/people-mine")
    assert mined.status_code == 200
    missing = client.get("/api/accounts/acct:nope/people-mine")
    assert missing.status_code == 404
