# CSM Dashboard

A Customer Success Manager desk on your laptop. One operator, many enterprise accounts, one place to see tickets, email chains, Slack, calendar, and account / PS teams — then draft the next email with that context.

Open [http://127.0.0.1:8788](http://127.0.0.1:8788) after you start it.

---

## The pain

CSMs live in five tabs. They lose threads, miss renewals, write emails without ticket or Slack context, and scramble Friday for a weekly report.

| Pain | What you get |
| --- | --- |
| Which book is this? | Color chip + 2–6 char abbreviation on every row |
| What is on fire? | Home board: health, open P1s, overdue actions, unread threads, meetings today |
| What is the story? | Account workspace: timeline, tickets, mail, Slack, calendar, projects, people |
| How do I reply? | Compose builds a draft from tickets + thread tail + Slack + calendar. Grok if you have a key; a template if you do not. **Send is off in v0.1.** |
| What is next? | First-class action items (many per account) |
| Friday report | Generate a weekly from the same context |

Your keys and the database stay on this machine. This is not a second Salesforce.

---

## Run it locally

You need:

1. **Python 3.11+**
2. **Couchbase Lite Community 4.0.3** — on a Mac: `brew install --cask libcblite-community`
3. Optional: an **xAI** key from [console.x.ai](https://console.x.ai) for Grok drafts / chat

```bash
cp .env.example .env
# put XAI_API_KEY in .env if you have one

make venv
make run
```

Then open [http://127.0.0.1:8788](http://127.0.0.1:8788). **Settings → Load seed data** loads three demo books (ACME navy, NWIN forest, GLX burgundy).

The desk binds **127.0.0.1** by default (customer mail and Slack live in the local file). To listen on the LAN: `CSM_DASHBOARD_BIND=0.0.0.0` — there is **no auth**. Community Couchbase Lite does **not** encrypt the `.cblite2` file; FileVault (or equivalent) is the disk story.

Docker:

```bash
docker compose up --build
```

On Apple Silicon the image runs as `linux/amd64` because the Community library is x86_64. Compose publishes `127.0.0.1:8788` only. Data lives in `./data/` on your disk (not in git).

If the build dies on `CERTIFICATE_VERIFY_FAILED` (Netskope / Zscaler / corp TLS inspection), export the intercept CA and rebuild:

```bash
python3 scripts/export_host_cas.py
docker compose up --build
```

See [`certs/README.md`](certs/README.md).

---

## Docs for builders

| Doc | What it is |
| --- | --- |
| [docs/DESIGN.md](docs/DESIGN.md) | How the desk is built |
| [docs/ROADMAP.md](docs/ROADMAP.md) | What’s next (connectors, drafts, chat ops, transcripts, App Services, EE vectors) |
| [guides/OPENAPI.md](guides/OPENAPI.md) | Adding HTTP APIs |
| [guides/HTML_CSS.md](guides/HTML_CSS.md) | Desk UI rules |
| [guides/SCHEMA.md](guides/SCHEMA.md) | JSON Schema conventions |
| [guides/LOGGING.md](guides/LOGGING.md) | `csm.*` events |
| [docs/openapi.yaml](docs/openapi.yaml) | HTTP API |

```bash
make ci         # compileall + node --check + unit tests
make test-e2e   # Playwright Chromium against a local desk
make ci-full    # both
```

Playwright MCP is in `.grok/config.toml` for local UI checks against a running desk (`make mcp-playwright` warms `npx`). In Grok, `/mcps` and enable **playwright**.

Version source of truth: `src/csm_dashboard/__init__.py` → `__version__`. The sidebar badge comes from `/api/status`.

---

## License

Copyright 2026 Fujio Turner.

CSM Dashboard is licensed under the **Apache License, Version 2.0**.
See [`LICENSE`](LICENSE).

Questions: mail@fuj.io
