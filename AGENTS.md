# Agent notes — CSM Dashboard

Short rules for AI coding agents in this repo.

## What this is

Local **Customer Success Manager desk**. Standalone product. One operator, one machine, port **8788**.

Do not fold this UI into another product. The ctypes wrapper lives in `src/csm_dashboard/storage/cblite.py` — do not import a wrapper from another repo.

## Version

Source of truth: `src/csm_dashboard/__init__.py` → `__version__` (keep `pyproject.toml` in lockstep).
The sidebar badge comes from `/api/status`. **Never** hard-code the semver in JS.

## Desk JS

Vanilla IIFE. **Never nest raw backticks** inside template literals. Prefer `createElement` + `textContent`.

Function declarations in that IIFE share one scope. **Never declare two `function foo`.** The later wins; earlier call sites throw. The empty Edit person sheet was `fieldLabel` colliding with a settings formatter (now `humanizeField`).

Account tabs live in `ACCOUNT_TABS`. Slack and Teams are one `chat` tab labeled **slack / teams**. `#account/{abbr}/slack` and `/teams` alias to it. Deep links: `#account/{abbr}/{tab}/id={id}`.

```bash
make check-js
# node --check src/csm_dashboard/web/static/app.js
# node --check src/csm_dashboard/web/static/compose.js
```

If that fails, the change is not done.

## Logging

stdlib `logging`. Event names `csm.<area>.<verb>`. Field names, not email/Slack/Jira bodies. No secrets. Mutations log in the **same change** as the handler. See [`guides/LOGGING.md`](guides/LOGGING.md).

## Store

Couchbase Lite **Community 4.0.3**. Strip top-level `_id` / `_created` on save. No vector index (EE). SQL++ lives in `CsmRepo` / `CBLStore` — **not** in `web/app.py`. Tests inject `create_app(repo=CsmRepo(MemoryStore()))`.

Default bind **127.0.0.1**. `CSM_DASHBOARD_BIND=0.0.0.0` is explicit and logged (`csm.boot.bind auth=none`).

**`__local/` is gitignored.** Operator credentials, OAuth client JSON, and machine URLs live there (`__local/SETUP.md`, `__local/credentials.json`). Never copy that folder into a commit, a PR, or the Docker image.

## Spec first

`docs/openapi.yaml` is SoT. JSON Schema under `schema/`. Guides: [`guides/OPENAPI.md`](guides/OPENAPI.md), [`guides/SCHEMA.md`](guides/SCHEMA.md), [`guides/HTML_CSS.md`](guides/HTML_CSS.md).

## Local gate

```bash
make ci         # compileall + node --check + unit tests
make test-e2e   # Playwright Chromium against a local MemoryStore desk
make ci-full    # ci + e2e
```

## Playwright MCP (local browser)

Project MCP: `.grok/config.toml` → `playwright`. Isolated Chromium, 1280×800. Desk must already be up.

```bash
make mcp-playwright   # first-time npx fetch
# Grok: /mcps → enable playwright, or start Grok from this repo
```

When a change is something a user sees (Settings, Home, OAuth copy, connectors), open `http://127.0.0.1:8788` (or `http://localhost:8788` under Docker) and exercise the path. Do not stop at a screenshot of a single render.
