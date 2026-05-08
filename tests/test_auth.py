"""
Auth flow tests: login, register page, logout, invalid credentials.

These tests verify the authentication system works end-to-end.
"""

import re
import pytest


class TestLogin:
    """Login flow tests."""

    def test_login_page_loads(self, page, base_url):
        """Login page renders with email/password form."""
        page.goto(f"{base_url}/auth/login")
        assert page.title() == "Login - WordPlayLeague.com"
        assert page.locator('input[name="email"]').is_visible()
        assert page.locator('input[name="password"]').is_visible()
        assert page.locator('button[type="submit"]').is_visible()

    def test_login_has_google_oauth(self, page, base_url):
        """Login page has Google sign-in button."""
        page.goto(f"{base_url}/auth/login")
        google_link = page.locator('a[href="/auth/google"]')
        assert google_link.is_visible()

    def test_login_has_register_link(self, page, base_url):
        """Login page links to registration."""
        page.goto(f"{base_url}/auth/login")
        assert page.locator('a[href="/auth/register"]').is_visible()

    def test_login_has_forgot_password_link(self, page, base_url):
        """Login page links to forgot password."""
        page.goto(f"{base_url}/auth/login")
        assert page.locator('a[href="/auth/forgot-password"]').is_visible()

    def test_login_invalid_credentials(self, page, base_url):
        """Login with wrong credentials shows error."""
        page.goto(f"{base_url}/auth/login")
        page.fill('input[name="email"]', "nonexistent@test.com")
        page.fill('input[name="password"]', "wrongpassword")
        page.click('button[type="submit"]')
        # Should stay on login page with an error
        page.wait_for_load_state("networkidle")
        assert "login" in page.url.lower()
        assert page.locator(".alert-error").is_visible()

    def test_login_empty_fields(self, page, base_url):
        """Login with empty fields shows error."""
        page.goto(f"{base_url}/auth/login")
        page.click('button[type="submit"]')
        # Browser validation or server-side error
        page.wait_for_load_state("networkidle")
        # Should still be on login page
        assert "login" in page.url.lower()

    def test_login_success(self, page, base_url, test_email, test_password):
        """Valid login redirects to dashboard."""
        page.goto(f"{base_url}/auth/login")
        page.fill('input[name="email"]', test_email)
        page.fill('input[name="password"]', test_password)
        page.click('button[type="submit"]')
        page.wait_for_url("**/dashboard**", timeout=10000)
        assert "/dashboard" in page.url

    def test_session_persists(self, page, base_url, test_email, test_password):
        """After login, navigating to dashboard doesn't require re-login."""
        page.goto(f"{base_url}/auth/login")
        page.fill('input[name="email"]', test_email)
        page.fill('input[name="password"]', test_password)
        page.click('button[type="submit"]')
        page.wait_for_url("**/dashboard**", timeout=10000)

        # Navigate away and back
        page.goto(f"{base_url}/dashboard")
        page.wait_for_load_state("networkidle")
        assert "/dashboard" in page.url
        # Should NOT be redirected to login
        assert "/auth/login" not in page.url


class TestLogout:
    """Logout flow tests."""

    def test_logout_redirects_to_login(self, logged_in_page, base_url):
        """Logging out redirects to login page."""
        logged_in_page.goto(f"{base_url}/auth/logout")
        logged_in_page.wait_for_load_state("networkidle")
        assert "/auth/login" in logged_in_page.url

    def test_logout_clears_session(self, logged_in_page, base_url):
        """After logout, dashboard redirects back to login."""
        logged_in_page.goto(f"{base_url}/auth/logout")
        logged_in_page.wait_for_load_state("networkidle")

        # Try to access dashboard — should redirect to login
        logged_in_page.goto(f"{base_url}/dashboard")
        logged_in_page.wait_for_load_state("networkidle")
        assert "/auth/login" in logged_in_page.url


class TestRegisterPage:
    """Registration page tests (does NOT create real accounts)."""

    def test_register_page_loads(self, page, base_url):
        """Register page renders with required fields."""
        page.goto(f"{base_url}/auth/register")
        assert page.locator('input[name="first_name"]').is_visible()
        assert page.locator('input[name="last_name"]').is_visible()
        assert page.locator('input[name="email"]').is_visible()
        assert page.locator('input[name="password"]').is_visible()
        assert page.locator('input[name="confirm_password"]').is_visible()

    def test_register_password_mismatch(self, page, base_url):
        """Mismatched passwords show error."""
        page.goto(f"{base_url}/auth/register")
        page.fill('input[name="first_name"]', "Test")
        page.fill('input[name="last_name"]', "User")
        page.fill('input[name="email"]', "mismatch-test@example.com")
        page.fill('input[name="password"]', "Password123!")
        page.fill('input[name="confirm_password"]', "DifferentPass!")
        page.click('button[type="submit"]')
        page.wait_for_load_state("networkidle")
        assert page.locator(".alert-error").is_visible()
        assert "match" in page.locator(".alert-error").inner_text().lower()


class TestForgotPassword:
    """Forgot password page tests."""

    def test_forgot_password_page_loads(self, page, base_url):
        """Forgot password page renders."""
        page.goto(f"{base_url}/auth/forgot-password")
        assert page.locator('input[name="email"]').is_visible()
        assert page.locator('button[type="submit"]').is_visible()


class TestUnauthenticatedRedirects:
    """Verify that protected pages redirect to login when not authenticated."""

    @pytest.mark.parametrize("path", [
        "/dashboard",
        "/dashboard/create-league",
        "/dashboard/profile",
        "/dashboard/membership",
    ])
    def test_protected_page_redirects(self, page, base_url, path):
        """Unauthenticated access to protected pages redirects to login."""
        page.goto(f"{base_url}{path}")
        page.wait_for_load_state("networkidle")
        assert "/auth/login" in page.url
