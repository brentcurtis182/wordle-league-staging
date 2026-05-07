#!/usr/bin/env python3
"""
Monitoring system for Wordle League
- Site health: pings a canary league page every 5 minutes
- Score verification: confirms first score of the day appears on the league page
Alerts via SMS (Twilio) and email (Brevo) when issues are detected.
"""

import os
import logging
import threading
import time
import requests
from datetime import datetime, timedelta, timezone

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Configuration ---
ALERT_PHONE = os.environ.get('ALERT_PHONE', '+18587359353')  # Brent's number
ALERT_EMAILS = [
    'brentcurtis182@gmail.com',
    'brentcurtis182@hotmail.com',
]
CANARY_LEAGUE_URL = 'https://brentcurtis182.github.io/wordle-league/party/index.html'  # League 4
HEALTH_CHECK_INTERVAL = 300  # 5 minutes
SCORE_VERIFY_DELAY = 45  # seconds to wait for GitHub Pages propagation

# Track alert state to avoid spamming
_last_health_alert_time = None
_health_alert_cooldown = 1800  # 30 min between repeat alerts
_score_verified_today = {}  # {league_id: date} — only verify first score per league per day


def _send_alert_sms(message):
    """Send an SMS alert via Twilio."""
    try:
        account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
        auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
        twilio_phone = os.environ.get('TWILIO_PHONE_NUMBER')
        if not all([account_sid, auth_token, twilio_phone]):
            logging.warning('Monitoring: Twilio credentials not set, skipping SMS alert')
            return
        from twilio.rest import Client
        client = Client(account_sid, auth_token)
        client.messages.create(
            body=message,
            from_=twilio_phone,
            to=ALERT_PHONE
        )
        logging.info(f'Monitoring: SMS alert sent to {ALERT_PHONE}')
    except Exception as e:
        logging.error(f'Monitoring: Failed to send SMS alert: {e}')


def _send_alert_email(subject, message):
    """Send an email alert via Brevo to all ALERT_EMAILS."""
    try:
        from email_utils import _send_email_sync
        html = f'<div style="font-family:monospace;padding:20px;background:#1a1a2e;color:#e0e0e0;">'
        html += f'<h2 style="color:#e74c3c;">WordPlayLeague Alert</h2>'
        html += f'<p>{message}</p>'
        html += f'<p style="color:#888;">Sent: {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")}</p>'
        html += '</div>'
        for email in ALERT_EMAILS:
            _send_alert_email_single(email, subject, html)
    except Exception as e:
        logging.error(f'Monitoring: Failed to send email alerts: {e}')


def _send_alert_email_single(email, subject, html):
    """Send to a single email address."""
    try:
        from email_utils import _send_email_sync
        _send_email_sync(email, subject, html)
        logging.info(f'Monitoring: Email alert sent to {email}')
    except Exception as e:
        logging.error(f'Monitoring: Failed to send email to {email}: {e}')


def _send_alert(subject, message):
    """Send alert via both SMS and email."""
    _send_alert_sms(f'[WordPlayLeague] {subject}: {message}')
    _send_alert_email(f'[Alert] {subject}', message)


def check_site_health():
    """Check if the canary league page is up and rendering properly.
    Returns True if healthy, False if there's a problem."""
    try:
        resp = requests.get(CANARY_LEAGUE_URL, timeout=15)
        if resp.status_code != 200:
            return False, f'HTTP {resp.status_code}'

        html = resp.text
        # Check for signs of a working page
        if len(html) < 1000:
            return False, f'Page too small ({len(html)} bytes) — likely blank/error'
        if 'No data available' in html:
            return False, 'Page shows "No data available"'
        # Check for expected content markers (scores table, player names)
        if '<table' not in html.lower() and 'wordle' not in html.lower():
            return False, 'Page missing expected content (no table or wordle reference)'

        return True, 'OK'
    except requests.Timeout:
        return False, 'Request timed out (15s)'
    except requests.ConnectionError as e:
        return False, f'Connection error: {e}'
    except Exception as e:
        return False, f'Unexpected error: {e}'


def run_health_check():
    """Run a single health check and alert if there's a problem."""
    global _last_health_alert_time

    healthy, detail = check_site_health()
    if healthy:
        # If we were in an alert state, send a recovery notification
        if _last_health_alert_time:
            _send_alert('Site Recovered', 'League pages are back up and rendering correctly.')
            _last_health_alert_time = None
        return

    # Site is down — check cooldown before alerting
    now = time.time()
    if _last_health_alert_time and (now - _last_health_alert_time) < _health_alert_cooldown:
        logging.warning(f'Monitoring: Site still down ({detail}) — alert on cooldown')
        return

    _last_health_alert_time = now
    logging.error(f'Monitoring: SITE DOWN — {detail}')
    _send_alert('Site Down', f'League pages are not rendering correctly. Detail: {detail}. URL: {CANARY_LEAGUE_URL}')


def verify_score_on_page(league_id, wordle_number):
    """Verify that a score appears on the league's public page.
    Only runs for the first score per league per day.
    Runs in a background thread after a delay for GitHub Pages propagation."""

    pacific_tz = timezone(timedelta(hours=-8))
    today = datetime.now(pacific_tz).date()

    # Only verify first score of the day per league
    if _score_verified_today.get(league_id) == today:
        return
    _score_verified_today[league_id] = today

    def _verify():
        time.sleep(SCORE_VERIFY_DELAY)
        try:
            # Build the league's GitHub Pages URL
            league_slugs = {
                1: '',
                3: 'pal',
                4: 'party',
                6: 'league6',
                7: 'bellyup'
            }
            slug = league_slugs.get(league_id, f'league{league_id}')
            if slug:
                url = f'https://brentcurtis182.github.io/wordle-league/{slug}/index.html'
            else:
                url = 'https://brentcurtis182.github.io/wordle-league/index.html'

            resp = requests.get(url, timeout=15)
            if resp.status_code != 200:
                logging.error(f'Monitoring: Score verify failed for league {league_id} — HTTP {resp.status_code}')
                _send_alert('Score Not Appearing',
                            f'League {league_id} page returned HTTP {resp.status_code} after score for Wordle #{wordle_number}. URL: {url}')
                return

            # Check if the wordle number appears on the page
            if str(wordle_number) in resp.text:
                logging.info(f'Monitoring: Score verified on page for league {league_id}, Wordle #{wordle_number}')
            else:
                logging.error(f'Monitoring: Wordle #{wordle_number} NOT found on league {league_id} page')
                _send_alert('Score Not Appearing',
                            f'Wordle #{wordle_number} score was recorded but is NOT showing on the league {league_id} page. URL: {url}')
        except Exception as e:
            logging.error(f'Monitoring: Score verify error for league {league_id}: {e}')

    thread = threading.Thread(target=_verify, daemon=True)
    thread.start()


def start_health_monitor():
    """Start the background health check loop. Call once at app startup."""
    def _loop():
        logging.info(f'Monitoring: Health check started (every {HEALTH_CHECK_INTERVAL}s, canary: {CANARY_LEAGUE_URL})')
        while True:
            try:
                run_health_check()
            except Exception as e:
                logging.error(f'Monitoring: Health check loop error: {e}')
            time.sleep(HEALTH_CHECK_INTERVAL)

    thread = threading.Thread(target=_loop, daemon=True)
    thread.start()
    logging.info('Monitoring: Background health monitor started')
