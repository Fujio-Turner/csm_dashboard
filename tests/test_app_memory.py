from __future__ import annotations


def test_healthz(client):
    res = client.get("/healthz")
    assert res.status_code == 200
    assert res.json()["ok"] is True
    assert res.json()["version"]


def test_seed_home_compose_send(client):
    seeded = client.post("/api/settings/seed")
    assert seeded.status_code == 200
    home = client.get("/api/home")
    assert home.status_code == 200
    items = home.json()["items"]
    assert len(items) == 3
    abbrs = {i["abbr"] for i in items}
    assert abbrs == {"ACME", "NWIN", "GLX"}
    acme_home = next(i for i in items if i["abbr"] == "ACME")
    assert "new_tickets" in acme_home["stats"]
    assert "new_email" in acme_home["stats"]
    assert "new_chat" in acme_home["stats"]
    assert "new_calendar" in acme_home["stats"]
    assert "next_action" not in acme_home
    if acme_home.get("next_meeting"):
        assert acme_home["next_meeting"].get("status") in {"scheduled", "proposed"}
    agenda = client.get("/api/home/agenda", params={"date": "2026-08-18"})
    assert agenda.status_code == 200
    assert agenda.json()["date"] == "2026-08-18"
    meets = agenda.json()["meetings"]
    assert any("ACME" in ((m.get("account") or {}).get("abbr") or "") for m in meets)
    inbox = agenda.json()["inbox"]
    assert inbox
    allowed_audience = {"me", "us", "them", "all", "unknown", "na"}
    assert all(i.get("audience") in allowed_audience for i in inbox)
    assert {i["audience"] for i in inbox} & {"me", "us", "them", "all"}
    filters = agenda.json().get("project_filters") or []
    assert filters
    assert any(":" in (p.get("label") or "") for p in filters)
    kinds = {i["kind"] for i in inbox}
    assert kinds & {"email", "slack", "teams"}
    ats = [i["at"] for i in inbox]
    assert ats == sorted(ats, reverse=True)
    acme = client.get("/api/accounts/by-abbr/acme")
    assert acme.status_code == 200
    aid = acme.json()["account_id"]
    task = client.post(
        "/api/tasks",
        json={
            "account_id": aid,
            "task_name": "Call Pat",
            "task_kind": "Follow up(s)",
            "due_at": "2026-08-20T15:00",
            "cc_addrs": ["pat@acme.com"],
            "body": "Confirm firmware date.",
        },
    )
    assert task.status_code == 200
    assert task.json()["subject"].startswith("Tasks: ")
    assert "Call Pat" in task.json()["subject"]
    assert "Follow up(s)" in task.json()["subject"]
    assert "When Due By:" in task.json()["body_text"]
    assert task.json()["operator"]["task"] is True
    tid = task.json()["_id"]
    again = client.put(
        f"/api/tasks/{tid}",
        json={
            "account_id": aid,
            "task_name": "Call Pat again",
            "task_kind": "Review(s)",
            "due_at": "2026-08-21T09:00",
            "cc_addrs": ["pat@acme.com", "bob@abc.com"],
            "body": "Bring notes.",
        },
    )
    assert again.status_code == 200
    assert "Call Pat again" in again.json()["subject"]
    assert "Review(s)" in again.json()["subject"]
    inbox2 = client.get("/api/home/agenda", params={"date": "2026-08-18"}).json()["inbox"]
    assert any(i["kind"] == "task" and "Call Pat again" in i["title"] for i in inbox2)
    assist = client.post(
        "/api/tasks/assist",
        json={"account_id": aid, "task_kind": "Follow up(s)", "task_name": ""},
    )
    assert assist.status_code == 200
    drafted = assist.json()
    assert drafted["result"] == "fallback"
    assert drafted["task_name"]
    assert drafted["task_kind"] == "Follow up(s)"
    assert drafted["due_at"]
    tickets = client.get("/api/tickets", params={"account_id": aid})
    assert tickets.json()["total"] >= 5
    composed = client.post("/api/drafts/compose", json={"account_id": aid})
    assert composed.status_code == 200
    draft_id = composed.json()["_id"]
    send = client.post(f"/api/drafts/{draft_id}/send")
    assert send.status_code == 409
    assert "send_not_configured" in send.json()["detail"]


def test_project_crud_search_and_owner(client):
    client.post("/api/settings/seed")
    created = client.post(
        "/api/projects",
        json={
            "account_id": "acct:acme",
            "name": "Firmware drop",
            "kind": "implementation",
            "status": "active",
            "owner_person_id": "person:ps01",
            "group_email": "firmware@acme.com",
            "tags": ["scanner", "dc3"],
        },
    )
    assert created.status_code == 200
    pid = created.json()["_id"]
    assert created.json()["group_email"] == "firmware@acme.com"
    assert "scanner" in created.json()["tags"]
    owner = client.get("/api/people", params={"account_id": "acct:acme"}).json()["items"]
    ps = next(p for p in owner if p["_id"] == "person:ps01")
    assert pid in (ps.get("project_ids") or [])
    found = client.get("/api/projects", params={"account_id": "acct:acme", "q": "firmware"})
    assert any(i["_id"] == pid for i in found.json()["items"])
    patched = client.patch(
        f"/api/projects/{pid}",
        json={"status": "blocked", "tags": ["scanner", "hot"]},
    )
    assert patched.status_code == 200
    assert patched.json()["status"] == "blocked"
    assert patched.json()["tags"] == ["scanner", "hot"]
    gone = client.delete(f"/api/projects/{pid}")
    assert gone.status_code == 200
    listed = client.get("/api/projects", params={"account_id": "acct:acme"}).json()["items"]
    assert all(i["_id"] != pid for i in listed)


def test_chat_fallback_sse(client):
    client.post("/api/settings/seed")
    with client.stream("POST", "/api/chat", json={"account_id": "acct:acme", "message": "status?"}) as res:
        assert res.status_code == 200
        body = b"".join(res.iter_bytes()).decode("utf-8")
    assert "event: token" in body
    assert "event: done" in body
    assert "fallback" in body


def test_chat_bookmark_and_scope(client):
    client.post("/api/settings/seed")
    with client.stream(
        "POST",
        "/api/chat",
        json={"account_id": "acct:acme", "message": "What is at risk on ACME?"},
    ) as res:
        assert res.status_code == 200
        body = b"".join(res.iter_bytes()).decode("utf-8")
    assert "event: done" in body
    listed = client.get("/api/chats", params={"account_id": "acct:acme"})
    assert listed.status_code == 200
    items = listed.json()["items"]
    assert items
    cid = items[0]["_id"]
    assert items[0]["account_id"] == "acct:acme"
    patched = client.patch("/api/chats/" + cid, json={"bookmarked": True})
    assert patched.status_code == 200
    assert patched.json()["bookmarked"] is True
    again = client.get("/api/chats", params={"account_id": "acct:acme"}).json()["items"]
    assert again[0]["_id"] == cid
    assert again[0]["bookmarked"] is True
    desk = client.get("/api/chats", params={"account_id": "desk"}).json()["items"]
    assert all(row.get("account_id") == "desk" for row in desk)
    missing = client.patch("/api/chats/chat:nope", json={"bookmarked": True})
    assert missing.status_code == 404


def test_home_chat_without_account_id(client):
    client.post("/api/settings/seed")
    with client.stream(
        "POST",
        "/api/chat",
        json={"message": "Is there any issue with #{ACME}?"},
    ) as res:
        assert res.status_code == 200
        body = b"".join(res.iter_bytes()).decode("utf-8")
    assert "ACME-12" in body


def test_teams_list(client):
    client.post("/api/settings/seed")
    res = client.get("/api/teams/messages", params={"account_id": "acct:acme"})
    assert res.status_code == 200
    assert res.json()["total"] >= 1


def test_salesforce_lists(client):
    client.post("/api/settings/seed")
    opps = client.get("/api/salesforce/opportunities", params={"account_id": "acct:acme"})
    assert opps.status_code == 200
    assert opps.json()["total"] >= 1
    cases = client.get("/api/salesforce/cases", params={"account_id": "acct:acme"})
    assert cases.status_code == 200
    assert cases.json()["total"] >= 1
    first = opps.json()["items"][0]
    assert client.get("/api/salesforce/opportunities/" + first["_id"]).status_code == 200


def test_timeline_items_are_flat(client):
    client.post("/api/settings/seed")
    res = client.get("/api/accounts/acct:acme/timeline")
    assert res.status_code == 200
    items = res.json()["items"]
    assert items
    first = items[0]
    assert first.get("kind")
    assert first.get("title")
    assert "a" not in first or not isinstance(first.get("a"), dict)


def test_timeline_related_docs(client):
    client.post("/api/settings/seed")
    items = client.get("/api/accounts/acct:acme/timeline", params={"limit": 200}).json()["items"]
    kinds = {row["kind"] for row in items}
    assert {"slack", "teams", "email_in", "email_out", "meeting", "salesforce"} <= kinds
    slack = next(row for row in items if row["kind"] == "slack")
    slack_doc = client.get("/api/slack/messages/" + slack["ref"]["id"])
    assert slack_doc.status_code == 200
    assert slack_doc.json().get("text")
    teams = next(row for row in items if row["kind"] == "teams")
    assert client.get("/api/teams/messages/" + teams["ref"]["id"]).status_code == 200
    meeting = next(row for row in items if row["kind"] == "meeting")
    assert client.get("/api/calendar/" + meeting["ref"]["id"]).status_code == 200
    mail = next(row for row in items if row["kind"].startswith("email"))
    assert client.get("/api/emails/" + mail["ref"]["id"]).status_code == 200
    ticket = next(row for row in items if str(row["kind"]).startswith("ticket"))
    assert client.get("/api/tickets/" + ticket["ref"]["id"]).status_code == 200


def test_people_create_and_project_filter(client):
    client.post("/api/settings/seed")
    created = client.post(
        "/api/people",
        json={
            "account_id": "acct:acme",
            "name": "Dana West",
            "email": "dana@acme.com",
            "location": "Boston",
            "title": "Buyer",
            "kind": "customer",
            "reports_to": "person:acme-pat",
            "project_ids": ["proj:acme-scan"],
            "functions": ["ops"],
        },
    )
    assert created.status_code == 200
    assert created.json()["location"] == "Boston"
    assert created.json()["functions"] == ["Ops"]
    people = client.get("/api/people", params={"account_id": "acct:acme", "q": "Dana West"}).json()["items"]
    assert len(people) == 1
    assert people[0]["name"] == "Dana West"
    scan = client.get(
        "/api/people", params={"account_id": "acct:acme", "project_id": "proj:acme-scan"}
    ).json()["items"]
    assert any(p["name"] == "Dana West" for p in scan)
    timeline = client.get(
        "/api/accounts/acct:acme/timeline", params={"project_id": "proj:acme-sso"}
    ).json()["items"]
    assert timeline
    assert any("ACME-18" in str(row.get("title") or "") for row in timeline)
    assert not any(
        str(row.get("kind") or "").startswith("ticket") and "ACME-12" in str(row.get("title") or "")
        for row in timeline
    )
    missing = client.post("/api/people", json={"account_id": "acct:acme", "name": "  "})
    assert missing.status_code == 400
    patched = client.patch(
        "/api/people/person:acme-pat",
        json={"functions": ["ops", "Accounting", "unknown"], "project_ids": ["proj:acme-scan"]},
    )
    assert patched.status_code == 200
    assert patched.json()["functions"] == ["Ops", "Accounting"]
    assert patched.json()["project_ids"] == ["proj:acme-scan"]
    ops = client.get("/api/people", params={"account_id": "acct:acme", "function": "Ops"}).json()["items"]
    assert any(p["_id"] == "person:acme-pat" for p in ops)


def test_activity_tag_project(client):
    client.post("/api/settings/seed")
    items = client.get("/api/accounts/acct:acme/timeline").json()["items"]
    ticket = next(row for row in items if str(row.get("kind") or "").startswith("ticket"))
    res = client.patch("/api/activities/" + ticket["_id"], json={"project_id": "proj:acme-sso"})
    assert res.status_code == 200
    assert res.json()["project_id"] == "proj:acme-sso"
    again = client.get("/api/activities/" + ticket["_id"])
    assert again.status_code == 200
    assert again.json()["project_id"] == "proj:acme-sso"
    related = client.get("/api/tickets/" + ticket["ref"]["id"])
    assert related.status_code == 200
    assert related.json()["project_id"] == "proj:acme-sso"
    filtered = client.get(
        "/api/accounts/acct:acme/timeline", params={"project_id": "proj:acme-sso"}
    ).json()["items"]
    assert any(row["_id"] == ticket["_id"] for row in filtered)
    bad = client.patch("/api/activities/" + ticket["_id"], json={"project_id": "proj:nope"})
    assert bad.status_code == 400
    cleared = client.patch("/api/activities/" + ticket["_id"], json={"project_id": ""})
    assert cleared.status_code == 200
    assert cleared.json()["project_id"] == ""
    missing = client.patch("/api/activities/act:does-not-exist", json={"project_id": "proj:acme-sso"})
    assert missing.status_code == 404


def test_account_input_counts_and_quiet(client):
    client.post("/api/settings/seed")
    acme = client.get("/api/accounts/by-abbr/acme").json()
    counts = acme["input_counts"]
    assert counts["tickets"] >= 5
    assert counts["email"] >= 1
    assert counts["people"] >= 1
    assert counts["chat"] == counts["slack"] + counts["teams"]
    assert counts["chat"] >= 1
    aid = acme["account_id"]
    quieted = client.patch("/api/accounts/" + aid, json={"quiet": True})
    assert quieted.status_code == 200
    home = client.get("/api/home").json()["items"]
    assert all(i["account_id"] != aid for i in home)
    listed = client.get("/api/accounts?include=all").json()["items"]
    assert any(i["account_id"] == aid and i.get("quiet") for i in listed)
    gone = client.delete("/api/accounts/" + aid)
    assert gone.status_code == 200
    assert client.get("/api/accounts/by-abbr/acme").status_code == 404


def test_suggest_reply_and_owns_all(client):
    client.post("/api/settings/seed")
    threads = client.get("/api/threads", params={"account_id": "acct:acme"}).json()["items"]
    assert threads
    sug = client.post("/api/threads/" + threads[0]["_id"] + "/suggest-reply")
    assert sug.status_code == 200
    assert sug.json()["body"]
    assert sug.json()["subject"]
    assert sug.json()["draft_id"]
    drafts = client.get("/api/drafts", params={"account_id": "acct:acme"}).json()["items"]
    assert any(d["_id"] == sug.json()["draft_id"] for d in drafts)
    directors = client.get(
        "/api/people", params={"account_id": "acct:acme", "project_id": "all"}
    ).json()["items"]
    assert any(p.get("owns_all_projects") for p in directors)
    scan = client.get(
        "/api/people", params={"account_id": "acct:acme", "project_id": "proj:acme-sso"}
    ).json()["items"]
    assert any(p["name"] == "Pat Nguyen" for p in scan)


PNG_1PX = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def test_account_logo_upload(client):
    client.post("/api/settings/seed")
    bad = client.post("/api/accounts/acct:acme/logo", json={"image": "not-an-image"})
    assert bad.status_code == 400
    saved = client.post("/api/accounts/acct:acme/logo", json={"image": PNG_1PX})
    assert saved.status_code == 200
    assert saved.json()["has_logo"] is True
    pic = client.get("/api/accounts/acct:acme/logo")
    assert pic.status_code == 200
    assert pic.headers["content-type"].startswith("image/")
    assert pic.content[:8] == b"\x89PNG\r\n\x1a\n"
    home = client.get("/api/home").json()["items"]
    acme = next(i for i in home if i["account_id"] == "acct:acme")
    assert acme["has_logo"] is True
    gone = client.delete("/api/accounts/acct:acme/logo")
    assert gone.status_code == 200
    assert gone.json()["has_logo"] is False
    assert client.get("/api/accounts/acct:acme/logo").status_code == 404


def test_operator_and_provider_test(client):
    saved = client.put(
        "/api/settings",
        json={
            "operator": {
                "name": "Bob Hale",
                "phone": "555-0100",
                "email": "bob@abc.com",
                "timezone": "America/New_York",
            }
        },
    )
    assert saved.status_code == 200
    status = client.get("/api/status").json()
    assert status["operator"]["email"] == "bob@abc.com"
    assert status["operator"]["timezone"] == "America/New_York"
    assert "abc.com" in status["operator"]["domains"]
    bad = client.put(
        "/api/settings",
        json={"operator": {"timezone": "Not/AZone"}},
    )
    assert bad.status_code == 200
    assert client.get("/api/status").json()["operator"]["timezone"] == "UTC"
    assert client.get("/api/status").json()["operator"]["email"] == "bob@abc.com"
    listed = client.put(
        "/api/settings",
        json={"operator": {"timezones": ["Europe/London", "America/Los_Angeles", "Europe/London", "Nope/Zone"]}},
    )
    assert listed.status_code == 200
    zones = client.get("/api/status").json()["operator"]["timezones"]
    assert zones == ["Europe/London", "America/Los_Angeles", "UTC"]
    clock = client.put(
        "/api/settings",
        json={"world_clock": {"timezones": ["Asia/Tokyo", "Europe/Paris"], "hour24": True}},
    )
    assert clock.status_code == 200
    status = client.get("/api/status").json()
    assert status["world_clock"]["timezones"] == ["Asia/Tokyo", "Europe/Paris"]
    assert status["world_clock"]["hour24"] is True
    assert status["operator"]["timezones"] == ["Asia/Tokyo", "Europe/Paris"]
    raw = client.get("/api/settings").json()
    assert raw["world_clock"]["hour24"] is True
    test = client.post("/api/settings/providers/test", json={"provider": "openai"})
    assert test.status_code == 200
    assert test.json()["ok"] is False


def test_preferences(client):
    status = client.get("/api/status").json()
    assert status["preferences"] == {
        "week_start": 0,
        "hidden_weekdays": [],
        "theme": "auto",
        "timeline_layout": "vertical",
        "timeline_past_days": 7,
        "timeline_next_days": 7,
    }
    saved = client.put(
        "/api/settings",
        json={"preferences": {"week_start": 1, "hidden_weekdays": [0, 6, 6, "x"], "theme": "dark"}},
    )
    assert saved.status_code == 200
    prefs = saved.json()["preferences"]
    assert prefs["week_start"] == 1
    assert prefs["hidden_weekdays"] == [0, 6]
    assert prefs["theme"] == "night"
    merged = client.put("/api/settings", json={"preferences": {"theme": "day"}})
    prefs = merged.json()["preferences"]
    assert prefs["theme"] == "day"
    assert prefs["week_start"] == 1
    assert prefs["hidden_weekdays"] == [0, 6]
    cleared = client.put(
        "/api/settings",
        json={"preferences": {"hidden_weekdays": [0, 1, 2, 3, 4, 5, 6]}},
    )
    assert cleared.json()["preferences"]["hidden_weekdays"] == []
    assert cleared.json()["preferences"]["week_start"] == 1
    bad = client.put("/api/settings", json={"preferences": {"week_start": 9, "theme": "sunset"}})
    prefs = bad.json()["preferences"]
    assert prefs["week_start"] == 0
    assert prefs["theme"] == "auto"
    raw = client.get("/api/settings").json()
    assert raw["preferences"]["theme"] == "auto"
    assert client.get("/api/status").json()["preferences"]["week_start"] == 0
    laid = client.put("/api/settings", json={"preferences": {"timeline_layout": "horizontal"}})
    prefs = laid.json()["preferences"]
    assert prefs["timeline_layout"] == "horizontal"
    assert prefs["theme"] == "auto"
    bad_layout = client.put("/api/settings", json={"preferences": {"timeline_layout": "diagonal"}})
    assert bad_layout.json()["preferences"]["timeline_layout"] == "vertical"
    days = client.put("/api/settings", json={"preferences": {"timeline_past_days": 30, "timeline_next_days": 7}})
    prefs = days.json()["preferences"]
    assert prefs["timeline_past_days"] == 30
    assert prefs["timeline_next_days"] == 7
    bad_days = client.put("/api/settings", json={"preferences": {"timeline_past_days": 90}})
    assert bad_days.json()["preferences"]["timeline_past_days"] == 7


def test_timeline_until_window(client):
    client.post("/api/settings/seed")
    all_items = client.get("/api/accounts/acct:acme/timeline", params={"limit": 200}).json()["items"]
    assert all_items
    stamps = sorted(str(i.get("at") or "") for i in all_items if i.get("at"))
    assert stamps
    mid = stamps[len(stamps) // 2]
    bounded = client.get(
        "/api/accounts/acct:acme/timeline",
        params={"since": stamps[0], "until": mid, "limit": 200},
    ).json()["items"]
    assert bounded
    assert all(str(i.get("at") or "") <= mid for i in bounded)
    assert all(str(i.get("at") or "") >= stamps[0] for i in bounded)


def test_activity_notes(client):
    client.post("/api/settings/seed")
    items = client.get("/api/accounts/acct:acme/timeline", params={"limit": 200}).json()["items"]
    row = next(
        i
        for i in items
        if str(i.get("kind") or "").startswith("ticket") and "ACME-12" in str(i.get("title") or "")
    )
    act_id = row["_id"]
    listed = client.get("/api/notes", params={"account_id": "acct:acme", "ref_id": act_id})
    assert listed.status_code == 200
    assert listed.json()["items"]
    created = client.post(
        "/api/notes",
        json={
            "account_id": "acct:acme",
            "body": "Need a new firmware pin before QBR.",
            "ref": {"collection": "activities", "id": act_id},
        },
    )
    assert created.status_code == 200
    again = client.get("/api/notes", params={"account_id": "acct:acme", "ref_id": act_id}).json()["items"]
    assert len(again) >= 2
    items = client.get("/api/accounts/acct:acme/timeline", params={"limit": 200}).json()["items"]
    row = next(i for i in items if i["_id"] == act_id)
    assert row["note_count"] >= 2
    q = client.get("/api/notes", params={"account_id": "acct:acme", "q": "firmware"}).json()["items"]
    assert q
