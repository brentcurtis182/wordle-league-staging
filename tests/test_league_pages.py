"""
Public league page tests: verify pages render, no crashes, expected content present.

These tests check the public-facing league pages (the ones players see).
They do NOT require authentication.

Tests run against known staging leagues with real data, plus a freshly
created test league to verify empty-state rendering.

IMPORTANT: This test file would have caught the May 6 2026 cache crash where
clear_min_scores_cache() accessed the wrong default parameter index, causing
ALL league pages to show "No data available".
"""

import pytest
import time


# Staging leagues with real score data — safe to test against
STAGING_LEAGUE_SLUGS = [
    "bellyup",
    "warriorz",
    "party",
]

# Minimum expected page size (bytes) for a real league page
MIN_PAGE_SIZE = 1000

_TS = str(int(time.time()))[-6:]
TEST_LEAGUE_NAME = f"Page Test {_TS}"
TEST_LEAGUE_SLUG = f"page-test-{_TS}"


@pytest.fixture(scope="module")
def test_league_slug(browser_instance, base_url, test_email, test_password):
    """Create a test league and return its slug. Cleans up after tests."""
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

    # Get league ID for cleanup
    league_id = None
    if "/dashboard/league/" in page.url:
        league_id = int(page.url.split("/dashboard/league/")[1].split("?")[0].split("/")[0])

    yield TEST_LEAGUE_SLUG

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


class TestLeaguePageRendering:
    """Verify public league pages with real data render correctly."""

    @pytest.mark.parametrize("slug", STAGING_LEAGUE_SLUGS)
    def test_league_page_loads(self, page, base_url, slug):
        """Public league page returns 200 and has substantial content."""
        response = page.goto(f"{base_url}/leagues/{slug}")
        assert response.status == 200, f"League page /{slug} returned HTTP {response.status}"

        content = page.content()
        assert len(content) > MIN_PAGE_SIZE, (
            f"League page /{slug} is too small ({len(content)} bytes) — likely blank or error"
        )

    @pytest.mark.parametrize("slug", STAGING_LEAGUE_SLUGS)
    def test_league_page_no_error_state(self, page, base_url, slug):
        """League page should NOT show error states.

        Regression test for the May 6 crash where all pages showed
        'No data available' due to a cache function bug.
        """
        page.goto(f"{base_url}/leagues/{slug}")
        page.wait_for_load_state("networkidle")
        body_text = page.inner_text("body")

        assert "No data available" not in body_text, (
            f"League page /{slug} shows 'No data available' — "
            "this likely means the data pipeline is broken"
        )

    @pytest.mark.parametrize("slug", STAGING_LEAGUE_SLUGS)
    def test_league_page_has_content_structure(self, page, base_url, slug):
        """League page has expected structural elements (scores, tables, tabs)."""
        page.goto(f"{base_url}/leagues/{slug}")
        page.wait_for_load_state("networkidle")

        has_table = page.locator("table").count() > 0
        has_scores = page.locator('[class*="score"], [class*="player"]').count() > 0
        has_tabs = page.locator('[class*="tab"], button:has-text("Weekly"), button:has-text("Season")').count() > 0

        assert has_table or has_scores or has_tabs, (
            f"League page /{slug} missing expected content structure "
            "(no tables, scores, or tabs found)"
        )

    @pytest.mark.parametrize("slug", STAGING_LEAGUE_SLUGS)
    def test_league_page_no_js_errors(self, page, base_url, slug):
        """League page should not have JavaScript errors."""
        js_errors = []
        page.on("pageerror", lambda err: js_errors.append(str(err)))

        page.goto(f"{base_url}/leagues/{slug}")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)

        assert len(js_errors) == 0, f"JavaScript errors on /{slug}: {js_errors}"


class TestNewLeaguePage:
    """Test that a freshly created league's public page works."""

    def test_new_league_page_loads(self, page, base_url, test_league_slug):
        """Newly created league page returns 200."""
        response = page.goto(f"{base_url}/leagues/{test_league_slug}")
        assert response.status == 200, f"New league page returned HTTP {response.status}"

    def test_new_league_page_no_crash(self, page, base_url, test_league_slug):
        """New league page doesn't crash (even with no scores)."""
        js_errors = []
        page.on("pageerror", lambda err: js_errors.append(str(err)))

        page.goto(f"{base_url}/leagues/{test_league_slug}")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)

        # Page should not 500 or have JS errors
        assert len(js_errors) == 0, f"JavaScript errors on new league page: {js_errors}"

    def test_new_league_shows_league_name(self, page, base_url, test_league_slug):
        """New league page displays the league name."""
        page.goto(f"{base_url}/leagues/{test_league_slug}")
        page.wait_for_load_state("networkidle")
        body_text = page.inner_text("body")
        assert TEST_LEAGUE_NAME in body_text, f"League name '{TEST_LEAGUE_NAME}' should appear on public page"


class TestLeaguePageNotFound:
    """Test behavior for non-existent leagues."""

    def test_nonexistent_slug_handled(self, page, base_url):
        """Non-existent league slug returns error or 404, not crash."""
        response = page.goto(f"{base_url}/leagues/this-league-does-not-exist-xyz")
        assert response.status != 500, "Non-existent league should not cause server error"
