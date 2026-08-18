# CSM Dashboard roadmap

> Living train map · last updated **2026-08-17**  
> **Current baseline:** `0.1.0`

This file answers: **what ships when**. Design depth lives in [`docs/DESIGN.md`](docs/DESIGN.md).

---

## 0. Source of truth

| Concern | Canonical home |
| --- | --- |
| **This train map** | `ROADMAP.md` |
| System design | [`docs/DESIGN.md`](docs/DESIGN.md) |
| HTTP contract | [`docs/openapi.yaml`](docs/openapi.yaml) · [`guides/OPENAPI.md`](guides/OPENAPI.md) |
| Documents | [`schema/`](schema/) · [`guides/SCHEMA.md`](guides/SCHEMA.md) |
| Desk UI | [`guides/HTML_CSS.md`](guides/HTML_CSS.md) |
| Version | `src/csm_dashboard/__init__.py` `__version__` |

---

## 1. v0.1.0 (this tag) — local desk on fixtures

| Area | State |
| --- | --- |
| Repo / Docker / `make ci` | `127.0.0.1:8788`, compose loopback publish |
| Couchbase Lite CE 4.0.3 | ctypes wrapper in this repo |
| Seed books | ACME / NWIN / GLX — color + abbr |
| Home + Account workspace | Timeline, tickets, mail, Slack, calendar, projects, people |
| Compose | Context builder + Grok or template fallback. **Send = 409** |
| Actions + weekly reports + account chat | Chat works without an xAI key (fallback SSE) |
| Connectors | Protocol + stubs. Sync reads `fixtures/seed/` |

Not in 0.1: live OAuth, SMTP send, Jira write, Slack write, Capella, auth, Prometheus.

---

## 2. Next trains

### 0.2 — first live connector + send

**Locked:** Jira Cloud API token first, then IMAP, then Slack read, then Google / M365 OAuth.

| Item | Notes |
| --- | --- |
| Jira Cloud REST | Token in `data/secrets.json`. Incremental `updated >= since`. Comments cap 10 × 2k |
| Confirm-before-send | SMTP or Gmail/Graph. Modal shows chip + abbr + To. No auto-send |
| Unassigned inbox | Events with empty `account_id` after ambiguous routing |

### 0.3 — mail + Slack read

| Item | Notes |
| --- | --- |
| IMAP / app password | Deterministic `em:` / `thr:` ids already locked |
| Slack bot + user token | `conversations.history`. Timeline still roots / pins / mentions only |
| Shared mailbox | Additive `emails.mailbox_id` — no schema break |

### 0.4 — calendars + OAuth

| Item | Notes |
| --- | --- |
| Google Calendar + Microsoft Graph | OAuth refresh in secrets only |
| Create invite from an action | Outbound connector, not on the v0.1 Protocol |

### 0.5 — Capella / second device

Conflict resolver **before** pull (first-party fields win vs connector refresh; two laptops editing notes need a written rule). Not a remodel — documents stay JSON in CBL.

---

## 3. Explicitly later / not this product

- Multi-tenant SaaS
- Salesforce / Gainsight as the store (this desk already has a **Salesforce connector** for opportunities + cases; do not move the store into Salesforce)
- Live Salesforce REST / OAuth (stub + fixtures first)
- Electron + SQLite
- Attachment / HTML legal-hold archive
- Prometheus (add `/metrics` only if you later run this next to an ops stack)
