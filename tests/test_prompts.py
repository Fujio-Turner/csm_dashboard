from __future__ import annotations

from csm_dashboard.prompts import help_public, load_prompt, prompt_system


def test_prompts_load():
    spec = load_prompt("email_draft")
    assert spec["system"]
    task = load_prompt("task_assist")
    assert "task_name" in task["system"]
    rendered = prompt_system("email_draft")
    assert "Jordan Lee" in rendered or "{operator_name}" not in spec["system"]
    help_doc = help_public()
    assert help_doc["groups"]
    ids = {g["id"] for g in help_doc["groups"]}
    assert {"start", "home", "chat", "clock", "setup", "find"} <= ids
    how = [
        item["h"]
        for g in help_doc["groups"]
        for item in g.get("items") or []
    ]
    assert any("project owner" in h.lower() for h in how)
    assert any("highest priority" in h.lower() for h in how)
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
