# Wordle League Regression Tests

Automated Playwright E2E tests that run against a live staging (or prod) instance.

## Setup

```bash
pip install pytest playwright
playwright install chromium
```

## Run

```bash
pytest tests/ -v --base-url https://staging.wordplayleague.com --test-email voxcurtis@gmail.com --test-password "TestPass123!"
```

### Options

| Flag | Description |
|------|-------------|
| `--base-url` | Target instance URL (default: staging) |
| `--test-email` | Login email for the test account |
| `--test-password` | Login password for the test account |
| `--headed` | Show the browser window while tests run |
| `-v` | Verbose output (show each test name) |
| `--tb=short` | Shorter tracebacks on failure |
| `-x` | Stop on first failure |
| `--lf` | Re-run only last-failed tests |

### Examples

```bash
# Watch tests run in a visible browser
pytest tests/ -v --headed --base-url https://staging.wordplayleague.com --test-email voxcurtis@gmail.com --test-password "TestPass123!"

# Run only auth tests
pytest tests/test_auth.py -v --base-url https://staging.wordplayleague.com --test-email voxcurtis@gmail.com --test-password "TestPass123!"

# Re-run only tests that failed last time
pytest tests/ -v --lf --base-url https://staging.wordplayleague.com --test-email voxcurtis@gmail.com --test-password "TestPass123!"
```

## Test Files

| File | Tests | What it covers |
|------|-------|----------------|
| `test_auth.py` | 17 | Login, logout, register, forgot password, session, redirects |
| `test_league_creation.py` | 7 | Create page, Slack/SMS leagues, slug validation |
| `test_league_pages.py` | 16 | Public league pages, content structure, JS errors, 404 handling |
| `test_league_settings.py` | 11 | Settings controls, AI toggles, delete flow, connect channel, navigation |
| `test_player_management.py` | 20 | Slack + SMS player add/remove/edit, phone validation, modal flows, safe_js regression |

## How It Works

- Tests create temporary leagues (both Slack and SMS), run checks, then delete them automatically
- Each test file has its own fixture that handles setup/cleanup
- Tests run against real staging data (e.g. bellyup, warriorz, party leagues) for public page checks
- SMS tests cover the different player layout (edit-mode-only Remove button, phone number field)
- No mocks -- everything hits the live server
- Full run takes ~2 minutes
