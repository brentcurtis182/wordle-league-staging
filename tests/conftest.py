"""
Shared fixtures for WordPlayLeague regression tests.

Usage:
    pytest tests/ --base-url https://staging.wordplayleague.com
    pytest tests/ --base-url https://staging.wordplayleague.com --headed  # watch in browser
"""

import pytest
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext


# ---------------------------------------------------------------------------
# CLI options
# ---------------------------------------------------------------------------

def pytest_addoption(parser):
    parser.addoption(
        "--base-url",
        action="store",
        default="https://staging.wordplayleague.com",
        help="Base URL of the WordPlayLeague instance to test against",
    )
    parser.addoption(
        "--test-email",
        action="store",
        default="testuser@wordplayleague.com",
        help="Email for the test account",
    )
    parser.addoption(
        "--test-password",
        action="store",
        default="TestPass123!",
        help="Password for the test account",
    )
    parser.addoption(
        "--headed",
        action="store_true",
        default=False,
        help="Run browser in headed mode (visible window)",
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def base_url(request):
    return request.config.getoption("--base-url").rstrip("/")


@pytest.fixture(scope="session")
def test_email(request):
    return request.config.getoption("--test-email")


@pytest.fixture(scope="session")
def test_password(request):
    return request.config.getoption("--test-password")


@pytest.fixture(scope="session")
def browser_instance(request):
    """Single browser instance for the entire test session."""
    headed = request.config.getoption("--headed")
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=not headed)
    yield browser
    browser.close()
    pw.stop()


@pytest.fixture
def context(browser_instance):
    """Fresh browser context per test (isolated cookies/storage)."""
    ctx = browser_instance.new_context(
        viewport={"width": 1280, "height": 800},
        ignore_https_errors=True,
    )
    yield ctx
    ctx.close()


@pytest.fixture
def page(context):
    """Fresh page per test."""
    p = context.new_page()
    yield p
    p.close()


@pytest.fixture
def logged_in_page(context, base_url, test_email, test_password):
    """Page that is already logged in to the dashboard.
    Reusable across any test that needs an authenticated session."""
    p = context.new_page()
    login(p, base_url, test_email, test_password)
    yield p
    p.close()


# ---------------------------------------------------------------------------
# Helpers (importable by test files)
# ---------------------------------------------------------------------------

def login(page: Page, base_url: str, email: str, password: str):
    """Log in via the auth form. Asserts redirect to dashboard."""
    page.goto(f"{base_url}/auth/login")
    page.fill('input[name="email"]', email)
    page.fill('input[name="password"]', password)
    page.click('button[type="submit"]')
    # Wait for redirect to dashboard
    page.wait_for_url(f"**/dashboard**", timeout=10000)


def get_league_ids_from_dashboard(page: Page) -> list[dict]:
    """Return list of {id, name} for leagues visible on the dashboard."""
    cards = page.query_selector_all('a[href*="/dashboard/league/"]')
    leagues = []
    for card in cards:
        href = card.get_attribute("href")
        if href and "/dashboard/league/" in href:
            league_id = href.split("/dashboard/league/")[-1].split("?")[0].split("/")[0]
            try:
                league_id = int(league_id)
            except ValueError:
                continue
            name = card.inner_text().strip()
            leagues.append({"id": league_id, "name": name})
    return leagues
