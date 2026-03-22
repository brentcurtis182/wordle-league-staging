#!/usr/bin/env python3
"""
Email utility for Wordle League
Sends branded HTML emails via SendGrid HTTP API for password resets and email verification
"""

import os
import logging
import threading
import requests

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY', '')
FROM_EMAIL = os.environ.get('FROM_EMAIL', 'WordPlayLeague <noreply@wordplayleague.com>')
APP_URL = os.environ.get('APP_URL', 'https://app.wordplayleague.com')
ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'Wordplayleague@gmail.com')

def _get_email_template(title, body_html):
    """Wrap content in a branded HTML email template.
    Uses bgcolor attributes + inline styles + multiple wrapper tables to force
    dark backgrounds on Gmail app and other mobile email clients."""
    # No leading whitespace - Gmail can be sensitive to it
    return (
'<!DOCTYPE html>'
'<html xmlns="http://www.w3.org/1999/xhtml" lang="en">'
'<head>'
'<meta charset="utf-8">'
'<meta name="viewport" content="width=device-width, initial-scale=1">'
'<meta name="color-scheme" content="dark">'
'<meta name="supported-color-schemes" content="dark">'
f'<title>{title}</title>'
'<style>'
':root { color-scheme: dark; supported-color-schemes: dark; }'
'body, html { background-color: #1a1a2e !important; margin: 0 !important; padding: 0 !important; }'
'u + .body { background-color: #1a1a2e !important; }'
'div[style*="margin: 16px 0"] { margin: 0 !important; }'
'</style>'
'</head>'
'<body bgcolor="#1a1a2e" style="margin:0;padding:0;background-color:#1a1a2e;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;-webkit-text-size-adjust:100%;-ms-text-size-adjust:100%;">'
'<!--[if mso]><table width="100%" bgcolor="#1a1a2e"><tr><td>&nbsp;</td><td width="600"><![endif]-->'
'<div class="body" style="background-color:#1a1a2e;width:100%;margin:0;padding:0;">'
'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#1a1a2e" style="background-color:#1a1a2e;margin:0;padding:0;border-collapse:collapse;">'
'<tr><td bgcolor="#1a1a2e" style="background-color:#1a1a2e;padding:0;margin:0;">'
'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#1a1a2e" style="background-color:#1a1a2e;border-collapse:collapse;">'
# Top spacer
'<tr><td bgcolor="#1a1a2e" style="background-color:#1a1a2e;height:40px;font-size:1px;line-height:1px;">&nbsp;</td></tr>'
# Content row
'<tr><td bgcolor="#1a1a2e" align="center" style="background-color:#1a1a2e;padding:0 20px;">'
'<table role="presentation" width="500" cellpadding="0" cellspacing="0" border="0" bgcolor="#16213e" style="max-width:500px;width:100%;background-color:#16213e;border-radius:12px;border:1px solid #333;border-collapse:separate;">'
# Header
'<tr>'
'<td bgcolor="#16213e" style="background-color:#16213e;padding:30px 30px 20px;text-align:center;border-bottom:1px solid #333;">'
'<span style="font-size:1.5em;font-weight:bold;color:#00E8DA;">WordPlay<span style="color:#FFA64D;">League.com</span></span>'
'</td>'
'</tr>'
# Body
'<tr>'
f'<td bgcolor="#16213e" style="background-color:#16213e;padding:30px;">'
f'<h2 style="color:#00E8DA;margin:0 0 20px;font-size:1.3em;">{title}</h2>'
f'{body_html}'
'</td>'
'</tr>'
# Footer
'<tr>'
'<td bgcolor="#16213e" style="background-color:#16213e;padding:20px 30px;text-align:center;border-top:1px solid #333;color:#888;font-size:0.8em;">'
'&copy; WordPlayLeague.com'
'</td>'
'</tr>'
'</table>'
'</td></tr>'
# Bottom spacer
'<tr><td bgcolor="#1a1a2e" style="background-color:#1a1a2e;height:40px;font-size:1px;line-height:1px;">&nbsp;</td></tr>'
'</table>'
'</td></tr>'
'</table>'
'</div>'
'<!--[if mso]></td><td>&nbsp;</td></tr></table><![endif]-->'
'</body>'
'</html>'
    )


def _send_email_sync(to_email, subject, html_content):
    """Send an HTML email via SendGrid HTTP API (synchronous)"""
    try:
        response = requests.post(
            'https://api.sendgrid.com/v3/mail/send',
            headers={
                'Authorization': f'Bearer {SENDGRID_API_KEY}',
                'Content-Type': 'application/json'
            },
            json={
                'personalizations': [{'to': [{'email': to_email}]}],
                'from': {'email': FROM_EMAIL.split('<')[-1].rstrip('>') if '<' in FROM_EMAIL else FROM_EMAIL,
                         'name': FROM_EMAIL.split('<')[0].strip() if '<' in FROM_EMAIL else 'WordPlayLeague'},
                'subject': subject,
                'content': [{'type': 'text/html', 'value': html_content}]
            },
            timeout=10
        )
        
        if response.status_code in (200, 202):
            logging.info(f"Email sent to {to_email}: {subject}")
        else:
            logging.error(f"SendGrid API error ({response.status_code}): {response.text}")
    except Exception as e:
        logging.error(f"Failed to send email to {to_email}: {e}")


def _send_email(to_email, subject, html_content):
    """Send an HTML email via SendGrid (non-blocking, runs in background thread)"""
    if not SENDGRID_API_KEY:
        logging.error("SENDGRID_API_KEY not set, cannot send email")
        return False
    
    thread = threading.Thread(target=_send_email_sync, args=(to_email, subject, html_content))
    thread.daemon = True
    thread.start()
    return True


def send_password_reset_email(to_email, reset_token, first_name=None):
    """Send a password reset email with a reset link"""
    reset_url = f"{APP_URL}/auth/reset-password?token={reset_token}"
    greeting = f"Hi {first_name}," if first_name else "Hi,"
    
    body = f"""
    <p style="color: #e0e0e0; line-height: 1.6;">{greeting}</p>
    <p style="color: #e0e0e0; line-height: 1.6;">We received a request to reset your password. Click the button below to create a new one:</p>
    <div style="text-align: center; margin: 30px 0;">
        <a href="{reset_url}" style="background: #00E8DA; color: #1a1a2e; padding: 14px 32px; border-radius: 8px; text-decoration: none; font-weight: bold; font-size: 1em; display: inline-block;">Reset Password</a>
    </div>
    <p style="color: #888; font-size: 0.85em; line-height: 1.5;">This link expires in 1 hour. If you didn't request this, you can safely ignore this email.</p>
    <p style="color: #666; font-size: 0.8em; word-break: break-all;">Or copy this link: {reset_url}</p>
    """
    
    html = _get_email_template("Reset Your Password", body)
    return _send_email(to_email, "Reset your WordPlayLeague password", html)


def send_verification_email(to_email, verify_token, first_name=None):
    """Send an email verification link to a new user"""
    verify_url = f"{APP_URL}/auth/verify-email?token={verify_token}"
    greeting = f"Welcome {first_name}!" if first_name else "Welcome!"
    
    body = f"""
    <p style="color: #e0e0e0; line-height: 1.6;">{greeting}</p>
    <p style="color: #e0e0e0; line-height: 1.6;">Thanks for signing up for WordPlayLeague! Please verify your email address to get started:</p>
    <div style="text-align: center; margin: 30px 0;">
        <a href="{verify_url}" style="background: #00E8DA; color: #1a1a2e; padding: 14px 32px; border-radius: 8px; text-decoration: none; font-weight: bold; font-size: 1em; display: inline-block;">Verify Email</a>
    </div>
    <p style="color: #888; font-size: 0.85em; line-height: 1.5;">This link expires in 24 hours.</p>
    <p style="color: #666; font-size: 0.8em; word-break: break-all;">Or copy this link: {verify_url}</p>
    """
    
    html = _get_email_template("Verify Your Email", body)
    return _send_email(to_email, "Verify your WordPlayLeague email", html)


def send_welcome_email(to_email, first_name=None):
    """Send a welcome email after a user verifies their email address"""
    greeting = f"Hey {first_name}!" if first_name else "Hey there!"
    dashboard_url = f"{APP_URL}/dashboard"
    
    body = f"""
    <p style="color: #e0e0e0; line-height: 1.6;">{greeting}</p>
    <p style="color: #e0e0e0; line-height: 1.6;">You're all set! Your email is verified and your WordPlayLeague account is ready to go. Here's a quick rundown of what you can do:</p>
    
    <table width="100%" cellpadding="0" cellspacing="0" style="margin: 20px 0;">
        <tr>
            <td style="padding: 12px 0; color: #e0e0e0; line-height: 1.6;">
                <span style="color: #00E8DA; font-weight: bold; font-size: 1.1em;">🏆 Create a League</span><br>
                <span style="color: #bbb; font-size: 0.95em;">Set up a league for your group in seconds. Works with SMS, Slack, or Discord.</span>
            </td>
        </tr>
        <tr>
            <td style="padding: 12px 0; color: #e0e0e0; line-height: 1.6;">
                <span style="color: #00E8DA; font-weight: bold; font-size: 1.1em;">📊 Automated Leaderboards</span><br>
                <span style="color: #bbb; font-size: 0.95em;">Scores are tracked automatically — weekly standings, season races, and all-time stats, all on your own league page.</span>
            </td>
        </tr>
        <tr>
            <td style="padding: 12px 0; color: #e0e0e0; line-height: 1.6;">
                <span style="color: #00E8DA; font-weight: bold; font-size: 1.1em;">🤖 AI-Powered Updates</span><br>
                <span style="color: #bbb; font-size: 0.95em;">Sunday race recaps, Monday morning wrap-ups, and fun roasts — delivered straight to your group chat.</span>
            </td>
        </tr>
        <tr>
            <td style="padding: 12px 0; color: #e0e0e0; line-height: 1.6;">
                <span style="color: #00E8DA; font-weight: bold; font-size: 1.1em;">🏅 Seasons & Division Mode</span><br>
                <span style="color: #bbb; font-size: 0.95em;">Compete across seasons with weekly wins. Larger groups can enable Division Mode for promotion/relegation.</span>
            </td>
        </tr>
    </table>
    
    <div style="text-align: center; margin: 30px 0;">
        <a href="{dashboard_url}" style="background: #00E8DA; color: #1a1a2e; padding: 14px 32px; border-radius: 8px; text-decoration: none; font-weight: bold; font-size: 1em; display: inline-block;">Go to Dashboard</a>
    </div>
    
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#1a1a2e" style="background-color: #1a1a2e; border-radius: 8px; margin-top: 20px; border-left: 3px solid #FFA64D;"><tr><td style="padding: 16px;">
        <p style="color: #FFA64D; font-weight: bold; margin: 0 0 6px;">🧪 Beta Notice</p>
        <p style="color: #999; font-size: 0.85em; margin: 0; line-height: 1.5;">WordPlayLeague is currently in beta and completely free to use while we fine-tune things. We'd love your feedback as we build — enjoy!</p>
    </td></tr></table>
    """
    
    html = _get_email_template("Welcome to WordPlayLeague!", body)
    return _send_email(to_email, "Welcome to WordPlayLeague! 🎉", html)


def send_league_created_email(to_email, first_name=None, league_name=None, league_slug=None, channel_type='sms'):
    """Send an informational email after a user creates a new league"""
    greeting = f"Hey {first_name}!" if first_name else "Hey there!"
    league_url = f"{APP_URL}/leagues/{league_slug}" if league_slug else f"{APP_URL}/dashboard"
    dashboard_url = f"{APP_URL}/dashboard"
    
    # Platform-specific activation steps
    if channel_type == 'slack':
        platform_name = "Slack"
        activation_steps = """
        <tr><td style="padding: 6px 0; color: #bbb; font-size: 0.95em;">1. Click <strong style="color: #e0e0e0;">"Connect Slack"</strong> on your league page</td></tr>
        <tr><td style="padding: 6px 0; color: #bbb; font-size: 0.95em;">2. Authorize WordPlayLeague in your Slack workspace</td></tr>
        <tr><td style="padding: 6px 0; color: #bbb; font-size: 0.95em;">3. Select the channel for your league</td></tr>
        <tr><td style="padding: 6px 0; color: #bbb; font-size: 0.95em;">4. Players share their Wordle results in that channel — we handle the rest!</td></tr>
        """
    elif channel_type == 'discord':
        platform_name = "Discord"
        activation_steps = """
        <tr><td style="padding: 6px 0; color: #bbb; font-size: 0.95em;">1. Click <strong style="color: #e0e0e0;">"Add to Discord"</strong> on your league page</td></tr>
        <tr><td style="padding: 6px 0; color: #bbb; font-size: 0.95em;">2. Add the WordPlayLeague bot to your server</td></tr>
        <tr><td style="padding: 6px 0; color: #bbb; font-size: 0.95em;">3. Select the channel for your league</td></tr>
        <tr><td style="padding: 6px 0; color: #bbb; font-size: 0.95em;">4. Players share their Wordle results in that channel — we handle the rest!</td></tr>
        """
    else:
        platform_name = "SMS"
        activation_steps = """
        <tr><td style="padding: 6px 0; color: #bbb; font-size: 0.95em;">1. Add the <strong style="color: #e0e0e0;">phone number</strong> shown on your league page to your group chat</td></tr>
        <tr><td style="padding: 6px 0; color: #bbb; font-size: 0.95em;">2. Add your players from the dashboard</td></tr>
        <tr><td style="padding: 6px 0; color: #bbb; font-size: 0.95em;">3. Players share their Wordle results in the group chat — we handle the rest!</td></tr>
        """
    
    league_display = f'<strong style="color: #00E8DA;">{league_name}</strong>' if league_name else "Your league"
    
    body = f"""
    <p style="color: #e0e0e0; line-height: 1.6;">{greeting}</p>
    <p style="color: #e0e0e0; line-height: 1.6;">Your new league {league_display} has been created! 🎉</p>
    
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#1a1a2e" style="background-color: #1a1a2e; border-radius: 8px; margin: 20px 0;"><tr><td style="padding: 16px;">
        <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
                <td style="color: #888; padding: 4px 0; width: 100px;">League</td>
                <td style="color: #e0e0e0; padding: 4px 0; font-weight: bold;">{league_name or 'New League'}</td>
            </tr>
            <tr>
                <td style="color: #888; padding: 4px 0;">Platform</td>
                <td style="color: #e0e0e0; padding: 4px 0;">{platform_name}</td>
            </tr>
            <tr>
                <td style="color: #888; padding: 4px 0;">Status</td>
                <td style="color: #FFA64D; padding: 4px 0; font-weight: bold;">⏳ Not Yet Activated</td>
            </tr>
            <tr>
                <td style="color: #888; padding: 4px 0;">League Page</td>
                <td style="padding: 4px 0;"><a href="{league_url}" style="color: #00E8DA; text-decoration: none;">{league_url}</a></td>
            </tr>
        </table>
    </td></tr></table>
    
    <p style="color: #00E8DA; font-weight: bold; font-size: 1.05em; margin-top: 24px;">📋 How to Activate</p>
    <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 20px;">
        {activation_steps}
    </table>
    
    <div style="text-align: center; margin: 30px 0;">
        <a href="{dashboard_url}" style="background: #00E8DA; color: #1a1a2e; padding: 14px 32px; border-radius: 8px; text-decoration: none; font-weight: bold; font-size: 1em; display: inline-block;">Go to League Dashboard</a>
    </div>
    
    <p style="color: #888; font-size: 0.85em; line-height: 1.5;">Once activated, scores will be tracked automatically and your league page will update in real time.</p>
    """
    
    subject = f"Your league \"{league_name}\" is ready!" if league_name else "Your new league is ready!"
    html = _get_email_template("League Created!", body)
    return _send_email(to_email, subject, html)


def send_admin_league_created_email(league_name, league_slug, channel_type, league_id, owner_name, owner_email):
    """Send admin notification when a new league is created"""
    from datetime import datetime
    
    league_url = f"{APP_URL}/leagues/{league_slug}" if league_slug else ""
    admin_url = f"{APP_URL}/admin"
    created_at = datetime.utcnow().strftime('%B %d, %Y at %I:%M %p UTC')
    
    platform_map = {'sms': 'SMS', 'slack': 'Slack', 'discord': 'Discord'}
    platform_name = platform_map.get(channel_type, channel_type)
    
    body = f"""
    <p style="color: #e0e0e0; line-height: 1.6;">A new league has been created on WordPlayLeague.</p>
    
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#1a1a2e" style="background-color: #1a1a2e; border-radius: 8px; margin: 20px 0;"><tr><td style="padding: 16px;">
        <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
                <td style="color: #888; padding: 6px 0; width: 120px;">League Name</td>
                <td style="color: #00E8DA; padding: 6px 0; font-weight: bold; font-size: 1.05em;">{league_name or 'N/A'}</td>
            </tr>
            <tr>
                <td style="color: #888; padding: 6px 0;">League ID</td>
                <td style="color: #e0e0e0; padding: 6px 0;">{league_id}</td>
            </tr>
            <tr>
                <td style="color: #888; padding: 6px 0;">Slug</td>
                <td style="color: #e0e0e0; padding: 6px 0; font-family: monospace;">{league_slug or 'N/A'}</td>
            </tr>
            <tr>
                <td style="color: #888; padding: 6px 0;">Platform</td>
                <td style="color: #e0e0e0; padding: 6px 0;">{platform_name}</td>
            </tr>
            <tr>
                <td style="color: #888; padding: 6px 0;">Status</td>
                <td style="color: #FFA64D; padding: 6px 0; font-weight: bold;">Not Yet Activated</td>
            </tr>
            <tr>
                <td style="color: #888; padding: 6px 0;">League Page</td>
                <td style="padding: 6px 0;"><a href="{league_url}" style="color: #00E8DA; text-decoration: none;">{league_url}</a></td>
            </tr>
        </table>
    </td></tr></table>
    
    <p style="color: #00E8DA; font-weight: bold; font-size: 1.05em; margin-top: 24px;">Created By</p>
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#1a1a2e" style="background-color: #1a1a2e; border-radius: 8px; margin: 10px 0 20px;"><tr><td style="padding: 16px;">
        <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
                <td style="color: #888; padding: 4px 0; width: 120px;">Name</td>
                <td style="color: #e0e0e0; padding: 4px 0; font-weight: bold;">{owner_name or 'N/A'}</td>
            </tr>
            <tr>
                <td style="color: #888; padding: 4px 0;">Email</td>
                <td style="padding: 4px 0;"><a href="mailto:{owner_email}" style="color: #00E8DA; text-decoration: none;">{owner_email or 'N/A'}</a></td>
            </tr>
            <tr>
                <td style="color: #888; padding: 4px 0;">Created</td>
                <td style="color: #e0e0e0; padding: 4px 0;">{created_at}</td>
            </tr>
        </table>
    </td></tr></table>
    
    <div style="text-align: center; margin: 30px 0;">
        <a href="{admin_url}" style="background: #00E8DA; color: #1a1a2e; padding: 14px 32px; border-radius: 8px; text-decoration: none; font-weight: bold; font-size: 1em; display: inline-block;">View in Admin Panel</a>
    </div>
    """
    
    subject = f"New League Created: {league_name}" if league_name else "New League Created"
    html = _get_email_template("New League Created", body)
    return _send_email(ADMIN_EMAIL, subject, html)


# ============================================================
# Newsletter / Feature Update Emails
# ============================================================

def get_all_newsletter_recipients():
    """Get all verified, active users who can receive newsletters"""
    try:
        from league_data_adapter import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT email, first_name FROM users
            WHERE is_active = TRUE AND (email_verified = TRUE OR email_verified IS NULL)
            ORDER BY email
        """)
        
        recipients = [{'email': row[0], 'first_name': row[1]} for row in cursor.fetchall()]
        cursor.close()
        conn.close()
        return recipients
    except Exception as e:
        logging.error(f"Error getting newsletter recipients: {e}")
        return []


def send_newsletter_single(to_email, first_name, subject, body_html):
    """Send a newsletter email to a single recipient (personalized greeting)"""
    greeting = f"Hey {first_name}!" if first_name else "Hey there!"
    
    personalized_body = f"""
    <p style="color: #e0e0e0; line-height: 1.6;">{greeting}</p>
    {body_html}
    
    <div style="border-top: 1px solid #333; margin-top: 30px; padding-top: 16px;">
        <p style="color: #666; font-size: 0.8em; margin: 0; line-height: 1.5;">
            You're receiving this because you have a WordPlayLeague account. 
            Questions or feedback? Reply to this email or reach us at {ADMIN_EMAIL}.
        </p>
    </div>
    """
    
    html = _get_email_template(subject, personalized_body)
    return _send_email_sync(to_email, subject, html)


def send_newsletter_to_all(subject, body_html):
    """Send a newsletter to all verified users. Returns count of emails sent."""
    recipients = get_all_newsletter_recipients()
    
    if not recipients:
        logging.warning("No newsletter recipients found")
        return 0
    
    sent_count = 0
    for recipient in recipients:
        try:
            send_newsletter_single(recipient['email'], recipient['first_name'], subject, body_html)
            sent_count += 1
        except Exception as e:
            logging.error(f"Failed to send newsletter to {recipient['email']}: {e}")
    
    logging.info(f"Newsletter sent to {sent_count}/{len(recipients)} recipients")
    return sent_count


def get_newsletter_templates():
    """Return available pre-built newsletter templates"""
    return {
        'division_mode': {
            'name': 'Division Mode Launch',
            'subject': 'New Feature: Division Mode is Here! 🏆',
            'body_html': _get_division_mode_newsletter_body()
        },
        'shared_leagues': {
            'name': 'Shared Leagues — Players Can Now View Their Leagues',
            'subject': 'New Feature: Your Players Can Now See Their Leagues! 🤝',
            'body_html': _get_shared_leagues_newsletter_body()
        }
    }


def _get_division_mode_newsletter_body():
    """Pre-built Division Mode feature announcement email body"""
    dashboard_url = f"{APP_URL}/dashboard"
    
    return f"""
    <p style="color: #e0e0e0; line-height: 1.6;">We've just shipped a major new feature — <strong style="color: #00E8DA;">Division Mode</strong>. If your league has 4+ players, you can now split into two competitive divisions with promotion, relegation, and independent season races.</p>
    
    <p style="color: #e0e0e0; line-height: 1.6;">Here's everything you need to know:</p>
    
    <!-- What is Division Mode -->
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#1a1a2e" style="background-color: #1a1a2e; border-radius: 10px; margin: 20px 0; border-left: 4px solid #00E8DA;"><tr><td style="padding: 20px;">
        <p style="color: #00E8DA; font-weight: bold; font-size: 1.1em; margin: 0 0 10px;">What is Division Mode?</p>
        <p style="color: #bbb; margin: 0; line-height: 1.6;">Division Mode splits your league into <strong style="color: #e0e0e0;">Division I</strong> and <strong style="color: #e0e0e0;">Division II</strong>. Each division runs its own weekly races and season standings independently. Win 3 weekly wins in your division to clinch the season — then promotion and relegation kick in.</p>
    </td></tr></table>
    
    <!-- How to Enable -->
    <p style="color: #00E8DA; font-weight: bold; font-size: 1.1em; margin-top: 28px;">📋 How to Enable</p>
    <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 20px;">
        <tr><td style="padding: 8px 0; color: #bbb; line-height: 1.6;">1. Go to your <strong style="color: #e0e0e0;">League Dashboard</strong> and find the <strong style="color: #e0e0e0;">Division Mode</strong> toggle in the Players section</td></tr>
        <tr><td style="padding: 8px 0; color: #bbb; line-height: 1.6;">2. Players are auto-split into two divisions — drag and drop to rearrange them however you'd like</td></tr>
        <tr><td style="padding: 8px 0; color: #bbb; line-height: 1.6;">3. Click <strong style="color: #e0e0e0;">Confirm Division Mode</strong> to publish the divisions to your league page</td></tr>
        <tr><td style="padding: 8px 0; color: #bbb; line-height: 1.6;">4. That's it — scores are automatically tracked per-division from that point on</td></tr>
    </table>
    
    <!-- Player Management -->
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#1a1a2e" style="background-color: #1a1a2e; border-radius: 10px; margin: 20px 0; border-left: 4px solid #FFA64D;"><tr><td style="padding: 20px;">
        <p style="color: #FFA64D; font-weight: bold; font-size: 1.05em; margin: 0 0 12px;">👥 Managing Players</p>
        <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
                <td style="padding: 8px 0; color: #bbb; line-height: 1.6;">
                    <strong style="color: #e0e0e0;">Moving Players Between Divisions</strong><br>
                    Before the first weekly race completes, you can freely drag players between Division I and Division II. Use the <em>Edit Divisions</em> button to enter rearrange mode.
                </td>
            </tr>
            <tr>
                <td style="padding: 8px 0; color: #bbb; line-height: 1.6;">
                    <strong style="color: #e0e0e0;">Locking After a Week Completes</strong><br>
                    Once the first week finishes with weekly winners recorded in both divisions, player positions are <strong style="color: #ff5c5c;">locked</strong>. This prevents mid-season disruptions to standings.
                </td>
            </tr>
            <tr>
                <td style="padding: 8px 0; color: #bbb; line-height: 1.6;">
                    <strong style="color: #e0e0e0;">Unlocking via Season Reset</strong><br>
                    Need to rearrange after locking? Use <em>Reset Season</em> to unlock divisions. This wipes the current season's in-progress weekly wins and advances to a new season, allowing you to move players again. All completed season winners are preserved.
                </td>
            </tr>
            <tr>
                <td style="padding: 8px 0; color: #bbb; line-height: 1.6;">
                    <strong style="color: #e0e0e0;">Adding New Players Mid-Season</strong><br>
                    New players can be added to either division at any time. They'll join mid-season and start accumulating scores immediately.
                </td>
            </tr>
        </table>
    </td></tr></table>
    
    <!-- Seasons & Promotion/Relegation -->
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#1a1a2e" style="background-color: #1a1a2e; border-radius: 10px; margin: 20px 0; border-left: 4px solid #00E8DA;"><tr><td style="padding: 20px;">
        <p style="color: #00E8DA; font-weight: bold; font-size: 1.05em; margin: 0 0 12px;">🏅 Seasons, Promotion & Relegation</p>
        <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
                <td style="padding: 8px 0; color: #bbb; line-height: 1.6;">
                    <strong style="color: #e0e0e0;">Winning a Season</strong><br>
                    The first player to reach <strong style="color: #00E8DA;">3 weekly wins</strong> in their division clinches the season. Each division tracks its own season race independently.
                </td>
            </tr>
            <tr>
                <td style="padding: 8px 0; color: #bbb; line-height: 1.6;">
                    <strong style="color: #e0e0e0;">Promotion (Division II → Division I)</strong><br>
                    The Division II season winner gets <strong style="color: #2ECC71;">promoted</strong> to Division I for the next season. They also receive immunity from relegation for that first season.
                </td>
            </tr>
            <tr>
                <td style="padding: 8px 0; color: #bbb; line-height: 1.6;">
                    <strong style="color: #e0e0e0;">Relegation (Division I → Division II)</strong><br>
                    When someone gets promoted to Division I, the worst-performing Division I player gets <strong style="color: #ff5c5c;">relegated</strong> to Division II. Relegation considers missed weeks first (players who miss weeks are relegated before those who don't), then worst season total as a tiebreaker.
                </td>
            </tr>
            <tr>
                <td style="padding: 8px 0; color: #bbb; line-height: 1.6;">
                    <strong style="color: #e0e0e0;">Immunity for Promoted Players</strong><br>
                    Newly promoted players are protected from immediate relegation during their first season in Division I. The season winner is also exempt from relegation.
                </td>
            </tr>
        </table>
    </td></tr></table>
    
    <!-- Leaderboard -->
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#1a1a2e" style="background-color: #1a1a2e; border-radius: 10px; margin: 20px 0; border-left: 4px solid #FFA64D;"><tr><td style="padding: 20px;">
        <p style="color: #FFA64D; font-weight: bold; font-size: 1.05em; margin: 0 0 8px;">📊 What Changes on Your League Page</p>
        <p style="color: #bbb; margin: 0; line-height: 1.6;">Your public league page will show separate tables for each division — weekly standings, season races, and promotion/relegation badges. AI-powered Sunday race updates and Monday recaps are also division-aware.</p>
    </td></tr></table>
    
    <div style="text-align: center; margin: 30px 0;">
        <a href="{dashboard_url}" style="background: #00E8DA; color: #1a1a2e; padding: 14px 32px; border-radius: 8px; text-decoration: none; font-weight: bold; font-size: 1em; display: inline-block;">Go to Dashboard</a>
    </div>
    
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#1a1a2e" style="background-color: #1a1a2e; border-radius: 8px; margin-top: 20px; border-left: 3px solid #FFA64D;"><tr><td style="padding: 16px;">
        <p style="color: #FFA64D; font-weight: bold; margin: 0 0 6px;">🧪 Beta Reminder</p>
        <p style="color: #999; font-size: 0.85em; margin: 0; line-height: 1.5;">WordPlayLeague is in beta and completely free while we continue building. We'd love to hear what you think of Division Mode — just reply to this email with any feedback!</p>
    </td></tr></table>
    """


def _get_shared_leagues_newsletter_body():
    """Pre-built Shared Leagues feature announcement email body"""
    dashboard_url = f"{APP_URL}/dashboard"
    signup_url = f"{APP_URL}/auth/register"
    
    return f"""
    <p style="color: #e0e0e0; line-height: 1.6;">We just launched a new feature — <strong style="color: #00E8DA;">Shared Leagues</strong>. Now you can see every league you're part of, all in one place on your dashboard.</p>
    
    <p style="color: #e0e0e0; line-height: 1.6;">Here's what's new:</p>
    
    <!-- How It Works -->
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#1a1a2e" style="background-color: #1a1a2e; border-radius: 10px; margin: 20px 0; border-left: 4px solid #00E8DA;"><tr><td style="padding: 20px;">
        <p style="color: #00E8DA; font-weight: bold; font-size: 1.1em; margin: 0 0 10px;">How It Works</p>
        <p style="color: #bbb; margin: 0; line-height: 1.6;">Add your phone number to your profile, and our system automatically matches it to any active league you're playing in. Those leagues appear in a new <strong style="color: #00E8DA;">Shared Leagues</strong> section on your dashboard — no invites or codes needed. It just works.</p>
    </td></tr></table>
    
    <!-- Steps -->
    <p style="color: #00E8DA; font-weight: bold; font-size: 1.1em; margin-top: 28px;">📋 Get Started</p>
    <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 20px;">
        <tr><td style="padding: 8px 0; color: #bbb; line-height: 1.6;">1. Log in or create a free account at <a href="{signup_url}" style="color: #00E8DA; text-decoration: underline;">wordplayleague.com</a></td></tr>
        <tr><td style="padding: 8px 0; color: #bbb; line-height: 1.6;">2. Go to <strong style="color: #e0e0e0;">Profile</strong> and add the phone number you use in your league</td></tr>
        <tr><td style="padding: 8px 0; color: #bbb; line-height: 1.6;">3. Head back to the <strong style="color: #e0e0e0;">Dashboard</strong> — any leagues you're in will appear under <strong style="color: #00E8DA;">Shared Leagues</strong></td></tr>
        <tr><td style="padding: 8px 0; color: #bbb; line-height: 1.6;">4. Click <strong style="color: #e0e0e0;">View</strong> for quick access to your league's standings, scores, and season history</td></tr>
    </table>
    
    <!-- What You See -->
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#1a1a2e" style="background-color: #1a1a2e; border-radius: 10px; margin: 20px 0; border-left: 4px solid #FFA64D;"><tr><td style="padding: 20px;">
        <p style="color: #FFA64D; font-weight: bold; font-size: 1.05em; margin: 0 0 12px;">👀 What You'll See</p>
        <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
                <td style="padding: 8px 0; color: #bbb; line-height: 1.6;">
                    <strong style="color: #e0e0e0;">Your Leagues at a Glance</strong><br>
                    Each shared league card shows the league name and the player name you're matched to.
                </td>
            </tr>
            <tr>
                <td style="padding: 8px 0; color: #bbb; line-height: 1.6;">
                    <strong style="color: #e0e0e0;">One-Click Access</strong><br>
                    Hit View to jump straight to your league page with standings, scores, season winners, and more.
                </td>
            </tr>
            <tr>
                <td style="padding: 8px 0; color: #bbb; line-height: 1.6;">
                    <strong style="color: #e0e0e0;">Fully Automatic</strong><br>
                    Join a new league in the future? It shows up on your dashboard automatically — no extra steps.
                </td>
            </tr>
        </table>
    </td></tr></table>
    
    <!-- For League Managers -->
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#1a1a2e" style="background-color: #1a1a2e; border-radius: 10px; margin: 20px 0; border-left: 4px solid #00E8DA;"><tr><td style="padding: 20px;">
        <p style="color: #00E8DA; font-weight: bold; font-size: 1.05em; margin: 0 0 8px;">� League Managers — Spread the Word</p>
        <p style="color: #bbb; margin: 0; line-height: 1.6;">Let the players in your leagues know they can create an account and add their phone number to see their leagues on their own dashboard. Everything stays <strong style="color: #e0e0e0;">read-only</strong> for players — league settings and management are still fully in your control.</p>
    </td></tr></table>
    
    <div style="text-align: center; margin: 30px 0;">
        <a href="{dashboard_url}" style="background: #00E8DA; color: #1a1a2e; padding: 14px 32px; border-radius: 8px; text-decoration: none; font-weight: bold; font-size: 1em; display: inline-block;">Go to Dashboard</a>
    </div>
    
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#1a1a2e" style="background-color: #1a1a2e; border-radius: 8px; margin-top: 20px; border-left: 3px solid #FFA64D;"><tr><td style="padding: 16px;">
        <p style="color: #FFA64D; font-weight: bold; margin: 0 0 6px;">🧪 Beta Reminder</p>
        <p style="color: #999; font-size: 0.85em; margin: 0; line-height: 1.5;">WordPlayLeague is in beta and completely free while we continue building. Spread the word and tell your friends to create a league — we'd love your feedback! Just reply to this email anytime.</p>
    </td></tr></table>
    """
