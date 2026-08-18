from __future__ import annotations

import json


def get_tools() -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": "get_account",
                "description": "Get the current account profile",
                "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_tickets",
                "description": "List open tickets for the account",
                "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_emails",
                "description": "List recent emails for the account",
                "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_actions",
                "description": "List open action items",
                "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "add_note",
                "description": "Add an operator note",
                "parameters": {
                    "type": "object",
                    "properties": {"body": {"type": "string"}},
                    "required": ["body"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "create_action",
                "description": "Create a follow-up action (does not send mail)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "due_on": {"type": "string"},
                        "kind": {"type": "string"},
                    },
                    "required": ["title"],
                },
            },
        },
    ]


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
