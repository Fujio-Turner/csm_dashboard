from __future__ import annotations

from csm_dashboard.ingest.route import route_event


def _acct(slug, **kwargs):
    row = {"account_id": f"acct:{slug}", "domains": [], "connectors": {}}
    row.update(kwargs)
    return row


def test_route_jira_project():
    accounts = [
        _acct("acme", connectors={"jira": {"project_keys": ["ACME"]}}),
        _acct("nwin", connectors={"jira": {"project_keys": ["NWIN"]}}),
    ]
    aid = route_event(accounts, {"kind": "ticket", "payload": {"project_key": "ACME"}})
    assert aid == "acct:acme"


def test_route_salesforce_account():
    accounts = [
        _acct("acme", connectors={"salesforce": {"account_ids": ["001ACME0001"]}}),
        _acct("nwin", connectors={"salesforce": {"account_ids": ["001NWIN0001"]}}),
    ]
    aid = route_event(
        accounts,
        {"kind": "salesforce_opportunity", "payload": {"sf_account_id": "001ACME0001"}},
    )
    assert aid == "acct:acme"


def test_route_ambiguous_domain():
    accounts = [
        _acct("a", domains=["shared.com"]),
        _acct("b", domains=["shared.com"]),
    ]
    aid = route_event(
        accounts,
        {"kind": "email", "payload": {"from_addr": "x@shared.com", "to_addrs": [], "cc_addrs": []}},
    )
    assert aid == ""


def test_route_skips_operator_domain():
    accounts = [
        _acct("acme", domains=["acme.com"]),
        _acct("nwin", domains=["northwind.example"]),
    ]
    aid = route_event(
        accounts,
        {
            "kind": "email",
            "payload": {"from_addr": "bob@abc.com", "to_addrs": ["pat@acme.com"], "cc_addrs": []},
        },
        operator_domains={"abc.com"},
    )
    assert aid == "acct:acme"
    only_us = route_event(
        accounts,
        {
            "kind": "email",
            "payload": {"from_addr": "bob@abc.com", "to_addrs": ["jordan@abc.com"], "cc_addrs": []},
        },
        operator_domains={"abc.com"},
    )
    assert only_us == ""
