# JSON Schema — csm_dashboard

Spec: [JSON Schema 2020-12](https://json-schema.org/draft/2020-12/json-schema-core.html).

Every durable document and `config.json` has a file under [`schema/`](../schema/).

## Files

| File | What it describes |
| --- | --- |
| [`config.schema.json`](../schema/config.schema.json) | `config.json` |
| [`account.schema.json`](../schema/account.schema.json) | CBL `accounts`. Optional caches: `stats` (`refreshed_at`, inbox counts, `next_meeting`) and `input_counts` (tab badges). Never source of truth. |
| [`person.schema.json`](../schema/person.schema.json) | `people` |
| [`project.schema.json`](../schema/project.schema.json) | `projects` |
| [`ticket.schema.json`](../schema/ticket.schema.json) | `tickets` |
| [`email.schema.json`](../schema/email.schema.json) | `emails` |
| [`thread.schema.json`](../schema/thread.schema.json) | `threads` |
| [`slack_channel.schema.json`](../schema/slack_channel.schema.json) | `slack_channels` |
| [`slack_message.schema.json`](../schema/slack_message.schema.json) | `slack_messages` |
| [`teams_channel.schema.json`](../schema/teams_channel.schema.json) | `teams_channels` |
| [`teams_message.schema.json`](../schema/teams_message.schema.json) | `teams_messages` |
| [`salesforce_case.schema.json`](../schema/salesforce_case.schema.json) | `salesforce_cases` |
| [`salesforce_opportunity.schema.json`](../schema/salesforce_opportunity.schema.json) | `salesforce_opportunities` |
| [`calendar_event.schema.json`](../schema/calendar_event.schema.json) | `calendar_events` |
| [`action_item.schema.json`](../schema/action_item.schema.json) | `action_items` |
| [`draft.schema.json`](../schema/draft.schema.json) | `drafts` |
| [`report.schema.json`](../schema/report.schema.json) | `reports` |
| [`chat_thread.schema.json`](../schema/chat_thread.schema.json) | `chats` |
| [`sync_job.schema.json`](../schema/sync_job.schema.json) | `sync_jobs` |
| [`settings.schema.json`](../schema/settings.schema.json) | CBL settings (no secrets). `preferences`: `week_start`, `hidden_weekdays`, `theme`, `timeline_layout`, `timeline_past_days` / `timeline_next_days` (7 or 30). Operator profile may include `persona` (csm / sales / tam / support / custom) and `intent` (textarea, max 4000 chars) — appended to every AI system prompt. |
| [`credential.schema.json`](../schema/credential.schema.json) | CBL `credentials` (AI keys + connector tokens) |
| [`activity.schema.json`](../schema/activity.schema.json) | `activities` |
| [`note.schema.json`](../schema/note.schema.json) | `notes` |
| [`compose_request.schema.json`](../schema/compose_request.schema.json) | `POST /api/drafts/compose` |
| [`operator_patch.schema.json`](../schema/operator_patch.schema.json) | `PATCH .../operator` bodies |

`$id` is `https://csm-dashboard.local/schema/<file>` so `$ref`s stay stable. That host is not served.

## Required header on every schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://csm-dashboard.local/schema/example.schema.json",
  "title": "Example",
  "type": "object"
}
```

| Field | Rule |
| --- | --- |
| `$schema` | Always draft **2020-12** |
| `$id` | `https://csm-dashboard.local/schema/<kebab>.schema.json` |
| `title` | Human name |
| `additionalProperties` | `true` on CBL docs (they grow). Tighten only request bodies that must reject extras. |
| `required` | The fields the store or loader will not accept without |
| `enum` | Closed sets (`status`, `kind`). Spelling is **`cancelled`**, never `canceled`. |

Token-bearing ids: prefix + `[a-z0-9-]{2,32}` (e.g. `^person:[a-z0-9-]{2,32}$`). Hex12 is the **generator**, not the only legal id. Structured ids (`tkt:jira:ACME-12`, `em:{hash20}`) have their own patterns.

Do **not** put secrets, API keys, or note/email bodies in examples.

Inbox **audience** (`me` / `us` / `them` / `all` / `unknown` / `na`) is computed on `GET /api/home/agenda`. It is not a stored field on `emails` or chat docs.

## Adding a schema

1. Create `schema/<name>.schema.json` with the header above.
2. `$ref` it from [`docs/openapi.yaml`](../docs/openapi.yaml).
3. If it is a CBL collection, mention it in [`docs/DESIGN.md`](../docs/DESIGN.md).
4. Extend `tests/test_schema.py`.
5. Run `make ci`.

## Config vs secrets

`config.json` is non-secret (bind, models, default connector *mode*). Operator-chosen mode lives on the CBL `settings` doc. **Secrets live in the CBL `credentials` collection** (`cred:ai:{provider}` / `cred:connector:{name}`), managed from Settings. Never put API keys on `accounts`, `emails`, `tickets`, or the `settings` document. HTTP list/status endpoints return `present` flags only — never `secret` values. Community Lite does not encrypt the file; FileVault is the disk story. Do not replicate the `credentials` collection.
