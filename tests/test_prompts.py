from __future__ import annotations

from csm_dashboard.prompts import help_public, load_prompt, prompt_system


def test_prompts_load():
    spec = load_prompt("email_draft")
    assert spec["system"]
    rendered = prompt_system("email_draft")
    assert "Jordan Lee" in rendered or "{operator_name}" not in spec["system"]
    help_doc = help_public()
    assert help_doc["groups"]
    ids = {g["id"] for g in help_doc["groups"]}
    assert {"start", "home", "chat", "clock", "setup"} <= ids
