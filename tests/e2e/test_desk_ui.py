from __future__ import annotations

import pytest

pytestmark = pytest.mark.e2e


def test_home_shows_version_and_opens_settings(page, live_server):
    page.goto(live_server, wait_until="domcontentloaded")
    page.wait_for_selector("#app-version")
    assert page.locator("#app-version").inner_text().startswith("v")
    page.click('[data-nav="settings"]')
    page.wait_for_selector("#btn-google-signin")
    assert page.locator("#btn-google-signin").is_visible()
    assert page.locator("#btn-sso-signin").is_visible()
    assert page.locator("#connector-picker").is_visible()
    body = page.locator("body").inner_text().lower()
    assert "timesheet" not in body
    assert "sign in with google" in body
    assert page.locator("#pref-week-start").is_visible()
    page.wait_for_selector("#op-timezone-picker .search-select-btn")
    page.locator("#op-timezone-picker .search-select-btn").click()
    page.wait_for_selector(".search-select-menu:not([hidden])")
    page.locator(".search-select-menu .search").fill("chicago")
    page.wait_for_selector(".search-select-opt")
    page.keyboard.press("Escape")
    assert page.get_by_text("User Preferences").is_visible()
    assert page.locator("#btn-theme").is_visible()


def test_seed_loads_companies_on_home(page, live_server):
    page.goto(f"{live_server}/#settings", wait_until="domcontentloaded")
    page.wait_for_selector("#btn-seed")
    page.click("#btn-seed")
    page.wait_for_timeout(400)
    page.click('[data-nav="home"]')
    page.wait_for_selector(".cal-event")
    assert page.locator(".cal-event").count() >= 8
    assert page.get_by_role("button", name="Week").is_visible()
    assert page.get_by_role("button", name="Month").is_visible()
    assert page.locator(".agenda-item-lead").count() >= 1
    page.wait_for_selector(".agenda-who")
    assert page.locator(".agenda-who").count() >= 1
    stamps = [t.strip() for t in page.locator(".agenda-who").all_inner_texts()]
    assert stamps
    assert set(stamps) <= {"Me", "Us", "Them", "All", "??", "n/a"}
    page.locator(".cal-event").first.click()
    page.wait_for_function("location.hash.indexOf('/id=') >= 0")
    page.wait_for_selector("#detail-box:not([hidden]) .sheet")
    page.locator("#detail-box .sheet-close").click()
    page.click('[data-nav="home"]')
    page.get_by_role("button", name="Companies").click()
    page.wait_for_selector(".acct-card")
    text = page.locator("body").inner_text()
    assert "ACME" in text
    assert "NWIN" in text or "Northwind" in text
    assert page.locator(".acct-card img.acct-logo").count() >= 3
    page.locator(".acct-card").first.click()
    page.wait_for_selector("#account-tabs")
    page.wait_for_selector(".timeline")
    page.wait_for_selector(".tl-now")
    assert page.get_by_role("button", name="Now").is_visible()
    assert page.get_by_role("button", name="Past 7 days").is_visible()
    assert page.get_by_role("button", name="Past 30 days").is_visible()
    assert page.get_by_role("button", name="Next 7 days").is_visible()
    assert page.get_by_role("button", name="Next 30 days").is_visible()
    assert page.get_by_role("button", name="Horizontal").is_visible()
    page.get_by_role("button", name="Horizontal").click()
    page.wait_for_selector(".timeline-horizontal")
    page.wait_for_selector(".timeline-horizontal .tl-now")
    past_w = page.locator(".timeline-shell.is-horizontal .timeline-range.is-past").bounding_box()["width"]
    next_w = page.locator(".timeline-shell.is-horizontal .timeline-range.is-next").bounding_box()["width"]
    assert past_w < 72
    assert next_w < 72
    page.evaluate("document.querySelector('.timeline-scroll').scrollLeft = 0")
    page.get_by_role("button", name="Now").click()
    page.wait_for_function(
        """() => {
          const sc = document.querySelector('.timeline-scroll');
          const now = document.querySelector('[data-now]');
          if (!sc || !now) return false;
          const sr = sc.getBoundingClientRect();
          const nr = now.getBoundingClientRect();
          return nr.left >= sr.left - 24 && nr.right <= sr.right + 24;
        }"""
    )
    page.get_by_role("button", name="Vertical").click()
    page.wait_for_selector(".timeline-vertical")
    page.wait_for_selector(".timeline-vertical .tl-now")
    assert page.locator("#account-tabs .tab[data-tab='chat']").count() == 1
    assert page.locator("#account-tabs .tab[data-tab='slack']").count() == 0
    assert page.locator("#account-tabs .tab[data-tab='teams']").count() == 0
    page.locator("#account-tabs .tab[data-tab='chat']").click()
    page.wait_for_selector("#account-pane .row.is-chat")
    assert page.locator("#account-pane .kind-icon.is-slack").count() >= 1
    assert page.locator("#account-pane .kind-icon.is-teams").count() >= 1
    page.wait_for_function("location.hash.indexOf('/chat') >= 0")
    page.locator("#account-head").get_by_role("button", name="Compose").click()
    page.wait_for_selector("#compose-box:not([hidden]) .mail-composer")
    assert page.get_by_role("button", name="AI Suggest").is_visible()
    assert page.get_by_role("button", name="Save draft").is_visible()
    assert page.get_by_role("button", name="Attach").is_visible()
    page.wait_for_selector("#compose-tickets .tagify")
    assert page.locator("#compose-tickets .tagify").count() == 1
    page.locator("#compose-box .sheet-close").click()
    page.get_by_role("button", name="org chart").click()
    page.wait_for_selector(".org-card")
    assert page.locator(".org-card").count() >= 8
    page.locator("#account-tabs .tab", has_text="people").click()
    page.wait_for_selector("#people-q")
    assert page.locator("#people-q").is_visible()
    page.get_by_role("button", name="Add person").click()
    page.wait_for_selector("#detail-box:not([hidden]) .sheet-person form.settings-form")
    assert "Add person" in page.locator("#detail-box h2").inner_text()
    assert page.locator("#detail-box .sheet-person form label").count() >= 6
    assert page.locator("#detail-box .sheet-person .search-select").count() == 2
    page.wait_for_selector("#detail-box .sheet-person .tagify")
    assert page.locator("#detail-box .sheet-person .tagify").count() >= 2
    assert page.get_by_role("button", name="Save").is_visible()
    assert page.get_by_text("All projects (director / VP)").is_visible()
    fn_box = page.locator("#person-functions .tagify")
    fn_input = page.locator("#person-functions .tagify__input")
    fn_input.click()
    fn_input.press_sequentially("Op")
    page.wait_for_selector(".tagify__dropdown__item")
    page.locator(".tagify__dropdown__item").filter(has_text="Ops").first.click()
    assert fn_box.locator(".tagify__tag").filter(has_text="Ops").count() >= 1
    page.locator("#detail-box h2").click()
    page.wait_for_selector(".tagify__dropdown", state="hidden")
    proj_box = page.locator("#person-projects .tagify")
    page.locator("#person-projects .tagify__input").click()
    page.wait_for_selector(".tagify__dropdown__item")
    first_proj = page.locator(".tagify__dropdown:visible .tagify__dropdown__item").first
    proj_label = first_proj.inner_text().strip()
    first_proj.click()
    assert proj_label
    assert proj_box.locator(".tagify__tag").filter(has_text=proj_label).count() >= 1
    page.locator("#detail-box .sheet-close").click()
    page.wait_for_selector("#account-pane .row.is-click")
    page.locator("#account-pane .row.is-click").first.click()
    page.wait_for_selector("#detail-box:not([hidden]) .sheet-person form.settings-form")
    assert "Edit person" in page.locator("#detail-box h2").inner_text()
    assert page.locator("#detail-box .sheet-person form input").first.input_value() != ""
    page.locator("#detail-box .sheet-close").click()


def test_help_and_connector_picker(page, live_server):
    page.goto(f"{live_server}/#help", wait_until="domcontentloaded")
    page.wait_for_selector("#view-help, .help-page, [data-view='help']")
    page.click('[data-nav="settings"]')
    page.wait_for_selector("#connector-picker")
    page.wait_for_function("document.querySelectorAll('#connector-picker option').length > 3")
    labels = page.locator("#connector-picker option").all_inner_texts()
    joined = " ".join(labels).lower()
    assert "jira" in joined
    assert "slack" in joined
    assert "gmail" in joined
    assert "teams" in joined
    page.select_option("#connector-picker", label=labels[0] if labels else None)
    page.wait_for_selector("#connector-detail")


def test_preferences_hide_weekends_and_theme(page, live_server):
    page.goto(f"{live_server}/#settings", wait_until="domcontentloaded")
    page.wait_for_selector("#pref-week-start")
    page.select_option("#pref-week-start", "1")
    page.locator('#pref-days input[value="0"]').uncheck()
    page.locator('#pref-days input[value="6"]').uncheck()
    page.wait_for_function(
        """() => {
          const p = window.CSM && CSM.getPreferences && CSM.getPreferences();
          return p && (p.hidden_weekdays || []).indexOf(0) >= 0 && (p.hidden_weekdays || []).indexOf(6) >= 0 && p.week_start === 1;
        }"""
    )
    page.click('[data-nav="home"]')
    page.get_by_role("button", name="Week").click()
    page.wait_for_selector(".cal-week-day")
    headers = page.locator(".cal-week-day").all_inner_texts()
    joined = " ".join(headers).lower()
    assert "sat" not in joined
    assert "sun" not in joined
    assert page.locator(".cal-week-day").count() == 5
    page.locator("#btn-theme").click()
    page.wait_for_function("document.documentElement.getAttribute('data-theme') === 'night'")
    page.goto(f"{live_server}/#settings", wait_until="domcontentloaded")
    page.wait_for_selector("#pref-week-start")
    page.select_option("#pref-week-start", "0")
    page.locator('#pref-days input[value="0"]').check()
    page.locator('#pref-days input[value="6"]').check()
    page.locator('#pref-theme input[value="auto"]').check()
    page.wait_for_timeout(200)
