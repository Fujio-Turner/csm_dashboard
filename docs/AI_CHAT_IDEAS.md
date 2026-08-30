# Desk chat — what it should solve

Operator questions the **right-hand desk chat** should answer from the open book (or `#{ABBR}` / `@person` / `/project` / `/ticket` in the prompt). This is the target set, not a claim that every question already works.

Chat **reads** the local book. It **never invents** tickets, replies, or meeting times. It **never sends** mail, Slack, Teams, or calendar invites — it proposes; the operator confirms.

Tags in questions below match the desk: `#{ACME}` is a book, `@bob` is a person, `/project XYZ` and `/ticket 12345` are slash jumps already used on account search.

---

## Follow-up and fire

| Ask | What a good answer does |
| --- | --- |
| What tickets do I need to follow up on? | Open / aging / P1–P2 (or Highest) on this book. Last customer line vs last us line. Promise without a later task. |
| What is on fire at `#{ACME}`? | Same, plus blocked projects, overdue tasks, and meetings that slipped. Short. Named keys and people, not a vibe. |
| What tasks are due this week? | Self-email tasks (`operator.task=true`) whose due date falls in the current week (operator timezone). Amber due stamp on Agenda is the same set. |

## Projects and blockers

| Ask | What a good answer does |
| --- | --- |
| Is project XYZ behind? What is the blocker? | Project status, owner, open tickets on that project, Slack/Teams that say blocked, last customer mail. If nothing says blocked, say so. |
| Who seems to be driving the conversations for Acme:SSO hardening — us, them, or both? Who on their end and our end? | Count recent mail / Slack / Teams on that **Company:Project**. Who starts threads, who replies last, who is only CC. Map to people (customer vs account team). Use the same Me / Us / Them idea as inbox who-stamps. |

## Ticket quality

| Ask | What a good answer does |
| --- | --- |
| What tickets look like a configuration or user issue vs a problem with the product or service? | Split open tickets by language in summary/comments (setup, how-to, permissions vs crash, outage, defect). Label **uncertain** when the text is thin. Never invent a root cause. |

## Mail, CC, and tone

| Ask | What a good answer does |
| --- | --- |
| What is the tone of the email chain for `/project XYZ` this last 6 weeks? | Threads tagged to that project, last 6 weeks. Calm / tense / stalled / escalating, with two or three quoted lines. Not a sentiment score. |
| Did `@bob` from `#{ACME}` reply to my last email? | Last outbound from You to that person (or thread they are on). Inbound after that timestamp, or **no**. |
| Has `rick.smith@acme.com` been CCed on the last few emails about `/ticket 12345`? | Last N messages on that ticket’s threads. Yes/no per message, with dates. |
| When did the director or VP get added/CCed to this email or ticket? | First time a person whose title/kind is director or VP (or reports-to chain) appears on To/Cc of that thread or ticket. Date + which message. |

## Meetings, tasks, and time

| Ask | What a good answer does |
| --- | --- |
| In any of yesterday’s meetings I had, are there action items that I didn’t create a task on yet? | Yesterday’s calendar (operator timezone). Promises in the meeting title/notes/linked Slack vs existing tasks. List the gaps; do not auto-create. |
| When is a typical datetime that members of Acme:SSO hardening have been available to meet? I want to suggest invites next week that they are likely to accept without too much back and forth. | Past accepted meetings with those people. Overlap of their local hours (people.location / timezone when set) and the world clock. Propose **windows next week**, not a send. |
| What’s a good time for a meeting with customer X: new project — they have an offshore team in India that will be doing the bulk of the work? | India working hours ∩ You ∩ named customer contacts on that book. World clock rows. Propose two or three windows; do not invent attendees. |

## QBR and the last 90 days

| Ask | What a good answer does |
| --- | --- |
| There is a QBR coming up with customer XYZ. What topics / issues / tickets do we need to address better? Also, what are some good things we did for them the last 90 days? | Two lists from the book, last 90 days: (1) open/aging/P1, blocked projects, unanswered mail; (2) closed tickets, shipped projects, QBRs already held, thanks in mail/Slack. Cite keys. No slide deck. |

---

## Actions in the bubble

Every assistant turn can end with **buttons** that run existing desk surfaces. Chat does not grow a second composer or a second people form.

| Button | Opens | Seed |
| --- | --- | --- |
| **Open** | `#account/{abbr}/{tab}` or `#account/{abbr}/{tab}/id={id}` | Book, ticket, thread, chat, meeting, project, person already on the desk |
| **Compose** | Shared `.mail-composer` (`#compose/{abbr}`) | **To:** and **Cc:** lists from the answer (and Bcc if present). Subject/body when the model proposed them. Operator still Save draft / Send. |
| **Add note** | Same **Notes** block as Timeline (`POST /api/notes`) | `ref` is the cited ticket / thread / meeting / chat. Body can start from the last assistant paragraph. |
| **Add person** | Add person sheet (`.sheet-person`) | Email (and name if known) of someone who appeared on a thread but is **not** in People yet. |
| **Update title** | Edit person sheet | When mail signatures or From headers show a new title/role for someone already in People. |

Buttons that do not apply stay off. No send from a button — Compose / SMTP confirm still sends.

## Links in the answer

Named evidence is a **link**, not plain text. Clicks use the same hashes as the rest of the desk (`goAccountItem` / `accountItemHash`).

| In the answer | Goes to |
| --- | --- |
| `#{ACME}` | `#account/ACME` |
| Ticket key `ACME-12` | `#account/ACME/tickets` (search `/ticket ACME-12`) |
| `/project SSO` `/people bob` `/email …` `/chat …` | Matching book tab + search |
| Thread / meeting / Slack id | `#account/{abbr}/{tab}/id={id}` |
| `#compose/ACME` | Compose lightbox |
| `#help/ticket-priority` | Help tile |

Do not invent ids. If the row is not in this desk, say **not in this desk** — no dead link.

## Notes (same as Timeline)

Timeline lightboxes already have **Notes** (`#detail-box` `.note-block`, `GET/POST /api/notes` with `ref.collection` + `ref.id`). Chat uses that store.

- A chat thread can carry notes (`ref.collection = chats`).
- **Add note** on a cited ticket/mail/meeting writes the same note the Timeline card would show.
- Notes are operator memory, not mail. They do not send.

## Automated operations

Chat **proposes**; the operator confirms with the button.

### Draft mail (To / Cc)

When the answer is a follow-up, it should include explicit lists the composer can seed:

```
To: bob@acme.com
Cc: rick.smith@acme.com, you@yourdomain
Subject: …
```

**Compose** copies To / Cc / Bcc into Tagify. AI Suggest and Save draft stay in the lightbox. Never auto-send.

### New person on a chain

If an address appears on To/Cc/From of a thread and **no** People row has that email:

- Call it out: “New on this chain: `pat@acme.com`.”
- **Add person** opens the sheet with email filled. Kind defaults to customer. Do not invent a name/title.

### Title / position sniff

When a later mail from a known person uses a different title (signature, From display, or “Pat is now Director…”):

- Call it out: “Title may have changed: Pat Chen, Manager → Director.”
- **Update title** opens Edit person with the new title suggested. Do not overwrite until Save on the sheet.

---

## How chat should behave

- **Scope.** Most threads stay on one book, or on **Company:Project** (`ACME:SSO hardening`). Home **Desk chat** is the all-accounts thread — “What tasks are due this week?” and “Do I have an opening next Tuesday for 1 hour with ACME:SSO hardening?” live there. Honor `#{ABBR}`, `@name`, `/project`, `/ticket`, `/company ACME:SSO …` in the prompt.
- **Evidence.** Every claim names a ticket key, thread, task, or meeting — and those names are links. If the book has no row, say **not in this desk**.
- **No send.** Propose a draft, a task, a meeting window, a person, or a title change. Buttons open existing sheets. The composer / SMTP confirm path still sends.
- **Who-stamps.** Me / Us / Them / All is already computed for inbox rows (`inbox_audience`). Chat should reuse that idea for “who is driving.”
- **Timezone.** Operator timezone from Settings → You. Customer people use location/timezone when present. World clock is the overlap tool.
- **Honesty.** Configuration vs product is a guess from text. Meeting-accept likelihood is from past overlap, not a calendar API of free/busy unless a connector later provides it. Title sniff is a guess from mail text.

## Not this list

Help (`#help`) is **how to click the desk**. This file is **what to ask chat**. Do not duplicate How-do-I steps here.

Finished weekly/QBR PDF packs, slash-in-chat creates, and Pydantic AI fan-out stay on [`ROADMAP.md`](ROADMAP.md) (0.4 / 0.45 / 0.5). These questions are the reason those trains exist.
