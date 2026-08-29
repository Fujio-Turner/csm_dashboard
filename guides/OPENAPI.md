# OpenAPI — adding APIs to csm_dashboard

Spec format: [OpenAPI 3.1.0](https://spec.openapis.org/oas/v3.1.0.html).

Spec file: [`docs/openapi.yaml`](../docs/openapi.yaml) — **hand-maintained source of truth**.

Live copy: `GET /openapi.yaml` (same file). FastAPI also exposes `/docs` from its auto map; if they disagree, **fix the handler to match `docs/openapi.yaml`**, do not “fix” the YAML to whatever the code did.

JSON Schema for documents: [`schema/`](../schema/) — see [SCHEMA.md](SCHEMA.md).

## Workflow — new or changed endpoint

Do this in order. A handler without a spec update is not done.

1. **Spec first.** Add the path, method, `operationId`, tags, parameters, request body, and status codes in `docs/openapi.yaml`.
2. **Schema next.** Non-trivial JSON goes in `schema/<name>.schema.json` ([JSON Schema 2020-12](https://json-schema.org/)). Reference it:

   ```yaml
   requestBody:
     content:
       application/json:
         schema:
           $ref: "../schema/example.schema.json"
   ```

3. **Handler.** Implement in `src/csm_dashboard/web/app.py` (or a router included from there). Match path, method, and status codes to the spec. Call `CsmRepo` — do not put SQL++ in the handler.
4. **Log mutations.** Successful writes use `log.info` with a `csm.<area>.<verb>` event and field names — not full bodies or secrets ([LOGGING.md](LOGGING.md)).
5. **UI** only if the desk needs it. Follow [HTML_CSS.md](HTML_CSS.md). New calls go through the `api()` helper in `app.js`.
6. **Test.** Markup or unit test for the new contract. `make ci`.

## Conventions

| Topic | Rule |
| --- | --- |
| Prefix | JSON API is `/api/...`. Health is `/healthz`. Spec is `/openapi.yaml`. |
| `operationId` | camelCase, unique (`listAccounts`, `composeDraft`). |
| Path params | Account ids look like `acct:acme`. Ticket ids look like `tkt:jira:ACME-12`. Encode in the client. |
| Errors | FastAPI `HTTPException` → `{ "detail": "..." }`. Use 400 validation, 404 missing, 409 conflict (`send_not_configured`, `slug_immutable`, abbr clash), 502 upstream (xAI / SMTP). |
| Lists | `{ "items": [...], "total"?: n }` unless the resource already has another shape. |
| Streaming | Chat is `text/event-stream`. |
| Secrets | Never in spec examples. Keys are `PUT /api/settings/keys` only. |
| Sync | `POST /api/connectors/{name}/sync` + `GET /api/sync/jobs`. Do not add `POST /api/sync/{name}`. |

## Tags

Use an existing tag (`meta`, `settings`, `accounts`, `people`, `projects`, `tickets`, `mail`, `slack`, `teams`, `salesforce`, `calendar`, `actions`, `drafts`, `reports`, `chat`, `sync`). Add a tag only when a whole new area lands.

## What not to do

- Do not add a second OpenAPI file per feature.
- Do not generate the checked-in YAML from FastAPI and commit the dump as SoT.
- Do not invent fields on `accounts` that belong in tickets, emails, Slack, or calendar.
- Do not version the URL (`/api/v2`) until 1.0 needs a break.

## Check

```bash
make check-schema
make ci
```

`GET http://127.0.0.1:8788/openapi.yaml` after `make run`.
