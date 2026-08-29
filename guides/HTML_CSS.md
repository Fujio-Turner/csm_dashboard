# HTML & CSS — csm_dashboard

The desk is **vanilla HTML + one CSS file + IIFE JavaScript**. No React, no bundler, no Tailwind, no DaisyUI CDN. The Account **Timeline** tab is a local recreation of [daisyUI’s vertical snap-icon timeline](https://daisyui.com/components/timeline/#timeline-with-icon-snapped-to-the-start) so we get that layout without Tailwind preflight restyling `.btn` / `.card`.

| File | Role |
| --- | --- |
| [`src/csm_dashboard/web/templates/index.html`](../src/csm_dashboard/web/templates/index.html) | Markup only |
| [`src/csm_dashboard/web/static/app.css`](../src/csm_dashboard/web/static/app.css) | All custom CSS |
| [`src/csm_dashboard/web/static/app.js`](../src/csm_dashboard/web/static/app.js) | Chrome, Home, Account, Actions, Reports, Settings, Help |
| [`src/csm_dashboard/web/static/compose.js`](../src/csm_dashboard/web/static/compose.js) | Compose lightbox |

## Golden rules

- **No HTML emojis** except the Account Timeline thumbs (`span.tl-emoji`): Slack, Teams, sent/received mail, Jira, calendar. Everywhere else stays inline SVG (24×24 `viewBox`, stroke, no fill unless a mark).
- **No inline `<style>` or `<script>`** in `index.html` except CDN `<link>` / `<script src>`.
- **No nested backticks** inside JS template literals. Prefer `createElement` + `textContent`. After any JS edit: `make check-js`.
- **Never hard-code the version.** Version comes from `/api/status`.
- **Cache-bust** `app.css` / `app.js` query strings when those files change (`?v=` matches the served version).
- **Playwright MCP** (`.grok/config.toml`) is the local browser check. Drive `http://127.0.0.1:8788` (Docker: `http://localhost:8788`). Click, type, and visit every view that shares the state you touched.
- **Buttons live on the edges.** Put actions in a **corner** or on the **far left / far right** of the bar they belong to. **Exception: lightboxes** — actions stay in the panel.
- Account **color + abbr** are data. Render chips with `accountChip()` (`createElement`). Do not invent 25 CSS themes.
- **Do not dump a large list into a native `<select>`.** Timezones, people, projects, threads, tickets: type-ahead. See [Search, select, Tagify](#search-select-tagify).
- **Arrays are Tagify chips.** If the value is a list (To, Projects, Functions, tags, tickets), each pick is a badge — not a one-line “N selected” picker.
- **Mail lives in the shared composer lightbox.** New compose / reply / task surfaces reuse `mountMailComposer`. Do not invent a second To/Cc/Bcc chrome.
- **Deep-link with `/id=`.** Opening a meeting, thread, chat, or task writes `#account/{abbr}/{tab}/id={id}` so refresh and share land on the same lightbox.

## Button placement

| Put here | What |
| --- | --- |
| **Far left** | Identity / search / filters |
| **Far right** | Commands (`Refresh health`, `Compose`, `Load seed data`) |
| **Corners** | Close (`×`) top-right of chrome; Save bottom-right of compose |

A toolbar is **one row**. Use space-between. Wrap only below 980px.

## Tokens

Use the `:root` variables in `app.css`. Do not introduce a second palette.

| Token | Use |
| --- | --- |
| `--page` | App background |
| `--panel` | Sidebar, toolbar, cards |
| `--ink` / `--muted` | Text |
| `--line` | Borders |
| `--accent` / `--navy` | Primary actions / headings |
| `--good` / `--mid` / `--low` | Health colors |
| `--now` | Agenda / timeline Now line and Now button |
| `--cal-bg` / `--cal-line` | Agenda calendar track |
| `--sidebar` / `--sidebar-mini` | Nav width |

Appearance: `html[data-theme="day"|"night"]` from User Preferences (`auto` follows `prefers-color-scheme`). Sidebar sun/moon is `#btn-theme`. Operator timezone is `#op-timezone-picker` (search-select), not a native `<select>` of every IANA zone.

Font: **Source Sans 3** (Google Fonts). CDN allow-list: that font, plus **Tagify** for people emails (To / Cc / Bcc) and every multi-value field (project tags, person Projects / Functions, compose tickets). No Leaflet, ECharts, or a second email-composer kit — the desk’s `.mail-composer` is the shared prompt.

## Components (reuse these)

| Need | Class / pattern |
| --- | --- |
| Button | `btn` |
| Primary | `btn btn-primary` |
| Quiet | `btn btn-ghost` |
| Destroy | `btn btn-cancel` |
| Account chip | `.acct-chip` + `.acct-swatch` + `.acct-abbr` |
| Health word | `.health-pill.healthy\|watch\|at_risk\|critical` |
| Card | `.card` |
| Mail composer | `.mail-composer` in a lightbox — To / Cc / Bcc (Tagify), Subject, Body, Attach, **AI Suggest**, **Save draft**, **Send**. Shared by Compose, thread Reply, and New task. See [Mail composer lightbox](#mail-composer-lightbox). |
| Search / type-ahead | `mountSearchSelect` / `.search-select` — **one** value from a list that can be large. See below. |
| Multi chips | `mountTagifyMulti` / `.tag-multi` — **many** values (arrays). Each pick is a Tagify badge. |
| Agenda calendar | `.agenda-cal` Day / Week / Month. `.cal-now` now-line. 24h track, default scroll ~7 AM |
| Meeting card | company logo left (`.acct-logo`), duration minutes right, subject on the card |
| Inbox row | `.agenda-item-lead` type icon (`.kind-icon.is-lg`) + company logo. Far right: `.agenda-who` stamp — **Me** (blue `--accent`) / **Us** (purple) / **Them** (`--mid`) / **All** (`--good`) / **??** / **n/a** (`--muted`) |
| Account timeline | `.timeline-shell` with `.timeline-range` (Past 7/30 · Next 7/30). Horizontal range labels: `writing-mode: vertical-rl`. Vertical: oldest at the bottom. `ul.timeline` cards. Now line `.tl-now`. **Now** button `.timeline-now-btn`. Layout: `.timeline-orient` |
| Timeline thumb | `span.tl-emoji` (Unicode emoji, operator-requested) |
| slack / teams tab | `data-tab="chat"`. Rows `.row.is-chat` with `.kind-icon.is-slack` / `.is-teams`. Hash aliases: `slack`, `teams` |
| People sheet | `#detail-box` `.sheet-person` + `settings-form` (same 2-col as New task). Kind / Reports to use `.search-select`. Projects / Functions are Tagify chips (`.tag-multi`). All-projects is `.check-inline`. |
| Org chart | `.org-chart` `width: max-content`; pane `overflow-x: auto`. Center with `scrollLeft` |
| Activity lightbox | `#detail-box` + `.sheet` — close `×` top-right. Notes live at the bottom. |
| Timeline note badge | `img.tl-sticky` → `/static/sticky-note.png` |

## Search, select, Tagify

Pick the control from the **shape of the value**, not from “it is a dropdown.”

| Value | Control | Why |
| --- | --- | --- |
| Short text, email, date, number | Native `<input>` / `<textarea>` | One value, no catalog |
| Tiny closed set (≤ ~12): project Type/Status, task kind | Native `<select>` | Fast, no JS |
| **One** value from a **large or searchable** catalog | `mountSearchSelect` | Type-ahead; do not paint 400 IANA zones or every person as `<option>` |
| **Many** values (array / list): To, Cc, Bcc, Projects, Functions, tags, tickets, domains, channel ids | `mountTagifyMulti` (or `bindAddrTagify` for people emails) | Each pick is a removable chip |

Never use `mountSearchSelect({ multiple: true })`. That shows “Plant onboarding” or “3 selected” instead of badges. Arrays are Tagify.

### Search-select (large single-value)

`mountSearchSelect(opts)` in `app.js`. Menu is portaled to `document.body` so a sheet with `overflow: auto` does not clip it.

| Option | Use |
| --- | --- |
| `items` | `{ value, label, search? }[]`. `search` is extra haystack (email, title, IANA id). |
| `value` | Current id / string |
| `trigger: "button"` | Closed field; search lives **inside** the menu (timezone, Kind, Reports to, Thread) |
| `trigger: "input"` | The field *is* the search box (`allowCustom` for Task name, Search projects) |
| `pinValues` | When the query is empty, show only these ids (timezone pins UTC + current). Typing still searches the **full** list. |
| `maxShown` | Cap painted rows (timezone uses 60). Default 80. |
| `emptyLabel` | First row for “none” (`No manager`, `No thread`) |
| `allowCustom` | Accept typed text that is not in the list |
| `btnClass: "search-select-btn-block"` | Full-width in a `settings-form` / mail context |

**Already on this pattern:** operator timezone (`#op-timezone-picker`), Task name, Search projects, Compose Thread, person Kind / Reports to, Agenda **Company : Project** filter (same type-ahead idea).

A native `<select>` of every timezone or every person on the book is a bug. Add the next large catalog here, not as `<option>` soup.

### Tagify (arrays)

`mountTagifyMulti(opts)` — whitelist `{ value, label }`, chips show `label`, payload is `value` (project id, ticket id, function name). `makeTagInput` is the free-form wrapper (domains, Jira keys, Slack/Teams channel ids). People emails on the composer use `bindAddrTagify` (`tagTextProp: "name"`).

| Option | Use |
| --- | --- |
| `enforceWhitelist: true` | Only real ids (person **Projects**, compose **Tickets**) |
| `allowCustom: true` | Type new tags (Functions, project Tags, domains) |
| `bind()` | Call **after** the input is in the DOM (Tagify on a detached node is silent) |
| `setReadonly` | Person “All projects” locks the project chips |

Close the Tagify dropdown with `appendTarget: document.body` so it is not clipped by `.sheet { overflow: auto }`.

**Already chips:** To / Cc / Bcc, person Projects / Functions, project Tags, compose Tickets, company Customer domains / Jira keys / Slack / Teams / Salesforce ids.

## Mail composer lightbox

This is the **standard message chrome**. Future mail, reply, forward, task-email, or “send this draft” UI must reuse it — do not add a second To/Cc/Bcc/Attach kit.

```text
lightbox (#compose-box | #detail-box | #task-box)
  .sheet
    header (title, account chip, ×)
    optional context (Thread search-select, Tickets Tagify)
    .mail-composer   ← mountMailComposer()
      To / Cc / Bcc (Tagify people+email)
      Subject
      Body
      Attach (chips, 5 MB × 8)
      AI Suggest · Save draft · Send
```

| Surface | Host | Notes |
| --- | --- | --- |
| Compose | `#compose-box` via `compose.js` | Hash `#compose/{abbr}` |
| Thread reply | `#detail-box` on a thread | Same composer under the message stack |
| New / edit task | `#task-box` | Task fields above; mail chrome below (self-email) |

`window.CSM.mountMailComposer` / `mountSearchSelect` / `mountTagifyMulti` are the public hooks. Send always confirms. SMTP off → `409 send_not_configured`.

## Who-stamp (Agenda inbox)

`audienceStamp()` in `app.js` maps API `audience` to the far-right label. Do not store the stamp on the email document — `CsmRepo.inbox_audience` / `home_agenda` compute it.

| `audience` | Label | Meaning |
| --- | --- | --- |
| `me` | Me | To the operator (inbox / DM / self-task) |
| `us` | Us | To our team |
| `them` | Them | To the customer |
| `all` | All | Shared room or both sides on the thread |
| `unknown` | ?? | Cannot tell |
| `na` | n/a | Does not apply |

## Rendering model output

Never `innerHTML` Grok, report Markdown, Slack, or email HTML. Use `textContent`. Help JSON is structured (`h` / `p` / `bullets`) — same rule.

## Hash routes and `/id=` deep links

The hash **is** the address of the desk. Clicks that open a record must write it (`goAccountItem` / `accountItemHash`) so refresh, back, and paste open the same lightbox.

Pattern: `#account/{abbr}/{tab}/id={id}`

`id=` may sit on any segment; `hashItemId()` reads the first `id=` piece. Slash in the id is encoded (`/` → `%2F`). `slack` and `teams` in `{tab}` alias to `chat`.

| Open this | Hash |
| --- | --- |
| Home Agenda | `#home` |
| Home Companies | `#home/companies` |
| Account (timeline) | `#account/ACME` |
| Account tab | `#account/ACME/people` — tabs: `timeline`, `tickets`, `email`, `chat`, `salesforce`, `calendar`, `projects`, `people`, `orgchart`, `accountteam` |
| Meeting | `#account/ACME/calendar/id=cal:stub:…` |
| Mail thread | `#account/ACME/email/id=thr:…` |
| Slack / Teams message | `#account/ACME/chat/id=slm:…` or `id=tmm:…` (also `#account/ACME/slack/id=…`) |
| Task | `#account/ACME/email/id=em:task:…` (task is a self-email) |
| Compose lightbox | `#compose/ACME` |
| Help topic | `#help/{id}` |
| Settings | `#settings` |

Account search is `#account-q` in `.account-tools` (far left). Type `/` for slash types (`/note`, `/project`, `/people`, `/email`, `/ticket`, `/chat`, `/slack`, `/teams`, …) in `#account-suggest`. Project filter `#account-project`. Compose stays far right in the header.

`#actions` and `#reports` redirect to Home (APIs stay). A future surface that opens a document from Agenda, chat, or a notification must go through `goAccountItem(abbr, tab, id)` — do not open a lightbox without updating the hash.

## Check

```bash
make check-js
```
