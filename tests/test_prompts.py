from __future__ import annotations

from csm_dashboard.chat.tools import get_tools
from csm_dashboard.config import prompts_dir
from csm_dashboard.prompts import (
    help_public,
    list_prompts,
    load_prompt,
    operator_identity,
    operator_intent_block,
    operator_personas,
    prompt_system,
)


def test_prompts_load():
    assert prompts_dir().as_posix().endswith("ai/prompts")
    catalog = {row["id"]: row for row in list_prompts()}
    assert catalog["desk_chat"]["source"] == "core"
    assert catalog["desk_tools"]["kind"] == "tools"
    assert catalog["help"]["kind"] == "ui"
    assert catalog["operator_persona"]["kind"] == "ui"
    personas = {row["id"]: row for row in operator_personas()}
    assert {"csm", "sales", "tam"} <= set(personas)
    assert personas["sales"]["intent"]
    flavored = prompt_system(
        "desk_chat",
        operator={"persona": "sales", "intent": "Keep it account-level. Mention upsell only when the book supports it."},
    )
    assert "account-level" in flavored.lower()
    assert "Operator persona:" in flavored
    default_block = operator_intent_block({"persona": "tam"})
    assert "Technical Account Manager" in default_block
    assert operator_intent_block({"persona": "custom", "intent": ""}) == ""
    spec = load_prompt("email_draft")
    assert spec["system"]
    task = load_prompt("task_assist")
    assert "task_name" in task["system"]
    rendered = prompt_system("email_draft")
    assert "Jordan Lee" in rendered or "{operator_name}" not in spec["system"]
    you = prompt_system(
        "email_draft",
        operator={"name": "Alex Rivera", "email": "alex@acme.com", "role": "csm"},
    )
    assert "Alex Rivera" in you
    assert "alex@acme.com" in you
    assert "Jordan Lee" not in you
    assert "jordan@example.com" not in you
    ident = operator_identity({"email": "alex.rivera@acme.com"})
    assert ident["email"] == "alex.rivera@acme.com"
    assert "Alex" in ident["name"]
    assert ident["name"] != "Jordan Lee"
    tools = get_tools()
    names = {str((t.get("function") or {}).get("name") or "") for t in tools}
    assert {"get_account", "list_tickets", "list_emails"} <= names
    help_doc = help_public()
    assert help_doc["groups"]
    ids = {g["id"] for g in help_doc["groups"]}
    assert {"start", "home", "chat", "clock", "setup", "find", "day"} <= ids
    how = [
        item["h"]
        for g in help_doc["groups"]
        for item in g.get("items") or []
    ]
    assert any("project owner" in h.lower() for h in how)
    assert any("highest priority" in h.lower() for h in how)
    assert any("how i work" in h.lower() or "how does ai know" in h.lower() for h in how)
    assert any("tag a company" in h.lower() for h in how)
    assert any("add a company" in h.lower() for h in how)
    assert any("what do #" in h.lower() for h in how)
    blob = str(help_doc).lower()
    assert "/people bob" in blob
    assert "/ticket" in blob
    assert "bound" in blob
    assert "#acme" in blob
    blocked = [
        item
        for g in help_doc["groups"]
        for item in g.get("items") or []
        if item.get("blocks")
    ]
    assert blocked
    assert any(
        block.get("ul")
        for item in blocked
        for block in item["blocks"]
    )
