# CSM Dashboard roadmap

> Living train map · last updated **2026-08-29**  
> **Current baseline:** `0.1.85` · Apache License 2.0

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

## 1. Shipped now (0.1.85)

| Area | State |
| --- | --- |
| Repo / Docker / `make ci` | `127.0.0.1:8788`, compose loopback publish. Playwright MCP: `.grok/config.toml` |
| Store | Couchbase Lite **Community 4.0.3**, ctypes wrapper in this repo. No vector index |
| Home | Agenda and Companies tiles. Mini sidebar default. Meeting cards: company logo left, duration minutes right, subject on the card. Inbox rows: type icon + company logo |
| Agenda calendar | **Day / Week / Month**. 24-hour Day and Week, default scroll ~7 AM. Now line. Time-proportional gaps. Hide weekdays and week-begins from User Preferences |
| Deep links | `#account/{abbr}/{tab}/id={id}` opens the matching meeting, mail, chat, or task lightbox |
| Inbox | Mail, Slack, Teams, **tasks** (self-emails). Filter All / Email / Slack / Tasks / Teams. `+` creates a task |
| World clock | Globe lightbox. Add / remove / reorder zones. Persists in CBL `settings.world_clock` |
| Appearance | Settings → User Preferences: Day / Night / Auto. Sidebar sun/moon toggle. `html[data-theme]` |
| Account | Timeline, tickets, mail, **slack / teams** (one tab), Salesforce, calendar, **projects CRUD**, people, org chart, account team |
| Timeline | Vertical (future top, oldest bottom) or Horizontal (past left, future right). Red **Now** line + **Now** button. Past 7 / 30 and Next 7 / 30 bound the window. Horizontal range labels are spine text so the rail stays narrow |
| People | Add / Edit person sheet (`#detail-box` `.sheet-person`). Org chart scrolls; the tree is `max-content` so the left edge is not clipped |
| Projects | Search, type, status, owner from people, group email, Tagify tags, remove |
| Compose | Context builder + Grok or template. Suggest reply writes a `drafts` doc. **Send after confirm** when SMTP is live; otherwise 409 `send_not_configured` |
| Chat | Desk / account scoped. Fallback SSE without a key |
| Settings / Help | Sectioned operator profile, companies, AI keys, connectors, lab seed, User Preferences |
| Connectors | Live **Jira**, **Slack**, **Teams**, **Gmail**, **Google Calendar**. **SMTP send** (drafts + task self-emails) after confirm when `smtp_imap` is live. Gmail/Calendar use local `credentials.json` plus Sign in with Google. Seed is Lab; Sync no longer replays fixtures. |
| Credentials | CBL `credentials` collection. Settings → AI keys + connector tokens. GET never returns secret values. Secrets and OAuth client JSON live in gitignored `__local/` |

**Not shipped:** IMAP / Salesforce live pull, Zendesk, Jira write, Pydantic AI multi-agent desk, scratch TTL collection, App Services sync, EE vectors, transcript ingest, PDF/image chat, slash-in-chat, finished QBR/monthly reports, shared mailbox.

---

## 2. Rules that do not move

| Rule | Why |
| --- | --- |
| **Never send a whole project to the model** | A long book (years of tickets, mail, Slack, notes) will not fit and will not stay relevant. Chat and compose retrieve a **brief + the slice that answers this turn** |
| **Confirm before send** | Drafts land in `drafts`. Human hits send. No auto-outbound |
| **CBL JSON is the store** | App Services is **replication**. Confluence is a **wiki sidecar**. Zendesk / Jira stay connectors |
| **First-party fields win** | Operator notes, task edits, and project tags survive connector refresh. Write the conflict rule **before** any pull |
| **Community stays the default** | EE (vector index) is an explicit later train. Do not require EE to open the desk |
| **Scratch is derived** | TTL summaries are disposable. They never overwrite tickets, mail, notes, or `operator.*`. Invalidate when the source `updated_at` moves |

**Project context (how talk-about-a-project works):**

1. Each project keeps a short **`project_brief`** document in CBL (goals, owners, open risks, last meeting, next date). Updated incrementally when mail, tickets, or notes change — not by dumping the archive into Grok.
2. A turn retrieves: the brief + top-N related tickets / threads / tasks / last transcript. That pack is what the model sees.
3. Optional **Confluence** push/pull: pull a space/page into the brief; push QBR / weekly status *out*. Confluence is the long-form wiki, not the prompt.
4. When **CBL EE** is on, vector search picks the slice. Until then: FTS `MATCH` + recency + project_id.

---

## 3. Next trains

### 0.2 — read-only content aggregator

The desk is a **local inbox of other systems**. No outbound mail, no Jira comments, no Slack posts. Manage every connection on **Settings**. Tokens live in CBL `credentials` (`cred:ai:*`, `cred:connector:*`), not `data/secrets.json`. Mode (`stub` / `live` / `off`) lives on the CBL `settings` doc (overlays `config.json`).

**Sign-in:** **Sign in with Okta/OIDC** (issuer URL + native client ID, loopback callback). That identity is then used to Connect Gmail / Microsoft / Slack. Connector mode is **live** or **disabled**. Jira and IMAP still use a pasted API token / app password.

**AI:** multiple keys (Grok, OpenAI, Gemini) + a provider/model select. Compose, chat, and reports use the selected provider. Empty password fields keep the stored key.

**Live reads, locked order:** Jira token → Slack read → Teams Graph → IMAP → **Zendesk** → Google / M365 mail.

| Item | Notes |
| --- | --- |
| Jira Cloud REST | **Shipped 0.1.57.** Token from Settings / `credentials`. Incremental `updated >= since`. Comments cap 10 × 2k |
| Slack bot + user token | **Shipped 0.1.57.** Paste `xoxp-` or OAuth. `conversations.history`. Timeline still roots / pins / mentions |
| Teams Graph | **Shipped 0.1.57.** Microsoft Connect (`Chat.Read`). Chats you belong to; channel messages if the token allows |
| IMAP / app password | Deterministic `em:` / `thr:` ids already locked |
| **Zendesk** | Tickets + comments as another input on the book. Map org/domain → `account_id`. Same operator triage as Jira |
| Unassigned inbox | Events with empty `account_id` after ambiguous routing |

### 0.3 — tasks as special self-emails

Tasks are **emails back to yourself**, stored as `emails` with `operator.task=true` and subject `Tasks: {Company} : {name} {{kind}}`. The Agenda Tasks filter already treats those as special. This train makes them leave the laptop.

| Item | Notes |
| --- | --- |
| **Local create (already shipped)** | Agenda `+` / `POST /api/tasks` writes a self-email (`from=to=operator`). Inbox kind `task`. |
| **Send to self** | **Shipped 0.1.70.** After confirm, SMTP delivers the formatted task (`POST /api/tasks/{id}/send`) and drafts (`POST /api/drafts/{id}/send`). 409 `send_not_configured` when SMTP is disabled or missing. Never auto-send. |
| **Suggested reply → Draft** | **Shipped 0.1.70.** Suggest reply writes a `drafts` doc. Operator can edit, then Send. |
| **Shared mailbox** | Additive `emails.mailbox_id` — no schema break |

### 0.4 — chat operates the desk

Slash types already work on **account search**. This train wires the **same verbs into desk chat**.

| Item | Notes |
| --- | --- |
| **Slash in chat** | `/note`, `/project`, `/people`, `/ticket`, `/task`, `/email`, `/sf` create or open, not only filter. Chat stays scoped to the book |
| **Create meeting invite** | Chat proposes title, attendees, window (world clock helps). Writes a calendar draft; connector sends after confirm |
| **Create task (email)** | Chat creates the same self-email task as Agenda `+` (`Tasks: Company : name {kind}`, due, CC) |
| **Analyze support tickets** | Summarize open / aging / P1s for the book or one key. Uses ticket slice, not the whole history |
| **Review email chains** | Thread brief: ask, last customer line, open promise, suggested next draft |

### 0.45 — Pydantic AI multi-agent + scratch TTL

Chat and compose stay **one operator turn**. Under that turn, a Python **Pydantic AI** orchestrator (typed agents, `pydantic-ai` + a small specialist catalog — the “+”) fans out to the book’s live sources instead of stuffing Jira + mail + Slack + Teams into one prompt.

This does **not** replace CBL. Agents **read** `CsmRepo` and existing connectors (`jira`, `google_mail`, `slack`, `teams`, calendar, Salesforce when live). They **write** either a chat answer, a `drafts` doc, or a scratch summary. Confirm-before-send still holds: nothing posts to mail / Slack / Teams / Jira until the operator hits send.

**When it runs**

| Trigger | What the orchestrator does |
| --- | --- |
| Desk / account chat (“What’s going on with ACME?”) | Pick specialists (tickets, mail, Slack, Teams, tasks, calendar). Merge into a short brief for this turn |
| Reply to **email / Slack / Teams / task** | Same pack, scoped to that thread or task. Result is a `drafts` row (To / channel / body), not a send |
| Ticket or project question | Ticket agent first; others only if the ask needs them |

**Specialist catalog** (each is a Pydantic AI agent with a typed result, not a free-text blob)

| Agent | Reads | Returns (typed, small) |
| --- | --- | --- |
| `ticket` | Jira connector + `tickets` | key, status, last comment, 1-paragraph summary |
| `mail` | Gmail / IMAP + `emails` / `threads` | last customer line, open promise, thread id |
| `slack` | Slack history + `slack_messages` | last roots / mentions in mapped channels |
| `teams` | Graph chats + `teams_messages` | same shape as Slack |
| `task` | self-email tasks | open tasks, due, CC |
| `calendar` | Google / M365 cal | next meeting, attendees |
| `reply` | the pack above | draft subject + body for the current channel |

Fan-out is capped (a handful in parallel, timeout per child). The orchestrator may skip a specialist when the connector is `disabled` or not connected. Missing source ≠ failed turn.

**Scratch collection (`scratch`) — same-day reuse**

CBL Community has no Server-style document expiry. We store **`expires_at`** and purge.

| Rule | Why |
| --- | --- |
| Collection `scratch`, never replicated | Disposable. Tokens never land here |
| Doc id like `scratch:{kind}:{subject}:{day}` | Example: `scratch:ticket_summary:tkt:jira:ACME-12:2026-08-28` |
| Default TTL **end of operator local day** (world-clock timezone), clamp 4h–24h | “I asked about ACME-12 this morning; this afternoon reuse it” |
| Fields | `kind`, `subject`, `account_id`, `source_updated_at`, `expires_at`, `text` (cap ~2k), `model` |
| **Reuse** if `now < expires_at` **and** source `updated_at` is unchanged | If Jira moved, recompute and replace the scratch doc |
| **Compare** | Optional second field `prev_text` when a refresh happens the same day so chat can say what changed |
| Sweeper | On chat/compose turn + idle tick: delete `expires_at < now`. No EE, no vector index |

Example: first chat turn summarizes ACME-12 from Jira (comments still capped 10 × 2k). A later turn the same day about that key **does not** re-pull the issue unless `updated_at` changed. Mail/Slack specialists still run if the question needs them.

**Prompt rule stays:** the model sees the **brief + this turn’s specialist results** (and any still-valid scratch docs). Never the whole book.

**Not in this train:** auto-send, auto-Jira comment, a second chat UI, or a new HTTP API per source. New capability is a specialist agent on top of an existing connector.

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
| **Secrets stay local** | API keys live in CBL `credentials`. **Never replicate that collection.** Community Lite is not encrypted; FileVault is the disk story. GET endpoints return present/absent only. |

---

## 4. Suggested order (do not skip the resolver)

```text
0.2 read-only aggregator (Settings credentials + Jira → mail → Slack → Zendesk)
0.3 tasks as special self-emails (SMTP send-to-self after confirm)
0.4 chat slash / invites / tasks / ticket+thread review
0.45 Pydantic AI multi-agent + scratch TTL (fan-out reads; drafts still confirm)
0.5 PDF, screenshots, transcript → proposed tasks
0.6 weekly / monthly / QBR finished
0.7 project_brief + optional Confluence
0.8 App Services sync + EE vectors
```

0.45 needs live reads (0.2) so specialists have something to fetch. 0.7 can start as soon as chat is useful; scratch summaries are a stepping stone to `project_brief`, not a replacement. 0.8 can overlap 0.7 if you need two machines, but **the conflict resolver ships before the first pull**. Scratch is never replicated.

---

## 5. Explicitly later / not this product

- Multi-tenant SaaS
- Salesforce / Gainsight as the store (Salesforce stays a **connector** for opportunities + cases)
- Electron + SQLite (CBL is the store so App Services does not require a remodel)
- Attachment / HTML legal-hold archive (excerpts + disk files, not a records system)
- Auto-send mail or auto-create customer-facing tickets from a transcript
- Requiring CBL EE to open the desk
- Prometheus (add `/metrics` only if this later sits next to an ops stack)
