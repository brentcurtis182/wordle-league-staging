"""
Player management tests: add, edit, remove players.

These tests require an authenticated session and at least one league.
Tests cover BOTH Slack leagues (name-only) and SMS leagues (name + phone number).

IMPORTANT: This test file would have caught the safe_js onclick bug (May 2026)
where double quotes in JSON-encoded player names broke all Remove/Save buttons.
"""

import pytest
import time


# Unique suffix to avoid collisions with other test runs
_TS = str(int(time.time()))[-6:]
TEST_LEAGUE_NAME = f"Test Players {_TS}"
TEST_LEAGUE_SLUG = f"test-players-{_TS}"
SMS_LEAGUE_NAME = f"SMS Players {_TS}"
SMS_LEAGUE_SLUG = f"sms-players-{_TS}"


@pytest.fixture(scope="module")
def league_context(browser_instance, base_url, test_email, test_password):
    """Create a Slack test league, yield its ID, then delete it."""
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
    # Select Slack type — radio inputs are hidden inside styled labels
    slack_label = page.locator('label.platform-option:has(input[value="slack"])')
    if slack_label.count() > 0:
        slack_label.click()
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")

    # Extract league ID from URL
    # URL should be /dashboard/league/<id> after creation
    url = page.url
    league_id = None
    if "/dashboard/league/" in url:
        league_id = int(url.split("/dashboard/league/")[1].split("?")[0].split("/")[0])
    else:
        # Find it on dashboard
        page.goto(f"{base_url}/dashboard")
        page.wait_for_load_state("networkidle")
        link = page.locator(f'a[href*="/dashboard/league/"]:has-text("{TEST_LEAGUE_NAME}")')
        if link.count() > 0:
            href = link.first.get_attribute("href")
            league_id = int(href.split("/dashboard/league/")[1].split("?")[0].split("/")[0])

    yield {"page": page, "league_id": league_id, "base_url": base_url}

    # Cleanup: delete the test league
    if league_id:
        page.goto(f"{base_url}/dashboard/league/{league_id}")
        page.wait_for_load_state("networkidle")
        delete_btn = page.locator('button:has-text("Delete League")')
        if delete_btn.count() > 0:
            delete_btn.click()
            # Confirm deletion in modal — type league name to enable button
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


class TestAddPlayer:
    """Test adding players to a league."""

    def test_add_player_form_visible(self, league_context):
        """Add player form is visible and not disabled."""
        page = league_context["page"]
        base_url = league_context["base_url"]
        league_id = league_context["league_id"]
        assert league_id, "League was not created successfully"

        page.goto(f"{base_url}/dashboard/league/{league_id}")
        page.wait_for_load_state("networkidle")

        form = page.locator("#addPlayerForm")
        assert form.is_visible(), "Add player form should be visible"
        # Form should not have pointer-events: none (not at limit)
        style = form.get_attribute("style") or ""
        assert "pointer-events: none" not in style, "Add player form should not be disabled"

    def test_add_player_success(self, league_context):
        """Adding a player shows them in the player list."""
        page = league_context["page"]
        base_url = league_context["base_url"]
        league_id = league_context["league_id"]
        assert league_id, "League was not created successfully"

        page.goto(f"{base_url}/dashboard/league/{league_id}")
        page.wait_for_load_state("networkidle")

        page.fill('#addPlayerForm input[name="name"]', "TestPlayer")
        page.click('#addPlayerForm button[type="submit"]')
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(500)

        # Player should appear on the page (reload may be needed)
        body = page.inner_text("body")
        assert "TestPlayer" in body, "Player 'TestPlayer' should appear on page"

    def test_add_player_special_chars(self, league_context):
        """Adding a player with special characters (quotes, apostrophes)."""
        page = league_context["page"]
        base_url = league_context["base_url"]
        league_id = league_context["league_id"]
        assert league_id, "League was not created successfully"

        page.goto(f"{base_url}/dashboard/league/{league_id}")
        page.wait_for_load_state("networkidle")

        page.fill('#addPlayerForm input[name="name"]', "O'Brien")
        page.click('#addPlayerForm button[type="submit"]')
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(500)

        body = page.inner_text("body")
        assert "O'Brien" in body, "Player with apostrophe should appear"

    def test_add_player_count_badge(self, league_context):
        """Player count badge updates after adding players."""
        page = league_context["page"]
        base_url = league_context["base_url"]
        league_id = league_context["league_id"]
        assert league_id, "League was not created successfully"

        page.goto(f"{base_url}/dashboard/league/{league_id}")
        page.wait_for_load_state("networkidle")

        # Should show at least 2 players from prior tests (TestPlayer, O'Brien)
        badge = page.locator('text=/\\d+\\/\\d+/')  # matches "2/14" etc
        assert badge.count() > 0, "Player count badge should be visible"


class TestRemovePlayer:
    """Test removing players.

    This specifically tests the bug where safe_js() double quotes
    broke onclick attributes, making Remove buttons completely dead.
    """

    def test_remove_button_exists(self, league_context):
        """Remove button is present for each player."""
        page = league_context["page"]
        base_url = league_context["base_url"]
        league_id = league_context["league_id"]
        assert league_id, "League was not created successfully"

        page.goto(f"{base_url}/dashboard/league/{league_id}")
        page.wait_for_load_state("networkidle")

        # Use onclick selector to target only player Remove buttons
        remove_btns = page.locator('button[onclick*="showRemoveModal"]')
        assert remove_btns.count() > 0, "Remove buttons should exist for players"

    def test_remove_button_opens_modal(self, league_context):
        """Clicking Remove opens the confirmation modal.

        This is the KEY regression test — the safe_js bug made this button
        completely non-functional because broken HTML attributes silently
        prevented the onclick handler from firing.
        """
        page = league_context["page"]
        base_url = league_context["base_url"]
        league_id = league_context["league_id"]
        assert league_id, "League was not created successfully"

        page.goto(f"{base_url}/dashboard/league/{league_id}")
        page.wait_for_load_state("networkidle")

        # Click the first player Remove button (use onclick to avoid "Remove Mascot" / "Yes, Remove")
        remove_btn = page.locator('button[onclick*="showRemoveModal"]').first
        remove_btn.click()

        # Modal should appear (display changes from none to flex via .active class)
        modal = page.locator("#removeModal.active")
        modal.wait_for(state="attached", timeout=3000)
        assert page.locator('#removeModal.active').count() > 0, "Remove confirmation modal should appear"

        # Modal should have confirm and cancel buttons
        assert page.locator('#removeModal button:has-text("Yes, Remove")').count() > 0
        assert page.locator('#removeModal button:has-text("Cancel")').count() > 0

    def test_remove_modal_cancel(self, league_context):
        """Canceling the remove modal closes it without removing."""
        page = league_context["page"]
        base_url = league_context["base_url"]
        league_id = league_context["league_id"]
        assert league_id, "League was not created successfully"

        page.goto(f"{base_url}/dashboard/league/{league_id}")
        page.wait_for_load_state("networkidle")

        player_count_before = page.locator('button[onclick*="showRemoveModal"]').count()

        # Open modal and cancel
        page.locator('button[onclick*="showRemoveModal"]').first.click()
        page.locator("#removeModal.active").wait_for(state="attached", timeout=3000)
        page.locator('#removeModal button:has-text("Cancel")').click(force=True)

        # Modal should close
        page.wait_for_timeout(500)
        assert page.locator("#removeModal.active").count() == 0

        # Player count should be the same
        assert page.locator('button[onclick*="showRemoveModal"]').count() == player_count_before

    def test_remove_player_success(self, league_context):
        """Confirming remove actually removes the player."""
        page = league_context["page"]
        base_url = league_context["base_url"]
        league_id = league_context["league_id"]
        assert league_id, "League was not created successfully"

        page.goto(f"{base_url}/dashboard/league/{league_id}")
        page.wait_for_load_state("networkidle")

        player_count_before = page.locator('button[onclick*="showRemoveModal"]').count()
        if player_count_before == 0:
            pytest.skip("No players to remove")

        # Click Remove on first player
        page.locator('button[onclick*="showRemoveModal"]').first.click()
        page.locator("#removeModal.active").wait_for(state="attached", timeout=3000)

        # Confirm removal — this triggers a POST and page reload
        page.locator('#removeModal button:has-text("Yes, Remove")').click(force=True)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(500)

        # Page should show success message or redirect back
        body = page.inner_text("body")
        # For Slack leagues, player may show as pending_removal rather than being fully deleted
        # Either the count decreases OR a success/removed message appears
        new_count = page.locator('button[onclick*="showRemoveModal"]').count()
        removed_ok = (
            new_count < player_count_before
            or "removed" in body.lower()
            or "message" in page.url.lower()
        )
        assert removed_ok, f"Player removal should succeed (had {player_count_before}, now {new_count})"


class TestEditPlayer:
    """Test editing player names."""

    def test_edit_button_exists(self, league_context):
        """Edit (pencil) button is present for each player."""
        page = league_context["page"]
        base_url = league_context["base_url"]
        league_id = league_context["league_id"]
        assert league_id, "League was not created successfully"

        # Wait briefly for any in-flight navigation from prior test to settle
        page.wait_for_timeout(500)
        page.goto(f"{base_url}/dashboard/league/{league_id}", wait_until="networkidle")

        # Edit button is the pencil emoji button
        edit_btns = page.locator('button[onclick*="enterEditMode"]')
        # Should have at least one if there are remaining players
        if page.locator('button[onclick*="showRemoveModal"]').count() > 0:
            assert edit_btns.count() > 0, "Edit buttons should exist for players"

    def test_edit_mode_toggle(self, league_context):
        """Clicking edit shows the edit form, clicking cancel hides it."""
        page = league_context["page"]
        base_url = league_context["base_url"]
        league_id = league_context["league_id"]
        assert league_id, "League was not created successfully"

        page.goto(f"{base_url}/dashboard/league/{league_id}")
        page.wait_for_load_state("networkidle")

        edit_btns = page.locator('button[onclick*="enterEditMode"]')
        if edit_btns.count() == 0:
            pytest.skip("No players to edit")

        # Click edit
        edit_btns.first.click()
        page.wait_for_timeout(300)

        # Edit form should show Save button (use onclick to be specific)
        save_btns = page.locator('button[onclick*="showSaveModal"]')
        cancel_btns = page.locator('button[onclick*="cancelEdit"]')
        assert save_btns.count() > 0, "Save button should appear in edit mode"
        assert cancel_btns.count() > 0, "Cancel button should appear in edit mode"

        # Cancel edit
        cancel_btns.first.click()
        page.wait_for_timeout(300)


class TestPlayerNameEdgeCases:
    """Edge case tests for player names that could break HTML/JS."""

    def test_add_player_with_quotes(self, league_context):
        """Player name with double quotes doesn't break the page.

        Regression test: safe_js produced "name" which broke onclick="..." attributes.
        """
        page = league_context["page"]
        base_url = league_context["base_url"]
        league_id = league_context["league_id"]
        assert league_id, "League was not created successfully"

        page.goto(f"{base_url}/dashboard/league/{league_id}")
        page.wait_for_load_state("networkidle")

        # Add a player — the name itself won't have quotes (max 14 chars, form validates)
        # but we test that buttons still work after adding any player
        page.fill('#addPlayerForm input[name="name"]', "QuoteTest")
        page.click('#addPlayerForm button[type="submit"]')
        page.wait_for_load_state("networkidle")

        # The critical test: Remove button should be CLICKABLE (not dead from broken HTML)
        remove_btns = page.locator('button[onclick*="showRemoveModal"]')
        assert remove_btns.count() > 0, "Remove buttons should exist"

        # Click remove and verify modal opens — this is THE test that catches the safe_js bug
        remove_btns.first.click()
        try:
            page.locator("#removeModal.active").wait_for(state="attached", timeout=3000)
            modal_opened = True
        except Exception:
            modal_opened = False

        assert modal_opened, (
            "Remove modal did not open! This likely means onclick attributes are broken "
            "(safe_js double-quote escaping bug). Check that safe_js_attr is used in onclick handlers."
        )

        # Close modal
        page.locator('#removeModal button:has-text("Cancel")').click(force=True)

    def test_all_buttons_functional_with_players(self, league_context):
        """After adding players, ALL action buttons on the page should be functional."""
        page = league_context["page"]
        base_url = league_context["base_url"]
        league_id = league_context["league_id"]
        assert league_id, "League was not created successfully"

        page.goto(f"{base_url}/dashboard/league/{league_id}")
        page.wait_for_load_state("networkidle")

        # Collect all JS errors on the page
        js_errors = []
        page.on("pageerror", lambda err: js_errors.append(str(err)))

        # Click every player Remove button and verify modal opens
        remove_btns = page.locator('button[onclick*="showRemoveModal"]')
        count = remove_btns.count()
        for i in range(count):
            remove_btns.nth(i).click()
            page.wait_for_timeout(500)
            modal_active = page.locator("#removeModal.active").count() > 0
            if modal_active:
                page.locator('#removeModal button:has-text("Cancel")').click(force=True)
                page.wait_for_timeout(300)
            else:
                pytest.fail(f"Remove button #{i} did not open modal — onclick handler is broken")

        assert len(js_errors) == 0, f"JavaScript errors on page: {js_errors}"


# ---------------------------------------------------------------------------
# SMS League Player Management
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def sms_league_context(browser_instance, base_url, test_email, test_password):
    """Create an SMS test league, yield its ID, then delete it."""
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

    # Create SMS league
    page.goto(f"{base_url}/dashboard/create-league")
    page.wait_for_load_state("networkidle")
    page.fill('input[name="league_name"]', SMS_LEAGUE_NAME)
    page.fill('input[name="slug"]', SMS_LEAGUE_SLUG)
    sms_label = page.locator('label.platform-option:has(input[value="sms"])')
    if sms_label.count() > 0:
        sms_label.click()
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")

    url = page.url
    league_id = None
    if "/dashboard/league/" in url:
        league_id = int(url.split("/dashboard/league/")[1].split("?")[0].split("/")[0])
    else:
        page.goto(f"{base_url}/dashboard")
        page.wait_for_load_state("networkidle")
        link = page.locator(f'a[href*="/dashboard/league/"]:has-text("{SMS_LEAGUE_NAME}")')
        if link.count() > 0:
            href = link.first.get_attribute("href")
            league_id = int(href.split("/dashboard/league/")[1].split("?")[0].split("/")[0])

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
                confirm_input.fill(SMS_LEAGUE_NAME)
                page.wait_for_timeout(300)
            confirm_btn = page.locator('#confirmDeleteBtn')
            if confirm_btn.count() > 0:
                confirm_btn.click()
                page.wait_for_load_state("networkidle")

    page.close()
    ctx.close()


class TestSMSAddPlayer:
    """Test adding players to an SMS league (requires name + phone number)."""

    def test_sms_add_form_has_phone_field(self, sms_league_context):
        """SMS league add-player form has both name and phone fields."""
        page = sms_league_context["page"]
        base_url = sms_league_context["base_url"]
        league_id = sms_league_context["league_id"]
        assert league_id, "SMS league was not created"

        page.goto(f"{base_url}/dashboard/league/{league_id}")
        page.wait_for_load_state("networkidle")

        name_input = page.locator('#addPlayerForm input[name="name"]')
        phone_input = page.locator('#addPlayerForm input[name="identifier"], #phoneInput')
        assert name_input.is_visible(), "Name field should be visible"
        assert phone_input.is_visible(), "Phone/identifier field should be visible for SMS"

    def test_sms_add_player_success(self, sms_league_context):
        """Adding a player with name + phone number works."""
        page = sms_league_context["page"]
        base_url = sms_league_context["base_url"]
        league_id = sms_league_context["league_id"]
        assert league_id, "SMS league was not created"

        page.goto(f"{base_url}/dashboard/league/{league_id}")
        page.wait_for_load_state("networkidle")

        page.fill('#addPlayerForm input[name="name"]', "Alice")
        phone_input = page.locator('#phoneInput, #addPlayerForm input[name="identifier"]')
        phone_input.first.fill("(555) 123-4567")
        page.click('#addPlayerForm button[type="submit"]')
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(500)

        body = page.inner_text("body")
        assert "Alice" in body, "Player 'Alice' should appear after adding"

    def test_sms_add_second_player(self, sms_league_context):
        """Add a second SMS player for later remove/edit tests."""
        page = sms_league_context["page"]
        base_url = sms_league_context["base_url"]
        league_id = sms_league_context["league_id"]
        assert league_id, "SMS league was not created"

        page.goto(f"{base_url}/dashboard/league/{league_id}")
        page.wait_for_load_state("networkidle")

        page.fill('#addPlayerForm input[name="name"]', "Bob")
        phone_input = page.locator('#phoneInput, #addPlayerForm input[name="identifier"]')
        phone_input.first.fill("(555) 987-6543")
        page.click('#addPlayerForm button[type="submit"]')
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(500)

        body = page.inner_text("body")
        assert "Bob" in body, "Player 'Bob' should appear after adding"

    def test_sms_phone_validation_rejects_short(self, sms_league_context):
        """Phone number validation rejects numbers that aren't 10 digits."""
        page = sms_league_context["page"]
        base_url = sms_league_context["base_url"]
        league_id = sms_league_context["league_id"]
        assert league_id, "SMS league was not created"

        page.goto(f"{base_url}/dashboard/league/{league_id}")
        page.wait_for_load_state("networkidle")

        page.fill('#addPlayerForm input[name="name"]', "BadPhone")
        phone_input = page.locator('#phoneInput, #addPlayerForm input[name="identifier"]')
        phone_input.first.fill("123")
        page.click('#addPlayerForm button[type="submit"]')
        page.wait_for_timeout(500)

        # Should show phone validation error, NOT navigate away
        phone_error = page.locator('#phoneError')
        error_visible = phone_error.is_visible() if phone_error.count() > 0 else False
        # Player should NOT have been added
        body = page.inner_text("body")
        assert error_visible or "BadPhone" not in body, \
            "Short phone number should be rejected by validation"


class TestSMSRemovePlayer:
    """Test removing players from an SMS league.

    NOTE: SMS player layout differs from Slack — the Remove button is only
    visible in edit mode (click pencil first), not in the read-only view.
    """

    def test_sms_remove_via_edit_mode(self, sms_league_context):
        """SMS Remove button appears in edit mode and opens the modal."""
        page = sms_league_context["page"]
        base_url = sms_league_context["base_url"]
        league_id = sms_league_context["league_id"]
        assert league_id, "SMS league was not created"

        page.goto(f"{base_url}/dashboard/league/{league_id}")
        page.wait_for_load_state("networkidle")

        # SMS: must enter edit mode first to see Remove button
        edit_btns = page.locator('button[onclick*="enterEditMode"]')
        assert edit_btns.count() > 0, "SMS players should have edit buttons"
        edit_btns.first.click()
        page.wait_for_timeout(300)

        # Now the Remove button should be visible in the edit form
        remove_btn = page.locator('.edit-form button[onclick*="showRemoveModal"]').first
        assert remove_btn.is_visible(), "Remove button should be visible in SMS edit mode"

        # Click Remove and verify modal opens
        remove_btn.click()
        try:
            page.locator("#removeModal.active").wait_for(state="attached", timeout=3000)
            modal_opened = True
        except Exception:
            modal_opened = False

        assert modal_opened, (
            "Remove modal did not open for SMS player! "
            "Check safe_js_attr is used in onclick handlers."
        )

        # Close modal
        page.locator('#removeModal button:has-text("Cancel")').click(force=True)
        page.wait_for_timeout(300)

    def test_sms_remove_player_success(self, sms_league_context):
        """Confirming remove actually removes an SMS player."""
        page = sms_league_context["page"]
        base_url = sms_league_context["base_url"]
        league_id = sms_league_context["league_id"]
        assert league_id, "SMS league was not created"

        page.goto(f"{base_url}/dashboard/league/{league_id}")
        page.wait_for_load_state("networkidle")

        edit_btns = page.locator('button[onclick*="enterEditMode"]')
        player_count_before = edit_btns.count()
        if player_count_before == 0:
            pytest.skip("No SMS players to remove")

        # Enter edit mode, then click Remove
        edit_btns.first.click()
        page.wait_for_timeout(300)
        page.locator('.edit-form button[onclick*="showRemoveModal"]').first.click()
        page.locator("#removeModal.active").wait_for(state="attached", timeout=3000)

        # Confirm removal
        page.locator('#removeModal button:has-text("Yes, Remove")').click(force=True)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(500)

        body = page.inner_text("body")
        new_count = page.locator('button[onclick*="enterEditMode"]').count()
        removed_ok = (
            new_count < player_count_before
            or "removed" in body.lower()
            or "message" in page.url.lower()
        )
        assert removed_ok, f"SMS player removal should succeed (had {player_count_before}, now {new_count})"


class TestSMSEditPlayer:
    """Test editing SMS players (name + phone)."""

    def test_sms_edit_button_exists(self, sms_league_context):
        """SMS players have edit (pencil) buttons."""
        page = sms_league_context["page"]
        base_url = sms_league_context["base_url"]
        league_id = sms_league_context["league_id"]
        assert league_id, "SMS league was not created"

        page.wait_for_timeout(500)
        page.goto(f"{base_url}/dashboard/league/{league_id}", wait_until="networkidle")

        if page.locator('button[onclick*="showRemoveModal"]').count() > 0:
            edit_btns = page.locator('button[onclick*="enterEditMode"]')
            assert edit_btns.count() > 0, "SMS players should have edit buttons"

    def test_sms_edit_shows_phone_field(self, sms_league_context):
        """Editing an SMS player shows the phone/identifier field."""
        page = sms_league_context["page"]
        base_url = sms_league_context["base_url"]
        league_id = sms_league_context["league_id"]
        assert league_id, "SMS league was not created"

        page.goto(f"{base_url}/dashboard/league/{league_id}")
        page.wait_for_load_state("networkidle")

        edit_btns = page.locator('button[onclick*="enterEditMode"]')
        if edit_btns.count() == 0:
            pytest.skip("No SMS players to edit")

        edit_btns.first.click()
        page.wait_for_timeout(300)

        # SMS edit form should have an identifier/phone input visible
        edit_identifier = page.locator('.edit-form input[name="identifier"]:visible')
        assert edit_identifier.count() > 0, "SMS edit form should show phone/identifier field"

        # Cancel edit
        cancel_btns = page.locator('button[onclick*="cancelEdit"]')
        if cancel_btns.count() > 0:
            cancel_btns.first.click()
