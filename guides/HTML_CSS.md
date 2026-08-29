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

Appearance: `html[data-theme="day"|"night"]` from User Preferences (`auto` follows `prefers-color-scheme`). Sidebar sun/moon is `#btn-theme`.

Font: **Source Sans 3** (Google Fonts). CDN allow-list: that font, plus **Tagify** for project tags only. No Leaflet or ECharts.

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
| Agenda calendar | `.agenda-cal` Day / Week / Month. `.cal-now` now-line. 24h track, default scroll ~7 AM |
| Meeting card | company logo left (`.acct-logo`), duration minutes right, subject on the card |
| Inbox row | `.agenda-item-lead` type icon (`.kind-icon.is-lg`) + company logo |
| Account timeline | `.timeline-shell` with `.timeline-range` (Past 7/30 · Next 7/30). Horizontal range labels: `writing-mode: vertical-rl`. Vertical: oldest at the bottom. `ul.timeline` cards. Now line `.tl-now`. **Now** button `.timeline-now-btn`. Layout: `.timeline-orient` |
| Timeline thumb | `span.tl-emoji` (Unicode emoji, operator-requested) |
| slack / teams tab | `data-tab="chat"`. Rows `.row.is-chat` with `.kind-icon.is-slack` / `.is-teams`. Hash aliases: `slack`, `teams` |
| People sheet | `#detail-box` `.sheet-person` + `form.form-grid`. Helper is `fieldLabel(text, node)` — do not reuse that name |
| Org chart | `.org-chart` `width: max-content`; pane `overflow-x: auto`. Center with `scrollLeft` |
| Activity lightbox | `#detail-box` + `.sheet` — close `×` top-right. Notes live at the bottom. |
| Timeline note badge | `img.tl-sticky` → `/static/sticky-note.png` |

## Rendering model output

Never `innerHTML` Grok, report Markdown, Slack, or email HTML. Use `textContent`. Help JSON is structured (`h` / `p` / `bullets`) — same rule.

## Hash routes

| View | Hash |
| --- | --- |
| Home | `#home` — board in the 70% pane, chat 30% |
| Account | `#account/{abbr}` or `#account/{abbr}/{tab}` stays on Home. Tabs: `timeline`, `tickets`, `email`, `chat` (slack / teams), `salesforce`, `calendar`, `projects`, `people`, `orgchart`, `accountteam`. The left pane swaps to the account desk (`#view-account.account-desk`). Chat stays visible and is scoped to that book. |
| Account item | `#account/{abbr}/{tab}/id={id}` opens the lightbox for that meeting, mail, Slack/Teams message, or task. `slack` and `teams` in the path alias to `chat`. |
| Account search | `#account-q` in `.account-tools` (far left). Type `/` for slash types (`/note`, `/project`, `/people`, `/email`, `/ticket`, `/chat`, `/slack`, `/teams`, …) in `#account-suggest`. Project filter `#account-project`. Compose stays far right in the header. |
| Actions | hidden in v0.1.9 — `#actions` redirects to Home; APIs stay |
| Reports | hidden in v0.1.9 — `#reports` and the account Reports tab redirect; APIs stay |
| Help | `#help` / `#help/{id}` |
| Settings | `#settings` |
| Compose | `#compose/{abbr}` (lightbox) |

## Check

```bash
make check-js
```
