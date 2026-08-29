from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "src" / "csm_dashboard" / "web" / "templates" / "index.html").read_text(encoding="utf-8")


def test_views_present():
    for name in ("view-home", "view-settings", "acct-board", "view-account", "view-actions"):
        assert name in HTML
    for name in ("home-split", "home-chat", "home-chat-form", "btn-chat-history", "btn-chat-bookmark", "btn-chat-new", "agenda-panel", "home-tabs"):
        assert name in HTML
    assert "btn-icon" in HTML
    assert 'id="app"' in HTML and "is-mini" in HTML
    assert 'data-tip="History"' in HTML
    assert 'data-tip="New chat"' in HTML
    assert "home-tagline" not in HTML
    assert "Accounts · tickets · mail" not in HTML
    assert "account-desk" in HTML
    css = (ROOT / "src" / "csm_dashboard" / "web" / "static" / "app.css").read_text(encoding="utf-8")
    assert "7fr 3fr" in css
    assert "is-account" in css
    assert "overflow-y: auto" in css
    assert "#view-home.is-account .home-main" in css
    js = (ROOT / "src" / "csm_dashboard" / "web" / "static" / "app.js").read_text(encoding="utf-8")
    assert "setHomeMode" in js
    assert "syncChatScope" in js
    assert "toggleChatBookmark" in js
    assert "tab-count" in js
    assert "AI Suggest" in js
    assert "mountMailComposer" in js
    assert "mail-composer" in js
    compose = (ROOT / "src" / "csm_dashboard" / "web" / "static" / "compose.js").read_text(encoding="utf-8")
    assert "mountMailComposer" in compose
    assert "Send this email now?" in js
    assert "openCompanyForm" in js
    assert "makeTagInput" in js
    assert "sheet-company" in js
    assert "owns_all_projects" in js
    assert "openProjectForm" in js
    assert "fillProjects" in js
    assert "project-q" in js
    assert "Tagify" in js
    assert "group_email" in js
    assert "yaireo/tagify" in HTML
    assert "Quicksand" in HTML
    assert "--accent: #7d80f5" in css
    assert "avatarEl" in js
    assert "has-avatar" in js
    assert "btn-add-company" in HTML
    assert "op-timezone" in HTML
    assert "settings-page" in HTML
    assert "settings-form" in HTML
    assert 'id="sso-portal"' in HTML
    assert 'id="btn-sso-signin"' in HTML
    assert 'id="sso-client-id"' in HTML
    assert 'id="ai-provider"' in HTML
    assert 'id="connector-picker"' in HTML
    assert 'id="ai-state"' in HTML
    assert 'id="connector-state"' in HTML
    assert "picker-row" in css
    assert "paintAiPicker" in js
    assert "paintConnectorPicker" in js
    assert "connectorStateOf" in js
    assert "help-page" in HTML
    assert "help-toc" not in HTML
    assert 'id="help-search"' in HTML
    assert "help-chips" in HTML
    assert "settings-page" in css
    assert "help-q" in css
    assert "help-body" in css
    assert "repeat(2, minmax(0, 1fr))" in css
    assert "filterHelp" in js
    assert "paintHelp" in js
    assert "appendHelpAnswer" in js
    assert "help-sub" in css
    assert "help-ul" in css
    assert "fillTimezoneSelect" in js
    assert "mountSearchSelect" in js
    assert "mountTagifyMulti" in js
    assert "tag-multi" in css
    assert "search-select-menu" in css
    assert "op-timezone-picker" in HTML
    assert "btn-world-clock" not in HTML
    assert "openHelpItem" in js
    assert "world-box" in HTML
    assert "worldclock.js" in HTML
    assert "side-foot" in css
    assert "side-version" in HTML
    assert "bind-pill" not in HTML
    assert "sheet-world" in css
    assert "100vh - 1.05rem" in css
    assert "#world-box.lightbox" in css
    world = (ROOT / "src" / "csm_dashboard" / "web" / "static" / "worldclock.js").read_text(encoding="utf-8")
    assert "CSMWorld" in world
    assert "Search city" in world
    assert "las angoles" in world
    assert "is-you" in world
    assert "wtb-grip" in world
    assert "bindRowSort" in world
    assert "nudgeZone" in world
    assert "world_clock" in world
    assert "getWorldClock" in js
    assert "crop-box" in HTML
    assert "#crop-box.lightbox" in css
    assert "z-index: 50" in css
    assert "Change logo" in js
    assert "Crop & Save" in js
    assert "openLogoCrop" in js
    assert "acct-meeting" in js
    assert "acct-status-row" in js
    assert "acct-renewal" in css
    assert "showHomeTab" in js
    assert "loadAgenda" in js
    assert 'id="desk-clock"' in HTML
    assert "desk-clock-time" in HTML
    assert "desk-clock-when" in HTML
    assert "desk-clock-meta" not in HTML
    assert "Click for World Clock" in HTML
    assert "crumb-abbr" in js
    assert "crumb-abbr" in css
    assert "home-company-tools" in HTML
    assert "home-top" in css
    assert 'id="home-crumb"' in HTML
    assert "renderHomeCrumb" in js
    assert "tickDeskClock" in js
    assert "startDeskClock" in js
    assert "paintHomeBoard" in js
    assert "setWorldClock" in js
    assert "query_by_account" in (ROOT / "src" / "csm_dashboard" / "storage" / "memory.py").read_text(encoding="utf-8")
    assert "New mail / chat / tasks" in js
    assert "agenda-inbox-filter" in js
    assert "agenda-proj-filter" in js
    assert "fillAgendaProjFilter" in js
    assert "placeAgendaProjMenu" in js
    assert "Search company or project" in js
    assert "agendaInboxFilter" in js
    assert "openTaskForm" in js
    assert "AI Suggest" in js
    assert "mountMailComposer" in js
    assert "bindAddrTagify" in js
    assert "/api/tasks/assist" in js
    assert "btn-add-task" in js
    assert "icon-task.svg" in js
    assert "task-box" in HTML
    assert "kindIcon" in js
    assert "goAccountItem" in js
    assert "openCalendarLightbox" in js
    assert "agenda-item-lead" in js
    assert "audienceStamp" in js
    assert "agenda-who" in css
    assert "To Me" in js
    assert "is-lg" in js
    assert "/id=" in js
    assert "agendaCalView" in js
    assert "User Preferences" in HTML
    assert 'id="pref-week-start"' in HTML
    assert 'id="pref-days"' in HTML
    assert 'id="pref-theme"' in HTML
    assert 'id="btn-theme"' in HTML
    assert "visibleWeekdays" in js
    assert "applyTheme" in js
    assert "savePreferences" in js
    assert "weekDaysFrom" in js
    assert 'html[data-theme="night"]' in css
    assert "theme-toggle" in css
    assert "pref-fieldset" in css
    assert "cal-event" in js
    assert "CAL_DAY_SPAN" in js
    assert "CAL_SCROLL_HOUR" in js
    assert "cal-now" in css
    assert "cal-track" in css
    assert "data-cal-view" in js
    assert "icon-slack.svg" in js
    assert "icon-teams.svg" in js
    assert "icon-email.svg" in js
    assert "new Slack/Teams" in js
    assert "new invite" in js
    assert "next_action" not in Path(ROOT / "src" / "csm_dashboard" / "web" / "static" / "app.js").read_text(encoding="utf-8").split("function homeCard")[1].split("function hideChatHistory")[0]
    assert 'type = "color"' in js


def test_no_emoji_in_html():
    assert "😀" not in HTML
    assert "📧" not in HTML


def test_timeline_css_present():
    css = (ROOT / "src" / "csm_dashboard" / "web" / "static" / "app.css").read_text(encoding="utf-8")
    js = (ROOT / "src" / "csm_dashboard" / "web" / "static" / "app.js").read_text(encoding="utf-8")
    assert "timeline-snap-icon" in css
    assert "timeline-vertical" in css
    assert "timeline-horizontal" in css
    assert "timeline-orient" in css
    assert "tl-emoji" in css
    assert "fillTimeline" in js
    assert "timeline-snap-icon" in js
    assert "timelineOrientBar" in js
    assert "data-tl-layout" in js
    assert "timeline_layout" in js
    assert "timelineNowItem" in js
    assert "scrollTimelineToNow" in js
    assert "timeline-now-btn" in js
    assert "Scroll to now" in js
    assert "timeline-now-btn" in css
    assert 'nowBtn.textContent = "Now"' in js
    assert "sortTimelineItems" in js
    assert "Past 7 days" in js
    assert "Past 30 days" in js
    assert "Next 7 days" in js
    assert "Next 30 days" in js
    assert "timeline-range" in css
    assert "writing-mode: vertical-rl" in css
    assert "timeline-shell" in css
    assert "timelineFetchUrl" in js
    assert "TL_SIDE_CAP" in js
    assert "slice().reverse()" in js
    assert "sheet-person" in js
    assert "Add person" in js
    assert "tl-now" in css
    assert "timeline-now-item" in css
    assert "tl-hour-mark" not in css
    assert "timeline-axis" not in js
    assert "tl-chip" not in css
    assert ".timeline .tl-emoji" in css
    assert "openActivityLightbox" in js
    assert "formatWhen" in js
    assert "detail-box" in HTML
    assert "account-q" in HTML
    assert "account-project" in HTML
    assert "orgchart" in js
    assert "accountteam" in js
    assert "org-chart" in css
    assert "org-card" in css
    assert "width: max-content" in css
    assert "scrollWidth" in js
    assert "data-table" in css
    assert "account-suggest" in HTML
    assert "sticky-note.png" in js
    assert "pickSlash" in js
    assert "salesforce" in js
    assert "fillSalesforce" in js
    assert "Save note" in js
    assert "Save project" in js
    assert "PERSON_FUNCS" in js
    assert "HIDDEN_TABS" in js
    assert 'href="#actions"' not in HTML
    assert 'href="#reports"' not in HTML
    assert "openPersonForm" in js
    assert "person-projects" in js
    assert "person-functions" in js
    assert "people-q" in js
    assert "Search people" in js
    assert "pinValues" in js
    assert "maxShown" in js
    assert "ACCOUNT_TABS" in js
    assert "TAB_ALIASES" in js
    assert "slack / teams" in js
    assert "function fillChat" in js
    assert "function canonicalTab" in js
    assert ".row.is-chat" in css
    assert "function humanizeField" in js
    # Function declarations in the desk IIFE share one scope. A later
    # `function fieldLabel` would overwrite the form helper and leave
    # Add/Edit person as a header-only sheet (appendChild of a string).
    top_fns = re.findall(r"^  function (\w+)\(", js, re.M)
    dups = sorted(name for name, n in Counter(top_fns).items() if n > 1)
    assert dups == [], dups
    assert top_fns.count("fieldLabel") == 1
    assert top_fns.count("humanizeField") == 1
