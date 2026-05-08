"""
League creation tests: create SMS, Slack, Discord leagues.

Tests the full flow from the create-league form through to the league management page.
Each test creates a league and deletes it afterward.
"""

import pytest
import time


_TS = str(int(time.time()))[-6:]


def _create_and_cleanup(page, base_url, league_name, slug, channel_type):
    """Helper: create a league, verify it, then delete it."""
    # Navigate to create league
    page.goto(f"{base_url}/dashboard/create-league")
    page.wait_for_load_state("networkidle")

    # Fill form
    page.fill('input[name="league_name"]', league_name)
    page.fill('input[name="slug"]', slug)

    # Select channel type — radio inputs are hidden inside styled labels
    label = page.locator(f'label.platform-option:has(input[value="{channel_type}"])')
    if label.count() > 0:
        label.click()
    else:
        # Fallback: force-click the hidden radio
        page.locator(f'input[value="{channel_type}"]').click(force=True)

    # Submit
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")

    # Should redirect to league management page
    url = page.url
    league_id = None
    if "/dashboard/league/" in url:
        league_id = int(url.split("/dashboard/league/")[1].split("?")[0].split("/")[0])

    return league_id


def _delete_league(page, base_url, league_id, league_name):
    """Delete a test league."""
    if not league_id:
        return
    page.goto(f"{base_url}/dashboard/league/{league_id}")
    page.wait_for_load_state("networkidle")
    delete_btn = page.locator('button:has-text("Delete League")')
    if delete_btn.count() > 0:
        delete_btn.click()
        confirm_input = page.locator('#deleteLeagueConfirmName')
        if confirm_input.count() > 0:
            confirm_input.fill(league_name)
            page.wait_for_timeout(300)
        confirm_btn = page.locator('#confirmDeleteBtn')
        if confirm_btn.count() > 0:
            confirm_btn.click()
            page.wait_for_load_state("networkidle")


class TestCreateLeaguePage:
    """Create league page structure tests."""

    def test_create_league_page_loads(self, logged_in_page, base_url):
        """Create league page renders with required fields."""
        logged_in_page.goto(f"{base_url}/dashboard/create-league")
        logged_in_page.wait_for_load_state("networkidle")

        assert logged_in_page.locator('input[name="league_name"]').is_visible()
        assert logged_in_page.locator('input[name="slug"]').is_visible()
        assert logged_in_page.locator('button[type="submit"]').is_visible()

    def test_create_league_has_channel_types(self, logged_in_page, base_url):
        """Create league page shows SMS, Slack, and possibly Discord options."""
        logged_in_page.goto(f"{base_url}/dashboard/create-league")
        logged_in_page.wait_for_load_state("networkidle")

        # Should have at least SMS and Slack options
        page_text = logged_in_page.inner_text("body")
        assert "SMS" in page_text, "SMS channel type should be available"
        assert "Slack" in page_text, "Slack channel type should be available"

    def test_create_league_validates_empty(self, logged_in_page, base_url):
        """Creating without name/slug shows error."""
        logged_in_page.goto(f"{base_url}/dashboard/create-league")
        logged_in_page.wait_for_load_state("networkidle")

        logged_in_page.click('button[type="submit"]')
        logged_in_page.wait_for_load_state("networkidle")

        # Should stay on create page with error, or browser validation stops it
        assert "create-league" in logged_in_page.url or logged_in_page.locator(".alert-error").count() > 0


class TestCreateSlackLeague:
    """Create and verify a Slack-type league."""

    def test_create_slack_league(self, logged_in_page, base_url):
        """Full flow: create Slack league, verify management page, delete."""
        name = f"Slack Test {_TS}"
        slug = f"slack-test-{_TS}"
        league_id = None

        try:
            league_id = _create_and_cleanup(logged_in_page, base_url, name, slug, "slack")
            assert league_id, "League should be created and redirect to management page"

            # Verify league management page has correct info
            page_text = logged_in_page.inner_text("body")
            assert name in page_text, f"League name '{name}' should appear on management page"
            assert "Slack" in page_text, "Channel type 'Slack' should appear on management page"
            assert "Setup Required" in page_text or "Connect Channel" in page_text, \
                "New Slack league should show setup required state"
        finally:
            _delete_league(logged_in_page, base_url, league_id, name)


class TestCreateSMSLeague:
    """Create and verify an SMS-type league."""

    def test_create_sms_league(self, logged_in_page, base_url):
        """Full flow: create SMS league, verify management page, delete."""
        name = f"SMS Test {_TS}"
        slug = f"sms-test-{_TS}"
        league_id = None

        try:
            league_id = _create_and_cleanup(logged_in_page, base_url, name, slug, "sms")
            assert league_id, "League should be created and redirect to management page"

            page_text = logged_in_page.inner_text("body")
            assert name in page_text, f"League name '{name}' should appear on management page"
            assert "SMS" in page_text, "Channel type 'SMS' should appear on management page"
        finally:
            _delete_league(logged_in_page, base_url, league_id, name)


class TestLeagueSlugValidation:
    """Test slug validation rules."""

    def test_duplicate_slug_rejected(self, logged_in_page, base_url):
        """Creating a league with an existing slug shows error."""
        name1 = f"Dup Test A {_TS}"
        slug = f"dup-test-{_TS}"
        league_id = None

        try:
            league_id = _create_and_cleanup(logged_in_page, base_url, name1, slug, "slack")
            assert league_id, "First league should be created"

            # Try to create another with same slug
            logged_in_page.goto(f"{base_url}/dashboard/create-league")
            logged_in_page.wait_for_load_state("networkidle")
            logged_in_page.fill('input[name="league_name"]', f"Dup Test B {_TS}")
            logged_in_page.fill('input[name="slug"]', slug)
            logged_in_page.click('button[type="submit"]')
            logged_in_page.wait_for_load_state("networkidle")

            # Should show error about slug being taken
            assert logged_in_page.locator(".alert-error").is_visible(), "Duplicate slug should show error"
            assert "taken" in logged_in_page.locator(".alert-error").inner_text().lower()
        finally:
            _delete_league(logged_in_page, base_url, league_id, name1)

    def test_invalid_slug_format(self, logged_in_page, base_url):
        """Slug with invalid characters shows error."""
        logged_in_page.goto(f"{base_url}/dashboard/create-league")
        logged_in_page.wait_for_load_state("networkidle")
        logged_in_page.fill('input[name="league_name"]', f"Bad Slug {_TS}")
        logged_in_page.fill('input[name="slug"]', "BAD SLUG!!!")
        logged_in_page.click('button[type="submit"]')
        logged_in_page.wait_for_load_state("networkidle")

        assert "create-league" in logged_in_page.url, "Should stay on create page"
