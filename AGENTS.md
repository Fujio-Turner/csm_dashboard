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

## Spec first

`docs/openapi.yaml` is SoT. JSON Schema under `schema/`. Guides: [`guides/OPENAPI.md`](guides/OPENAPI.md), [`guides/SCHEMA.md`](guides/SCHEMA.md), [`guides/HTML_CSS.md`](guides/HTML_CSS.md).

## Local gate

```bash
make ci    # compileall + node --check + pytest
```
