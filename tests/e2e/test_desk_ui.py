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


def test_seed_loads_companies_on_home(page, live_server):
    page.goto(f"{live_server}/#settings", wait_until="domcontentloaded")
    page.wait_for_selector("#btn-seed")
    page.click("#btn-seed")
    page.wait_for_timeout(400)
    page.click('[data-nav="home"]')
    page.wait_for_selector(".agenda-meet")
    assert page.locator(".agenda-meet").count() >= 8
    page.get_by_role("button", name="Companies").click()
    page.wait_for_selector(".acct-card")
    text = page.locator("body").inner_text()
    assert "ACME" in text
    assert "NWIN" in text or "Northwind" in text
    assert page.locator(".acct-card img.acct-logo").count() >= 3
    page.locator(".acct-card").first.click()
    page.wait_for_selector("#account-tabs")
    page.get_by_role("button", name="org chart").click()
    page.wait_for_selector(".org-card")
    assert page.locator(".org-card").count() >= 8


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
