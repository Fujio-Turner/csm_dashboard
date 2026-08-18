# Logging — csm_dashboard

Use **stdlib `logging`**. Structured events, no secrets, field names not bodies.

Format (`logging_setup.py`):

```text
%(asctime)s %(levelname)s %(name)s %(message)s
```

Event names: `csm.<area>.<verb>`.

## Rules

| Do | Don't |
| --- | --- |
| `log.info("csm.account.updated account_id=%s changed_fields=%s", aid, fields)` | Dump the account JSON |
| Log **field names** that changed | Log email / Slack / Jira bodies |
| `Error` + `err=` on write/sync failures | Swallow with only HTTP 500 |
| Log `csm.draft.compose result=fallback` | Log the draft body |
| Log token counts on `csm.ai.complete` | Log the Grok prompt payload |

## Catalogue

| Event | When |
| --- | --- |
| `csm.boot` | lifespan start (`version`, `db`, `host`) |
| `csm.boot.bind` | **Warn** when `host=0.0.0.0` (`auth=none`) |
| `csm.operator.patched` | operator PATCH; `collection`, `id`, field names |
| `csm.account.created` / `updated` | `changed_fields` |
| `csm.person.saved` | create/patch; `changed_fields` on patch (includes `project_ids`, `functions`) |
| `csm.activity.tagged` | timeline input assigned a project; `activity_id`, `project_id` |
| `csm.project.saved` | create/patch; `changed_fields` on patch |
| `csm.project.deleted` | soft-remove; `project_id` |
| `csm.ticket.upserted` | `key`, `account_id` |
| `csm.email.upserted` | `thread_id`, `direction` |
| `csm.task.created` / `updated` | self-email task; `account_id`, `task_kind`, `cc_count` on create |
| `csm.slack.upserted` | `channel_id` |
| `csm.calendar.upserted` | `external_id` |
| `csm.action.created` / `updated` / `done` | |
| `csm.note.added` | `account_id` only |
| `csm.chat.updated` | bookmark/title patch; `changed_fields` |
| `csm.account.removed` | Settings remove company |
| `csm.account.logo_saved` / `logo_deleted` | company tile image |
| `csm.draft.suggest_reply` | email reply suggestion; `result=grok\|fallback` |
| `csm.settings.provider_test` | AI test button |
| `csm.connector.test` | connector Test button |
| `csm.draft.created` / `updated` / `compose` | `result=grok\|fallback`, `prompt_name` |
| `csm.draft.send_blocked` | v0.1 409 |
| `csm.report.generated` | `kind`, `account_id` |
| `csm.ai.complete` | `account_id`, `prompt_name`, `model`, token counts, `truncated` |
| `csm.chat.turn` | `model`, `tools=`, `result=` |
| `csm.sync.started` / `finished` / `failed` | `connector`, counts, `err` |
| `csm.route.ambiguous` | hint fields, candidate abbrs |
| `csm.health.updated` | `account_id`, `score`, `scored_by` |
| `csm.settings.updated` / `keys_updated` | field names |
| `csm.seed.applied` | counts per collection |
| `csm.store.reset` | |
| `csm.query.fts_failed` | `err` |
| `csm.index.fts_failed` | |
| `csm.cbl.unavailable` | boot |

**Logs ship with the handler.** Do not defer “missing logs” to a polish PR.

No Prometheus in v0.1.

`CSM_DASHBOARD_LOG=DEBUG` may log SQL text — still no bodies.
