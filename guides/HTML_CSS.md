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
| `--sidebar` / `--sidebar-mini` | Nav width |

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
| Account timeline | `ul.timeline.timeline-vertical.timeline-snap-icon` + `timeline-start` / `timeline-middle` / `timeline-end` |
| Timeline thumb | `span.tl-emoji` (Unicode emoji, operator-requested) |
| Activity lightbox | `#detail-box` + `.sheet` — close `×` top-right. Notes live at the bottom. |
| Timeline note badge | `img.tl-sticky` → `/static/sticky-note.png` |

## Rendering model output

Never `innerHTML` Grok, report Markdown, Slack, or email HTML. Use `textContent`. Help JSON is structured (`h` / `p` / `bullets`) — same rule.

## Hash routes

| View | Hash |
| --- | --- |
| Home | `#home` — board in the 70% pane, chat 30% |
| Account | `#account/{abbr}` or `#account/{abbr}/{tab}` stays on Home. The left pane swaps to the account desk (`#view-account.account-desk`). Chat stays visible and is scoped to that book. |
| Account search | `#account-q` in `.account-tools` (far left). Type `/` for slash types (`/note`, `/project`, `/people`, `/email`, `/ticket`, …) in `#account-suggest`. Project filter `#account-project`. Compose stays far right in the header. |
| Actions | hidden in v0.1.9 — `#actions` redirects to Home; APIs stay |
| Reports | hidden in v0.1.9 — `#reports` and the account Reports tab redirect; APIs stay |
| Help | `#help` / `#help/{id}` |
| Settings | `#settings` |
| Compose | `#compose/{abbr}` (lightbox) |

## Check

```bash
make check-js
```
