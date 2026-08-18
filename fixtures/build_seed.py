#!/usr/bin/env python3
"""Generate fixtures/seed/*.json — run from repo root: python3 fixtures/build_seed.py"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SEED = ROOT / "seed"
sys.path.insert(0, str(ROOT.parent / "src"))

from csm_dashboard.ingest.identity import activity_doc_id, email_doc_id, thread_doc_id  # noqa: E402


def dump(name: str, rows: list) -> None:
    SEED.mkdir(parents=True, exist_ok=True)
    (SEED / name).write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")


def account(slug, name, abbr, color, domains, health, renewal, arr, team, next_action, jira, slack):
    return {
        "_id": f"acct:{slug}",
        "type": "account",
        "account_id": f"acct:{slug}",
        "name": name,
        "abbr": abbr,
        "slug": slug,
        "color": color,
        "domains": domains,
        "connectors": {
            "jira": {"project_keys": [jira], "jql": f"project = {jira} ORDER BY updated DESC"},
            "slack": {"channel_ids": [slack]},
            "calendar": {"attendee_domains": domains},
            "mail": {"labels": []},
        },
        "health": {
            "score": health,
            "score_max": 100,
            "scored_by": "rules",
            "rules_score": health,
            "status": "watch",
            "breakdown": [],
            "override": None,
        },
        "contract": {
            "source": "operator",
            "renewal_on": renewal,
            "start_on": "2024-11-01",
            "arr": arr,
            "currency": "USD",
            "tier": "enterprise",
        },
        "team": team,
        "next_action": next_action,
        "stats": {},
        "sources": {},
        "created_at": "2026-08-01T00:00:00Z",
        "updated_at": "2026-08-17T15:00:00Z",
    }


def person(_id, account_id, kind, name, email, title, role):
    return {
        "_id": _id,
        "type": "person",
        "account_id": account_id,
        "kind": kind,
        "name": name,
        "email": email,
        "title": title,
        "role": role,
        "external_ids": {},
        "sources": {},
        "created_at": "2026-08-01T00:00:00Z",
        "updated_at": "2026-08-01T00:00:00Z",
    }


def project(_id, account_id, name, kind, status, owner, start, end, epic, summary):
    return {
        "_id": _id,
        "type": "project",
        "account_id": account_id,
        "name": name,
        "kind": kind,
        "status": status,
        "owner_person_id": owner,
        "start_on": start,
        "end_on": end,
        "jira_epic": epic,
        "summary": summary,
        "sources": {},
        "created_at": "2026-07-01T00:00:00Z",
        "updated_at": "2026-08-17T00:00:00Z",
    }


def ticket(key, account_id, summary, status, pri, updated, comments, created="2026-08-10T12:00:00Z"):
    return {
        "_id": f"tkt:jira:{key}",
        "type": "ticket",
        "account_id": account_id,
        "source": "jira",
        "key": key,
        "external_id": key.split("-")[-1],
        "summary": summary,
        "status": status,
        "status_raw": status.replace("_", " ").title(),
        "priority": pri,
        "priority_raw": {"p1": "Highest", "p2": "High", "p3": "Medium", "p4": "Low"}[pri],
        "issue_type": "bug" if pri in {"p1", "p2"} else "task",
        "assignee_email": "tam@example.com",
        "reporter_email": "pat@example.com",
        "url": f"https://example.atlassian.net/browse/{key}",
        "project_key": key.split("-")[0],
        "labels": [],
        "created_at": created,
        "updated_at": updated,
        "resolved_at": "2026-08-16T00:00:00Z" if status == "done" else "",
        "comment_count": len(comments),
        "last_comment_at": comments[-1]["at"] if comments else "",
        "comments": comments,
        "operator": {"triage": "", "ignore": False},
        "sources": {"jira": {"fetched_at": "2026-08-17T15:00:00Z"}},
    }


def email_row(account_id, message_id, in_reply_to, frm, to, subject, sent, snippet, body, direction="inbound"):
    doc = {
        "type": "email",
        "account_id": account_id,
        "direction": direction,
        "message_id": message_id,
        "in_reply_to": in_reply_to,
        "references": in_reply_to,
        "from_addr": frm,
        "to_addrs": [to],
        "cc_addrs": [],
        "subject": subject,
        "sent_at": sent,
        "snippet": snippet,
        "body_text": body,
        "body_bytes": len(body.encode("utf-8")),
        "has_attachments": False,
        "operator": {"unread": direction == "inbound"},
        "sources": {"stub": {"fetched_at": "2026-08-17T15:00:00Z"}},
    }
    doc["thread_id"] = thread_doc_id(doc)
    doc["_id"] = email_doc_id(doc)
    return doc


def slack_channel(account_id, cid, name, topic):
    return {
        "type": "slack_channel",
        "account_id": account_id,
        "channel_id": cid,
        "name": name,
        "is_private": False,
        "topic": topic,
    }


def slack_msg(account_id, cid, ts, user, name, text, thread_ts=""):
    return {
        "type": "slack_message",
        "account_id": account_id,
        "channel_id": cid,
        "ts": ts,
        "thread_ts": thread_ts,
        "user": user,
        "user_name": name,
        "text": text,
        "permalink": f"https://slack.com/archives/{cid}/p{ts.replace('.', '')}",
        "operator": {"pin": False},
        "sources": {"stub": {"fetched_at": "2026-08-17T15:00:00Z"}},
    }


def cal(account_id, ext, title, start, end, email, name):
    return {
        "type": "calendar_event",
        "account_id": account_id,
        "provider": "stub",
        "external_id": ext,
        "title": title,
        "start_at": start,
        "end_at": end,
        "attendees": [{"email": email, "name": name}],
        "location": "Meet",
        "operator": {"prep_note": ""},
        "sources": {},
    }


def action(_id, account_id, title, kind, status, due, owner, label):
    return {
        "_id": _id,
        "type": "action_item",
        "account_id": account_id,
        "title": title,
        "kind": kind,
        "status": status,
        "due_on": due,
        "owner_person_id": owner,
        "owner_label": label,
        "source": "operator",
        "linked": {},
        "created_by": "you",
        "created_at": "2026-08-10T00:00:00Z",
        "completed_at": "2026-08-16T00:00:00Z" if status == "done" else "",
    }


def note(_id, account_id, body):
    return {
        "_id": _id,
        "type": "note",
        "account_id": account_id,
        "ref": {"collection": "accounts", "id": account_id},
        "body": body,
        "author": "you",
        "created_at": "2026-08-12T00:00:00Z",
    }


def main() -> None:
    accounts = [
        account(
            "acme",
            "Acme Corporation",
            "ACME",
            "#0B3D91",
            ["acme.com", "acme.co.uk"],
            62,
            "2026-11-01",
            240000,
            {
                "account": [
                    {"person_id": "person:ae01", "role": "ae"},
                    {"person_id": "person:csm01", "role": "csm"},
                    {"person_id": "person:tam01", "role": "tam"},
                ],
                "ps": [{"person_id": "person:ps01", "role": "ps_lead"}],
            },
            {"kind": "email", "due_on": "2026-08-18", "title": "Send ACME-12 workaround", "action_id": "actn:acme-fw"},
            "ACME",
            "C0ACME1",
        ),
        account(
            "northwind",
            "Northwind Traders",
            "NWIN",
            "#1B5E20",
            ["northwind.example"],
            28,
            "2026-09-05",
            180000,
            {
                "account": [
                    {"person_id": "person:ae01", "role": "ae"},
                    {"person_id": "person:csm01", "role": "csm"},
                ],
                "ps": [{"person_id": "person:ps02", "role": "ps_consultant"}],
            },
            {"kind": "call", "due_on": "2026-08-10", "title": "Reach champion", "action_id": "actn:nwin-call"},
            "NWIN",
            "C0NWIN1",
        ),
        account(
            "globex",
            "Globex Industrial",
            "GLX",
            "#7B1E3A",
            ["globex.example"],
            84,
            "2027-03-01",
            96000,
            {
                "account": [
                    {"person_id": "person:ae02", "role": "ae"},
                    {"person_id": "person:csm01", "role": "csm"},
                ],
                "ps": [{"person_id": "person:ps01", "role": "ps_lead"}],
            },
            {"kind": "meeting", "due_on": "2026-08-20", "title": "Kickoff recap", "action_id": "actn:glx-recap"},
            "GLX",
            "C0GLX1",
        ),
    ]
    dump("accounts.json", accounts)

    people = [
        person("person:acme-pat", "acct:acme", "customer", "Pat Nguyen", "pat.nguyen@acme.com", "VP Operations", "champion"),
        person("person:acme-lee", "acct:acme", "customer", "Sam Ortiz", "sam.ortiz@acme.com", "Warehouse lead", "technical"),
        person("person:nwin-kim", "acct:northwind", "customer", "Kim Hale", "kim.hale@northwind.example", "IT Director", "champion"),
        person("person:nwin-rob", "acct:northwind", "customer", "Rob Singh", "rob.singh@northwind.example", "CFO", "economic_buyer"),
        person("person:glx-ava", "acct:globex", "customer", "Ava Chen", "ava.chen@globex.example", "Plant manager", "champion"),
        person("person:ae01", "acct:acme", "account_team", "Riley Park", "riley@example.com", "Account Executive", "ae"),
        person("person:ae02", "acct:globex", "account_team", "Morgan Diaz", "morgan@example.com", "Account Executive", "ae"),
        person("person:csm01", "acct:acme", "account_team", "Jordan Lee", "jordan@example.com", "CSM", "csm"),
        person("person:tam01", "acct:acme", "account_team", "Chris Vale", "chris@example.com", "TAM", "tam"),
        person("person:ps01", "acct:acme", "ps_team", "Alex Rivera", "alex@example.com", "PS lead", "ps_lead"),
        person("person:ps02", "acct:northwind", "ps_team", "Quinn Brooks", "quinn@example.com", "PS consultant", "ps_consultant"),
        person("person:nwin-csm", "acct:northwind", "account_team", "Jordan Lee", "jordan@example.com", "CSM", "csm"),
        person("person:glx-csm", "acct:globex", "account_team", "Jordan Lee", "jordan@example.com", "CSM", "csm"),
        person("person:glx-ps", "acct:globex", "ps_team", "Alex Rivera", "alex@example.com", "PS lead", "ps_lead"),
    ]
    dump("people.json", people)

    dump(
        "projects.json",
        [
            project("proj:acme-scan", "acct:acme", "Warehouse scan rollout", "implementation", "active", "person:ps01", "2026-07-01", "2026-09-30", "ACME-100", "Handheld scanners in 4 DCs."),
            project("proj:nwin-renew", "acct:northwind", "Renewal rescue", "qbr", "blocked", "person:ps02", "2026-07-15", "2026-09-05", "NWIN-80", "Champion going dark before renewal."),
            project("proj:glx-onboard", "acct:globex", "Plant onboarding", "implementation", "active", "person:ps01", "2026-08-10", "2026-10-15", "GLX-10", "Kickoff last week. Clean start."),
        ],
    )

    tickets = [
        ticket("ACME-12", "acct:acme", "Scanner firmware bricks on OS 14", "in_progress", "p1", "2026-08-17T09:00:00Z", [{"at": "2026-08-17T08:50:00Z", "author": "pat.nguyen@acme.com", "text": "Still dying after 20 minutes on the DC3 floor."}]),
        ticket("ACME-18", "acct:acme", "SSO timeout after 8 hours", "open", "p2", "2026-08-16T11:00:00Z", []),
        ticket("ACME-21", "acct:acme", "Add scan-to-ERP mapping", "waiting", "p3", "2026-08-14T10:00:00Z", []),
        ticket("ACME-9", "acct:acme", "Label printer driver", "done", "p3", "2026-08-12T10:00:00Z", []),
        ticket("ACME-30", "acct:acme", "Training videos for DC2", "open", "p4", "2026-08-15T10:00:00Z", []),
        ticket("ACME-31", "acct:acme", "Nightly inventory job slow", "open", "p2", "2026-08-17T07:00:00Z", []),
        ticket("NWIN-4", "acct:northwind", "Auth outage on Friday", "open", "p1", "2026-08-15T18:00:00Z", [{"at": "2026-08-15T18:10:00Z", "author": "kim.hale@northwind.example", "text": "We missed the cutoff. Call me."}]),
        ticket("NWIN-7", "acct:northwind", "Invoice export wrong currency", "open", "p1", "2026-08-16T12:00:00Z", []),
        ticket("NWIN-11", "acct:northwind", "User provisioning lag", "waiting", "p2", "2026-08-08T12:00:00Z", []),
        ticket("NWIN-12", "acct:northwind", "SSO mapping for contractors", "open", "p2", "2026-08-14T12:00:00Z", []),
        ticket("NWIN-19", "acct:northwind", "QBR deck numbers", "open", "p3", "2026-08-13T12:00:00Z", []),
        ticket("NWIN-2", "acct:northwind", "Sandbox refresh", "cancelled", "p4", "2026-08-01T12:00:00Z", []),
        ticket("GLX-3", "acct:globex", "Kickoff environment", "done", "p3", "2026-08-12T12:00:00Z", []),
        ticket("GLX-5", "acct:globex", "Add second plant code", "open", "p3", "2026-08-16T12:00:00Z", []),
        ticket("GLX-6", "acct:globex", "Training date hold", "open", "p4", "2026-08-17T12:00:00Z", []),
        ticket("GLX-8", "acct:globex", "VPN allowlist", "in_progress", "p2", "2026-08-17T13:00:00Z", []),
        ticket("GLX-9", "acct:globex", "Welcome packet typos", "done", "p4", "2026-08-11T12:00:00Z", []),
    ]
    dump("tickets.json", tickets)

    emails = []
    # ACME thread
    chain = [
        ("<acme-root@acme.com>", "", "pat.nguyen@acme.com", "jordan@example.com", "ACME-12 workaround", "2026-08-15T14:00:00Z", "Scanner died again.", "The handheld still dies after 20 minutes on OS 14."),
        ("<acme-2@example.com>", "<acme-root@acme.com>", "jordan@example.com", "pat.nguyen@acme.com", "Re: ACME-12 workaround", "2026-08-15T16:00:00Z", "We have a firmware pin.", "Pat — we have a firmware pin. TAM will send steps tonight.", "outbound"),
        ("<acme-3@acme.com>", "<acme-2@example.com>", "pat.nguyen@acme.com", "jordan@example.com", "Re: ACME-12 workaround", "2026-08-16T09:00:00Z", "Tried it on DC1.", "Tried the pin on DC1. DC3 still fails."),
        ("<acme-4@example.com>", "<acme-3@acme.com>", "jordan@example.com", "pat.nguyen@acme.com", "Re: ACME-12 workaround", "2026-08-16T18:00:00Z", "New build tomorrow.", "New build tomorrow morning. Booking TAM.", "outbound"),
        ("<acme-5@acme.com>", "<acme-4@example.com>", "pat.nguyen@acme.com", "jordan@example.com", "Re: ACME-12 workaround", "2026-08-17T14:22:00Z", "The handheld still dies…", "The handheld still dies after 20 minutes on the DC3 floor. Need a date."),
    ]
    for item in chain:
        mid, irt, frm, to, sub, sent, snip, body, *rest = item
        direction = rest[0] if rest else "inbound"
        emails.append(email_row("acct:acme", mid, irt, frm, to, sub, sent, snip, body, direction))
    emails.append(
        email_row(
            "acct:acme",
            "<acme-sso@acme.com>",
            "",
            "sam.ortiz@acme.com",
            "jordan@example.com",
            "SSO timeout after 8 hours",
            "2026-08-16T11:30:00Z",
            "Night shift gets kicked.",
            "Night shift gets kicked after 8 hours. Related to ACME-18?",
        )
    )
    nwin_chain = [
        ("<nwin-root@northwind.example>", "", "kim.hale@northwind.example", "jordan@example.com", "Friday auth outage", "2026-08-15T19:00:00Z", "We missed cutoff.", "We missed the cutoff. This is the second P1 this month."),
        ("<nwin-2@example.com>", "<nwin-root@northwind.example>", "jordan@example.com", "kim.hale@northwind.example", "Re: Friday auth outage", "2026-08-16T08:00:00Z", "Incident doc attached.", "Kim — incident doc is in the ticket. Can we talk Tuesday?", "outbound"),
        ("<nwin-3@northwind.example>", "<nwin-2@example.com>", "kim.hale@northwind.example", "jordan@example.com", "Re: Friday auth outage", "2026-08-16T20:00:00Z", "I am out until the 28th.", "I am out until the 28th. Rob can talk numbers."),
        ("<nwin-4@northwind.example>", "<nwin-3@example.com>", "rob.singh@northwind.example", "jordan@example.com", "Re: Friday auth outage", "2026-08-17T10:00:00Z", "Renewal is at risk.", "If auth is this shaky the renewal is at risk."),
    ]
    for item in nwin_chain:
        mid, irt, frm, to, sub, sent, snip, body, *rest = item
        emails.append(email_row("acct:northwind", mid, irt, frm, to, sub, sent, snip, body, rest[0] if rest else "inbound"))
    glx_chain = [
        ("<glx-root@globex.example>", "", "ava.chen@globex.example", "jordan@example.com", "Kickoff recap", "2026-08-11T16:00:00Z", "Great start.", "Great start yesterday. Plant 2 wants a date."),
        ("<glx-2@example.com>", "<glx-root@globex.example>", "jordan@example.com", "ava.chen@globex.example", "Re: Kickoff recap", "2026-08-12T09:00:00Z", "Drafting the plan.", "Drafting the plan. PS will hold Thursday.", "outbound"),
        ("<glx-3@globex.example>", "<glx-2@example.com>", "ava.chen@globex.example", "jordan@example.com", "Re: Kickoff recap", "2026-08-13T15:00:00Z", "Thursday works.", "Thursday works. Sending badge list."),
        ("<glx-4@example.com>", "<glx-3@globex.example>", "jordan@example.com", "ava.chen@globex.example", "Re: Kickoff recap", "2026-08-14T11:00:00Z", "Got the list.", "Got the list. See you Thursday.", "outbound"),
    ]
    for item in glx_chain:
        mid, irt, frm, to, sub, sent, snip, body, *rest = item
        emails.append(email_row("acct:globex", mid, irt, frm, to, sub, sent, snip, body, rest[0] if rest else "inbound"))
    dump("emails.json", emails)

    threads = {}
    for em in emails:
        tid = em["thread_id"]
        th = threads.setdefault(
            tid,
            {
                "_id": tid,
                "type": "thread",
                "account_id": em["account_id"],
                "subject": em["subject"],
                "last_at": em["sent_at"],
                "message_count": 0,
                "participants": [],
                "operator": {"unread": True, "pinned": False},
            },
        )
        th["message_count"] += 1
        if em["sent_at"] >= th["last_at"]:
            th["last_at"] = em["sent_at"]
            th["subject"] = em["subject"]
        parts = set(th["participants"])
        parts.add(em["from_addr"])
        parts.update(em["to_addrs"])
        th["participants"] = sorted(parts)
    dump("threads.json", list(threads.values()))

    channels = [
        slack_channel("acct:acme", "C0ACME1", "acme-success", "ACME production"),
        slack_channel("acct:northwind", "C0NWIN1", "northwind-success", "Northwind"),
        slack_channel("acct:globex", "C0GLX1", "globex-onboard", "Globex onboarding"),
    ]
    dump("slack_channels.json", channels)

    slack = []
    base = 1723900000
    acme_texts = [
        "Scanner died again in DC3",
        "TAM is looking at the logs",
        "OS 14 image went out last night",
        "Can we get a date for the pin?",
        "DC1 is fine, DC3 is the problem",
        "QBR is on the calendar",
        "Pat prefers email before Slack",
        "Firmware build tagged 14.2-rc2",
        "Need a war room if it fails again",
        "Ack, watching the channel",
    ]
    for i, text in enumerate(acme_texts):
        ts = f"{base + i}.000100"
        slack.append(slack_msg("acct:acme", "C0ACME1", ts, "U0PAT" if i % 2 == 0 else "U0JOR", "pat.nguyen" if i % 2 == 0 else "jordan", text))
    slack.append(slack_msg("acct:acme", "C0ACME1", f"{base + 20}.000200", "U0PAT", "pat.nguyen", "thread: still failing", f"{base}.000100"))
    for i, text in enumerate(["Anyone seen Kim?", "She is dark since the outage", "Renewal is 19 days out", "Rob wants numbers", "I pinged twice", "Need exec sponsor", "P1 still open", "Call recap?"]):
        slack.append(slack_msg("acct:northwind", "C0NWIN1", f"{base + 100 + i}.000100", "U0KIM" if i == 0 else "U0JOR", "kim.hale" if i == 0 else "jordan", text))
    for i, text in enumerate(["Kickoff went well", "Badge list incoming", "Plant 2 wants training", "VPN ticket opened", "See you Thursday", "Notes in the drive", "No blockers", "Nice start"]):
        slack.append(slack_msg("acct:globex", "C0GLX1", f"{base + 200 + i}.000100", "U0AVA" if i % 2 == 0 else "U0JOR", "ava.chen" if i % 2 == 0 else "jordan", text))
    dump("slack_messages.json", slack)

    dump(
        "calendar_events.json",
        [
            cal("acct:acme", "evt-acme-qbr", "ACME QBR", "2026-08-17T16:00:00Z", "2026-08-17T17:00:00Z", "pat.nguyen@acme.com", "Pat Nguyen"),
            cal("acct:acme", "evt-acme-tam", "ACME TAM working session", "2026-08-18T15:00:00Z", "2026-08-18T16:00:00Z", "pat.nguyen@acme.com", "Pat Nguyen"),
            cal("acct:acme", "evt-acme-old", "ACME weekly", "2026-08-03T16:00:00Z", "2026-08-03T16:30:00Z", "pat.nguyen@acme.com", "Pat Nguyen"),
            cal("acct:acme", "evt-acme-ps", "Scan rollout checkpoint", "2026-08-20T14:00:00Z", "2026-08-20T15:00:00Z", "sam.ortiz@acme.com", "Sam Ortiz"),
            cal("acct:northwind", "evt-nwin-old", "NWIN monthly", "2026-07-02T16:00:00Z", "2026-07-02T17:00:00Z", "kim.hale@northwind.example", "Kim Hale"),
            cal("acct:northwind", "evt-nwin-missed", "NWIN incident review", "2026-08-10T16:00:00Z", "2026-08-10T16:30:00Z", "kim.hale@northwind.example", "Kim Hale"),
            cal("acct:northwind", "evt-nwin-renew", "NWIN renewal", "2026-08-25T16:00:00Z", "2026-08-25T17:00:00Z", "rob.singh@northwind.example", "Rob Singh"),
            cal("acct:globex", "evt-glx-kick", "GLX kickoff", "2026-08-10T16:00:00Z", "2026-08-10T18:00:00Z", "ava.chen@globex.example", "Ava Chen"),
            cal("acct:globex", "evt-glx-plant", "GLX plant walk", "2026-08-14T16:00:00Z", "2026-08-14T17:00:00Z", "ava.chen@globex.example", "Ava Chen"),
            cal("acct:globex", "evt-glx-next", "GLX weekly", "2026-08-21T16:00:00Z", "2026-08-21T16:30:00Z", "ava.chen@globex.example", "Ava Chen"),
        ],
    )

    dump(
        "action_items.json",
        [
            action("actn:acme-fw", "acct:acme", "Send firmware workaround and book TAM call", "email", "open", "2026-08-18", "person:csm01", "Jordan Lee"),
            action("actn:acme-qbr", "acct:acme", "Prep QBR numbers", "internal", "open", "2026-08-17", "person:csm01", "Jordan Lee"),
            action("actn:acme-done", "acct:acme", "Ship training videos", "ticket", "done", "2026-08-12", "person:ps01", "Alex Rivera"),
            action("actn:nwin-call", "acct:northwind", "Reach champion", "call", "open", "2026-08-10", "person:csm01", "Jordan Lee"),
            action("actn:nwin-p1", "acct:northwind", "Close Friday auth P1", "ticket", "open", "2026-08-16", "person:csm01", "Jordan Lee"),
            action("actn:nwin-exec", "acct:northwind", "Brief exec sponsor", "meeting", "open", "2026-08-14", "person:ae01", "Riley Park"),
            action("actn:nwin-renew", "acct:northwind", "Renewal commercial options", "internal", "open", "2026-08-12", "person:csm01", "Jordan Lee"),
            action("actn:glx-recap", "acct:globex", "Kickoff recap email", "email", "open", "2026-08-20", "person:csm01", "Jordan Lee"),
            action("actn:glx-vpn", "acct:globex", "Confirm VPN allowlist", "ticket", "open", "2026-08-19", "person:ps01", "Alex Rivera"),
            action("actn:glx-done", "acct:globex", "Send welcome packet", "email", "done", "2026-08-11", "person:csm01", "Jordan Lee"),
        ],
    )

    dump(
        "notes.json",
        [
            note("note:acme-pref", "acct:acme", "Pat prefers email before Slack."),
            note("note:acme-dc3", "acct:acme", "DC3 is the only site on the new OS image."),
            note("note:nwin-dark", "acct:northwind", "Kim has gone dark since the outage. Rob is the economic buyer."),
            note("note:nwin-risk", "acct:northwind", "Renewal 2026-09-05. Two P1s open."),
            note("note:glx-good", "acct:globex", "Clean kickoff. Plant 2 is the expansion."),
            note("note:glx-badge", "acct:globex", "Badge list arrived 2026-08-13."),
        ],
    )

    activities = []
    for t in tickets:
        verb = "created" if t["status"] != "done" else "updated"
        at = t["updated_at"]
        source_ref = f"jira:ticket:{t['key']}:{verb}:{at}"
        activities.append(
            {
                "_id": activity_doc_id(source_ref),
                "type": "activity",
                "account_id": t["account_id"],
                "kind": "ticket_updated",
                "at": at,
                "title": f"{t['key']} {t['status_raw']}",
                "ref": {"collection": "tickets", "id": t["_id"]},
                "source_ref": source_ref,
                "actor": "jira",
                "body": "",
            }
        )
    for em in emails:
        source_ref = f"mail:{em['message_id']}"
        activities.append(
            {
                "_id": activity_doc_id(source_ref),
                "type": "activity",
                "account_id": em["account_id"],
                "kind": "email_in" if em["direction"] == "inbound" else "email_out",
                "at": em["sent_at"],
                "title": em["subject"][:160],
                "ref": {"collection": "emails", "id": em["_id"]},
                "source_ref": source_ref,
                "actor": em["from_addr"],
                "body": "",
            }
        )
    for ev in json.loads((SEED / "calendar_events.json").read_text()):
        source_ref = f"cal:stub:{ev['external_id']}"
        activities.append(
            {
                "_id": activity_doc_id(source_ref),
                "type": "activity",
                "account_id": ev["account_id"],
                "kind": "meeting",
                "at": ev["start_at"],
                "title": ev["title"],
                "ref": {"collection": "calendar_events", "id": f"cal:stub:{ev['external_id']}"},
                "source_ref": source_ref,
                "actor": "calendar",
                "body": "",
            }
        )
    dump("activities.json", activities)
    print(f"wrote {len(accounts)} accounts, {len(tickets)} tickets, {len(emails)} emails, {len(activities)} activities")


if __name__ == "__main__":
    main()
