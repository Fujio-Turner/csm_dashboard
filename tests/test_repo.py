from __future__ import annotations

import pytest

from csm_dashboard.ingest.identity import activity_doc_id


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
