from __future__ import annotations

import json

from csm_dashboard.prompts import load_prompt


def get_tools() -> list[dict]:
    spec = load_prompt("desk_tools")
    tools = spec.get("tools")
    if not isinstance(tools, list) or not tools:
        raise ValueError("desk_tools.tools missing")
    return tools


def run_tool(repo, account_id: str, name: str, args: dict) -> str:
    if name == "get_account":
        acct = repo.get_account(account_id) or {}
        return json.dumps(
            {
                "name": acct.get("name"),
                "abbr": acct.get("abbr"),
                "health": acct.get("health"),
                "contract": acct.get("contract"),
            }
        )
    if name == "list_tickets":
        rows, _ = repo.page_tickets(account_id, limit=20)
        return json.dumps(
            [{"key": r.get("key"), "summary": r.get("summary"), "status": r.get("status"), "priority": r.get("priority")} for r in rows]
        )
    if name == "list_emails":
        rows, _ = repo.page_emails(account_id, limit=20)
        return json.dumps(
            [
                {
                    "from_addr": r.get("from_addr"),
                    "to_addrs": r.get("to_addrs"),
                    "subject": r.get("subject"),
                    "sent_at": r.get("sent_at"),
                    "direction": r.get("direction"),
                }
                for r in rows
            ]
        )
    if name == "list_actions":
        rows = repo.page_actions(account_id=account_id, status="open")
        return json.dumps([{"title": r.get("title"), "due_on": r.get("due_on")} for r in rows])
    if name == "add_note":
        repo.add_note({"account_id": account_id, "body": args.get("body") or ""})
        return json.dumps({"ok": True})
    if name == "create_action":
        repo.create_action(
            {
                "account_id": account_id,
                "title": args.get("title") or "",
                "due_on": args.get("due_on") or "",
                "kind": args.get("kind") or "other",
                "source": "grok",
            }
        )
        return json.dumps({"ok": True})
    return json.dumps({"error": "unknown tool"})
