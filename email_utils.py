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

def _get_email_template(title, body_html):
    """Wrap content in a branded HTML email template"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
    </head>
    <body style="margin: 0; padding: 0; background-color: #1a1a2e; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
        <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #1a1a2e; padding: 40px 20px;">
            <tr>
                <td align="center">
                    <table width="100%" cellpadding="0" cellspacing="0" style="max-width: 500px; background-color: #16213e; border-radius: 12px; border: 1px solid #333;">
                        <tr>
                            <td style="padding: 30px 30px 20px; text-align: center; border-bottom: 1px solid #333;">
                                <span style="font-size: 1.5em; font-weight: bold; color: #00E8DA;">WordPlay<span style="color: #FFA64D;">League.com</span></span>
                            </td>
                        </tr>
                        <tr>
                            <td style="padding: 30px;">
                                <h2 style="color: #00E8DA; margin: 0 0 20px; font-size: 1.3em;">{title}</h2>
                                {body_html}
                            </td>
                        </tr>
                        <tr>
                            <td style="padding: 20px 30px; text-align: center; border-top: 1px solid #333; color: #888; font-size: 0.8em;">
                                &copy; WordPlayLeague.com
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """


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
    
    <div style="background: #1a1a2e; border-radius: 8px; padding: 16px; margin-top: 20px; border-left: 3px solid #FFA64D;">
        <p style="color: #FFA64D; font-weight: bold; margin: 0 0 6px;">🧪 Beta Notice</p>
        <p style="color: #999; font-size: 0.85em; margin: 0; line-height: 1.5;">WordPlayLeague is currently in beta and completely free to use while we fine-tune things. We'd love your feedback as we build — enjoy!</p>
    </div>
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
    
    <div style="background: #1a1a2e; border-radius: 8px; padding: 16px; margin: 20px 0;">
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
    </div>
    
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
