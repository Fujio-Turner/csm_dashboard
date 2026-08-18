from __future__ import annotations

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
    assert "Suggest reply" in js
    assert "openCompanyForm" in js
    assert "owns_all_projects" in js
    assert "openProjectForm" in js
    assert "fillProjects" in js
    assert "project-q" in js
    assert "Tagify" in js
    assert "group_email" in js
    assert "yaireo/tagify" in HTML
    assert "btn-add-company" in HTML
    assert "op-timezone" in HTML
    assert "settings-page" in HTML
    assert "settings-form" in HTML
    assert "help-page" in HTML
    assert "help-toc" in HTML
    assert "settings-page" in css
    assert "help-toc" in css
    assert "fillTimezoneSelect" in js
    assert "btn-world-clock" in HTML
    assert "world-box" in HTML
    assert "worldclock.js" in HTML
    assert "side-foot" in css
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
    assert "Change logo" in js
    assert "Crop & Save" in js
    assert "openLogoCrop" in js
    assert "acct-meeting" in js
    assert "acct-status-row" in js
    assert "acct-renewal" in css
    assert "showHomeTab" in js
    assert "loadAgenda" in js
    assert "New mail / chat / tasks" in js
    assert "agenda-inbox-filter" in js
    assert "agendaInboxFilter" in js
    assert "openTaskForm" in js
    assert "btn-add-task" in js
    assert "icon-task.svg" in js
    assert "task-box" in HTML
    assert "kindIcon" in js
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
    assert "tl-emoji" in css
    assert "fillTimeline" in js
    assert "timeline-snap-icon" in js
    assert "openActivityLightbox" in js
    assert "formatWhen" in js
    assert "detail-box" in HTML
    assert "account-q" in HTML
    assert "account-project" in HTML
    assert "orgchart" in js
    assert "accountteam" in js
    assert "org-chart" in css
    assert "org-card" in css
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
