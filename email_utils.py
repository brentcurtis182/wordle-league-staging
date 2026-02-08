#!/usr/bin/env python3
"""
Email utility for Wordle League
Sends branded HTML emails via Gmail SMTP for password resets and email verification
"""

import os
import logging
import smtplib
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

GMAIL_USER = os.environ.get('GMAIL_USER', 'wordplayleague@gmail.com')
GMAIL_APP_PASSWORD = os.environ.get('GMAIL_APP_PASSWORD', '')
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
                                &copy; WordPlayLeague.com &mdash; Wordle, but make it competitive.
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
    """Send an HTML email via Gmail SMTP (synchronous)"""
    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = f'WordPlayLeague <{GMAIL_USER}>'
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(html_content, 'html'))
        
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=10) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_USER, to_email, msg.as_string())
        
        logging.info(f"Email sent to {to_email}: {subject}")
    except Exception as e:
        logging.error(f"Failed to send email to {to_email}: {e}")


def _send_email(to_email, subject, html_content):
    """Send an HTML email via Gmail SMTP (non-blocking, runs in background thread)"""
    if not GMAIL_APP_PASSWORD:
        logging.error("GMAIL_APP_PASSWORD not set, cannot send email")
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
