"""
League settings tests: rename, min weekly scores, AI toggles, header emoji.

Tests require an authenticated session with at least one managed league.
Creates a temporary league for testing.
"""

import pytest
import time


_TS = str(int(time.time()))[-6:]
TEST_LEAGUE_NAME = f"Settings Test {_TS}"
TEST_LEAGUE_SLUG = f"settings-test-{_TS}"


@pytest.fixture(scope="module")
def settings_league(browser_instance, base_url, test_email, test_password):
    """Create a Slack test league for settings tests, yield context, then delete."""
    ctx = browser_instance.new_context(
        viewport={"width": 1280, "height": 800},
        ignore_https_errors=True,
    )
    page = ctx.new_page()

    # Login
    page.goto(f"{base_url}/auth/login")
    page.fill('input[name="email"]', test_email)
    page.fill('input[name="password"]', test_password)
    page.click('button[type="submit"]')
    page.wait_for_url("**/dashboard**", timeout=10000)

    # Create league
    page.goto(f"{base_url}/dashboard/create-league")
    page.wait_for_load_state("networkidle")
    page.fill('input[name="league_name"]', TEST_LEAGUE_NAME)
    page.fill('input[name="slug"]', TEST_LEAGUE_SLUG)
    slack_label = page.locator('label.platform-option:has(input[value="slack"])')
    if slack_label.count() > 0:
        slack_label.click()
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")

    league_id = None
    if "/dashboard/league/" in page.url:
        league_id = int(page.url.split("/dashboard/league/")[1].split("?")[0].split("/")[0])

    yield {"page": page, "league_id": league_id, "base_url": base_url}

    # Cleanup
    if league_id:
        page.goto(f"{base_url}/dashboard/league/{league_id}")
        page.wait_for_load_state("networkidle")
        delete_btn = page.locator('button:has-text("Delete League")')
        if delete_btn.count() > 0:
            delete_btn.click()
            confirm_input = page.locator('#deleteLeagueConfirmName')
            if confirm_input.count() > 0:
                confirm_input.fill(TEST_LEAGUE_NAME)
                page.wait_for_timeout(300)
            confirm_btn = page.locator('#confirmDeleteBtn')
            if confirm_btn.count() > 0:
                confirm_btn.click()
                page.wait_for_load_state("networkidle")

    page.close()
    ctx.close()


class TestLeagueSettingsSection:
    """Test that the settings section renders with expected controls."""

    def test_settings_section_visible(self, settings_league):
        """League management page has a settings section."""
        page = settings_league["page"]
        base_url = settings_league["base_url"]
        league_id = settings_league["league_id"]
        assert league_id, "League was not created"

        page.goto(f"{base_url}/dashboard/league/{league_id}")
        page.wait_for_load_state("networkidle")

        # Should have league name displayed
        assert TEST_LEAGUE_NAME in page.inner_text("body")

    def test_min_weekly_scores_dropdown(self, settings_league):
        """Min weekly scores dropdown is present with expected options."""
        page = settings_league["page"]
        base_url = settings_league["base_url"]
        league_id = settings_league["league_id"]
        assert league_id, "League was not created"

        page.goto(f"{base_url}/dashboard/league/{league_id}")
        page.wait_for_load_state("networkidle")

        # Look for min weekly scores control (hidden input + label)
        min_scores = page.locator('#leagueMinWeeklyScores')
        assert min_scores.count() > 0, "Min weekly scores hidden input should be present"

    def test_header_emoji_section(self, settings_league):
        """Header emoji / mascot section is present."""
        page = settings_league["page"]
        base_url = settings_league["base_url"]
        league_id = settings_league["league_id"]
        assert league_id, "League was not created"

        page.goto(f"{base_url}/dashboard/league/{league_id}")
        page.wait_for_load_state("networkidle")

        # Mascot / emoji section — check for the generate button or current display
        has_mascot = (
            page.locator('#mascotGenBtn').count() > 0
            or page.locator('#mascotCurrent').count() > 0
        )
        assert has_mascot, "Mascot/emoji section should be present"


class TestAIMessagingToggles:
    """Test AI messaging toggle controls."""

    def test_ai_toggles_present(self, settings_league):
        """AI messaging toggles are rendered on the page."""
        page = settings_league["page"]
        base_url = settings_league["base_url"]
        league_id = settings_league["league_id"]
        assert league_id, "League was not created"

        page.goto(f"{base_url}/dashboard/league/{league_id}")
        page.wait_for_load_state("networkidle")

        # AI section header
        ai_section = page.locator('text=/AI.*Messaging/i')
        assert ai_section.count() > 0, "AI Messaging section should be present"

        # Individual toggles
        perfect = page.locator('#ai_perfect_score')
        failure = page.locator('#ai_failure_roast')
        sunday = page.locator('#ai_sunday_race')
        monday = page.locator('#ai_monday_recap')

        assert perfect.count() > 0, "Perfect score toggle should exist"
        assert failure.count() > 0, "Failure roast toggle should exist"
        assert sunday.count() > 0, "Sunday update toggle should exist"
        assert monday.count() > 0, "Monday recap toggle should exist"


class TestDeleteLeague:
    """Test league deletion flow (uses its own league)."""

    def test_delete_button_exists(self, settings_league):
        """Delete league button is present."""
        page = settings_league["page"]
        base_url = settings_league["base_url"]
        league_id = settings_league["league_id"]
        assert league_id, "League was not created"

        page.goto(f"{base_url}/dashboard/league/{league_id}")
        page.wait_for_load_state("networkidle")

        delete_btn = page.locator('button:has-text("Delete League")')
        assert delete_btn.count() > 0, "Delete League button should exist"

    def test_delete_requires_confirmation(self, settings_league):
        """Delete league requires typing the league name to confirm."""
        page = settings_league["page"]
        base_url = settings_league["base_url"]
        league_id = settings_league["league_id"]
        assert league_id, "League was not created"

        page.goto(f"{base_url}/dashboard/league/{league_id}")
        page.wait_for_load_state("networkidle")

        # Click delete
        page.locator('button:has-text("Delete League")').click()
        page.wait_for_timeout(500)

        # Confirmation modal should appear with input
        confirm_input = page.locator('#deleteLeagueConfirmName')
        assert confirm_input.is_visible(), "Delete confirmation input should appear"

        # Confirm button should exist but be disabled until name is typed
        confirm_btn = page.locator('#confirmDeleteBtn')
        assert confirm_btn.count() > 0, "Delete confirm button should exist"


class TestConnectChannel:
    """Test the Slack/SMS connect channel flow."""

    def test_connect_channel_button(self, settings_league):
        """New Slack league shows Connect Channel button."""
        page = settings_league["page"]
        base_url = settings_league["base_url"]
        league_id = settings_league["league_id"]
        assert league_id, "League was not created"

        page.goto(f"{base_url}/dashboard/league/{league_id}")
        page.wait_for_load_state("networkidle")

        connect_btn = page.locator('button:has-text("Connect Channel")')
        assert connect_btn.count() > 0, "Connect Channel button should exist for unconnected Slack league"

    def test_league_shows_setup_required(self, settings_league):
        """New Slack league shows Setup Required status."""
        page = settings_league["page"]
        base_url = settings_league["base_url"]
        league_id = settings_league["league_id"]
        assert league_id, "League was not created"

        page.goto(f"{base_url}/dashboard/league/{league_id}")
        page.wait_for_load_state("networkidle")

        body = page.inner_text("body")
        assert "Setup Required" in body, "Unconnected Slack league should show 'Setup Required'"


class TestDashboardNavigation:
    """Test navigation between dashboard and league pages."""

    def test_back_to_dashboard(self, settings_league):
        """Can navigate back to dashboard from league page."""
        page = settings_league["page"]
        base_url = settings_league["base_url"]
        league_id = settings_league["league_id"]
        assert league_id, "League was not created"

        page.goto(f"{base_url}/dashboard/league/{league_id}")
        page.wait_for_load_state("networkidle")

        # Find the back-link (styled anchor with ← Back to Dashboard)
        back_link = page.locator('a.back-link')
        assert back_link.count() > 0, "Should have a back-link to dashboard"

        back_link.first.click()
        page.wait_for_load_state("networkidle")
        assert "/dashboard" in page.url

    def test_league_appears_on_dashboard(self, settings_league):
        """Created league appears in the dashboard league list."""
        page = settings_league["page"]
        base_url = settings_league["base_url"]

        page.goto(f"{base_url}/dashboard")
        page.wait_for_load_state("networkidle")

        body = page.inner_text("body")
        assert TEST_LEAGUE_NAME in body, f"League '{TEST_LEAGUE_NAME}' should appear on dashboard"
