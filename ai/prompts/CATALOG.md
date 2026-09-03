# AI prompts catalog

Agents: **edit files in this folder**, not Python strings, when you change what Grok (or another model) is told.

Runtime loader: `csm_dashboard.prompts.load_prompt(name)` → `ai/prompts/<name>.json`.
Override the directory with `CSM_DASHBOARD_PROMPTS`. Tokens `{operator_name}`, `{operator_email}`, `{tagline}` are filled from Settings → You (CBL operator profile), then `config.json` seed defaults. Saved operator persona + intent is appended to every `prompt_system()` call.

Help UI copy also lives here (`help.json`, `kind: ui`). It is **not** sent to an API.

## Do not

- Bake a 200-line system string into `.py`.
- Grow `desk_chat.json` into a super-prompt that explains Jira, Slack, Salesforce, Gmail, etc.
- Invent ticket keys, meeting times, or people.
- Tell the model it may send mail, Slack, Teams, or calendar invites. The operator confirms Send.

## Core vs source

| `source` | Meaning |
| --- | --- |
| `core` | Desk-wide coach, compose, report, tools. Always loaded for that surface. |
| `jira` / `slack` / `teams` / `salesforce` / `gmail` / … | Connector- or API-specific brief. Add a **new file** when that source needs its own extraction or tone. Do not append it to `desk_chat`. |

Future files (not shipped yet) should look like `jira_ticket_brief.json` with `"source": "jira"` and a short `when`. `load_prompt("jira_ticket_brief")` is enough; nested folders are allowed (`sources/jira_ticket_brief` → `ai/prompts/sources/jira_ticket_brief.json`).

## JSON shape

**Prompt** (`kind` omitted or `prompt`):

```json
{
  "id": "email_draft",
  "title": "Email draft",
  "kind": "prompt",
  "source": "core",
  "used_by": "src/csm_dashboard/compose/grok.py",
  "when": "Compose / Reply AI Suggest.",
  "system": "You are …",
  "user_template": "{payload}",
  "fallback": "Shown when no API key."
}
```

**Tools** (`kind: tools`): OpenAI-style `tools` array. Wired by `get_tools()`.

**UI** (`kind: ui`): Help tiles, or persona presets (`operator_persona.json`). Not an API completion payload. Persona `intent` is still injected into `prompt_system()`.

## Files

| File | Kind | Source | Wired? | Used by | When |
| --- | --- | --- | --- | --- | --- |
| `desk_chat.json` | prompt | core | yes | `web/app.py` chat SSE | Account / desk coach. `brief_prefix` prefixes the local (non-Grok) brief as a second system message. |
| `desk_tools.json` | tools | core | yes | `chat/grok.py` | Function tools on desk-chat completions. |
| `email_draft.json` | prompt | core | yes | `compose/grok.py` | Compose / Reply AI Suggest and auto-draft To:you replies. JSON: subject, body, to, cc, next_steps, risks. |
| `task_assist.json` | prompt | core | yes | `compose/grok.py` | New task assist. JSON: task_name, task_kind, due_at, cc_addrs, body. |
| `weekly_report.json` | prompt | core | yes | `web/app.py` reports | Generate weekly. |
| `help.json` | ui | core | yes | `web/app.py` `GET /api/help` | How-do-I Help page. |
| `operator_persona.json` | ui | core | yes | `prompts.py` `prompt_system()` + Settings → You | Persona presets. Saved intent is appended to every AI system prompt. |
| `next_steps.json` | prompt | core | **no** | (parked) | Propose 3–5 next steps. Wire when that button exists. |
| `action_items.json` | prompt | core | **no** | (parked) | Extract follow-ups from context. |
| `health_overlay.json` | prompt | core | **no** | (parked) | Narrative overlay on a rules health score. Do not change the number. |

## Adding a source prompt

1. New `ai/prompts/<id>.json` with `source` set to the connector (not `core`).
2. Call `prompt_system("<id>")` / `prompt_user("<id>", payload)` from that connector’s path only.
3. Add a row to the table above.
4. Keep `desk_chat.json` ignorant of that API’s field names.

Python fallbacks (no API key) stay in `compose/grok.py` as short templates. They are not sent to a model.
