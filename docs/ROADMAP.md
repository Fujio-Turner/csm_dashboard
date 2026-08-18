# CSM Dashboard roadmap

> Living train map · last updated **2026-08-18**  
> **Current baseline:** `0.1.32` · Apache License 2.0

This file answers **what ships when**. Design depth lives in [`DESIGN.md`](DESIGN.md).

The desk stays **one operator, one machine, Couchbase Lite JSON documents**. Bigger features (App Services, EE vectors, Confluence) attach to that store. They do not replace it.

---

## 0. Source of truth

| Concern | Canonical home |
| --- | --- |
| **This train map** | `docs/ROADMAP.md` |
| System design | [`DESIGN.md`](DESIGN.md) |
| HTTP contract | [`openapi.yaml`](openapi.yaml) · [`guides/OPENAPI.md`](../guides/OPENAPI.md) |
| Documents | [`schema/`](../schema/) · [`guides/SCHEMA.md`](../guides/SCHEMA.md) |
| Desk UI | [`guides/HTML_CSS.md`](../guides/HTML_CSS.md) |
| Version | `src/csm_dashboard/__init__.py` `__version__` |

---

## 1. Shipped now (0.1.32)

| Area | State |
| --- | --- |
| Repo / Docker / `make ci` | `127.0.0.1:8788`, compose loopback publish |
| Store | Couchbase Lite **Community 4.0.3**, ctypes wrapper in this repo. No vector index |
| Home | Agenda (meetings + mixed inbox) and Companies tiles. Mini sidebar default |
| Inbox | Mail, Slack, Teams, **tasks** (self-emails). Filter All / Email / Slack / Tasks / Teams. `+` creates a task |
| World clock | Globe lightbox. Add / remove / reorder zones. Persists in CBL `settings.world_clock` |
| Account | Timeline, tickets, mail, Slack, Teams, Salesforce, calendar, **projects CRUD**, people |
| Projects | Search, type, status, owner from people, group email, Tagify tags, remove |
| Compose | Context builder + Grok or template. Suggest reply exists. **Send = 409** |
| Chat | Desk / account scoped. Fallback SSE without a key |
| Settings / Help | Sectioned operator profile, companies, AI keys, connectors, lab seed |
| Connectors | Protocol + stubs. Sync still reads `fixtures/seed/` |

**Not shipped:** live OAuth, SMTP send, Jira/Zendesk write, App Services sync, EE vectors, transcript ingest, PDF/image chat, slash-in-chat, finished QBR/monthly reports.

---

## 2. Rules that do not move

| Rule | Why |
| --- | --- |
| **Never send a whole project to the model** | A long book (years of tickets, mail, Slack, notes) will not fit and will not stay relevant. Chat and compose retrieve a **brief + the slice that answers this turn** |
| **Confirm before send** | Drafts land in `drafts`. Human hits send. No auto-outbound |
| **CBL JSON is the store** | App Services is **replication**. Confluence is a **wiki sidecar**. Zendesk / Jira stay connectors |
| **First-party fields win** | Operator notes, task edits, and project tags survive connector refresh. Write the conflict rule **before** any pull |
| **Community stays the default** | EE (vector index) is an explicit later train. Do not require EE to open the desk |

**Project context (how talk-about-a-project works):**

1. Each project keeps a short **`project_brief`** document in CBL (goals, owners, open risks, last meeting, next date). Updated incrementally when mail, tickets, or notes change — not by dumping the archive into Grok.
2. A turn retrieves: the brief + top-N related tickets / threads / tasks / last transcript. That pack is what the model sees.
3. Optional **Confluence** push/pull: pull a space/page into the brief; push QBR / weekly status *out*. Confluence is the long-form wiki, not the prompt.
4. When **CBL EE** is on, vector search picks the slice. Until then: FTS `MATCH` + recency + project_id.

---

## 3. Next trains

### 0.2 — live read connectors

**Locked order:** Jira token → IMAP → Slack read → **Zendesk** → Google / M365 OAuth.

| Item | Notes |
| --- | --- |
| Jira Cloud REST | Token in `data/secrets.json`. Incremental `updated >= since`. Comments cap 10 × 2k |
| IMAP / app password | Deterministic `em:` / `thr:` ids already locked |
| Slack bot + user token | `conversations.history`. Timeline still roots / pins / mentions |
| **Zendesk** | Tickets + comments as another input on the book. Map org/domain → `account_id`. Same operator triage as Jira |
| Unassigned inbox | Events with empty `account_id` after ambiguous routing |

### 0.3 — drafts that persist

| Item | Notes |
| --- | --- |
| **Suggested reply → Draft** | Suggest reply already exists. Save the result as a `drafts` doc (To / Subject / body), not only a toast. Operator edits, then send (0.2 confirm-before-send) |
| **New email from chat / task** | Same draft collection. Chip + abbr on the draft so the wrong book cannot go out |
| **More AI providers** | Keys already: Grok, OpenAI, Gemini. Finish provider test + model lists. Add Anthropic (and later others) the same way: key in secrets, `ai.provider`, no prompt logging |
| Shared mailbox | Additive `emails.mailbox_id` — no schema break |

### 0.4 — chat operates the desk

Slash types already work on **account search**. This train wires the **same verbs into desk chat**.

| Item | Notes |
| --- | --- |
| **Slash in chat** | `/note`, `/project`, `/people`, `/ticket`, `/task`, `/email`, `/sf` create or open, not only filter. Chat stays scoped to the book |
| **Create meeting invite** | Chat proposes title, attendees, window (world clock helps). Writes a calendar draft; connector sends after confirm |
| **Create task (email)** | Chat creates the same self-email task as Agenda `+` (`Tasks: Company : name {kind}`, due, CC) |
| **Analyze support tickets** | Summarize open / aging / P1s for the book or one key. Uses ticket slice, not the whole history |
| **Review email chains** | Thread brief: ask, last customer line, open promise, suggested next draft |

### 0.5 — files and meeting transcripts

| Item | Notes |
| --- | --- |
| **PDF + images / screenshots** | Attach to chat or a note. Extract text (PDF) / caption (screenshot). Store bytes on disk (like logos), metadata + excerpt in CBL. Never put the raw file in the prompt — only the excerpt |
| **Meeting transcript listen** | Ingest transcript from Meet / Teams / Zoom / a drop folder. Parse **Action item / Follow up / To-do**. Propose tasks (self-emails) with owner + due. Operator accepts before they land in Agenda |
| Create invite from an action | Complements 0.4 calendar draft |

### 0.6 — reports that finish

Generate weekly already stubs. This train makes reports something you send.

| Item | Notes |
| --- | --- |
| **Weekly** | Finish generate → review sheet → export / draft email. One book or the portfolio |
| **Monthly** | Same pipeline, longer window, renewal + health trend |
| **QBR** | Pull project brief + closed/open work + last transcripts + health. Draft the narrative; do **not** stuff every ticket into the model. Optional Confluence push of the accepted QBR |

### 0.7 — project memory + Confluence

This is the “project got big” train. It can start on CE (brief + FTS). EE vectors (0.8) make retrieval better, not required to start.

| Item | Notes |
| --- | --- |
| **`project_brief` doc** | One per `proj:`. Rolling summary, owners, risks, next date. Updated on ingest / note / task — small, always prompt-safe |
| **Retrieve, don’t dump** | Compose, chat, and QBR load brief + ranked slice (`project_id`, recency, FTS) |
| **Confluence (optional)** | OAuth. Pull page → refresh brief. Push accepted weekly / QBR. Confluence is not the database |

### 0.8 — App Services sync + CBL EE vectors

| Item | Notes |
| --- | --- |
| **Couchbase App Services** | CBL replicator push/pull to Capella App Services (or Server + Sync Gateway). Same collections, same JSON. Second device / backup without remodeling |
| **Conflict resolver first** | Write it before enabling pull. First-party `operator.*`, notes, project tags, world clock, and task emails win vs connector refresh. Two laptops editing a note need a documented rule |
| **Channels / access** | One operator still. Channels per `account_id` so a book can be scoped later. Do not invent multi-tenant SaaS here |
| **CBL Enterprise** | Optional build / flag. Add vector index binds in `cblite.py` **only** on EE. Use for project-slice retrieval, transcript chunks, and ticket/email similarity. CE build must still run (FTS fallback) |
| **Secrets stay local** | API keys never replicate. `data/secrets.json` mode 0600 |

---

## 4. Suggested order (do not skip the resolver)

```text
0.2 live reads (Jira → mail → Slack → Zendesk)
0.3 drafts persist + more providers
0.4 chat slash / invites / tasks / ticket+thread review
0.5 PDF, screenshots, transcript → proposed tasks
0.6 weekly / monthly / QBR finished
0.7 project_brief + optional Confluence
0.8 App Services sync + EE vectors
```

0.7 can start as soon as chat is useful. 0.8 can overlap 0.7 if you need two machines, but **the conflict resolver ships before the first pull**.

---

## 5. Explicitly later / not this product

- Multi-tenant SaaS
- Salesforce / Gainsight as the store (Salesforce stays a **connector** for opportunities + cases)
- Electron + SQLite (CBL is the store so App Services does not require a remodel)
- Attachment / HTML legal-hold archive (excerpts + disk files, not a records system)
- Auto-send mail or auto-create customer-facing tickets from a transcript
- Requiring CBL EE to open the desk
- Prometheus (add `/metrics` only if this later sits next to an ops stack)
