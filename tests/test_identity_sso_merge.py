from __future__ import annotations

from csm_dashboard.ingest.identity import email_doc_id, thread_doc_id
from csm_dashboard.ingest.merge import merge_account_connectors, merge_operator
from csm_dashboard.sso import dashboard_url, infer_provider, normalize_org_url, public_sso


def test_email_and_thread_ids_without_message_id():
    doc = {
        "from_addr": "pat@acme.com",
        "sent_at": "2026-08-20T12:00:00Z",
        "subject": "Re: ACME-12 workaround",
        "body_bytes": 12,
        "to_addrs": ["jordan@example.com"],
    }
    eid = email_doc_id(doc)
    assert eid.startswith("em:")
    assert email_doc_id({"message_id": "<a@b>"}) != eid
    tid = thread_doc_id(doc)
    assert tid.startswith("thr:")
    assert thread_doc_id({"in_reply_to": "<root@x>"}) != tid
    assert thread_doc_id({"references": "<root@x> <next@x>"}) == thread_doc_id({"references": "<root@x>"})
    assert thread_doc_id({"message_id": "<solo@x>"}).startswith("thr:")


def test_merge_keeps_operator_and_sources():
    incoming = {"summary": "new", "operator": {"triage": "x"}}
    existing = {"summary": "old", "operator": {"triage": "keep", "ignore": True}}
    merged = merge_operator(existing, incoming)
    assert merged["operator"]["triage"] == "keep"
    assert merge_operator(None, incoming)["summary"] == "new"
    acct = merge_account_connectors(
        {"sources": {"jira": {"fetched_at": "a"}}},
        {"sources": {"slack": {"fetched_at": "b"}}},
    )
    assert "jira" in acct["sources"] and "slack" in acct["sources"]


def test_sso_normalize_and_providers():
    assert normalize_org_url("") == ""
    assert normalize_org_url("idp.example.com") == "https://idp.example.com"
    assert infer_provider("https://foo.okta.com") == "okta"
    assert infer_provider("https://login.microsoftonline.com") == "microsoft"
    assert infer_provider("https://accounts.google.com") == "google"
    assert infer_provider("https://other.example") == "custom"
    assert dashboard_url("") == ""
    assert dashboard_url("https://foo.okta.com").endswith("/app/UserHome")
    assert dashboard_url("https://foo.okta.com/app/UserHome") == "https://foo.okta.com/app/UserHome"
    pub = public_sso({"sso": {"org_url": "https://foo.okta.com"}}, identity={"client_id": "0oa", "access_token": "t", "email": "a@b", "name": "A"})
    assert pub["signed_in"] is True
    assert pub["configured"] is True
    assert pub["provider"] == "okta"
