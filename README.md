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

---

## Docs for builders

| Doc | What it is |
| --- | --- |
| [docs/DESIGN.md](docs/DESIGN.md) | How the desk is built |
| [ROADMAP.md](ROADMAP.md) | What’s next (live Jira, IMAP, Slack, OAuth, send) |
| [guides/OPENAPI.md](guides/OPENAPI.md) | Adding HTTP APIs |
| [guides/HTML_CSS.md](guides/HTML_CSS.md) | Desk UI rules |
| [guides/SCHEMA.md](guides/SCHEMA.md) | JSON Schema conventions |
| [guides/LOGGING.md](guides/LOGGING.md) | `csm.*` events |
| [docs/openapi.yaml](docs/openapi.yaml) | HTTP API |

```bash
make ci    # compileall + node --check + pytest
```

Version source of truth: `src/csm_dashboard/__init__.py` → `__version__`. The sidebar badge comes from `/api/status`.

---

## License

CSM Dashboard is licensed under the **Business Source License 1.1 (BUSL-1.1)**
with `Additional Use Grant: None` — **no production use is permitted
without a commercial license** from the copyright holder.
The license converts to **Apache License 2.0** on the Change Date
(2030-08-17).

- Repo-wide default: [`LICENSE`](LICENSE)
- Full BSL text and parameters: [`licenses/BSL-1.1.txt`](licenses/BSL-1.1.txt)

**Commercial licensing or questions:** mail@fuj.io
