from __future__ import annotations

import pytest

from csm_dashboard.ingest.identity import activity_doc_id


def test_account_rows_skips_other_books(repo):
    repo.create_account({"name": "Acme", "slug": "acme", "abbr": "ACME", "color": "#0B3D91"})
    repo.create_account({"name": "North", "slug": "nwin", "abbr": "NWIN", "color": "#14532d"})
    repo.create_person({"account_id": "acct:acme", "name": "Pat"})
    repo.create_person({"account_id": "acct:nwin", "name": "Kim"})
    only = repo._account_rows("people", "acct:acme")
    assert len(only) == 1
    assert only[0]["name"] == "Pat"
    counts = repo.account_input_counts("acct:acme")
    assert counts["people"] == 1
    assert counts["orgchart"] == 1
    assert counts["chat"] == counts["slack"] + counts["teams"]


def test_create_person_refreshes_people_badge(repo):
    repo.create_account({"name": "Acme", "slug": "acme", "abbr": "ACME", "color": "#0B3D91"})
    repo.refresh_input_counts("acct:acme")
    assert repo.account_input_counts("acct:acme")["people"] == 0
    repo.create_person({"account_id": "acct:acme", "name": "Pat Nguyen", "kind": "customer"})
    counts = repo.account_input_counts("acct:acme")
    assert counts["people"] == 1
    assert counts["orgchart"] == 1
    assert counts["accountteam"] == 0
    repo.create_person(
        {"account_id": "acct:acme", "name": "Jordan Lee", "kind": "account_team", "role": "csm"}
    )
    counts = repo.account_input_counts("acct:acme")
    assert counts["people"] == 2
    assert counts["orgchart"] == 1
    assert counts["accountteam"] == 1


def test_expand_account_heals_stale_people_badge(repo):
    repo.create_account({"name": "Acme", "slug": "acme", "abbr": "ACME", "color": "#0B3D91"})
    repo.refresh_input_counts("acct:acme")
    repo.store.save(
        "people",
        "person:stale1",
        {
            "type": "person",
            "account_id": "acct:acme",
            "name": "Pat Nguyen",
            "kind": "customer",
            "role": "other",
            "email": "pat@acme.com",
        },
    )
    raw = repo.get_account("acct:acme") or {}
    assert (raw.get("input_counts") or {}).get("people") == 0
    expanded = repo.expand_account(raw)
    assert expanded["input_counts"]["people"] == 1
    assert expanded["input_counts"]["orgchart"] == 1
    healed = repo.get_account("acct:acme") or {}
    assert (healed.get("input_counts") or {}).get("people") == 1


def test_coverage_defaults_and_takeover_requires_owner(repo):
    from csm_dashboard.storage.repo import normalize_coverage

    bare = repo.create_account({"name": "Acme", "slug": "acme", "abbr": "ACME", "color": "#0B3D91"})
    assert bare["coverage"]["mode"] == "view"
    assert bare["coverage"]["lookback_days"] == 14
    taken = repo.create_account(
        {
            "name": "North",
            "slug": "nwin",
            "abbr": "NWIN",
            "color": "#14532d",
            "coverage": {
                "mode": "takeover",
                "previous_owner_email": "jane@example.com",
                "lookback_days": 90,
            },
        }
    )
    assert taken["coverage"]["mode"] == "takeover"
    assert taken["coverage"]["previous_owner_email"] == "jane@example.com"
    assert taken["coverage"]["lookback_days"] == 90
    assert taken["coverage"]["feeds"] == []
    fed = repo.create_account(
        {
            "name": "Globex",
            "slug": "globex",
            "abbr": "GLX",
            "color": "#7B1E3A",
            "coverage": {"mode": "view", "feeds": ["google_mail", "google_cal", "nope"]},
        }
    )
    assert fed["coverage"]["feeds"] == ["google_mail", "google_cal"]
    fresh = repo.create_account(
        {
            "name": "Brand",
            "slug": "brand",
            "abbr": "BRAND",
            "color": "#0B3D91",
            "coverage": {"mode": "new"},
        }
    )
    assert fresh["coverage"]["mode"] == "new"
    assert fresh["coverage"]["lookback_days"] == 14
    assert fresh["coverage"]["previous_owner_email"] == ""
    assert fresh["coverage"]["mine_people"] is True
    assert fresh["coverage"]["refresh_minutes"] == 5
    with pytest.raises(ValueError, match="previous_owner_email"):
        normalize_coverage({"mode": "takeover"}, require_owner=True)
    with pytest.raises(ValueError, match="until"):
        normalize_coverage(
            {"mode": "covering", "previous_owner_email": "jane@example.com"},
            require_owner=True,
        )


def test_reattach_unassigned_email_by_domain(repo):
    repo.create_account({"name": "Acme", "slug": "acme", "abbr": "ACME", "color": "#0B3D91", "domains": ["acme.com"]})
    repo.upsert_email(
        {
            "from_addr": "pat@acme.com",
            "to_addrs": ["you@example.com"],
            "subject": "Hello",
            "body_text": "hi",
            "message_id": "<unassigned-acme@test>",
            "sent_at": "2026-09-01T12:00:00Z",
        }
    )
    counts = repo.reattach_unassigned("acct:acme")
    assert counts["emails"] == 1
    rows, _ = repo.page_emails("acct:acme")
    assert any(r.get("subject") == "Hello" for r in rows)


def test_create_account_and_abbr_lookup(repo):
    doc = repo.create_account({"name": "Acme", "slug": "acme", "abbr": "acme", "color": "#0B3D91"})
    assert doc["account_id"] == "acct:acme"
    assert doc["abbr"] == "ACME"
    found = repo.get_account_by_abbr("acme")
    assert found["_id"] == "acct:acme"


def test_slug_immutable(repo):
    repo.create_account({"name": "Acme", "slug": "acme", "abbr": "ACME", "color": "#0B3D91"})
    with pytest.raises(PermissionError):
        repo.patch_account("acct:acme", {"slug": "other"})


def test_activity_source_ref_stable(repo):
    first = repo.upsert_activity_by_source_ref(
        {"account_id": "acct:acme", "kind": "ticket_updated", "title": "one", "source_ref": "jira:ticket:ACME-12:updated:1"}
    )
    second = repo.upsert_activity_by_source_ref(
        {"account_id": "acct:acme", "kind": "ticket_updated", "title": "two", "source_ref": "jira:ticket:ACME-12:updated:1"}
    )
    assert first["_id"] == second["_id"] == activity_doc_id("jira:ticket:ACME-12:updated:1")
    assert repo.store.count("activities") == 1
    assert second["title"] == "two"


def test_person_functions_and_activity_tag(repo):
    repo.create_account({"name": "Acme", "slug": "acme", "abbr": "ACME", "color": "#0B3D91"})
    proj = repo.create_project({"_id": "proj:acme-scan", "account_id": "acct:acme", "name": "Scan"})
    person = repo.create_person(
        {
            "account_id": "acct:acme",
            "name": "Pat",
            "functions": ["ops", "DBA", "legal"],
            "project_ids": [proj["_id"]],
        }
    )
    assert person["functions"] == ["Ops", "DBA"]
    act = repo.add_operator_activity(
        {"account_id": "acct:acme", "kind": "note", "title": "Call Pat", "project_id": ""}
    )
    tagged = repo.patch_activity(act["_id"], {"project_id": proj["_id"]})
    assert tagged["project_id"] == proj["_id"]
    listed = repo.list_people("acct:acme", function="Ops")
    assert listed[0]["_id"] == person["_id"]


def test_chat_title_and_bookmark(repo):
    chat = repo.save_chat({"account_id": "acct:acme", "title": "Account coach", "messages": []})
    chat = repo.save_chat(
        {**chat, "messages": [{"role": "user", "content": "What is at risk?"}]},
        chat_id=chat["_id"],
    )
    assert chat["title"] == "What is at risk?"
    starred = repo.patch_chat(chat["_id"], {"bookmarked": True})
    assert starred["bookmarked"] is True
    listed = repo.list_chats("acct:acme")
    assert listed[0]["_id"] == chat["_id"]
    assert listed[0]["bookmarked"] is True


def test_email_thread_attach(repo):
    repo.upsert_email(
        {
            "account_id": "acct:acme",
            "message_id": "<a@x>",
            "from_addr": "a@acme.com",
            "to_addrs": ["b@example.com"],
            "subject": "Hello",
            "sent_at": "2026-08-17T10:00:00Z",
            "snippet": "hi",
            "body_text": "hi",
        }
    )
    repo.upsert_email(
        {
            "account_id": "acct:acme",
            "message_id": "<b@x>",
            "in_reply_to": "<a@x>",
            "from_addr": "b@example.com",
            "to_addrs": ["a@acme.com"],
            "subject": "Re: Hello",
            "sent_at": "2026-08-17T11:00:00Z",
            "snippet": "yo",
            "body_text": "yo",
        }
    )
    assert repo.store.count("threads") == 1
    assert repo.store.count("emails") == 2
