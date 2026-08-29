#!/usr/bin/env python3
"""Generate fixtures/seed/*.json — run from repo root: python3 fixtures/build_seed.py"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SEED = ROOT / "seed"
sys.path.insert(0, str(ROOT.parent / "src"))

from csm_dashboard.ingest.identity import activity_doc_id, email_doc_id, thread_doc_id  # noqa: E402
from csm_dashboard.storage.repo import ts_to_iso  # noqa: E402

DEMO_DAY = "2026-08-28"
TEST_DAY = "2026-08-18"
TOKEN_RE = re.compile(r"^[a-z0-9-]{2,32}$")
DEMO_TS = int(datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc).timestamp())


def dump(name: str, rows: list) -> None:
    SEED.mkdir(parents=True, exist_ok=True)
    (SEED / name).write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")


def account(slug, name, abbr, color, domains, health, renewal, arr, team, next_action, jira, slack, teams):
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
            "teams": {"channel_ids": [teams]},
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


def person(
    _id,
    account_id,
    kind,
    name,
    email,
    title,
    role,
    *,
    reports_to="",
    location="",
    functions=None,
    project_ids=None,
    owns_all=False,
    external_ids=None,
):
    return {
        "_id": _id,
        "type": "person",
        "account_id": account_id,
        "kind": kind,
        "name": name,
        "email": email,
        "title": title,
        "role": role,
        "location": location,
        "reports_to": reports_to,
        "project_ids": project_ids or [],
        "functions": functions or [],
        "owns_all_projects": owns_all,
        "external_ids": external_ids or {},
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


def ticket(key, account_id, summary, status, pri, updated, comments, created="2026-08-10T12:00:00Z", project_id=""):
    row = {
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
    if project_id:
        row["project_id"] = project_id
    return row


def email_row(account_id, message_id, in_reply_to, frm, to, subject, sent, snippet, body, direction="inbound"):
    doc = {
        "type": "email",
        "account_id": account_id,
        "direction": direction,
        "message_id": message_id,
        "in_reply_to": in_reply_to,
        "references": in_reply_to,
        "from_addr": frm,
        "to_addrs": [to] if isinstance(to, str) else list(to),
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
        "operator": {"pin": False, "unread": True},
        "sources": {"stub": {"fetched_at": "2026-08-17T15:00:00Z"}},
    }


def teams_channel(account_id, cid, name, team_name, topic):
    return {
        "type": "teams_channel",
        "account_id": account_id,
        "channel_id": cid,
        "name": name,
        "team_name": team_name,
        "topic": topic,
    }


def teams_msg(account_id, cid, ts, user, name, text):
    return {
        "type": "teams_message",
        "account_id": account_id,
        "channel_id": cid,
        "ts": ts,
        "thread_id": "",
        "user": user,
        "user_name": name,
        "text": text,
        "permalink": f"https://teams.microsoft.com/l/message/{cid}/{ts}",
        "operator": {"pin": False, "unread": True},
        "sources": {"stub": {"fetched_at": "2026-08-17T15:00:00Z"}},
    }


def cal(account_id, ext, title, start, end, attendees, location="Meet", *, status="", unread=False):
    row = {
        "type": "calendar_event",
        "account_id": account_id,
        "provider": "stub",
        "external_id": ext,
        "title": title,
        "start_at": start,
        "end_at": end,
        "attendees": attendees,
        "location": location,
        "operator": {"prep_note": "", "unread": unread},
        "sources": {},
    }
    if status:
        row["status"] = status
    return row


def slot(day: str, hh: int, mm: int, dur: int = 30) -> tuple[str, str]:
    start_m = hh * 60 + mm
    end_m = start_m + dur
    eh, em = divmod(end_m, 60)
    return f"{day}T{hh:02d}:{mm:02d}:00Z", f"{day}T{eh:02d}:{em:02d}:00Z"


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


def note(_id, account_id, body, ref=None):
    return {
        "_id": _id,
        "type": "note",
        "account_id": account_id,
        "ref": ref or {"collection": "accounts", "id": account_id},
        "body": body,
        "author": "you",
        "created_at": "2026-08-12T00:00:00Z",
    }


def sf_opp(_id, account_id, ext, sf_acct, name, kind, stage, amount, close, owner, url, project_id=""):
    return {
        "_id": _id,
        "type": "salesforce_opportunity",
        "account_id": account_id,
        "external_id": ext,
        "sf_account_id": sf_acct,
        "name": name,
        "kind": kind,
        "stage": stage,
        "amount": amount,
        "currency": "USD",
        "close_on": close,
        "owner_name": owner,
        "url": url,
        "project_id": project_id,
        "operator": {"pin": False},
        "updated_at": "2026-08-16T18:00:00Z",
        "created_at": "2026-05-01T00:00:00Z",
    }


def sf_case(_id, account_id, number, subject, status, priority, sf_acct, url, updated):
    return {
        "_id": _id,
        "type": "salesforce_case",
        "account_id": account_id,
        "case_number": number,
        "subject": subject,
        "status": status,
        "priority": priority,
        "sf_account_id": sf_acct,
        "url": url,
        "updated_at": updated,
    }


def att(*pairs):
    return [{"email": e, "name": n} for e, n in pairs]


def assert_people(people: list[dict]) -> None:
    ids = {p["_id"] for p in people}
    for p in people:
        token = str(p["_id"]).removeprefix("person:")
        if not TOKEN_RE.match(token):
            raise SystemExit(f"invalid person id {p['_id']}")
        mgr = p.get("reports_to") or ""
        if mgr and mgr not in ids:
            raise SystemExit(f"{p['_id']} reports_to missing {mgr}")
        if mgr and p.get("account_id") != next(x["account_id"] for x in people if x["_id"] == mgr):
            raise SystemExit(f"{p['_id']} reports_to crosses accounts")


def build_accounts() -> list[dict]:
    return [
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
            "19:acme-success",
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
                    {"person_id": "person:nwin-ae", "role": "ae"},
                    {"person_id": "person:nwin-csm", "role": "csm"},
                    {"person_id": "person:nwin-tam", "role": "tam"},
                ],
                "ps": [{"person_id": "person:ps02", "role": "ps_consultant"}],
            },
            {"kind": "call", "due_on": "2026-08-10", "title": "Reach champion", "action_id": "actn:nwin-call"},
            "NWIN",
            "C0NWIN1",
            "19:nwin-success",
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
                    {"person_id": "person:glx-csm", "role": "csm"},
                    {"person_id": "person:glx-tam", "role": "tam"},
                ],
                "ps": [{"person_id": "person:glx-ps", "role": "ps_lead"}],
            },
            {"kind": "meeting", "due_on": "2026-08-20", "title": "Kickoff recap", "action_id": "actn:glx-recap"},
            "GLX",
            "C0GLX1",
            "19:glx-onboard",
        ),
    ]


def build_people() -> list[dict]:
    acme = "acct:acme"
    nwin = "acct:northwind"
    glx = "acct:globex"
    scan = ["proj:acme-scan"]
    sso = ["proj:acme-sso"]
    both = ["proj:acme-scan", "proj:acme-sso"]
    renew = ["proj:nwin-renew"]
    onboard = ["proj:glx-onboard"]
    return [
        # ACME customer org — Dana's tree
        person("person:acme-dana", acme, "customer", "Dana Cole", "dana.cole@acme.com", "Chief Executive Officer", "executive", location="Chicago HQ", owns_all=True),
        person("person:acme-taylor", acme, "customer", "Taylor Brooks", "taylor.brooks@acme.com", "Chief Financial Officer", "economic_buyer", reports_to="person:acme-dana", location="Chicago HQ", functions=["Accounting"]),
        person("person:acme-grace", acme, "customer", "Grace Lin", "grace.lin@acme.com", "Controller", "other", reports_to="person:acme-taylor", location="Chicago HQ", functions=["Accounting"]),
        person("person:acme-ap", acme, "customer", "Chris Adeyemi", "chris.adeyemi@acme.com", "AP manager", "other", reports_to="person:acme-grace", location="Chicago HQ", functions=["Accounting"]),
        person("person:acme-ar", acme, "customer", "Hannah Cole", "hannah.cole@acme.com", "AR specialist", "other", reports_to="person:acme-grace", location="Chicago HQ", functions=["Accounting"]),
        person("person:acme-pat", acme, "customer", "Pat Nguyen", "pat.nguyen@acme.com", "VP Operations", "champion", reports_to="person:acme-dana", location="Chicago HQ", functions=["Ops"], project_ids=both, owns_all=True),
        person("person:acme-dc1", acme, "customer", "Lee Park", "lee.park@acme.com", "DC1 manager", "technical", reports_to="person:acme-pat", location="DC1", functions=["Ops"], project_ids=scan),
        person("person:acme-dc2", acme, "customer", "Priya Shah", "priya.shah@acme.com", "DC2 manager", "technical", reports_to="person:acme-pat", location="DC2", functions=["Ops"], project_ids=scan),
        person("person:acme-lee", acme, "customer", "Sam Ortiz", "sam.ortiz@acme.com", "Warehouse lead", "technical", reports_to="person:acme-pat", location="DC3 warehouse", functions=["Ops"], project_ids=scan),
        person("person:acme-bob", acme, "customer", "Bob Hale", "bob.hale@acme.com", "Plant ops", "technical", reports_to="person:acme-pat", location="DC3 floor", functions=["Ops"], project_ids=scan, external_ids={"teams": "bob-hale"}),
        person("person:acme-log", acme, "customer", "Noah Kim", "noah.kim@acme.com", "Logistics coordinator", "other", reports_to="person:acme-pat", location="Chicago HQ", functions=["Ops"]),
        person("person:acme-inv", acme, "customer", "Maya Singh", "maya.singh@acme.com", "Inventory analyst", "other", reports_to="person:acme-pat", location="Chicago HQ", functions=["Ops"], project_ids=scan),
        person("person:acme-safe", acme, "customer", "Tom Brennan", "tom.brennan@acme.com", "Safety lead", "other", reports_to="person:acme-pat", location="DC3 warehouse", functions=["Ops"]),
        person("person:acme-mei", acme, "customer", "Mei Wong", "mei.wong@acme.com", "VP Information Technology", "technical", reports_to="person:acme-dana", location="Chicago HQ", functions=["DBA"], project_ids=sso, owns_all=True),
        person("person:acme-raj", acme, "customer", "Raj Patel", "raj.patel@acme.com", "Lead DBA", "technical", reports_to="person:acme-mei", location="Chicago HQ", functions=["DBA"], project_ids=sso),
        person("person:acme-vic", acme, "customer", "Vic Torres", "vic.torres@acme.com", "Night-shift DBA", "technical", reports_to="person:acme-raj", location="Remote", functions=["DBA"], project_ids=sso),
        person("person:acme-elena", acme, "customer", "Elena Ruiz", "elena.ruiz@acme.com", "Security engineer", "technical", reports_to="person:acme-mei", location="Remote", functions=["DBA"], project_ids=sso),
        person("person:acme-omar", acme, "customer", "Omar Haddad", "omar.haddad@acme.com", "Platform engineer", "technical", reports_to="person:acme-mei", location="Chicago HQ", project_ids=scan),
        person("person:acme-help", acme, "customer", "Lila Chen", "lila.chen@acme.com", "Helpdesk manager", "other", reports_to="person:acme-mei", location="Chicago HQ"),
        person("person:acme-amira", acme, "customer", "Amira Sol", "amira.sol@acme.com", "VP People", "other", reports_to="person:acme-dana", location="Chicago HQ"),
        person("person:acme-hr", acme, "customer", "Kate Brennan", "kate.brennan@acme.com", "HR business partner", "other", reports_to="person:acme-amira", location="Chicago HQ"),
        # Northwind customer org — Helen's tree
        person("person:nwin-helen", nwin, "customer", "Helen Cho", "helen.cho@northwind.example", "Chief Executive Officer", "executive", location="Seattle HQ", owns_all=True),
        person("person:nwin-rob", nwin, "customer", "Rob Singh", "rob.singh@northwind.example", "Chief Financial Officer", "economic_buyer", reports_to="person:nwin-helen", location="Seattle HQ", functions=["Accounting"]),
        person("person:nwin-nina", nwin, "customer", "Nina Vogt", "nina.vogt@northwind.example", "Controller", "other", reports_to="person:nwin-rob", location="Seattle HQ", functions=["Accounting"]),
        person("person:nwin-owen", nwin, "customer", "Owen Park", "owen.park@northwind.example", "FP&A lead", "other", reports_to="person:nwin-rob", location="Seattle HQ", functions=["Accounting"]),
        person("person:nwin-kim", nwin, "customer", "Kim Hale", "kim.hale@northwind.example", "IT Director", "champion", reports_to="person:nwin-helen", location="Seattle HQ", functions=["DBA"], project_ids=renew, owns_all=True),
        person("person:nwin-jules", nwin, "customer", "Jules Hart", "jules.hart@northwind.example", "Application owner", "technical", reports_to="person:nwin-kim", location="Seattle HQ", project_ids=renew),
        person("person:nwin-devin", nwin, "customer", "Devin Cole", "devin.cole@northwind.example", "Identity engineer", "technical", reports_to="person:nwin-kim", location="Remote", functions=["DBA"], project_ids=renew),
        person("person:nwin-sara", nwin, "customer", "Sara Nguyen", "sara.nguyen@northwind.example", "Helpdesk lead", "other", reports_to="person:nwin-kim", location="Seattle HQ"),
        person("person:nwin-pedro", nwin, "customer", "Pedro Alves", "pedro.alves@northwind.example", "Network engineer", "technical", reports_to="person:nwin-kim", location="Seattle HQ", functions=["DBA"]),
        person("person:nwin-marco", nwin, "customer", "Marco Rossi", "marco.rossi@northwind.example", "VP Supply Chain", "other", reports_to="person:nwin-helen", location="Tacoma DC", functions=["Ops"]),
        person("person:nwin-imani", nwin, "customer", "Imani Wells", "imani.wells@northwind.example", "Warehouse supervisor", "technical", reports_to="person:nwin-marco", location="Tacoma DC", functions=["Ops"]),
        person("person:nwin-tess", nwin, "customer", "Tess Okonkwo", "tess.okonkwo@northwind.example", "Buyer", "other", reports_to="person:nwin-marco", location="Seattle HQ", functions=["Ops"]),
        person("person:nwin-cal", nwin, "customer", "Cal Winters", "cal.winters@northwind.example", "Yard lead", "technical", reports_to="person:nwin-marco", location="Tacoma DC", functions=["Ops"]),
        person("person:nwin-yuki", nwin, "customer", "Yuki Tanaka", "yuki.tanaka@northwind.example", "General counsel", "other", reports_to="person:nwin-helen", location="Seattle HQ"),
        person("person:nwin-seth", nwin, "customer", "Seth Brown", "seth.brown@northwind.example", "Sales operations", "other", reports_to="person:nwin-helen", location="Seattle HQ"),
        # Globex customer org — Eleanor's tree
        person("person:glx-eleanor", glx, "customer", "Eleanor Voss", "eleanor.voss@globex.example", "Chief Executive Officer", "executive", location="Cleveland HQ", owns_all=True),
        person("person:glx-victor", glx, "customer", "Victor Lang", "victor.lang@globex.example", "Chief Operating Officer", "champion", reports_to="person:glx-eleanor", location="Cleveland HQ", functions=["Ops"], project_ids=onboard, owns_all=True),
        person("person:glx-ava", glx, "customer", "Ava Chen", "ava.chen@globex.example", "Plant 1 manager", "champion", reports_to="person:glx-victor", location="Plant 1", functions=["Ops"], project_ids=onboard, owns_all=True),
        person("person:glx-ben", glx, "customer", "Ben Ortiz", "ben.ortiz@globex.example", "Shift lead", "technical", reports_to="person:glx-ava", location="Plant 1", functions=["Ops"]),
        person("person:glx-carla", glx, "customer", "Carla Diaz", "carla.diaz@globex.example", "Quality lead", "technical", reports_to="person:glx-ava", location="Plant 1", functions=["Ops"]),
        person("person:glx-hiro", glx, "customer", "Hiro Tanaka", "hiro.tanaka@globex.example", "Maintenance", "other", reports_to="person:glx-ava", location="Plant 1"),
        person("person:glx-rita", glx, "customer", "Rita Gomez", "rita.gomez@globex.example", "Safety coordinator", "other", reports_to="person:glx-ava", location="Plant 1", functions=["Ops"]),
        person("person:glx-sofia", glx, "customer", "Sofia Berg", "sofia.berg@globex.example", "Plant 2 manager", "other", reports_to="person:glx-victor", location="Plant 2", functions=["Ops"], project_ids=onboard),
        person("person:glx-luis", glx, "customer", "Luis Romero", "luis.romero@globex.example", "Line supervisor", "technical", reports_to="person:glx-sofia", location="Plant 2", functions=["Ops"]),
        person("person:glx-paul", glx, "customer", "Paul Nkrumah", "paul.nkrumah@globex.example", "Night shift lead", "technical", reports_to="person:glx-sofia", location="Plant 2", functions=["Ops"]),
        person("person:glx-ines", glx, "customer", "Ines Costa", "ines.costa@globex.example", "Shipping lead", "other", reports_to="person:glx-sofia", location="Plant 2", functions=["Ops"]),
        person("person:glx-nadia", glx, "customer", "Nadia Ali", "nadia.ali@globex.example", "Plant IT", "technical", reports_to="person:glx-eleanor", location="Cleveland HQ", functions=["DBA"]),
        person("person:glx-ken", glx, "customer", "Ken Walsh", "ken.walsh@globex.example", "Plant DBA", "technical", reports_to="person:glx-nadia", location="Cleveland HQ", functions=["DBA"]),
        person("person:glx-moira", glx, "customer", "Moira Flynn", "moira.flynn@globex.example", "OT engineer", "technical", reports_to="person:glx-nadia", location="Plant 1", functions=["DBA"]),
        person("person:glx-greg", glx, "customer", "Greg Hale", "greg.hale@globex.example", "Chief Financial Officer", "economic_buyer", reports_to="person:glx-eleanor", location="Cleveland HQ", functions=["Accounting"]),
        person("person:glx-ivy", glx, "customer", "Ivy Chen", "ivy.chen@globex.example", "Plant controller", "other", reports_to="person:glx-greg", location="Cleveland HQ", functions=["Accounting"]),
        # Account / PS teams
        person("person:ae01", acme, "account_team", "Riley Park", "riley@example.com", "Account Executive", "ae", location="Chicago"),
        person("person:csm01", acme, "account_team", "Jordan Lee", "jordan@example.com", "CSM", "csm", reports_to="person:ae01", location="Chicago"),
        person("person:tam01", acme, "account_team", "Chris Vale", "chris@example.com", "TAM", "tam", reports_to="person:csm01", location="Remote"),
        person("person:ps01", acme, "ps_team", "Alex Rivera", "alex@example.com", "PS lead", "ps_lead", reports_to="person:csm01", location="Chicago"),
        person("person:nwin-ae", nwin, "account_team", "Riley Park", "riley@example.com", "Account Executive", "ae", location="Chicago"),
        person("person:nwin-csm", nwin, "account_team", "Jordan Lee", "jordan@example.com", "CSM", "csm", reports_to="person:nwin-ae", location="Chicago"),
        person("person:nwin-tam", nwin, "account_team", "Chris Vale", "chris@example.com", "TAM", "tam", reports_to="person:nwin-csm", location="Remote"),
        person("person:ps02", nwin, "ps_team", "Quinn Brooks", "quinn@example.com", "PS consultant", "ps_consultant", reports_to="person:nwin-csm", location="Seattle"),
        person("person:ae02", glx, "account_team", "Morgan Diaz", "morgan@example.com", "Account Executive", "ae", location="Cleveland"),
        person("person:glx-csm", glx, "account_team", "Jordan Lee", "jordan@example.com", "CSM", "csm", reports_to="person:ae02", location="Chicago"),
        person("person:glx-tam", glx, "account_team", "Chris Vale", "chris@example.com", "TAM", "tam", reports_to="person:glx-csm", location="Remote"),
        person("person:glx-ps", glx, "ps_team", "Alex Rivera", "alex@example.com", "PS lead", "ps_lead", reports_to="person:glx-csm", location="Chicago"),
    ]


def build_calendar() -> list[dict]:
    j = att(("jordan@example.com", "Jordan Lee"))
    d, t = DEMO_DAY, TEST_DAY
    s = slot
    return [
        # History + test-day TAM (kept for tests)
        cal("acct:acme", "evt-acme-old", "ACME weekly", "2026-08-03T16:00:00Z", "2026-08-03T16:30:00Z", att(("pat.nguyen@acme.com", "Pat Nguyen"))),
        cal("acct:acme", "evt-acme-qbr-prep", "ACME QBR", "2026-08-17T16:00:00Z", "2026-08-17T17:00:00Z", att(("pat.nguyen@acme.com", "Pat Nguyen"))),
        cal("acct:acme", "evt-acme-tam", "ACME TAM working session", f"{t}T15:00:00Z", f"{t}T16:00:00Z", att(("pat.nguyen@acme.com", "Pat Nguyen"), ("chris@example.com", "Chris Vale"))),
        cal("acct:acme", "evt-acme-ps", "Scan rollout checkpoint", "2026-08-20T14:00:00Z", "2026-08-20T15:00:00Z", att(("sam.ortiz@acme.com", "Sam Ortiz")), status="proposed", unread=True),
        cal("acct:northwind", "evt-nwin-old", "NWIN monthly", "2026-07-02T16:00:00Z", "2026-07-02T17:00:00Z", att(("kim.hale@northwind.example", "Kim Hale"))),
        cal("acct:northwind", "evt-nwin-missed", "NWIN incident review", "2026-08-10T16:00:00Z", "2026-08-10T16:30:00Z", att(("kim.hale@northwind.example", "Kim Hale"))),
        cal("acct:northwind", "evt-nwin-renew", "NWIN renewal", "2026-08-25T16:00:00Z", "2026-08-25T17:00:00Z", att(("rob.singh@northwind.example", "Rob Singh"))),
        cal("acct:globex", "evt-glx-kick", "GLX kickoff", "2026-08-10T16:00:00Z", "2026-08-10T18:00:00Z", att(("ava.chen@globex.example", "Ava Chen"))),
        cal("acct:globex", "evt-glx-plant", "GLX plant walk", "2026-08-14T16:00:00Z", "2026-08-14T17:00:00Z", att(("ava.chen@globex.example", "Ava Chen"))),
        cal("acct:globex", "evt-glx-next", "GLX weekly", "2026-08-21T16:00:00Z", "2026-08-21T16:30:00Z", att(("ava.chen@globex.example", "Ava Chen"))),
        # Packed demo day — ~8am–6pm Chicago (UTC-5)
        cal("acct:globex", "evt-glx-p1", "GLX Plant 1 standup", *s(d, 13, 0, 25), att(("ava.chen@globex.example", "Ava Chen"), ("ben.ortiz@globex.example", "Ben Ortiz")) + j),
        cal("acct:acme", "evt-acme-dc1", "ACME DC1 check-in", *s(d, 13, 30, 25), att(("lee.park@acme.com", "Lee Park")) + j),
        cal("acct:globex", "evt-glx-print", "GLX Plant 2 badge printer", *s(d, 14, 30, 40), att(("sofia.berg@globex.example", "Sofia Berg")) + j, "Plant 2"),
        cal("acct:acme", "evt-acme-stand", "ACME standup", *s(d, 15, 0, 25), att(("pat.nguyen@acme.com", "Pat Nguyen"), ("sam.ortiz@acme.com", "Sam Ortiz"), ("bob.hale@acme.com", "Bob Hale")) + j),
        cal("acct:northwind", "evt-nwin-am", "NWIN renewal commercial", *s(d, 15, 30, 45), att(("rob.singh@northwind.example", "Rob Singh"), ("helen.cho@northwind.example", "Helen Cho")) + j),
        cal("acct:acme", "evt-acme-dc3", "ACME DC3 firmware war room", *s(d, 16, 0, 45), att(("sam.ortiz@acme.com", "Sam Ortiz"), ("bob.hale@acme.com", "Bob Hale"), ("chris@example.com", "Chris Vale")) + j, "DC3 floor"),
        cal("acct:globex", "evt-glx-vpn", "GLX VPN allowlist with Nadia", *s(d, 16, 30, 30), att(("nadia.ali@globex.example", "Nadia Ali")) + j),
        cal("acct:acme", "evt-acme-sso", "ACME SSO 8-hour timeout review", *s(d, 17, 0, 45), att(("mei.wong@acme.com", "Mei Wong"), ("elena.ruiz@acme.com", "Elena Ruiz")) + j),
        cal("acct:northwind", "evt-nwin-sso", "NWIN contractor SSO patch", *s(d, 17, 30, 45), att(("jules.hart@northwind.example", "Jules Hart"), ("devin.cole@northwind.example", "Devin Cole")) + j),
        cal("acct:acme", "evt-acme-fin", "ACME finance QBR prep", *s(d, 18, 0, 30), att(("grace.lin@acme.com", "Grace Lin"), ("taylor.brooks@acme.com", "Taylor Brooks")) + j),
        cal("acct:globex", "evt-glx-coo", "GLX Victor onboarding review", *s(d, 18, 30, 45), att(("victor.lang@globex.example", "Victor Lang"), ("ava.chen@globex.example", "Ava Chen")) + j),
        cal("acct:acme", "evt-acme-qbrn", "ACME QBR numbers", *s(d, 19, 0, 60), att(("taylor.brooks@acme.com", "Taylor Brooks"), ("pat.nguyen@acme.com", "Pat Nguyen"), ("dana.cole@acme.com", "Dana Cole")) + j),
        cal("acct:northwind", "evt-nwin-fpa", "NWIN FP&A renewal model", *s(d, 19, 30, 30), att(("owen.park@northwind.example", "Owen Park"), ("nina.vogt@northwind.example", "Nina Vogt")) + j),
        cal("acct:northwind", "evt-nwin-ops", "NWIN Tacoma ops check-in", *s(d, 20, 0, 30), att(("marco.rossi@northwind.example", "Marco Rossi"), ("imani.wells@northwind.example", "Imani Wells")) + j),
        cal("acct:globex", "evt-glx-p2w", "GLX Plant 2 walkthrough", *s(d, 20, 30, 30), att(("sofia.berg@globex.example", "Sofia Berg"), ("luis.romero@globex.example", "Luis Romero")) + j, "Plant 2"),
        cal("acct:acme", "evt-acme-train", "ACME DC2 training slot", *s(d, 21, 0, 45), att(("priya.shah@acme.com", "Priya Shah")) + j),
        cal("acct:globex", "evt-glx-ceo", "GLX Eleanor exec brief", *s(d, 21, 30, 30), att(("eleanor.voss@globex.example", "Eleanor Voss"), ("greg.hale@globex.example", "Greg Hale")) + j),
        cal("acct:northwind", "evt-nwin-exec", "NWIN Helen exec brief", *s(d, 22, 0, 30), att(("helen.cho@northwind.example", "Helen Cho"), ("riley@example.com", "Riley Park")) + j),
        cal("acct:acme", "evt-acme-dana", "ACME Dana one-pager", *s(d, 22, 30, 30), att(("dana.cole@acme.com", "Dana Cole")) + j),
        cal("acct:northwind", "evt-nwin-wrap", "NWIN commercial follow-up", *s(d, 23, 0, 25), att(("rob.singh@northwind.example", "Rob Singh"), ("seth.brown@northwind.example", "Seth Brown")) + j),
    ]


def chain_emails(account_id: str, items: list[tuple]) -> list[dict]:
    out = []
    for item in items:
        mid, irt, frm, to, sub, sent, snip, body, *rest = item
        out.append(email_row(account_id, mid, irt, frm, to, sub, sent, snip, body, rest[0] if rest else "inbound"))
    return out


def build_emails() -> list[dict]:
    emails = chain_emails(
        "acct:acme",
        [
            ("<acme-root@acme.com>", "", "pat.nguyen@acme.com", "jordan@example.com", "ACME-12 workaround", "2026-08-15T14:00:00Z", "Scanner died again.", "The handheld still dies after 20 minutes on OS 14."),
            ("<acme-2@example.com>", "<acme-root@acme.com>", "jordan@example.com", "pat.nguyen@acme.com", "Re: ACME-12 workaround", "2026-08-15T16:00:00Z", "We have a firmware pin.", "Pat — we have a firmware pin. TAM will send steps tonight.", "outbound"),
            ("<acme-3@acme.com>", "<acme-2@example.com>", "pat.nguyen@acme.com", "jordan@example.com", "Re: ACME-12 workaround", "2026-08-16T09:00:00Z", "Tried it on DC1.", "Tried the pin on DC1. DC3 still fails."),
            ("<acme-4@example.com>", "<acme-3@acme.com>", "jordan@example.com", "pat.nguyen@acme.com", "Re: ACME-12 workaround", "2026-08-16T18:00:00Z", "New build tomorrow.", "New build tomorrow morning. Booking TAM.", "outbound"),
            ("<acme-5@acme.com>", "<acme-4@example.com>", "pat.nguyen@acme.com", "jordan@example.com", "Re: ACME-12 workaround", "2026-08-17T14:22:00Z", "The handheld still dies…", "The handheld still dies after 20 minutes on the DC3 floor. Need a date."),
            ("<acme-6@acme.com>", "<acme-5@acme.com>", "sam.ortiz@acme.com", "jordan@example.com", "Re: ACME-12 workaround", f"{DEMO_DAY}T13:10:00Z", "DC3 floor log attached.", "Attaching tonight's DC3 log. Same brick after 18 minutes."),
        ],
    )
    emails.append(email_row("acct:acme", "<acme-sso@acme.com>", "", "sam.ortiz@acme.com", "jordan@example.com", "SSO timeout after 8 hours", "2026-08-16T11:30:00Z", "Night shift gets kicked.", "Night shift gets kicked after 8 hours. Related to ACME-18?"))
    emails.append(email_row("acct:acme", "<acme-qbr@acme.com>", "", "taylor.brooks@acme.com", "jordan@example.com", "QBR numbers for Friday", f"{DEMO_DAY}T14:05:00Z", "Need ARR and open P1s.", "Need ARR, open P1s, and a firmware date before the QBR."))
    emails.append(email_row("acct:acme", "<acme-bob-1@example.com>", "", "jordan@example.com", "bob.hale@acme.com", "DC3 scanner pin for ACME-12", "2026-08-16T19:00:00Z", "Bob — can you try the pin on DC3 tonight?", "Bob — can you try the pin on DC3 tonight and tell me if it holds?", "outbound"))
    emails.append(email_row("acct:acme", "<acme-bob-2@acme.com>", "<acme-bob-1@example.com>", "bob.hale@acme.com", "jordan@example.com", "Re: DC3 scanner pin for ACME-12", "2026-08-17T07:15:00Z", "Tried it. DC3 still dies after 20 minutes.", "Tried it. DC3 still dies after 20 minutes. Need a new build."))
    emails.append(email_row("acct:acme", "<acme-dana@acme.com>", "", "dana.cole@acme.com", "jordan@example.com", "One-pager before 3pm", f"{DEMO_DAY}T12:40:00Z", "Need a one-pager.", "Need a one-pager on firmware and SSO before the QBR."))
    emails.extend(
        chain_emails(
            "acct:northwind",
            [
                ("<nwin-root@northwind.example>", "", "kim.hale@northwind.example", "jordan@example.com", "Friday auth outage", "2026-08-15T19:00:00Z", "We missed cutoff.", "We missed the cutoff. This is the second P1 this month."),
                ("<nwin-2@example.com>", "<nwin-root@northwind.example>", "jordan@example.com", "kim.hale@northwind.example", "Re: Friday auth outage", "2026-08-16T08:00:00Z", "Incident doc attached.", "Kim — incident doc is in the ticket. Can we talk Tuesday?", "outbound"),
                ("<nwin-3@northwind.example>", "<nwin-2@example.com>", "kim.hale@northwind.example", "jordan@example.com", "Re: Friday auth outage", "2026-08-16T20:00:00Z", "I am out until the 28th.", "I am out until the 28th. Rob can talk numbers."),
                ("<nwin-4@northwind.example>", "<nwin-3@example.com>", "rob.singh@northwind.example", "jordan@example.com", "Re: Friday auth outage", "2026-08-17T10:00:00Z", "Renewal is at risk.", "If auth is this shaky the renewal is at risk."),
                ("<nwin-5@northwind.example>", "<nwin-4@northwind.example>", "rob.singh@northwind.example", "jordan@example.com", "Re: Friday auth outage", f"{DEMO_DAY}T15:20:00Z", "Need a commercial option today.", "Need a commercial option on this morning's call."),
                ("<nwin-6@northwind.example>", "", "helen.cho@northwind.example", "jordan@example.com", "Exec brief agenda", f"{DEMO_DAY}T16:05:00Z", "Keep it to ten minutes.", "Keep the 3pm to ten minutes. Commercial option first."),
            ],
        )
    )
    emails.extend(
        chain_emails(
            "acct:globex",
            [
                ("<glx-root@globex.example>", "", "ava.chen@globex.example", "jordan@example.com", "Kickoff recap", "2026-08-11T16:00:00Z", "Great start.", "Great start yesterday. Plant 2 wants a date."),
                ("<glx-2@example.com>", "<glx-root@globex.example>", "jordan@example.com", "ava.chen@globex.example", "Re: Kickoff recap", "2026-08-12T09:00:00Z", "Drafting the plan.", "Drafting the plan. PS will hold Thursday.", "outbound"),
                ("<glx-3@globex.example>", "<glx-2@example.com>", "ava.chen@globex.example", "jordan@example.com", "Re: Kickoff recap", "2026-08-13T15:00:00Z", "Thursday works.", "Thursday works. Sending badge list."),
                ("<glx-4@example.com>", "<glx-3@globex.example>", "jordan@example.com", "ava.chen@globex.example", "Re: Kickoff recap", "2026-08-14T11:00:00Z", "Got the list.", "Got the list. See you Thursday.", "outbound"),
                ("<glx-5@globex.example>", "<glx-4@example.com>", "sofia.berg@globex.example", "jordan@example.com", "Re: Kickoff recap", f"{DEMO_DAY}T16:40:00Z", "Plant 2 badge printer.", "Plant 2 badge printer is still down. Can PS bring a spare?"),
                ("<glx-6@globex.example>", "", "eleanor.voss@globex.example", "jordan@example.com", "Onboarding review", f"{DEMO_DAY}T17:10:00Z", "I will sit in.", "I will sit in on Victor's review. Keep Plant 2 first."),
            ],
        )
    )
    return emails


def build_threads(emails: list[dict]) -> list[dict]:
    threads: dict[str, dict] = {}
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
    return list(threads.values())


def build_slack() -> list[dict]:
    slack = []
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
        "Dana wants a one-pager before 3pm",
        "Raj says SSO logs look clean after 8h",
        "Grace needs ARR confirmed for QBR",
        "Priya can take the DC2 training slot",
        "Standup in 10 — bring the DC3 log",
        "Bob is on the floor with the spare batteries",
        "Mei wants contractor mapping before QBR",
        "Safety walk at DC3 is clear",
    ]
    for i, text in enumerate(acme_texts):
        ts = f"{DEMO_TS + i}.000100"
        slack.append(slack_msg("acct:acme", "C0ACME1", ts, "U0PAT" if i % 2 == 0 else "U0JOR", "pat.nguyen" if i % 2 == 0 else "jordan", text))
    slack.append(slack_msg("acct:acme", "C0ACME1", f"{DEMO_TS + 20}.000200", "U0BOB", "bob.hale", "thread: still failing on DC3", f"{DEMO_TS}.000100"))
    nwin_texts = [
        "Anyone seen Kim?",
        "She is dark since the outage",
        "Renewal is 19 days out",
        "Rob wants numbers",
        "I pinged twice",
        "Need exec sponsor",
        "P1 still open",
        "Call recap?",
        "Helen asked for a commercial option",
        "Devin has a contractor SSO patch",
        "Nina can join the 11:00",
        "Marco says Tacoma is quiet",
        "Owen has a renewal model draft",
        "Pedro opened a network ticket",
        "Seth wants sales ops on the exec brief",
    ]
    for i, text in enumerate(nwin_texts):
        slack.append(slack_msg("acct:northwind", "C0NWIN1", f"{DEMO_TS + 100 + i}.000100", "U0KIM" if i == 0 else "U0JOR", "kim.hale" if i == 0 else "jordan", text))
    glx_texts = [
        "Kickoff went well",
        "Badge list incoming",
        "Plant 2 wants training",
        "VPN ticket opened",
        "See you Thursday",
        "Notes in the drive",
        "No blockers",
        "Nice start",
        "Sofia needs a spare printer",
        "Ben can cover the 2pm walk",
        "Nadia opened GLX-12",
        "Victor sitting in on standup",
        "Eleanor wants Plant 2 first",
        "Moira is on OT allowlist",
        "Ivy asked for onboarding cost",
    ]
    for i, text in enumerate(glx_texts):
        slack.append(slack_msg("acct:globex", "C0GLX1", f"{DEMO_TS + 200 + i}.000100", "U0AVA" if i % 2 == 0 else "U0JOR", "ava.chen" if i % 2 == 0 else "jordan", text))
    return slack


def build_teams() -> list[dict]:
    teams = []
    tbase = DEMO_TS + 800
    for i, (who, text) in enumerate(
        [
            ("bob.hale", "Tried the pin on DC3 — still dying."),
            ("jordan", "Thanks Bob. Logging on ACME-12."),
            ("pat.nguyen", "QBR deck needs the firmware date."),
            ("chris", "TAM on the 15:00 working session."),
            ("sam.ortiz", "DC3 log is in the channel."),
            ("jordan", "Bringing it to standup."),
            ("dana.cole", "One-pager by 3pm please."),
            ("mei.wong", "SSO mapping for contractors is still open."),
        ]
    ):
        teams.append(teams_msg("acct:acme", "19:acme-success", f"{tbase + i}.000000", who, who, text))
    for i, (who, text) in enumerate(
        [
            ("kim.hale", "I am out — Rob has the numbers."),
            ("jordan", "Rob, joining the 11:00 renewal."),
            ("rob.singh", "Need a commercial option today."),
            ("jules.hart", "Contractor SSO patch is in test."),
            ("helen.cho", "Ten minutes. Commercial first."),
            ("marco.rossi", "Tacoma is quiet this week."),
        ]
    ):
        teams.append(teams_msg("acct:northwind", "19:nwin-success", f"{tbase + 50 + i}.000000", who, who, text))
    for i, (who, text) in enumerate(
        [
            ("ava.chen", "Plant 1 is green. Plant 2 printer is down."),
            ("jordan", "PS bringing a spare this afternoon."),
            ("sofia.berg", "Thanks — badge line is blocked."),
            ("victor.lang", "I will sit in on the 16:00 standup."),
            ("eleanor.voss", "Keep Plant 2 first on the review."),
            ("nadia.ali", "VPN allowlist is in GLX-8."),
        ]
    ):
        teams.append(teams_msg("acct:globex", "19:glx-onboard", f"{tbase + 80 + i}.000000", who, who, text))
    return teams


def build_tickets() -> list[dict]:
    return [
        ticket("ACME-12", "acct:acme", "Scanner firmware bricks on OS 14", "in_progress", "p1", "2026-08-17T09:00:00Z", [{"at": "2026-08-17T08:50:00Z", "author": "pat.nguyen@acme.com", "text": "Still dying after 20 minutes on the DC3 floor."}], project_id="proj:acme-scan"),
        ticket("ACME-18", "acct:acme", "SSO timeout after 8 hours", "open", "p2", "2026-08-16T11:00:00Z", [], project_id="proj:acme-sso"),
        ticket("ACME-21", "acct:acme", "Add scan-to-ERP mapping", "waiting", "p3", "2026-08-14T10:00:00Z", [], project_id="proj:acme-scan"),
        ticket("ACME-9", "acct:acme", "Label printer driver", "done", "p3", "2026-08-12T10:00:00Z", [], project_id="proj:acme-scan"),
        ticket("ACME-30", "acct:acme", "Training videos for DC2", "open", "p4", "2026-08-15T10:00:00Z", [], project_id="proj:acme-scan"),
        ticket("ACME-31", "acct:acme", "Nightly inventory job slow", "open", "p2", "2026-08-17T07:00:00Z", [], project_id="proj:acme-scan"),
        ticket("ACME-33", "acct:acme", "Contractor SSO mapping", "open", "p2", "2026-08-27T16:00:00Z", [{"at": "2026-08-27T16:10:00Z", "author": "elena.ruiz@acme.com", "text": "Need a date before QBR."}], project_id="proj:acme-sso"),
        ticket("ACME-34", "acct:acme", "DC3 spare battery SKU", "waiting", "p3", "2026-08-28T09:00:00Z", [], project_id="proj:acme-scan"),
        ticket("ACME-36", "acct:acme", "Night-shift DBA VPN", "open", "p3", "2026-08-28T11:00:00Z", [], project_id="proj:acme-sso"),
        ticket("ACME-37", "acct:acme", "QBR one-pager", "open", "p3", f"{DEMO_DAY}T12:00:00Z", [], project_id="proj:acme-scan"),
        ticket("NWIN-4", "acct:northwind", "Auth outage on Friday", "open", "p1", "2026-08-15T18:00:00Z", [{"at": "2026-08-15T18:10:00Z", "author": "kim.hale@northwind.example", "text": "We missed the cutoff. Call me."}], project_id="proj:nwin-renew"),
        ticket("NWIN-7", "acct:northwind", "Invoice export wrong currency", "open", "p1", "2026-08-16T12:00:00Z", [], project_id="proj:nwin-renew"),
        ticket("NWIN-11", "acct:northwind", "User provisioning lag", "waiting", "p2", "2026-08-08T12:00:00Z", [], project_id="proj:nwin-renew"),
        ticket("NWIN-12", "acct:northwind", "SSO mapping for contractors", "open", "p2", "2026-08-14T12:00:00Z", [], project_id="proj:nwin-renew"),
        ticket("NWIN-19", "acct:northwind", "QBR deck numbers", "open", "p3", "2026-08-13T12:00:00Z", [], project_id="proj:nwin-renew"),
        ticket("NWIN-2", "acct:northwind", "Sandbox refresh", "cancelled", "p4", "2026-08-01T12:00:00Z", []),
        ticket("NWIN-22", "acct:northwind", "Renewal commercial pack", "open", "p2", "2026-08-28T11:00:00Z", [], project_id="proj:nwin-renew"),
        ticket("NWIN-24", "acct:northwind", "Tacoma Wi-Fi drop", "open", "p3", f"{DEMO_DAY}T10:00:00Z", [], project_id="proj:nwin-renew"),
        ticket("NWIN-25", "acct:northwind", "Helpdesk SLA miss", "waiting", "p3", "2026-08-27T12:00:00Z", []),
        ticket("GLX-3", "acct:globex", "Kickoff environment", "done", "p3", "2026-08-12T12:00:00Z", [], project_id="proj:glx-onboard"),
        ticket("GLX-5", "acct:globex", "Add second plant code", "open", "p3", "2026-08-16T12:00:00Z", [], project_id="proj:glx-onboard"),
        ticket("GLX-6", "acct:globex", "Training date hold", "open", "p4", "2026-08-17T12:00:00Z", [], project_id="proj:glx-onboard"),
        ticket("GLX-8", "acct:globex", "VPN allowlist", "in_progress", "p2", "2026-08-17T13:00:00Z", [], project_id="proj:glx-onboard"),
        ticket("GLX-9", "acct:globex", "Welcome packet typos", "done", "p4", "2026-08-11T12:00:00Z", []),
        ticket("GLX-12", "acct:globex", "Badge printer at plant 2", "open", "p3", "2026-08-28T10:00:00Z", [], project_id="proj:glx-onboard"),
        ticket("GLX-14", "acct:globex", "OT network segment", "open", "p2", f"{DEMO_DAY}T09:30:00Z", [], project_id="proj:glx-onboard"),
        ticket("GLX-15", "acct:globex", "Plant 2 shipping labels", "waiting", "p3", f"{DEMO_DAY}T11:00:00Z", [], project_id="proj:glx-onboard"),
    ]


def _activity(source_ref, account_id, kind, at, title, ref, actor, **extra):
    row = {
        "_id": activity_doc_id(source_ref),
        "type": "activity",
        "account_id": account_id,
        "kind": kind,
        "at": at,
        "title": title,
        "ref": ref,
        "source_ref": source_ref,
        "actor": actor,
        "body": "",
    }
    row.update(extra)
    return row


def build_activities(tickets, emails, calendar, slack, teams, opps, cases) -> list[dict]:
    activities = []
    for t in tickets:
        verb = "created" if t["status"] != "done" else "updated"
        at = t["updated_at"]
        source_ref = f"jira:ticket:{t['key']}:{verb}:{at}"
        activities.append(
            _activity(
                source_ref,
                t["account_id"],
                "ticket_updated",
                at,
                f"{t['key']} {t['status_raw']}",
                {"collection": "tickets", "id": t["_id"]},
                "jira",
            )
        )
    for em in emails:
        source_ref = f"mail:{em['message_id']}"
        activities.append(
            _activity(
                source_ref,
                em["account_id"],
                "email_in" if em["direction"] == "inbound" else "email_out",
                em["sent_at"],
                em["subject"][:160],
                {"collection": "emails", "id": em["_id"]},
                em["from_addr"],
            )
        )
    for ev in calendar:
        source_ref = f"cal:stub:{ev['external_id']}"
        activities.append(
            _activity(
                source_ref,
                ev["account_id"],
                "meeting",
                ev["start_at"],
                ev["title"],
                {"collection": "calendar_events", "id": f"cal:stub:{ev['external_id']}"},
                "calendar",
            )
        )
    for msg in slack:
        ts = msg["ts"]
        thread_ts = str(msg.get("thread_ts") or "")
        if thread_ts and thread_ts != ts:
            continue
        cid = msg["channel_id"]
        doc_id = f"slm:{cid}:{ts.replace('.', '_')}"
        source_ref = f"slack:{cid}:{ts}"
        activities.append(
            _activity(
                source_ref,
                msg["account_id"],
                "slack",
                ts_to_iso(ts),
                (msg.get("text") or "")[:160],
                {"collection": "slack_messages", "id": doc_id},
                msg.get("user_name") or "slack",
            )
        )
    for msg in teams:
        ts = msg["ts"]
        cid = msg["channel_id"]
        doc_id = f"tmm:{cid}:{ts.replace('.', '_')}"
        source_ref = f"teams:{cid}:{ts}"
        activities.append(
            _activity(
                source_ref,
                msg["account_id"],
                "teams",
                ts_to_iso(ts),
                (msg.get("text") or "")[:160],
                {"collection": "teams_messages", "id": doc_id},
                msg.get("user_name") or "teams",
            )
        )
    for opp in opps:
        ext = opp["external_id"]
        at = opp["updated_at"]
        source_ref = f"sfdc:opp:{ext}:{opp.get('stage') or ''}:{at}"
        activities.append(
            _activity(
                source_ref,
                opp["account_id"],
                "salesforce",
                at,
                f"{opp.get('name') or ext} · {opp.get('stage') or ''}".strip(" ·"),
                {"collection": "salesforce_opportunities", "id": opp["_id"]},
                "salesforce",
                project_id=opp.get("project_id") or "",
            )
        )
    for case in cases:
        at = case["updated_at"]
        source_ref = f"sfdc:case:{case['case_number']}:{case.get('status') or ''}:{at}"
        activities.append(
            _activity(
                source_ref,
                case["account_id"],
                "salesforce",
                at,
                f"{case.get('case_number')} {case.get('subject')}".strip(),
                {"collection": "salesforce_cases", "id": case["_id"]},
                "salesforce",
            )
        )
    return activities


def main() -> None:
    accounts = build_accounts()
    people = build_people()
    assert_people(people)
    tickets = build_tickets()
    emails = build_emails()
    calendar = build_calendar()
    dump("accounts.json", accounts)
    dump("people.json", people)
    dump(
        "projects.json",
        [
            project("proj:acme-scan", "acct:acme", "Warehouse scan rollout", "implementation", "active", "person:ps01", "2026-07-01", "2026-09-30", "ACME-100", "Handheld scanners in 4 DCs."),
            project("proj:acme-sso", "acct:acme", "SSO hardening", "implementation", "active", "person:tam01", "2026-08-01", "2026-10-15", "ACME-200", "Night-shift timeout and contractor mapping."),
            project("proj:nwin-renew", "acct:northwind", "Renewal rescue", "qbr", "blocked", "person:ps02", "2026-07-15", "2026-09-05", "NWIN-80", "Champion going dark before renewal."),
            project("proj:glx-onboard", "acct:globex", "Plant onboarding", "implementation", "active", "person:ps01", "2026-08-10", "2026-10-15", "GLX-10", "Kickoff last week. Clean start."),
        ],
    )
    slack = build_slack()
    teams = build_teams()
    opps = [
        sf_opp("sfo:006ACME0001", "acct:acme", "006ACME0001", "001ACME0001", "ACME Enterprise Renewal FY27", "renewal", "negotiation", 240000, "2026-11-01", "Riley Park", "https://example.my.salesforce.com/006ACME0001", "proj:acme-scan"),
        sf_opp("sfo:006ACME0002", "acct:acme", "006ACME0002", "001ACME0001", "Warehouse scanners add-on", "upsell", "proposal", 45000, "2026-10-15", "Riley Park", "https://example.my.salesforce.com/006ACME0002", "proj:acme-scan"),
        sf_opp("sfo:006NWIN0001", "acct:northwind", "006NWIN0001", "001NWIN0001", "Northwind renewal", "renewal", "proposal", 180000, "2026-09-05", "Riley Park", "https://example.my.salesforce.com/006NWIN0001", "proj:nwin-renew"),
        sf_opp("sfo:006NWIN0002", "acct:northwind", "006NWIN0002", "001NWIN0001", "Identity add-on", "upsell", "discovery", 22000, "2026-10-01", "Riley Park", "https://example.my.salesforce.com/006NWIN0002", "proj:nwin-renew"),
        sf_opp("sfo:006GLX0001", "acct:globex", "006GLX0001", "001GLX0001", "Globex plant 2 expansion", "upsell", "discovery", 40000, "2026-12-01", "Morgan Diaz", "https://example.my.salesforce.com/006GLX0001", "proj:glx-onboard"),
        sf_opp("sfo:006GLX0002", "acct:globex", "006GLX0002", "001GLX0001", "Globex plant 1 renewal", "renewal", "qualification", 96000, "2027-03-01", "Morgan Diaz", "https://example.my.salesforce.com/006GLX0002", "proj:glx-onboard"),
    ]
    cases = [
        sf_case("sfc:500ACME12", "acct:acme", "00001234", "DC3 scanner brick", "working", "high", "001ACME0001", "https://example.my.salesforce.com/500ACME12", "2026-08-17T09:00:00Z"),
        sf_case("sfc:500ACME18", "acct:acme", "00001290", "Night-shift SSO timeout", "escalated", "high", "001ACME0001", "https://example.my.salesforce.com/500ACME18", "2026-08-16T11:00:00Z"),
        sf_case("sfc:500NWIN4", "acct:northwind", "00002004", "Friday auth outage", "escalated", "critical", "001NWIN0001", "https://example.my.salesforce.com/500NWIN4", "2026-08-15T18:00:00Z"),
        sf_case("sfc:500NWIN7", "acct:northwind", "00002011", "Invoice currency", "working", "high", "001NWIN0001", "https://example.my.salesforce.com/500NWIN7", "2026-08-16T12:00:00Z"),
        sf_case("sfc:500GLX12", "acct:globex", "00003012", "Plant 2 badge printer", "working", "medium", "001GLX0001", "https://example.my.salesforce.com/500GLX12", "2026-08-28T10:00:00Z"),
        sf_case("sfc:500GLX8", "acct:globex", "00003008", "VPN allowlist", "waiting", "medium", "001GLX0001", "https://example.my.salesforce.com/500GLX8", "2026-08-17T13:00:00Z"),
    ]
    activities = build_activities(tickets, emails, calendar, slack, teams, opps, cases)
    acme12 = next(a for a in activities if str(a.get("source_ref") or "").startswith("jira:ticket:ACME-12:"))
    dump("tickets.json", tickets)
    dump("emails.json", emails)
    dump("threads.json", build_threads(emails))
    dump(
        "slack_channels.json",
        [
            slack_channel("acct:acme", "C0ACME1", "acme-success", "ACME production"),
            slack_channel("acct:northwind", "C0NWIN1", "northwind-success", "Northwind"),
            slack_channel("acct:globex", "C0GLX1", "globex-onboard", "Globex onboarding"),
        ],
    )
    dump("slack_messages.json", slack)
    dump(
        "teams_channels.json",
        [
            teams_channel("acct:acme", "19:acme-success", "ACME Success", "Acme", "ACME production"),
            teams_channel("acct:northwind", "19:nwin-success", "NWIN Success", "Northwind", "Renewal"),
            teams_channel("acct:globex", "19:glx-onboard", "GLX Onboard", "Globex", "Kickoff"),
        ],
    )
    dump("teams_messages.json", teams)
    dump("calendar_events.json", calendar)
    dump(
        "action_items.json",
        [
            action("actn:acme-fw", "acct:acme", "Send firmware workaround and book TAM call", "email", "open", "2026-08-18", "person:csm01", "Jordan Lee"),
            action("actn:acme-qbr", "acct:acme", "Prep QBR numbers", "internal", "open", "2026-08-17", "person:csm01", "Jordan Lee"),
            action("actn:acme-done", "acct:acme", "Ship training videos", "ticket", "done", "2026-08-12", "person:ps01", "Alex Rivera"),
            action("actn:nwin-call", "acct:northwind", "Reach champion", "call", "open", "2026-08-10", "person:nwin-csm", "Jordan Lee"),
            action("actn:nwin-p1", "acct:northwind", "Close Friday auth P1", "ticket", "open", "2026-08-16", "person:nwin-csm", "Jordan Lee"),
            action("actn:nwin-exec", "acct:northwind", "Brief exec sponsor", "meeting", "open", "2026-08-14", "person:nwin-ae", "Riley Park"),
            action("actn:nwin-renew", "acct:northwind", "Renewal commercial options", "internal", "open", "2026-08-12", "person:nwin-csm", "Jordan Lee"),
            action("actn:glx-recap", "acct:globex", "Kickoff recap email", "email", "open", "2026-08-20", "person:glx-csm", "Jordan Lee"),
            action("actn:glx-vpn", "acct:globex", "Confirm VPN allowlist", "ticket", "open", "2026-08-19", "person:glx-ps", "Alex Rivera"),
            action("actn:glx-done", "acct:globex", "Send welcome packet", "email", "done", "2026-08-11", "person:glx-csm", "Jordan Lee"),
        ],
    )
    dump(
        "notes.json",
        [
            note("note:acme-pref", "acct:acme", "Pat prefers email before Slack."),
            note("note:acme-dc3", "acct:acme", "DC3 is the only site on the new OS image. Bob Hale is plant ops on the floor."),
            note("note:acme-org", "acct:acme", "Dana Cole is CEO. Pat owns Ops; Mei owns IT; Taylor is CFO; Amira is People."),
            note(
                "note:acme-fw-act",
                "acct:acme",
                "Firmware drop slipped a week.",
                ref={"collection": "activities", "id": acme12["_id"]},
            ),
            note("note:nwin-dark", "acct:northwind", "Kim has gone dark since the outage. Rob is the economic buyer. Helen wants a ten-minute exec brief."),
            note("note:nwin-risk", "acct:northwind", "Renewal 2026-09-05. Two P1s open."),
            note("note:nwin-org", "acct:northwind", "Helen Cho is CEO. Kim owns IT; Rob is CFO; Marco owns supply chain."),
            note("note:glx-good", "acct:globex", "Clean kickoff. Plant 2 is the expansion."),
            note("note:glx-badge", "acct:globex", "Badge list arrived 2026-08-13."),
            note("note:glx-org", "acct:globex", "Eleanor Voss is CEO. Victor is COO. Ava runs Plant 1; Sofia runs Plant 2; Nadia is plant IT; Greg is CFO."),
        ],
    )
    dump("salesforce_opportunities.json", opps)
    dump("salesforce_cases.json", cases)
    dump("activities.json", activities)
    demo_meets = [e for e in calendar if str(e.get("start_at") or "").startswith(DEMO_DAY)]
    print(
        f"wrote {len(accounts)} accounts, {len(people)} people, {len(tickets)} tickets, "
        f"{len(emails)} emails, {len(calendar)} meetings ({len(demo_meets)} on {DEMO_DAY}), "
        f"{len(activities)} activities"
    )


if __name__ == "__main__":
    main()
