#!/usr/bin/env python3
"""
Dashboard and League Management UI for Wordle League
"""

import os
import logging
from flask import Blueprint, request, jsonify, redirect, make_response
from auth import login_required, can_manage_league, get_user_leagues, validate_session
from league_data_adapter import get_db_connection

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

dashboard_bp = Blueprint('dashboard', __name__)

# Color scheme matching the site
COLORS = {
    'bg_dark': '#1a1a1b',
    'bg_card': '#272729',
    'accent': '#00E8DA',
    'accent_orange': '#FFA64D',
    'text': '#d7dadc',
    'text_muted': '#818384',
    'success': '#4CAF50',
    'error': '#f44336',
    'border': '#333',
}

def get_base_styles():
    """Return base CSS styles for all dashboard pages"""
    return f"""
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        html, body {{
            overflow-x: hidden;
            width: 100%;
            position: relative;
        }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: {COLORS['bg_dark']};
            color: {COLORS['text']};
            min-height: 100vh;
        }}
        .container {{
            max-width: 1000px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            padding: 20px 0;
            border-bottom: 1px solid #333;
            margin-bottom: 30px;
        }}
        .header-logo-row {{
            text-align: center;
            margin-bottom: 12px;
        }}
        .header-nav-row {{
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .logo {{
            font-size: 1.5em;
            font-weight: bold;
            color: {COLORS['accent']};
        }}
        .logo .orange {{ color: #FFA64D; }}
        .header-logo {{
            height: 50px;
            width: auto;
        }}
        .logo-header {{
            text-align: center;
            margin-bottom: 10px;
        }}
        .logo-img {{
            height: 120px;
            width: auto;
        }}
        .nav-link {{
            color: {COLORS['text']};
            text-decoration: none;
            padding: 8px 16px;
            border-radius: 6px;
            transition: background 0.2s;
            font-size: 0.95em;
        }}
        .nav-link:hover {{ background: {COLORS['bg_card']}; }}
        .nav-link.logout {{ color: {COLORS['accent_orange']}; }}
        .back-link {{
            color: {COLORS['accent']};
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 20px;
        }}
        .back-link:hover {{ text-decoration: underline; }}
        .card {{
            background: {COLORS['bg_card']};
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 20px;
            border: 1px solid #333;
        }}
        .card h2 {{
            color: {COLORS['accent']};
            margin-bottom: 16px;
            font-size: 1.3em;
        }}
        .btn {{
            display: inline-block;
            padding: 12px 24px;
            border-radius: 8px;
            border: none;
            cursor: pointer;
            font-size: 1em;
            font-weight: 600;
            text-decoration: none;
            transition: all 0.2s;
        }}
        .btn-primary {{
            background: {COLORS['accent']};
            color: {COLORS['bg_dark']};
        }}
        .btn-primary:hover {{ background: #00c4b8; }}
        .btn-secondary {{
            background: transparent;
            color: {COLORS['accent']};
            border: 2px solid {COLORS['accent']};
        }}
        .btn-secondary:hover {{ background: rgba(0, 232, 218, 0.1); }}
        .btn-danger {{
            background: {COLORS['error']};
            color: white;
        }}
        .btn-danger:hover {{ background: #d32f2f; }}
        .btn-small {{
            padding: 8px 16px;
            font-size: 0.9em;
        }}
        .form-group {{
            margin-bottom: 20px;
        }}
        .form-group label {{
            display: block;
            margin-bottom: 8px;
            color: {COLORS['text_muted']};
            font-size: 0.9em;
        }}
        .form-group input, .form-group select {{
            width: 100%;
            padding: 12px 16px;
            border-radius: 8px;
            border: 1px solid #444;
            background: {COLORS['bg_dark']};
            color: {COLORS['text']};
            font-size: 1em;
        }}
        .form-group input:focus {{
            outline: none;
            border-color: {COLORS['accent']};
        }}
        .league-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 20px;
        }}
        .league-card {{
            background: {COLORS['bg_card']};
            border-radius: 12px;
            padding: 20px;
            border: 2px solid {COLORS['accent']};
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        .league-card:hover {{ 
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0, 232, 218, 0.2);
        }}
        .league-card h3 {{
            color: {COLORS['accent']};
            margin-bottom: 8px;
        }}
        .league-card .meta {{
            color: {COLORS['text_muted']};
            font-size: 0.9em;
            margin-bottom: 16px;
        }}
        .league-card .actions {{
            display: flex;
            gap: 10px;
        }}
        .player-list {{
            list-style: none;
        }}
        .player-item {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 16px;
            background: {COLORS['bg_dark']};
            border-radius: 8px;
            margin-bottom: 8px;
        }}
        .player-item .name {{ font-weight: 500; }}
        .player-item .phone {{ color: {COLORS['text_muted']}; font-size: 0.9em; }}
        .alert {{
            padding: 16px 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            transition: opacity 0.5s ease;
        }}
        .alert.fade-out {{
            opacity: 0;
        }}
        .alert-success {{ background: rgba(76, 175, 80, 0.2); border: 1px solid {COLORS['success']}; }}
        .alert-error {{ background: rgba(244, 67, 54, 0.2); border: 1px solid {COLORS['error']}; }}
        .tabs {{
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            border-bottom: 1px solid #333;
            padding-bottom: 10px;
        }}
        .tab {{
            padding: 10px 20px;
            background: transparent;
            border: none;
            color: {COLORS['text_muted']};
            cursor: pointer;
            border-radius: 6px 6px 0 0;
            font-size: 1em;
        }}
        .tab.active {{
            color: {COLORS['accent']};
            background: {COLORS['bg_card']};
        }}
        .tab:hover {{ color: {COLORS['text']}; }}
        .modal-overlay {{
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.7);
            z-index: 1000;
            align-items: center;
            justify-content: center;
        }}
        .modal {{
            background: {COLORS['bg_card']};
            border-radius: 12px;
            padding: 30px;
            max-width: 500px;
            width: 90%;
        }}
        .modal h2 {{ margin-bottom: 20px; }}
    """


def render_login_page(error=None, success=None):
    """Render the login page"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Login - WordPlayLeague.com</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            {get_base_styles()}
            .auth-container {{
                max-width: 450px;
                margin: 80px auto;
                padding: 20px;
            }}
            .auth-card {{
                background: {COLORS['bg_card']};
                border-radius: 16px;
                padding: 40px 20px;
                border: 1px solid #333;
            }}
            .auth-card h1 {{
                text-align: center;
                margin-bottom: 8px;
                color: {COLORS['accent']};
                font-size: clamp(1.4rem, 5vw, 2rem);
                white-space: nowrap;
            }}
            .auth-card .subtitle {{
                text-align: center;
                color: {COLORS['text_muted']};
                margin-bottom: 30px;
            }}
            .auth-footer {{
                text-align: center;
                margin-top: 20px;
                color: {COLORS['text_muted']};
            }}
            .auth-footer a {{ color: {COLORS['accent']}; }}
            .orange {{ color: {COLORS['accent_orange']}; }}
            @media (max-width: 400px) {{
                .auth-card h1 {{ font-size: 1.3rem; }}
                .auth-card {{ padding: 30px 16px; }}
            }}
        </style>
    </head>
    <body>
        <div class="auth-container">
            <div class="auth-card">
                <h1><a href="https://www.wordplayleague.com" style="text-decoration: none; color: inherit;">WordPlay<span class="orange">League.com</span></a></h1>
                <p class="subtitle">Sign in to manage your leagues</p>
                
                {'<div class="alert alert-error">' + error + '</div>' if error else ''}
                {'<div class="alert alert-success">' + success + '</div>' if success else ''}
                
                <a href="/auth/google" style="display: flex; align-items: center; justify-content: center; gap: 10px; width: 100%; padding: 12px; background: #fff; color: #333; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 1em; border: 1px solid #ddd; box-sizing: border-box; margin-bottom: 20px;">
                    <svg width="20" height="20" viewBox="0 0 48 48"><path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/><path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/><path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/><path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/></svg>
                    Sign in with Google
                </a>
                
                <div style="display: flex; align-items: center; margin-bottom: 20px;">
                    <div style="flex: 1; height: 1px; background: #333;"></div>
                    <span style="padding: 0 12px; color: {COLORS['text_muted']}; font-size: 0.85em;">or</span>
                    <div style="flex: 1; height: 1px; background: #333;"></div>
                </div>
                
                <form method="POST" action="/auth/login">
                    <div class="form-group">
                        <label>Email</label>
                        <input type="email" name="email" required placeholder="you@example.com">
                    </div>
                    <div class="form-group">
                        <label>Password</label>
                        <input type="password" name="password" required placeholder="••••••••">
                    </div>
                    <button type="submit" class="btn btn-primary" style="width: 100%;">Sign In</button>
                </form>
                
                <div style="text-align: center; margin-top: 16px;">
                    <a href="/auth/forgot-password" style="color: {COLORS['text_muted']}; font-size: 0.9em;">Forgot Password?</a>
                </div>
                
                <div class="auth-footer">
                    Don't have an account? <a href="/auth/register">Sign up</a>
                </div>
            </div>
        </div>
    </body>
    </html>
    """


def render_forgot_password_page(error=None, success=None):
    """Render the forgot password page"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Forgot Password - WordPlayLeague.com</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            {get_base_styles()}
            .auth-container {{
                max-width: 450px;
                margin: 80px auto;
                padding: 20px;
            }}
            .auth-card {{
                background: {COLORS['bg_card']};
                border-radius: 16px;
                padding: 40px 20px;
                border: 1px solid #333;
            }}
            .auth-card h1 {{
                text-align: center;
                margin-bottom: 8px;
                color: {COLORS['accent']};
                font-size: clamp(1.4rem, 5vw, 2rem);
                white-space: nowrap;
            }}
            .auth-card .subtitle {{
                text-align: center;
                color: {COLORS['text_muted']};
                margin-bottom: 30px;
            }}
            .auth-footer {{
                text-align: center;
                margin-top: 20px;
                color: {COLORS['text_muted']};
            }}
            .auth-footer a {{ color: {COLORS['accent']}; }}
            .orange {{ color: {COLORS['accent_orange']}; }}
        </style>
    </head>
    <body>
        <div class="auth-container">
            <div class="auth-card">
                <h1><a href="https://www.wordplayleague.com" style="text-decoration: none; color: inherit;">WordPlay<span class="orange">League.com</span></a></h1>
                <p class="subtitle">Reset your password</p>
                
                {'<div class="alert alert-error">' + error + '</div>' if error else ''}
                {'<div class="alert alert-success">' + success + '</div>' if success else ''}
                
                <p style="color: {COLORS['text_muted']}; font-size: 0.9em; margin-bottom: 20px; text-align: center;">Enter your email and we'll send you a link to reset your password.</p>
                
                <form method="POST" action="/auth/forgot-password">
                    <div class="form-group">
                        <label>Email</label>
                        <input type="email" name="email" required placeholder="you@example.com">
                    </div>
                    <button type="submit" class="btn btn-primary" style="width: 100%;">Send Reset Link</button>
                </form>
                
                <div class="auth-footer">
                    <a href="/auth/login">← Back to Login</a>
                </div>
            </div>
        </div>
    </body>
    </html>
    """


def render_reset_password_page(token, email=None, error=None, success=None):
    """Render the reset password form"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Reset Password - WordPlayLeague.com</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            {get_base_styles()}
            .auth-container {{
                max-width: 450px;
                margin: 80px auto;
                padding: 20px;
            }}
            .auth-card {{
                background: {COLORS['bg_card']};
                border-radius: 16px;
                padding: 40px 20px;
                border: 1px solid #333;
            }}
            .auth-card h1 {{
                text-align: center;
                margin-bottom: 8px;
                color: {COLORS['accent']};
                font-size: clamp(1.4rem, 5vw, 2rem);
                white-space: nowrap;
            }}
            .auth-card .subtitle {{
                text-align: center;
                color: {COLORS['text_muted']};
                margin-bottom: 30px;
            }}
            .auth-footer {{
                text-align: center;
                margin-top: 20px;
                color: {COLORS['text_muted']};
            }}
            .auth-footer a {{ color: {COLORS['accent']}; }}
            .orange {{ color: {COLORS['accent_orange']}; }}
        </style>
    </head>
    <body>
        <div class="auth-container">
            <div class="auth-card">
                <h1><a href="https://www.wordplayleague.com" style="text-decoration: none; color: inherit;">WordPlay<span class="orange">League.com</span></a></h1>
                <p class="subtitle">Create a new password</p>
                
                {'<div class="alert alert-error">' + error + '</div>' if error else ''}
                {'<div class="alert alert-success">' + success + '</div>' if success else ''}
                
                {f'<p style="color: {COLORS["text_muted"]}; font-size: 0.9em; margin-bottom: 20px; text-align: center;">Resetting password for <strong style="color: {COLORS["text"]};">{email}</strong></p>' if email else ''}
                
                <form method="POST" action="/auth/reset-password">
                    <input type="hidden" name="token" value="{token}">
                    <div class="form-group">
                        <label>New Password</label>
                        <input type="password" name="new_password" required placeholder="At least 8 characters" minlength="8">
                    </div>
                    <div class="form-group">
                        <label>Confirm New Password</label>
                        <input type="password" name="confirm_password" required placeholder="Confirm password">
                    </div>
                    <button type="submit" class="btn btn-primary" style="width: 100%;">Reset Password</button>
                </form>
                
                <div class="auth-footer">
                    <a href="/auth/login">← Back to Login</a>
                </div>
            </div>
        </div>
    </body>
    </html>
    """


def render_verify_email_page(success=False, error=None):
    """Render the email verification result page"""
    if success:
        message_html = f"""
            <div style="text-align: center;">
                <div style="font-size: 3em; margin-bottom: 16px;">✅</div>
                <h2 style="color: {COLORS['success']}; margin-bottom: 12px;">Email Verified!</h2>
                <p style="color: {COLORS['text_muted']}; margin-bottom: 24px;">Your email has been verified. You can now sign in.</p>
                <a href="/auth/login" class="btn btn-primary" style="display: inline-block; text-decoration: none;">Sign In</a>
            </div>
        """
    else:
        message_html = f"""
            <div style="text-align: center;">
                <div style="font-size: 3em; margin-bottom: 16px;">❌</div>
                <h2 style="color: {COLORS['error']}; margin-bottom: 12px;">Verification Failed</h2>
                <p style="color: {COLORS['text_muted']}; margin-bottom: 24px;">{error or 'Invalid or expired verification link.'}</p>
                <a href="/auth/login" class="btn btn-secondary" style="display: inline-block; text-decoration: none;">Back to Login</a>
            </div>
        """
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Email Verification - WordPlayLeague.com</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            {get_base_styles()}
            .auth-container {{
                max-width: 450px;
                margin: 80px auto;
                padding: 20px;
            }}
            .auth-card {{
                background: {COLORS['bg_card']};
                border-radius: 16px;
                padding: 40px 20px;
                border: 1px solid #333;
            }}
            .auth-card h1 {{
                text-align: center;
                margin-bottom: 24px;
                color: {COLORS['accent']};
                font-size: clamp(1.4rem, 5vw, 2rem);
                white-space: nowrap;
            }}
            .orange {{ color: {COLORS['accent_orange']}; }}
        </style>
    </head>
    <body>
        <div class="auth-container">
            <div class="auth-card">
                <h1><a href="https://www.wordplayleague.com" style="text-decoration: none; color: inherit;">WordPlay<span class="orange">League.com</span></a></h1>
                {message_html}
            </div>
        </div>
    </body>
    </html>
    """


def render_unverified_email_page(email):
    """Render page shown when user tries to login with unverified email"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Verify Email - WordPlayLeague.com</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            {get_base_styles()}
            .auth-container {{
                max-width: 450px;
                margin: 80px auto;
                padding: 20px;
            }}
            .auth-card {{
                background: {COLORS['bg_card']};
                border-radius: 16px;
                padding: 40px 20px;
                border: 1px solid #333;
            }}
            .auth-card h1 {{
                text-align: center;
                margin-bottom: 8px;
                color: {COLORS['accent']};
                font-size: clamp(1.4rem, 5vw, 2rem);
                white-space: nowrap;
            }}
            .orange {{ color: {COLORS['accent_orange']}; }}
            .auth-footer {{
                text-align: center;
                margin-top: 20px;
                color: {COLORS['text_muted']};
            }}
            .auth-footer a {{ color: {COLORS['accent']}; }}
        </style>
    </head>
    <body>
        <div class="auth-container">
            <div class="auth-card">
                <h1><a href="https://www.wordplayleague.com" style="text-decoration: none; color: inherit;">WordPlay<span class="orange">League.com</span></a></h1>
                
                <div style="text-align: center;">
                    <div style="font-size: 3em; margin-bottom: 16px;">📧</div>
                    <h2 style="color: {COLORS['accent_orange']}; margin-bottom: 12px;">Email Not Verified</h2>
                    <p style="color: {COLORS['text_muted']}; margin-bottom: 8px;">Please check your inbox for a verification email.</p>
                    <p style="color: {COLORS['text_muted']}; margin-bottom: 24px; font-size: 0.9em;">Sent to: <strong style="color: {COLORS['text']};">{email}</strong></p>
                    
                    <form method="POST" action="/auth/resend-verification" style="margin-bottom: 16px;">
                        <input type="hidden" name="email" value="{email}">
                        <button type="submit" class="btn btn-primary" style="width: 100%;">Resend Verification Email</button>
                    </form>
                </div>
                
                <div class="auth-footer">
                    <a href="/auth/login">← Back to Login</a>
                </div>
            </div>
        </div>
    </body>
    </html>
    """


def render_register_page(error=None):
    """Render the registration page with Twilio compliance fields"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Sign Up - WordPlayLeague.com</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            {get_base_styles()}
            .auth-container {{
                max-width: 480px;
                margin: 40px auto;
                padding: 20px;
            }}
            .auth-card {{
                background: {COLORS['bg_card']};
                border-radius: 16px;
                padding: 40px 20px;
                border: 1px solid #333;
            }}
            .auth-card h1 {{
                text-align: center;
                margin-bottom: 8px;
                color: {COLORS['accent']};
                font-size: clamp(1.4rem, 5vw, 2rem);
                white-space: nowrap;
            }}
            @media (max-width: 400px) {{
                .auth-card h1 {{ font-size: 1.3rem; }}
                .auth-card {{ padding: 30px 16px; }}
            }}
            .auth-card .subtitle {{
                text-align: center;
                color: {COLORS['text_muted']};
                margin-bottom: 30px;
            }}
            .auth-footer {{
                text-align: center;
                margin-top: 20px;
                color: {COLORS['text_muted']};
            }}
            .auth-footer a {{ color: {COLORS['accent']}; }}
            .name-row {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 16px;
            }}
            .consent-group {{
                margin: 24px 0;
                padding: 16px;
                background: {COLORS['bg_dark']};
                border-radius: 8px;
                border: 1px solid #333;
            }}
            .consent-group .legal-text {{
                font-size: 0.85em;
                color: {COLORS['text_muted']};
                line-height: 1.5;
                margin-bottom: 16px;
            }}
            .consent-group .legal-text a {{
                color: {COLORS['accent']};
            }}
            .checkbox-wrapper {{
                display: flex;
                align-items: flex-start;
                gap: 12px;
            }}
            .checkbox-wrapper input[type="checkbox"] {{
                width: 20px;
                height: 20px;
                margin-top: 2px;
                accent-color: {COLORS['accent']};
            }}
            .checkbox-wrapper label {{
                font-size: 0.9em;
                color: {COLORS['text']};
                line-height: 1.4;
                cursor: pointer;
            }}
            .orange {{ color: {COLORS['accent_orange']}; }}
        </style>
    </head>
    <body>
        <div class="auth-container">
            <div class="auth-card">
                <h1><a href="https://www.wordplayleague.com" style="text-decoration: none; color: inherit;">WordPlay<span class="orange">League.com</span></a></h1>
                <p class="subtitle">Sign Up</p>
                
                {'<div class="alert alert-error">' + error + '</div>' if error else ''}
                
                <a href="/auth/google" style="display: flex; align-items: center; justify-content: center; gap: 10px; width: 100%; padding: 12px; background: #fff; color: #333; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 1em; border: 1px solid #ddd; box-sizing: border-box; margin-bottom: 20px;">
                    <svg width="20" height="20" viewBox="0 0 48 48"><path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/><path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/><path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/><path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/></svg>
                    Sign up with Google
                </a>
                
                <div style="display: flex; align-items: center; margin-bottom: 20px;">
                    <div style="flex: 1; height: 1px; background: #333;"></div>
                    <span style="padding: 0 12px; color: {COLORS['text_muted']}; font-size: 0.85em;">or</span>
                    <div style="flex: 1; height: 1px; background: #333;"></div>
                </div>
                
                <form method="POST" action="/auth/register">
                    <div class="name-row">
                        <div class="form-group">
                            <label>First Name</label>
                            <input type="text" name="first_name" required placeholder="First name">
                        </div>
                        <div class="form-group">
                            <label>Last Name</label>
                            <input type="text" name="last_name" required placeholder="Last name">
                        </div>
                    </div>
                    <div class="form-group">
                        <label>Email</label>
                        <input type="email" name="email" required placeholder="you@example.com">
                    </div>
                    <div class="form-group">
                        <label>Password</label>
                        <input type="password" name="password" required placeholder="••••••••" minlength="8">
                    </div>
                    <div class="form-group">
                        <label>Confirm Password</label>
                        <input type="password" name="confirm_password" required placeholder="••••••••">
                    </div>
                    <div class="form-group">
                        <label>Phone</label>
                        <input type="tel" name="phone" placeholder="(858) 555-1234">
                    </div>
                    
                    <div class="consent-group">
                        <p class="legal-text">
                            By providing your mobile phone number and creating an account, you agree to receive 
                            automated text messages from Wordplay League at the number you provide. These messages 
                            may include score confirmations, league standings, and other information related to your 
                            Wordplay League participation. Message and data rates may apply. Reply STOP to cancel, 
                            HELP for help. See our <a href="https://www.wordplayleague.com/sms-terms" target="_blank">Text Messaging Terms</a> and <a href="https://www.wordplayleague.com/privacy-policy" target="_blank">Privacy Policy</a>.
                        </p>
                        <div class="checkbox-wrapper">
                            <input type="checkbox" name="sms_consent" id="sms_consent" value="1">
                            <label for="sms_consent">
                                I agree to receive automated text messages from Wordplay League at the phone number 
                                I provided, including score confirmations and league standings. Message and data rates may apply.
                            </label>
                        </div>
                    </div>
                    
                    <button type="submit" class="btn btn-primary" style="width: 100%;">Sign Up</button>
                </form>
                
                <div class="auth-footer">
                    Already a member? <a href="/auth/login">Log In</a>
                </div>
            </div>
        </div>
    </body>
    </html>
    """


def render_profile_page(user, user_details, leagues, active_sessions, message=None, error=None):
    """Render the user profile page"""
    
    created_str = user_details['created_at'].strftime('%B %d, %Y') if user_details.get('created_at') else 'Unknown'
    last_login_str = user_details['last_login'].strftime('%B %d, %Y at %I:%M %p') if user_details.get('last_login') else 'Never'
    
    league_list_html = ""
    if leagues:
        for league in leagues:
            league_list_html += f"""
            <div style="display: flex; justify-content: space-between; align-items: center; padding: 12px 16px; background: {COLORS['bg_dark']}; border-radius: 8px; margin-bottom: 8px;">
                <div>
                    <strong style="color: {COLORS['text']};">{league['display_name']}</strong>
                    <span style="color: {COLORS['text_muted']}; font-size: 0.85em; margin-left: 8px;">{league['role']}</span>
                </div>
                <a href="/dashboard/league/{league['id']}" style="color: {COLORS['accent']}; text-decoration: none; font-size: 0.9em;">Manage →</a>
            </div>
            """
    else:
        league_list_html = f'<p style="color: {COLORS["text_muted"]}; text-align: center; padding: 20px;">No leagues yet.</p>'
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Profile - WordPlayLeague.com</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            {get_base_styles()}
            .profile-section {{
                margin-bottom: 24px;
            }}
            .profile-section h2 {{
                color: {COLORS['accent']};
                margin-bottom: 16px;
                font-size: 1.2em;
            }}
            .info-row {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 12px 0;
                border-bottom: 1px solid {COLORS['border']};
            }}
            .info-row:last-child {{ border-bottom: none; }}
            .info-label {{
                color: {COLORS['text_muted']};
                font-size: 0.9em;
            }}
            .info-value {{
                color: {COLORS['text']};
                font-weight: 500;
            }}
            .password-form {{
                display: none;
            }}
            .password-form.active {{
                display: block;
            }}
            .edit-form-section {{
                display: none;
            }}
            .edit-form-section.active {{
                display: block;
            }}
            .toast {{
                position: fixed;
                bottom: 20px;
                left: 50%;
                transform: translateX(-50%) translateY(100px);
                background: {COLORS['success']};
                color: #000;
                padding: 12px 24px;
                border-radius: 8px;
                font-weight: 600;
                opacity: 0;
                transition: all 0.3s ease;
                z-index: 10000;
            }}
            .toast.show {{
                transform: translateX(-50%) translateY(0);
                opacity: 1;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="header-logo-row">
                    <a href="https://www.wordplayleague.com" class="logo" style="text-decoration: none;">WordPlay<span class="orange">League.com</span></a>
                </div>
                <div class="header-nav-row">
                    <a href="/dashboard" class="nav-link" style="color: {COLORS['accent']};">Dashboard</a>
                    <a href="/auth/logout" class="nav-link logout">Logout</a>
                </div>
            </div>
            
            <a href="/dashboard" class="back-link">← Back to Dashboard</a>
            
            {'<div class="alert alert-success">' + message + '</div>' if message else ''}
            {'<div class="alert alert-error">' + error + '</div>' if error else ''}
            
            <!-- Profile Info -->
            <div class="card profile-section">
                <h2>👤 Profile Information</h2>
                
                <div id="profileView">
                    <div class="info-row">
                        <span class="info-label">Name</span>
                        <span class="info-value">{user_details['first_name']} {user_details['last_name']}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Email</span>
                        <span class="info-value">{user_details['email']}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Phone</span>
                        <span class="info-value">{user_details['phone'] or 'Not set'}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Member Since</span>
                        <span class="info-value">{created_str}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Last Login</span>
                        <span class="info-value">{last_login_str}</span>
                    </div>
                    <button type="button" class="btn btn-secondary btn-small" style="margin-top: 16px;" onclick="showEditProfile()">Edit Profile</button>
                </div>
                
                <div id="profileEdit" class="edit-form-section">
                    <form id="editProfileForm">
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
                            <div class="form-group">
                                <label>First Name</label>
                                <input type="text" name="first_name" value="{user_details['first_name']}" required>
                            </div>
                            <div class="form-group">
                                <label>Last Name</label>
                                <input type="text" name="last_name" value="{user_details['last_name']}" required>
                            </div>
                        </div>
                        <div class="form-group">
                            <label>Email</label>
                            <input type="email" name="email" value="{user_details['email']}" required>
                        </div>
                        <div class="form-group">
                            <label>Phone</label>
                            <input type="tel" name="phone" value="{user_details['phone']}" placeholder="(858) 555-1234">
                        </div>
                        <div style="display: flex; gap: 12px; margin-top: 8px;">
                            <button type="button" class="btn btn-primary btn-small" onclick="saveProfile()">Save Changes</button>
                            <button type="button" class="btn btn-secondary btn-small" onclick="cancelEditProfile()">Cancel</button>
                        </div>
                    </form>
                </div>
            </div>
            
            <!-- Change Password -->
            <div class="card profile-section">
                <h2>🔒 {'Set Password' if not user_details.get('has_password') else 'Change Password'}</h2>
                <div id="passwordToggle">
                    {'<p style="color: ' + COLORS['text_muted'] + '; margin-bottom: 12px;">You signed in with Google. Set a password to also log in with email/password.</p>' if not user_details.get('has_password') else '<p style="color: ' + COLORS['text_muted'] + '; margin-bottom: 12px;">Update your account password.</p>'}
                    {'<p style="color: ' + COLORS['accent'] + '; font-size: 0.85em; margin-bottom: 12px;">✓ Connected with Google</p>' if user_details.get('has_google') else ''}
                    <button type="button" class="btn btn-secondary btn-small" onclick="showPasswordForm()">{'Set Password' if not user_details.get('has_password') else 'Change Password'}</button>
                </div>
                <div id="passwordForm" class="password-form">
                    <form id="changePasswordForm">
                        {'<div class="form-group"><label>Current Password</label><input type="password" name="current_password" required placeholder="Enter current password"></div>' if user_details.get('has_password') else ''}
                        <div class="form-group">
                            <label>New Password</label>
                            <input type="password" name="new_password" required placeholder="Enter new password" minlength="8">
                        </div>
                        <div class="form-group">
                            <label>Confirm New Password</label>
                            <input type="password" name="confirm_password" required placeholder="Confirm new password">
                        </div>
                        <div style="display: flex; gap: 12px;">
                            <button type="button" class="btn btn-primary btn-small" onclick="changePassword()">{'Set Password' if not user_details.get('has_password') else 'Update Password'}</button>
                            <button type="button" class="btn btn-secondary btn-small" onclick="hidePasswordForm()">Cancel</button>
                        </div>
                    </form>
                </div>
            </div>
            
            <!-- Leagues -->
            <div class="card profile-section">
                <h2>🏆 Your Leagues ({len(leagues)})</h2>
                {league_list_html}
            </div>
            
            <!-- Session Management -->
            <div class="card profile-section">
                <h2>📱 Active Sessions</h2>
                <div class="info-row">
                    <span class="info-label">Active sessions</span>
                    <span class="info-value">{active_sessions}</span>
                </div>
                <p style="color: {COLORS['text_muted']}; font-size: 0.85em; margin: 12px 0;">Log out of all other devices. Your current session will remain active.</p>
                <button type="button" class="btn btn-secondary btn-small" onclick="logoutAllSessions()">Log Out All Other Devices</button>
            </div>
            
            <!-- Danger Zone -->
            <div class="card profile-section" style="border: 1px solid {COLORS['error']};">
                <h2 style="color: {COLORS['error']};">⚠️ Danger Zone</h2>
                <p style="color: {COLORS['text_muted']}; margin-bottom: 16px;">Permanently delete your account. This will remove your access to all leagues you manage.</p>
                <button type="button" class="btn btn-small" style="background: {COLORS['error']}; color: white;" onclick="showDeleteAccountModal()">Delete Account</button>
            </div>
        </div>
        
        <!-- Profile Update Confirmation Modal -->
        <div class="modal-overlay" id="profileUpdateModal">
            <div class="modal">
                <h3>👤 Update Profile?</h3>
                <div id="profileChanges" style="margin: 16px 0; padding: 12px; background: {COLORS['bg_dark']}; border-radius: 8px; font-size: 0.9em;"></div>
                <div style="display: flex; gap: 12px; justify-content: flex-end;">
                    <button type="button" class="btn btn-secondary btn-small" onclick="closeProfileUpdateModal()">Cancel</button>
                    <button type="button" class="btn btn-primary btn-small" onclick="confirmProfileUpdate()">Yes, Update</button>
                </div>
            </div>
        </div>
        
        <!-- Password Change Confirmation Modal -->
        <div class="modal-overlay" id="passwordChangeModal">
            <div class="modal">
                <h3>🔒 Change Password?</h3>
                <p>Are you sure you want to update your password?</p>
                <div style="display: flex; gap: 12px; justify-content: flex-end; margin-top: 20px;">
                    <button type="button" class="btn btn-secondary btn-small" onclick="closePasswordChangeModal()">Cancel</button>
                    <button type="button" class="btn btn-primary btn-small" onclick="confirmPasswordChange()">Yes, Change Password</button>
                </div>
            </div>
        </div>
        
        <!-- Delete Account Modal -->
        <div class="modal-overlay" id="deleteAccountModal">
            <div class="modal">
                <h3 style="color: {COLORS['error']};">🗑️ Delete Account?</h3>
                <p>This will permanently deactivate your account and remove your access to all leagues. This cannot be undone.</p>
                <div class="form-group" style="margin: 16px 0;">
                    <label>Enter your password to confirm:</label>
                    <input type="password" id="deleteAccountPassword" placeholder="Your password">
                </div>
                <div style="display: flex; gap: 12px; justify-content: flex-end;">
                    <button type="button" class="btn btn-secondary btn-small" onclick="closeDeleteAccountModal()">Cancel</button>
                    <button type="button" class="btn btn-small" style="background: {COLORS['error']}; color: white;" onclick="confirmDeleteAccount()">Delete Forever</button>
                </div>
            </div>
        </div>
        
        <script>
            // Auto-hide alerts
            setTimeout(function() {{
                document.querySelectorAll('.alert-success, .alert-error').forEach(function(alert) {{
                    alert.classList.add('fade-out');
                    setTimeout(function() {{ alert.remove(); }}, 500);
                }});
            }}, 5000);
            
            function showToast(message, isError) {{
                const toast = document.createElement('div');
                toast.className = 'toast';
                if (isError) toast.style.background = '{COLORS["error"]}';
                toast.textContent = message;
                document.body.appendChild(toast);
                setTimeout(() => toast.classList.add('show'), 10);
                setTimeout(() => {{
                    toast.classList.remove('show');
                    setTimeout(() => toast.remove(), 300);
                }}, 3000);
            }}
            
            // Edit Profile
            function showEditProfile() {{
                document.getElementById('profileView').style.display = 'none';
                document.getElementById('profileEdit').classList.add('active');
            }}
            
            function cancelEditProfile() {{
                document.getElementById('profileEdit').classList.remove('active');
                document.getElementById('profileView').style.display = 'block';
            }}
            
            // Original values for change detection
            const originalProfile = {{
                first_name: '{user_details['first_name']}',
                last_name: '{user_details['last_name']}',
                email: '{user_details['email']}',
                phone: '{user_details['phone']}'
            }};
            let pendingProfileData = null;
            
            function saveProfile() {{
                const form = document.getElementById('editProfileForm');
                const data = {{
                    first_name: form.querySelector('[name="first_name"]').value.trim(),
                    last_name: form.querySelector('[name="last_name"]').value.trim(),
                    email: form.querySelector('[name="email"]').value.trim(),
                    phone: form.querySelector('[name="phone"]').value.trim()
                }};
                
                if (!data.first_name || !data.last_name || !data.email) {{
                    showToast('First name, last name, and email are required', true);
                    return;
                }}
                
                // Build changes list
                const changes = [];
                if (data.first_name !== originalProfile.first_name) changes.push('First Name: ' + originalProfile.first_name + ' → ' + data.first_name);
                if (data.last_name !== originalProfile.last_name) changes.push('Last Name: ' + originalProfile.last_name + ' → ' + data.last_name);
                if (data.email !== originalProfile.email) changes.push('Email: ' + originalProfile.email + ' → ' + data.email);
                if (data.phone !== originalProfile.phone) changes.push('Phone: ' + (originalProfile.phone || 'Not set') + ' → ' + (data.phone || 'Not set'));
                
                if (changes.length === 0) {{
                    showToast('No changes to save', true);
                    return;
                }}
                
                pendingProfileData = data;
                document.getElementById('profileChanges').innerHTML = changes.join('<br>');
                document.getElementById('profileUpdateModal').style.display = 'flex';
            }}
            
            function closeProfileUpdateModal() {{
                document.getElementById('profileUpdateModal').style.display = 'none';
                pendingProfileData = null;
            }}
            
            function confirmProfileUpdate() {{
                if (!pendingProfileData) return;
                const dataToSend = pendingProfileData;
                closeProfileUpdateModal();
                
                fetch('/dashboard/profile/update', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify(dataToSend)
                }})
                .then(r => r.json())
                .then(data => {{
                    if (data.success) {{
                        showToast('Profile updated!');
                        setTimeout(() => window.location.reload(), 1000);
                    }} else {{
                        showToast(data.error || 'Error updating profile', true);
                    }}
                }})
                .catch(e => showToast('Error: ' + e, true));
            }}
            
            // Change Password
            function showPasswordForm() {{
                document.getElementById('passwordToggle').style.display = 'none';
                document.getElementById('passwordForm').classList.add('active');
            }}
            
            function hidePasswordForm() {{
                document.getElementById('passwordForm').classList.remove('active');
                document.getElementById('passwordToggle').style.display = 'block';
                document.getElementById('changePasswordForm').reset();
            }}
            
            let pendingPasswordData = null;
            
            function changePassword() {{
                const form = document.getElementById('changePasswordForm');
                const current = form.querySelector('[name="current_password"]').value;
                const newPw = form.querySelector('[name="new_password"]').value;
                const confirmPw = form.querySelector('[name="confirm_password"]').value;
                
                if (!current || !newPw || !confirmPw) {{
                    showToast('All fields are required', true);
                    return;
                }}
                if (newPw.length < 8) {{
                    showToast('New password must be at least 8 characters', true);
                    return;
                }}
                if (newPw !== confirmPw) {{
                    showToast('New passwords do not match', true);
                    return;
                }}
                
                pendingPasswordData = {{ current_password: current, new_password: newPw }};
                document.getElementById('passwordChangeModal').style.display = 'flex';
            }}
            
            function closePasswordChangeModal() {{
                document.getElementById('passwordChangeModal').style.display = 'none';
                pendingPasswordData = null;
            }}
            
            function confirmPasswordChange() {{
                if (!pendingPasswordData) return;
                const dataToSend = pendingPasswordData;
                closePasswordChangeModal();
                
                fetch('/dashboard/profile/change-password', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify(dataToSend)
                }})
                .then(r => r.json())
                .then(data => {{
                    if (data.success) {{
                        showToast('Password updated!');
                        hidePasswordForm();
                    }} else {{
                        showToast(data.error || 'Error changing password', true);
                    }}
                }})
                .catch(e => showToast('Error: ' + e, true));
                pendingPasswordData = null;
            }}
            
            // Session Management
            function logoutAllSessions() {{
                if (!confirm('Log out of all other devices? Your current session will stay active.')) return;
                
                fetch('/dashboard/profile/logout-all', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }}
                }})
                .then(r => r.json())
                .then(data => {{
                    if (data.success) {{
                        showToast(data.sessions_invalidated + ' session(s) logged out');
                        setTimeout(() => window.location.reload(), 1500);
                    }} else {{
                        showToast(data.error || 'Error', true);
                    }}
                }})
                .catch(e => showToast('Error: ' + e, true));
            }}
            
            // Delete Account
            function showDeleteAccountModal() {{
                document.getElementById('deleteAccountModal').style.display = 'flex';
                document.getElementById('deleteAccountPassword').value = '';
            }}
            
            function closeDeleteAccountModal() {{
                document.getElementById('deleteAccountModal').style.display = 'none';
            }}
            
            function confirmDeleteAccount() {{
                const password = document.getElementById('deleteAccountPassword').value;
                if (!password) {{
                    showToast('Please enter your password', true);
                    return;
                }}
                
                fetch('/dashboard/profile/delete-account', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ password: password }})
                }})
                .then(r => r.json())
                .then(data => {{
                    if (data.success) {{
                        window.location.href = '/auth/login?deleted=1';
                    }} else {{
                        showToast(data.error || 'Error deleting account', true);
                    }}
                }})
                .catch(e => showToast('Error: ' + e, true));
            }}
            
            // Close modals on escape/overlay click
            document.addEventListener('keydown', function(e) {{
                if (e.key === 'Escape') {{
                    closeDeleteAccountModal();
                    closeProfileUpdateModal();
                    closePasswordChangeModal();
                }}
            }});
            document.getElementById('deleteAccountModal').addEventListener('click', function(e) {{
                if (e.target === this) closeDeleteAccountModal();
            }});
            document.getElementById('profileUpdateModal').addEventListener('click', function(e) {{
                if (e.target === this) closeProfileUpdateModal();
            }});
            document.getElementById('passwordChangeModal').addEventListener('click', function(e) {{
                if (e.target === this) closePasswordChangeModal();
            }});
        </script>
    </body>
    </html>
    """


def get_league_wix_url(league_id):
    """Get the correct Wix URL path for a league"""
    wix_paths = {
        1: 'wordle-warriorz',
        3: 'pal',
        4: 'pickle-party',
        7: 'bellyup'
    }
    return wix_paths.get(league_id, f'league{league_id}')

def render_dashboard(user, leagues, message=None, error=None):
    """Render the main dashboard with leagues grouped by platform"""
    
    # Group leagues by channel type
    sms_leagues = [l for l in leagues if (l.get('channel_type') or 'sms') == 'sms']
    slack_leagues = [l for l in leagues if l.get('channel_type') == 'slack']
    discord_leagues = [l for l in leagues if l.get('channel_type') == 'discord']
    
    def render_league_card(league):
        wix_path = get_league_wix_url(league['id'])
        channel_type = league.get('channel_type') or 'sms'
        
        # Determine active status based on channel type
        if channel_type == 'sms':
            is_active = league.get('conversation_sid') is not None
        elif channel_type == 'slack':
            is_active = league.get('slack_channel_id') is not None
        elif channel_type == 'discord':
            is_active = league.get('discord_channel_id') is not None
        else:
            is_active = False
        
        status_color = '#2ECC71' if is_active else COLORS['accent_orange']
        status_text = '✓ Active' if is_active else '⚠ Setup Required'
        
        return f"""
        <div class="league-card">
            <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                <h3>{league['display_name']}</h3>
                <span style="background: {status_color}; color: #000; padding: 3px 8px; border-radius: 10px; font-size: 0.7em; font-weight: 600; white-space: nowrap;">{status_text}</span>
            </div>
            <div class="meta">ID: {league['id']} • Role: {league['role']}</div>
            <div class="actions">
                <a href="/dashboard/league/{league['id']}" class="btn btn-primary btn-small">Manage</a>
                <a href="{f'https://app.wordplayleague.com/leagues/{league.get("slug")}' if league.get('slug') else f'https://www.wordplayleague.com/{wix_path}'}" target="_blank" class="btn btn-secondary btn-small">View</a>
            </div>
        </div>
        """
    
    def render_platform_section(icon, title, leagues_list, empty_text):
        if not leagues_list:
            cards = f'<p style="color: {COLORS["text_muted"]}; padding: 20px; text-align: center;">{empty_text}</p>'
        else:
            cards = "".join([render_league_card(l) for l in leagues_list])
        
        return f"""
        <div class="platform-section">
            <h3 class="platform-title">{icon} {title}</h3>
            <div class="league-grid">
                {cards}
            </div>
        </div>
        """
    
    # Build platform sections
    sms_section = render_platform_section(
        "📱", "SMS Text Leagues", 
        sms_leagues, 
        "No SMS leagues yet"
    )
    slack_section = render_platform_section(
        "💬", "Slack Leagues", 
        slack_leagues, 
        "No Slack leagues yet"
    )
    discord_section = render_platform_section(
        "🎮", "Discord Leagues", 
        discord_leagues, 
        "No Discord leagues yet"
    )
    
    # If no leagues at all, show a different message
    if not leagues:
        all_sections = """
        <div class="card" style="text-align: center; padding: 40px;">
            <p style="color: #818384; margin-bottom: 20px;">You don't have any leagues yet.</p>
            <a href="/dashboard/create-league" class="btn btn-primary">Create Your First League</a>
        </div>
        """
    else:
        all_sections = sms_section + slack_section + discord_section
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Dashboard - WordPlayLeague.com</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            {get_base_styles()}
            .platform-section {{
                margin-bottom: 30px;
                background: {COLORS['bg_card']};
                border-radius: 12px;
                padding: 20px;
                border: 1px solid {COLORS['border']};
            }}
            .platform-title {{
                color: {COLORS['text']};
                font-size: 1.1em;
                margin-bottom: 16px;
                padding-bottom: 10px;
                border-bottom: 1px solid {COLORS['border']};
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="header-logo-row">
                    <a href="https://www.wordplayleague.com" class="logo" style="text-decoration: none;">WordPlay<span class="orange">League.com</span></a>
                </div>
                <div class="header-nav-row">
                    <a href="/dashboard/profile" class="nav-link">Profile</a>
                    <a href="/auth/logout" class="nav-link logout">Logout</a>
                </div>
            </div>
            
            {'<div class="alert alert-success">' + message + '</div>' if message else ''}
            {'<div class="alert alert-error">' + error + '</div>' if error else ''}
            
            <div class="card">
                <h2>👋 Welcome, {user['name'] or user['email']}!</h2>
                <p style="color: {COLORS['text_muted']};">Manage your Wordle leagues from here.</p>
            </div>
            
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                <h2 style="color: {COLORS['text']};">Your Leagues</h2>
                <a href="/dashboard/create-league" class="btn btn-primary btn-small">+ Create League</a>
            </div>
            
            {all_sections}
        </div>
        <script>
            // Auto-hide alerts after 5 seconds
            setTimeout(function() {{
                document.querySelectorAll('.alert-success, .alert-error').forEach(function(alert) {{
                    alert.classList.add('fade-out');
                    setTimeout(function() {{ alert.remove(); }}, 500);
                }});
            }}, 5000);
        </script>
    </body>
    </html>
    """


def render_create_league(user, error=None):
    """Render the create league page with platform selection"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Create League - WordPlayLeague.com</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            {get_base_styles()}
            .form-group {{
                margin-bottom: 20px;
            }}
            .form-group label {{
                display: block;
                color: {COLORS['text']};
                margin-bottom: 8px;
                font-weight: 500;
            }}
            .form-group input {{
                width: 100%;
                padding: 12px;
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                background: {COLORS['bg_dark']};
                color: {COLORS['text']};
                font-size: 1em;
                box-sizing: border-box;
            }}
            .form-group input:focus {{
                outline: none;
                border-color: {COLORS['accent']};
            }}
            .form-group .hint {{
                color: {COLORS['text_muted']};
                font-size: 0.85em;
                margin-top: 6px;
            }}
            .slug-preview {{
                background: {COLORS['bg_dark']};
                padding: 12px;
                border-radius: 8px;
                margin-top: 10px;
                font-family: monospace;
                color: {COLORS['accent']};
            }}
            .status-info {{
                background: {COLORS['bg_dark']};
                padding: 16px;
                border-radius: 8px;
                margin-top: 20px;
                border-left: 4px solid {COLORS['accent_orange']};
            }}
            .status-info h4 {{
                color: {COLORS['accent_orange']};
                margin: 0 0 8px 0;
            }}
            .status-info p {{
                color: {COLORS['text_muted']};
                margin: 0;
                font-size: 0.9em;
            }}
            .platform-options {{
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 16px;
                margin-bottom: 24px;
            }}
            @media (max-width: 600px) {{
                .platform-options {{
                    grid-template-columns: 1fr;
                }}
            }}
            .platform-option {{
                background: {COLORS['bg_dark']};
                border: 2px solid {COLORS['border']};
                border-radius: 12px;
                padding: 20px;
                text-align: center;
                cursor: pointer;
                transition: all 0.2s;
            }}
            .platform-option:hover {{
                border-color: {COLORS['accent']};
            }}
            .platform-option.selected {{
                border-color: {COLORS['accent']};
                background: rgba(0, 232, 218, 0.1);
            }}
            .platform-option input {{
                display: none;
            }}
            .platform-option .icon {{
                font-size: 2.5em;
                margin-bottom: 12px;
            }}
            .platform-option .name {{
                font-weight: 600;
                color: {COLORS['text']};
                margin-bottom: 6px;
            }}
            .platform-option .desc {{
                font-size: 0.85em;
                color: {COLORS['text_muted']};
            }}
            .platform-option .price {{
                margin-top: 10px;
                font-size: 0.9em;
                color: {COLORS['accent']};
                font-weight: 600;
            }}
            .platform-option .price.free {{
                color: #2ECC71;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="header-logo-row">
                    <a href="https://www.wordplayleague.com" class="logo" style="text-decoration: none;">WordPlay<span class="orange">League.com</span></a>
                </div>
                <div class="header-nav-row">
                    <a href="/dashboard/profile" class="nav-link">Profile</a>
                    <a href="/auth/logout" class="nav-link logout">Logout</a>
                </div>
            </div>
            
            {'<div class="alert alert-error">' + error + '</div>' if error else ''}
            
            <div class="card">
                <h2>🏆 Create New League</h2>
                <p style="color: {COLORS['text_muted']}; margin-bottom: 24px;">
                    Set up a new Wordle league for your group.
                </p>
                
                <form method="POST" action="/dashboard/create-league">
                    <div class="form-group">
                        <label>Choose Your Platform</label>
                        <div class="platform-options">
                            <label class="platform-option selected" onclick="selectPlatform(this, 'sms')">
                                <input type="radio" name="channel_type" value="sms" checked>
                                <div class="icon">📱</div>
                                <div class="name">SMS Text</div>
                                <div class="desc">iMessage or group text</div>
                            </label>
                            <label class="platform-option" onclick="selectPlatform(this, 'slack')">
                                <input type="radio" name="channel_type" value="slack">
                                <div class="icon">💬</div>
                                <div class="name">Slack</div>
                                <div class="desc">Slack workspace channel</div>
                            </label>
                            <label class="platform-option" onclick="selectPlatform(this, 'discord')">
                                <input type="radio" name="channel_type" value="discord">
                                <div class="icon">🎮</div>
                                <div class="name">Discord</div>
                                <div class="desc">Discord server channel</div>
                            </label>
                        </div>
                    </div>
                    
                    <div class="form-group">
                        <label for="league_name">League Name</label>
                        <input type="text" id="league_name" name="league_name" 
                               placeholder="e.g., Office Champions" required
                               oninput="updateSlugPreview(this.value)">
                        <div class="hint">This will be displayed on your leaderboard</div>
                    </div>
                    
                    <div class="form-group">
                        <label for="slug">URL Slug</label>
                        <input type="text" id="slug" name="slug" 
                               placeholder="e.g., office-champions" required
                               pattern="[a-z0-9-]+" 
                               title="Only lowercase letters, numbers, and hyphens allowed">
                        <div class="hint">Your league will be at: <span class="slug-preview">app.wordplayleague.com/leagues/<span id="slugPreview">your-slug</span></span></div>
                    </div>
                    
                    <div class="status-info">
                        <h4>⚠️ What's Next?</h4>
                        <p id="platform-hint">After creating your league, you'll receive a phone number to add to your group chat.</p>
                    </div>
                    
                    <div style="margin-top: 24px; display: flex; gap: 12px;">
                        <button type="submit" class="btn btn-primary">Create League</button>
                        <a href="/dashboard" class="btn btn-secondary">Cancel</a>
                    </div>
                </form>
            </div>
        </div>
        
        <script>
            function selectPlatform(element, platform) {{
                // Remove selected from all
                document.querySelectorAll('.platform-option').forEach(el => el.classList.remove('selected'));
                // Add selected to clicked
                element.classList.add('selected');
                // Check the radio
                element.querySelector('input').checked = true;
                
                // Update hint text
                const hints = {{
                    'sms': "After creating your league, you'll receive a phone number to add to your group chat.",
                    'slack': "After creating your league, you'll connect your Slack workspace and select a channel.",
                    'discord': "After creating your league, you'll add our bot to your Discord server and select a channel."
                }};
                document.getElementById('platform-hint').textContent = hints[platform];
            }}
            
            function updateSlugPreview(name) {{
                const slug = name.toLowerCase()
                    .replace(/[^a-z0-9\\s-]/g, '')
                    .replace(/\\s+/g, '-')
                    .replace(/-+/g, '-')
                    .trim();
                document.getElementById('slug').value = slug;
                document.getElementById('slugPreview').textContent = slug || 'your-slug';
            }}
        </script>
    </body>
    </html>
    """


def render_league_management(user, league, players, player_ai_settings=None, message=None, error=None):
    """Render the league management page"""
    
    if player_ai_settings is None:
        player_ai_settings = {}
    
    # Get channel type for platform-specific UI
    channel_type = league.get('channel_type') or 'sms'
    
    # Pre-compute AI settings checkbox states
    ai_perfect_checked = 'checked' if league.get('ai_perfect_score_congrats') else ''
    ai_failure_checked = 'checked' if league.get('ai_failure_roast') else ''
    ai_sunday_checked = 'checked' if league.get('ai_sunday_race_update') else ''
    ai_daily_checked = 'checked' if league.get('ai_daily_loser_roast') else ''
    
    # Platform-specific labels
    if channel_type == 'slack':
        identifier_label = 'Slack Username'
        identifier_placeholder = '@username'
        identifier_empty = 'No Slack username'
    elif channel_type == 'discord':
        identifier_label = 'Discord Username'
        identifier_placeholder = 'username#1234'
        identifier_empty = 'No Discord username'
    else:
        identifier_label = 'Phone Number'
        identifier_placeholder = '18585551234'
        identifier_empty = 'No phone'
    
    player_rows = ""
    for player in players:
        pending_badge = f'<span style="background: {COLORS["accent_orange"]}; color: #000; padding: 2px 6px; border-radius: 8px; font-size: 0.7em; font-weight: 600; margin-left: 8px;">PENDING</span>' if player.get('pending_activation') else ''
        
        # Get the appropriate identifier based on channel type
        if channel_type == 'slack':
            identifier_value = player.get('slack_user_id') or ''
            identifier_display = player.get('slack_user_id') or identifier_empty
        elif channel_type == 'discord':
            identifier_value = player.get('discord_user_id') or ''
            identifier_display = player.get('discord_user_id') or identifier_empty
        else:
            identifier_value = player.get('phone') or ''
            identifier_display = player.get('phone') or identifier_empty
        
        player_rows += f"""
        <div class="player-item" id="player-{player['id']}">
            <!-- Read-only view -->
            <div class="player-view" id="view-{player['id']}">
                <div class="player-info">
                    <div class="name">{player['name']}{pending_badge}</div>
                    <div class="phone">{identifier_display}</div>
                </div>
                <button type="button" class="btn-icon" onclick="enterEditMode({player['id']})" title="Edit player">
                    ✏️
                </button>
            </div>
            <!-- Edit mode (hidden by default) -->
            <div class="player-edit" id="edit-{player['id']}" style="display: none;">
                <form id="form-{player['id']}" class="edit-form">
                    <input type="hidden" name="player_id" value="{player['id']}">
                    <div class="edit-fields">
                        <input type="text" name="name" value="{player['name']}" class="edit-input" placeholder="Name">
                        <input type="text" name="identifier" value="{identifier_value}" class="edit-input" placeholder="{identifier_placeholder}">
                    </div>
                    <div class="edit-actions">
                        <button type="button" class="btn btn-primary btn-small" onclick="showSaveModal({player['id']}, '{player['name']}')">Save</button>
                        <button type="button" class="btn btn-danger btn-small" onclick="showRemoveModal({player['id']}, '{player['name']}')">Remove</button>
                        <button type="button" class="btn btn-secondary btn-small" onclick="cancelEdit({player['id']})">Cancel</button>
                    </div>
                </form>
            </div>
        </div>
        """
    
    if not players:
        player_rows = '<p style="color: #818384; padding: 20px; text-align: center;">No players in this league yet.</p>'
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{league['display_name']} - Manage League</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            {get_base_styles()}
            .back-link {{
                color: {COLORS['accent']};
                text-decoration: none;
                display: inline-flex;
                align-items: center;
                gap: 8px;
                margin-bottom: 20px;
            }}
            .back-link:hover {{ text-decoration: underline; }}
            .section {{ margin-bottom: 30px; }}
            
            /* Player item styles */
            .player-item {{
                background: {COLORS['bg_dark']};
                border-radius: 8px;
                margin-bottom: 8px;
                padding: 12px 16px;
                width: 100%;
                max-width: 100%;
                overflow: hidden;
            }}
            .player-view {{
                display: flex;
                justify-content: space-between;
                align-items: center;
            }}
            .player-info {{
                flex: 1;
                min-width: 0;
                overflow: hidden;
            }}
            .player-info .name {{
                font-weight: 500;
                color: {COLORS['text']};
                overflow: hidden;
                text-overflow: ellipsis;
            }}
            .player-info .phone {{
                color: {COLORS['text_muted']};
                font-size: 0.9em;
                overflow: hidden;
                text-overflow: ellipsis;
            }}
            .btn-icon {{
                background: transparent;
                border: none;
                cursor: pointer;
                font-size: 1.2em;
                padding: 8px;
                border-radius: 6px;
                transition: background 0.2s;
            }}
            .btn-icon:hover {{
                background: {COLORS['bg_card']};
            }}
            .player-edit {{
                padding: 8px 0;
            }}
            .edit-form {{
                display: flex;
                flex-direction: column;
                gap: 12px;
            }}
            .edit-fields {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 12px;
                width: 100%;
                max-width: 100%;
            }}
            .edit-input {{
                padding: 10px 12px;
                border-radius: 6px;
                border: 1px solid #444;
                background: {COLORS['bg_card']};
                color: {COLORS['text']};
                font-size: 16px;
                width: 100%;
                max-width: 100%;
                min-width: 0;
            }}
            .edit-input:focus {{
                outline: none;
                border-color: {COLORS['accent']};
            }}
            @media (max-width: 600px) {{
                .edit-fields {{
                    grid-template-columns: 1fr;
                }}
                .edit-input {{
                    font-size: 16px;
                }}
            }}
            .edit-actions {{
                display: flex;
                gap: 10px;
            }}
            
            /* Modal styles */
            .modal-overlay {{
                display: none;
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0, 0, 0, 0.75);
                z-index: 1000;
                align-items: center;
                justify-content: center;
            }}
            .modal-overlay.active {{
                display: flex;
            }}
            .modal {{
                background: {COLORS['bg_card']};
                border-radius: 12px;
                padding: 30px;
                max-width: 400px;
                width: 90%;
                border: 1px solid #444;
            }}
            .modal h3 {{
                color: {COLORS['text']};
                margin-bottom: 16px;
            }}
            .modal p {{
                color: {COLORS['text_muted']};
                margin-bottom: 24px;
                line-height: 1.5;
            }}
            .modal-actions {{
                display: flex;
                gap: 12px;
                justify-content: flex-end;
            }}
            .toast {{
                position: fixed;
                bottom: 20px;
                left: 50%;
                transform: translateX(-50%) translateY(100px);
                background: {COLORS['success']};
                color: #000;
                padding: 12px 24px;
                border-radius: 8px;
                font-weight: 600;
                opacity: 0;
                transition: all 0.3s ease;
                z-index: 10000;
            }}
            .toast.show {{
                transform: translateX(-50%) translateY(0);
                opacity: 1;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="header-logo-row">
                    <a href="https://www.wordplayleague.com" class="logo" style="text-decoration: none;">WordPlay<span class="orange">League.com</span></a>
                </div>
                <div class="header-nav-row">
                    <a href="/dashboard/profile" class="nav-link">Profile</a>
                    <a href="/auth/logout" class="nav-link logout">Logout</a>
                </div>
            </div>
            
            <a href="/dashboard" class="back-link">← Back to Dashboard</a>
            
            {'<div class="alert alert-success">' + message + '</div>' if message else ''}
            {'<div class="alert alert-error">' + error + '</div>' if error else ''}
            
            {f'''<div class="alert" style="background: {COLORS['accent_orange']}20; border: 1px solid {COLORS['accent_orange']}; color: {COLORS['text']};">
                <strong>⚠️ Pending Players:</strong> You have {len([p for p in players if p.get('pending_activation')])} new player(s) not yet in your group chat. 
                They won't receive messages until you add them to your group and re-link.
                <button type="button" class="btn btn-small" style="background: {COLORS['accent_orange']}; color: #000; margin-left: 12px;" onclick="showActivateModal()">Re-link Group Chat</button>
            </div>''' if any(p.get('pending_activation') for p in players) else ''}
            
            <div class="card">
                <h2>⚙️ {league['display_name']}</h2>
                <div style="display: flex; gap: 16px; align-items: center; flex-wrap: wrap;">
                    <span style="color: {COLORS['text_muted']};">League ID: {league['id']}</span>
                    <span style="background: {COLORS['bg_dark']}; color: {COLORS['text']}; padding: 4px 10px; border-radius: 12px; font-size: 0.8em;">
                        {'📱 SMS' if channel_type == 'sms' else '💬 Slack' if channel_type == 'slack' else '🎮 Discord'}
                    </span>
                    <span style="background: {'#2ECC71' if (league.get('conversation_sid') if channel_type == 'sms' else league.get('slack_channel_id') if channel_type == 'slack' else league.get('discord_channel_id')) else COLORS['accent_orange']}; color: #000; padding: 4px 10px; border-radius: 12px; font-size: 0.8em; font-weight: 600;">
                        {'✓ Active' if (league.get('conversation_sid') if channel_type == 'sms' else league.get('slack_channel_id') if channel_type == 'slack' else league.get('discord_channel_id')) else '⚠ Setup Required'}
                    </span>
                    {f'<button type="button" class="btn btn-small" style="background: {COLORS["accent"]}; color: #000; padding: 6px 12px;" onclick="showActivateModal()">Connect Channel</button>' if not (league.get('conversation_sid') if channel_type == 'sms' else league.get('slack_channel_id') if channel_type == 'slack' else league.get('discord_channel_id')) else ''}
                    {f'<a href="https://app.wordplayleague.com/leagues/{league["slug"]}" target="_blank" style="color: {COLORS["accent"]}; font-size: 0.9em;">app.wordplayleague.com/leagues/{league["slug"]}</a>' if league.get('slug') else ''}
                </div>
                {f"""
                <div style="margin-top: 16px; padding: 12px; background: {COLORS['bg_dark']}; border-radius: 8px; border-left: 3px solid {COLORS['accent']};">
                    <p style="margin: 0 0 8px 0; color: {COLORS['text']}; font-weight: 600;">📋 How to Submit Scores</p>
                    <p style="margin: 0; color: {COLORS['text_muted']}; font-size: 0.9em;">Players type <code style="background: {COLORS['bg_card']}; padding: 2px 6px; border-radius: 4px;">/wordplay</code> and paste their full Wordle share (with emoji pattern).</p>
                </div>
                """ if channel_type == 'discord' and league.get('discord_channel_id') else ''}
            </div>
            
            <!-- Rename League Section -->
            <div class="card section">
                <h2>📝 League Settings</h2>
                <div class="form-group">
                    <label>League Display Name</label>
                    <input type="text" id="leagueDisplayName" value="{league['display_name']}" required>
                </div>
                <button type="button" class="btn btn-primary" onclick="showRenameModal()">Save Changes</button>
            </div>
            
            <!-- Players Section -->
            <div class="card section">
                <h2>👥 Players ({len(players)})</h2>
                <div class="player-list">
                    {player_rows}
                </div>
            </div>
            
            <!-- Add Player Section -->
            <div class="card section">
                <h2>➕ Add Player</h2>
                <form method="POST" action="/dashboard/league/{league['id']}/add-player" id="addPlayerForm" onsubmit="showLoading('Adding player...')">
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
                        <div class="form-group">
                            <label>Player Name</label>
                            <input type="text" name="name" required placeholder="John Doe">
                        </div>
                        <div class="form-group">
                            <label>{identifier_label}</label>
                            <input type="text" name="identifier" required placeholder="{identifier_placeholder}">
                        </div>
                    </div>
                    <button type="submit" class="btn btn-primary">Add Player</button>
                </form>
            </div>
            
            <!-- AI Messaging Settings -->
            <div class="card section">
                <h2>🤖 AI Automated Messaging</h2>
                <p style="color: {COLORS['text_muted']}; margin-bottom: 16px;">Control which AI-generated messages are sent to this league's group chat.</p>
                
                <div class="ai-toggle-list">
                    <div class="ai-toggle-item">
                        <div class="ai-toggle-header">
                            <label class="toggle-label">
                                <input type="checkbox" id="ai_perfect_score" {ai_perfect_checked}>
                                <span class="toggle-text">
                                    <strong>🎯 Perfect Score Congrats</strong>
                                    <small>Celebrate amazing 1/6 or 2/6 scores</small>
                                </span>
                            </label>
                            <button type="button" class="btn btn-secondary btn-small" onclick="openMessageConfig('perfect_score', '🎯 Perfect Score Congrats')">Edit ✏️</button>
                        </div>
                        <div class="ai-toggle-meta">
                            <span>Tone: <strong id="perfect_score_tone_label">{['Savage', 'Spicy', 'Playful', 'Gentle'][league.get('ai_perfect_score_severity', 2) - 1]}</strong></span>
                            <span>Players: <strong id="perfect_score_players_label">All</strong></span>
                        </div>
                    </div>
                    
                    <div class="ai-toggle-item">
                        <div class="ai-toggle-header">
                            <label class="toggle-label">
                                <input type="checkbox" id="ai_failure_roast" {ai_failure_checked}>
                                <span class="toggle-text">
                                    <strong>🔥 Failure Roast</strong>
                                    <small>Roast players who fail with X/6</small>
                                </span>
                            </label>
                            <button type="button" class="btn btn-secondary btn-small" onclick="openMessageConfig('failure_roast', '🔥 Failure Roast')">Edit ✏️</button>
                        </div>
                        <div class="ai-toggle-meta">
                            <span>Tone: <strong id="failure_roast_tone_label">{['Savage', 'Spicy', 'Playful', 'Gentle'][league.get('ai_failure_roast_severity', 2) - 1]}</strong></span>
                            <span>Players: <strong id="failure_roast_players_label">All</strong></span>
                        </div>
                    </div>
                    
                    <div class="ai-toggle-item">
                        <div class="ai-toggle-header">
                            <label class="toggle-label">
                                <input type="checkbox" id="ai_sunday_race" {ai_sunday_checked}>
                                <span class="toggle-text">
                                    <strong>📊 Sunday Race Update</strong>
                                    <small>10am Sunday summary showing who can still win</small>
                                </span>
                            </label>
                        </div>
                        <div class="ai-toggle-meta">
                            <span class="tone-na">Tone: N/A (informational)</span>
                        </div>
                    </div>
                    
                    <div class="ai-toggle-item">
                        <div class="ai-toggle-header">
                            <label class="toggle-label">
                                <input type="checkbox" id="ai_daily_loser" {ai_daily_checked}>
                                <span class="toggle-text">
                                    <strong>😈 Daily Loser Roast</strong>
                                    <small>Roast the worst scorer(s) when all players have posted, using the Wordle word subtly</small>
                                </span>
                            </label>
                            <button type="button" class="btn btn-secondary btn-small" onclick="openMessageConfig('daily_loser', '😈 Daily Loser Roast')">Edit ✏️</button>
                        </div>
                        <div class="ai-toggle-meta">
                            <span>Tone: <strong id="daily_loser_tone_label">{['Savage', 'Spicy', 'Playful', 'Gentle'][league.get('ai_daily_loser_severity', 2) - 1]}</strong></span>
                            <span>Players: <strong id="daily_loser_players_label">All</strong></span>
                        </div>
                    </div>
                </div>
                
                <button type="button" class="btn btn-primary" onclick="saveAISettings()" style="margin-top: 16px;">Save AI Settings</button>
            </div>
            
            <!-- View League Link -->
            <div class="card">
                <h2>🔗 Public League Page</h2>
                <p style="margin-bottom: 16px; color: {COLORS['text_muted']};">Share this link with your league members:</p>
                <a href="{f'https://app.wordplayleague.com/leagues/{league["slug"]}' if league.get('slug') else f'https://www.wordplayleague.com/{get_league_wix_url(league["id"])}'}" target="_blank" class="btn btn-secondary">
                    View Public Page →
                </a>
            </div>
            
            <!-- Danger Zone -->
            <div class="card" style="border: 1px solid {COLORS['error']};">
                <h2 style="color: {COLORS['error']};">⚠️ Danger Zone</h2>
                <p style="margin-bottom: 16px; color: {COLORS['text_muted']};">Permanently delete this league and all associated data. This action cannot be undone.</p>
                <button type="button" class="btn" style="background: {COLORS['error']}; color: white;" onclick="showDeleteLeagueModal()">
                    Delete League
                </button>
            </div>
        </div>
        
        <!-- Save Confirmation Modal -->
        <div class="modal-overlay" id="saveModal">
            <div class="modal">
                <h3>💾 Save Changes?</h3>
                <p id="saveModalText">Are you sure you want to save changes to this player?</p>
                <div class="modal-actions" id="saveModalActions">
                    <button type="button" class="btn btn-secondary btn-small" onclick="closeSaveModal()">Cancel</button>
                    <button type="button" class="btn btn-primary btn-small" onclick="confirmSave()">Yes, Save</button>
                </div>
            </div>
        </div>
        
        <!-- Remove Confirmation Modal -->
        <div class="modal-overlay" id="removeModal">
            <div class="modal">
                <h3>⚠️ Remove Player?</h3>
                <p id="removeModalText">Are you sure you want to remove this player from the league? Their historical scores will be preserved.</p>
                <div class="modal-actions" id="removeModalActions">
                    <button type="button" class="btn btn-secondary btn-small" onclick="closeRemoveModal()">Cancel</button>
                    <button type="button" class="btn btn-danger btn-small" onclick="confirmRemove()">Yes, Remove</button>
                </div>
            </div>
        </div>
        
        <!-- Rename League Confirmation Modal -->
        <div class="modal-overlay" id="renameModal">
            <div class="modal">
                <h3>📝 Rename League?</h3>
                <p id="renameModalText">Are you sure you want to rename this league?</p>
                <div class="modal-actions">
                    <button type="button" class="btn btn-secondary btn-small" onclick="closeRenameModal()">Cancel</button>
                    <button type="button" class="btn btn-primary btn-small" onclick="confirmRename()">Yes, Rename</button>
                </div>
            </div>
        </div>
        
        <!-- AI Settings Confirmation Modal -->
        <div class="modal-overlay" id="aiSettingsModal">
            <div class="modal">
                <h3>🤖 Update AI Messaging?</h3>
                <p id="aiSettingsModalText">Are you sure you want to update your AI messaging settings?</p>
                <div id="aiSettingsChanges" style="margin: 16px 0; padding: 12px; background: {COLORS['bg_dark']}; border-radius: 8px; font-size: 0.9em;"></div>
                <div class="modal-actions">
                    <button type="button" class="btn btn-secondary btn-small" onclick="closeAISettingsModal()">Cancel</button>
                    <button type="button" class="btn btn-primary btn-small" onclick="confirmAISettings()">Yes, Update</button>
                </div>
            </div>
        </div>
        
        <!-- Message Config Modal -->
        <div class="modal-overlay" id="messageConfigModal">
            <div class="modal config-modal">
                <h3 id="messageConfigTitle">Configure Message</h3>
                
                <div class="config-section">
                    <h4>Default Tone for All Players</h4>
                    <div class="severity-section" style="margin-bottom: 0;">
                        <input type="range" id="configSeverity" min="1" max="4" value="2" class="severity-slider" oninput="updateConfigSeverityLabel(this.value)">
                        <div class="severity-scale">
                            <span>Savage</span>
                            <span>Spicy</span>
                            <span>Playful</span>
                            <span>Gentle</span>
                        </div>
                        <p style="text-align: center; margin-top: 8px; color: {COLORS['accent']}; font-weight: 600;" id="configSeverityLabel">Spicy 🌶️</p>
                    </div>
                    <div class="tone-preview" id="tonePreview">
                        <p class="preview-label">Example:</p>
                        <p class="preview-text" id="previewText">"Loading example..."</p>
                    </div>
                </div>
                
                <div class="config-section">
                    <h4>Player Settings</h4>
                    <p style="color: {COLORS['text_muted']}; font-size: 0.85em; margin-bottom: 12px;">Uncheck to exclude from this message. Use dropdown to override tone.</p>
                    <div class="player-config-list" id="playerConfigList">
                        <!-- Players will be populated by JavaScript -->
                    </div>
                </div>
                
                <div class="modal-actions">
                    <button type="button" class="btn btn-secondary btn-small" onclick="closeMessageConfig()">Cancel</button>
                    <button type="button" class="btn btn-primary btn-small" onclick="showMessageConfigConfirm()">Save</button>
                </div>
            </div>
        </div>
        
        <!-- Message Config Confirmation Modal -->
        <div class="modal-overlay" id="messageConfigConfirmModal">
            <div class="modal">
                <h3>🤖 Update Message Settings?</h3>
                <p>Are you sure you want to update these settings?</p>
                <div id="messageConfigChanges" style="margin: 16px 0; padding: 12px; background: {COLORS['bg_dark']}; border-radius: 8px; font-size: 0.9em;"></div>
                <div class="modal-actions">
                    <button type="button" class="btn btn-secondary btn-small" onclick="closeMessageConfigConfirm()">Cancel</button>
                    <button type="button" class="btn btn-primary btn-small" onclick="confirmMessageConfig()">Yes, Update</button>
                </div>
            </div>
        </div>
        
        <!-- Activate League Modal -->
        <div class="modal-overlay" id="activateModal">
            <div class="modal" style="max-width: 500px; max-height: 90vh; overflow-y: auto;">
                <h3 style="color: {COLORS['accent']};">🚀 {'Connect Your Channel' if channel_type != 'sms' else 'Activate Your League'}</h3>
                
                <!-- Passcode Gate -->
                <div id="activatePasscodeGate">
                    <div style="background: {COLORS['accent_orange']}20; border: 1px solid {COLORS['accent_orange']}; padding: 16px; border-radius: 8px; margin-bottom: 16px;">
                        <p style="color: {COLORS['text']}; margin: 0 0 12px 0;"><strong>🔒 Activation Locked</strong></p>
                        <p style="color: {COLORS['text_muted']}; margin: 0; font-size: 0.9em;">League activation is currently restricted. Enter the admin passcode to continue, or contact support to get access.</p>
                    </div>
                    <div class="form-group" style="margin-bottom: 16px;">
                        <label>Admin Passcode</label>
                        <input type="password" id="activatePasscode" placeholder="Enter passcode" style="width: 100%;">
                    </div>
                    <div class="modal-actions">
                        <button type="button" class="btn btn-secondary" onclick="closeActivateModal()">Cancel</button>
                        <button type="button" class="btn btn-primary" onclick="checkActivatePasscode()">Unlock</button>
                    </div>
                </div>
                
                <!-- Activation Steps (hidden until passcode entered) -->
                <div id="activateSteps" style="display: none;">
                    {'<p style="margin-bottom: 20px;">Follow these steps to connect your Slack channel:</p>' if channel_type == 'slack' else '<p style="margin-bottom: 20px;">Follow these steps to connect your Discord channel:</p>' if channel_type == 'discord' else '<p style="margin-bottom: 20px;">Follow these steps to connect your group chat:</p>'}
                    
                    {f"""
                    <div style="background: {COLORS['bg_dark']}; padding: 16px; border-radius: 8px; margin-bottom: 16px;">
                        <h4 style="margin: 0 0 12px 0; color: {COLORS['text']};">Step 1: Install the Wordle League app</h4>
                        <p style="color: {COLORS['text_muted']}; margin-bottom: 12px;">Click the button below to add the Wordle League bot to your Slack workspace:</p>
                        <a href="/slack/install?league_id={league['id']}" class="btn btn-primary" style="display: inline-block; text-decoration: none;">Add to Slack</a>
                    </div>
                    
                    <div style="background: {COLORS['bg_dark']}; padding: 16px; border-radius: 8px; margin-bottom: 16px;">
                        <h4 style="margin: 0 0 12px 0; color: {COLORS['text']};">Step 2: Invite the bot to your channel</h4>
                        <p style="color: {COLORS['text_muted']}; margin: 0;">In your Slack channel, type <code style="background: {COLORS['bg_card']}; padding: 2px 6px; border-radius: 4px;">/invite @WordPlayLeague</code> to add the bot.</p>
                    </div>
                    
                    <div style="background: {COLORS['bg_dark']}; padding: 16px; border-radius: 8px; margin-bottom: 16px;">
                        <h4 style="margin: 0 0 12px 0; color: {COLORS['text']};">Step 3: Link your channel</h4>
                        <p style="color: {COLORS['text_muted']}; margin-bottom: 8px;">Send this verification code in the channel:</p>
                        <div id="verificationCode" style="background: {COLORS['bg_card']}; padding: 16px; border-radius: 6px; font-size: 1.3em; text-align: center; color: {COLORS['accent']}; font-weight: 600;">
                            {league.get('verification_code') or 'Loading...'}
                        </div>
                    </div>
                    """ if channel_type == 'slack' else f"""
                    <div style="background: {COLORS['bg_dark']}; padding: 16px; border-radius: 8px; margin-bottom: 16px;">
                        <h4 style="margin: 0 0 12px 0; color: {COLORS['text']};">Step 1: Add the Wordle League bot</h4>
                        <p style="color: {COLORS['text_muted']}; margin-bottom: 12px;">Click the button below to add the Wordle League bot to your Discord server:</p>
                        <a href="/discord/install?league_id={league['id']}" class="btn btn-primary" style="display: inline-block; text-decoration: none;">Add to Discord</a>
                    </div>
                    
                    <div style="background: {COLORS['bg_dark']}; padding: 16px; border-radius: 8px; margin-bottom: 16px;">
                        <h4 style="margin: 0 0 12px 0; color: {COLORS['text']};">Step 2: Link your channel</h4>
                        <p style="color: {COLORS['text_muted']}; margin-bottom: 8px;">In your Discord channel, use the slash command with this code:</p>
                        <div id="verificationCode" style="background: {COLORS['bg_card']}; padding: 16px; border-radius: 6px; font-size: 1.1em; text-align: center; color: {COLORS['accent']}; font-weight: 600;">
                            /wordle-link {league.get('verification_code') or 'Loading...'}
                        </div>
                    </div>
                    
                    <div style="background: {COLORS['bg_dark']}; padding: 16px; border-radius: 8px; margin-bottom: 16px;">
                        <h4 style="margin: 0 0 12px 0; color: {COLORS['text']};">Step 3: Submit scores</h4>
                        <p style="color: {COLORS['text_muted']}; margin-bottom: 8px;">Players submit their daily Wordle scores by typing <code style="background: {COLORS['bg_card']}; padding: 2px 6px; border-radius: 4px;">/wordplay</code> and pasting their full Wordle share:</p>
                        <code style="display: block; background: {COLORS['bg_card']}; padding: 12px; border-radius: 6px; font-size: 0.95em; white-space: pre-wrap;">/wordplay Wordle 1,689 3/6\n⬛⬛🟨⬛⬛\n🟨⬛⬛🟩⬛\n🟩🟩🟩🟩🟩</code>
                    </div>
                    """ if channel_type == 'discord' else f"""
                    <div style="background: {COLORS['bg_dark']}; padding: 16px; border-radius: 8px; margin-bottom: 16px;">
                        <h4 style="margin: 0 0 12px 0; color: {COLORS['text']};">Step 1: Add the Wordle Bot to your group</h4>
                        <p style="color: {COLORS['text_muted']}; margin-bottom: 8px;">Add this phone number to your iMessage or SMS group chat:</p>
                        <div style="background: {COLORS['bg_card']}; padding: 12px; border-radius: 6px; font-family: monospace; font-size: 1.2em; text-align: center; color: {COLORS['accent']};">
                            +1 (858) 666-6827
                        </div>
                    </div>
                    
                    <div style="background: {COLORS['bg_dark']}; padding: 16px; border-radius: 8px; margin-bottom: 16px;">
                        <h4 style="margin: 0 0 12px 0; color: {COLORS['text']};">Step 2: Send the secret code phrase</h4>
                        <p style="color: {COLORS['text_muted']}; margin-bottom: 8px;">Once the bot is added, send this phrase in the group chat:</p>
                        <div id="verificationCode" style="background: {COLORS['bg_card']}; padding: 16px; border-radius: 6px; font-size: 1.3em; text-align: center; color: {COLORS['accent']}; font-weight: 600;">
                            {league.get('verification_code') or 'Loading...'}
                        </div>
                    </div>
                    """}
                
                <div style="background: {COLORS['bg_dark']}; padding: 16px; border-radius: 8px; margin-bottom: 20px;">
                    <h4 style="margin: 0 0 8px 0; color: {COLORS['text']};">{'Step 4' if channel_type in ['slack', 'discord'] else 'Step 3'}: Wait for confirmation</h4>
                    <p style="color: {COLORS['text_muted']}; margin: 0;">The bot will respond once connected. Click "Check Status" below to verify.</p>
                </div>
                
                <div class="modal-actions">
                    <button type="button" class="btn btn-secondary" onclick="closeActivateModal()">Close</button>
                    <button type="button" class="btn btn-primary" onclick="checkActivationStatus()">Check Status</button>
                </div>
                </div>
            </div>
        </div>
        
        <!-- Delete League Modal -->
        <div class="modal-overlay" id="deleteLeagueModal">
            <div class="modal">
                <h3 style="color: {COLORS['error']};">🗑️ Delete League Permanently?</h3>
                <p style="margin-bottom: 16px;">This will permanently delete <strong>{league['display_name']}</strong> and all associated data including:</p>
                <ul style="text-align: left; margin: 0 0 16px 20px; color: {COLORS['text_muted']};">
                    <li>All player records</li>
                    <li>All score history</li>
                    <li>All weekly winners</li>
                    <li>The public league page</li>
                </ul>
                <p style="color: {COLORS['error']}; font-weight: 600; margin-bottom: 16px;">This action CANNOT be undone!</p>
                <div class="form-group" style="margin-bottom: 16px;">
                    <label>Type the league name to confirm:</label>
                    <input type="text" id="deleteLeagueConfirmName" placeholder="{league['display_name']}" style="width: 100%;">
                </div>
                <div class="modal-actions">
                    <button type="button" class="btn btn-secondary btn-small" onclick="closeDeleteLeagueModal()">Cancel</button>
                    <button type="button" class="btn btn-small" style="background: {COLORS['error']}; color: white;" onclick="confirmDeleteLeague()" id="confirmDeleteBtn" disabled>Delete Forever</button>
                </div>
            </div>
        </div>
        
        <!-- Loading Overlay -->
        <div class="modal-overlay" id="loadingOverlay">
            <div class="loading-spinner">
                <div class="spinner"></div>
                <p id="loadingText">Saving changes...</p>
            </div>
        </div>
        
        <style>
            .loading-spinner {{
                text-align: center;
                color: {COLORS['text']};
            }}
            .spinner {{
                width: 50px;
                height: 50px;
                border: 4px solid {COLORS['bg_card']};
                border-top: 4px solid {COLORS['accent']};
                border-radius: 50%;
                animation: spin 1s linear infinite;
                margin: 0 auto 20px auto;
            }}
            @keyframes spin {{
                0% {{ transform: rotate(0deg); }}
                100% {{ transform: rotate(360deg); }}
            }}
            @keyframes shake {{
                0%, 100% {{ transform: translateX(0); }}
                20%, 60% {{ transform: translateX(-5px); }}
                40%, 80% {{ transform: translateX(5px); }}
            }}
            .loading-spinner p {{
                font-size: 1.1em;
                margin: 0;
            }}
            .ai-toggle-list {{
                display: flex;
                flex-direction: column;
                gap: 12px;
            }}
            .ai-toggle-item {{
                background: {COLORS['bg_dark']};
                padding: 12px 16px;
                border-radius: 8px;
                border: 1px solid {COLORS['border']};
            }}
            .toggle-label {{
                display: flex;
                align-items: flex-start;
                gap: 12px;
                cursor: pointer;
            }}
            .toggle-label input[type="checkbox"] {{
                width: 20px;
                height: 20px;
                min-width: 20px;
                min-height: 20px;
                flex-shrink: 0;
                margin-top: 2px;
                accent-color: {COLORS['accent']};
                cursor: pointer;
                -webkit-appearance: none;
                -moz-appearance: none;
                appearance: none;
                background: {COLORS['bg_card']};
                border: 2px solid {COLORS['border']};
                border-radius: 4px;
                position: relative;
            }}
            .toggle-label input[type="checkbox"]:checked {{
                background: {COLORS['accent']};
                border-color: {COLORS['accent']};
            }}
            .toggle-label input[type="checkbox"]:checked::after {{
                content: '✓';
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                color: #000;
                font-size: 14px;
                font-weight: bold;
            }}
            .toggle-text {{
                display: flex;
                flex-direction: column;
                gap: 4px;
            }}
            .toggle-text strong {{
                color: {COLORS['text']};
            }}
            .toggle-text small {{
                color: {COLORS['text_muted']};
                font-size: 0.85em;
            }}
            .tone-na {{
                font-size: 0.75em;
                color: {COLORS['text_muted']};
                font-style: italic;
            }}
            .ai-toggle-header {{
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                gap: 12px;
            }}
            .ai-toggle-meta {{
                display: flex;
                gap: 20px;
                margin-top: 8px;
                padding-top: 8px;
                border-top: 1px solid {COLORS['border']};
                font-size: 0.85em;
                color: {COLORS['text_muted']};
            }}
            .ai-toggle-meta strong {{
                color: {COLORS['accent']};
            }}
            .config-modal {{
                max-width: 600px;
                max-height: 80vh;
                overflow-y: auto;
            }}
            .config-section {{
                margin-bottom: 20px;
            }}
            .config-section h4 {{
                margin-bottom: 12px;
                color: {COLORS['text']};
            }}
            .player-config-list {{
                display: flex;
                flex-direction: column;
                gap: 8px;
            }}
            .player-config-item {{
                display: flex;
                align-items: center;
                gap: 12px;
                padding: 10px 12px;
                background: {COLORS['bg_dark']};
                border-radius: 6px;
            }}
            .player-config-item .player-name {{
                flex: 1;
                font-weight: 500;
            }}
            .player-config-item select {{
                padding: 6px 10px;
                border-radius: 4px;
                border: 1px solid {COLORS['border']};
                background: {COLORS['bg_card']};
                color: {COLORS['text']};
                font-size: 0.9em;
            }}
            .tone-preview {{
                margin-top: 16px;
                padding: 12px;
                background: {COLORS['bg_card']};
                border-radius: 8px;
                border-left: 3px solid {COLORS['accent']};
            }}
            .preview-label {{
                font-size: 0.8em;
                color: {COLORS['text_muted']};
                margin: 0 0 6px 0;
            }}
            .preview-text {{
                margin: 0;
                font-style: italic;
                color: {COLORS['text']};
                font-size: 0.9em;
                line-height: 1.4;
            }}
            .severity-section {{
                background: {COLORS['bg_dark']};
                padding: 16px;
                border-radius: 8px;
                margin-bottom: 16px;
                border: 1px solid {COLORS['border']};
            }}
            .severity-label {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 12px;
            }}
            .severity-value {{
                color: {COLORS['accent']};
                font-weight: 600;
            }}
            .severity-slider {{
                width: 100%;
                height: 8px;
                -webkit-appearance: none;
                appearance: none;
                background: linear-gradient(to right, #f44336, #FFA64D, #4CAF50, #00E8DA);
                border-radius: 4px;
                outline: none;
            }}
            .severity-slider::-webkit-slider-thumb {{
                -webkit-appearance: none;
                appearance: none;
                width: 24px;
                height: 24px;
                background: white;
                border-radius: 50%;
                cursor: pointer;
                box-shadow: 0 2px 6px rgba(0,0,0,0.3);
            }}
            .severity-slider::-moz-range-thumb {{
                width: 24px;
                height: 24px;
                background: white;
                border-radius: 50%;
                cursor: pointer;
                border: none;
                box-shadow: 0 2px 6px rgba(0,0,0,0.3);
            }}
            .severity-scale {{
                display: flex;
                justify-content: space-between;
                margin-top: 8px;
                font-size: 0.75em;
                color: {COLORS['text_muted']};
            }}
        </style>
        
        <!-- Hidden forms for submission -->
        <form id="editPlayerForm" method="POST" action="/dashboard/league/{league['id']}/edit-player" style="display:none;">
            <input type="hidden" name="player_id" id="editPlayerId">
            <input type="hidden" name="name" id="editPlayerName">
            <input type="hidden" name="phone" id="editPlayerPhone">
        </form>
        <form id="removePlayerForm" method="POST" action="/dashboard/league/{league['id']}/remove-player" style="display:none;">
            <input type="hidden" name="player_id" id="removePlayerId">
        </form>
        <form id="renameLeagueForm" method="POST" action="/dashboard/league/{league['id']}/rename" style="display:none;">
            <input type="hidden" name="display_name" id="renameDisplayName">
        </form>
        <form id="aiSettingsForm" method="POST" action="/dashboard/league/{league['id']}/ai-settings" style="display:none;">
            <input type="hidden" name="ai_perfect_score_congrats" id="aiPerfectScoreInput">
            <input type="hidden" name="ai_failure_roast" id="aiFailureRoastInput">
            <input type="hidden" name="ai_sunday_race_update" id="aiSundayRaceInput">
            <input type="hidden" name="ai_daily_loser_roast" id="aiDailyLoserInput">
            <input type="hidden" name="ai_message_severity" id="aiSeverityInput">
        </form>
        
        <script>
            // Auto-hide alerts after 5 seconds
            setTimeout(function() {{
                document.querySelectorAll('.alert-success, .alert-error').forEach(function(alert) {{
                    alert.classList.add('fade-out');
                    setTimeout(function() {{ alert.remove(); }}, 500);
                }});
            }}, 5000);
            
            let currentEditPlayerId = null;
            let currentRemovePlayerId = null;
            
            function enterEditMode(playerId) {{
                // Hide view, show edit
                document.getElementById('view-' + playerId).style.display = 'none';
                document.getElementById('edit-' + playerId).style.display = 'block';
            }}
            
            function cancelEdit(playerId) {{
                // Show view, hide edit
                document.getElementById('view-' + playerId).style.display = 'flex';
                document.getElementById('edit-' + playerId).style.display = 'none';
            }}
            
            function showSaveModal(playerId, playerName) {{
                currentEditPlayerId = playerId;
                const form = document.getElementById('form-' + playerId);
                const newName = form.querySelector('input[name="name"]').value;
                document.getElementById('saveModalText').textContent = 
                    'Are you sure you want to save changes to ' + newName + '?';
                document.getElementById('saveModal').classList.add('active');
            }}
            
            function closeSaveModal() {{
                document.getElementById('saveModal').classList.remove('active');
                currentEditPlayerId = null;
            }}
            
            function showLoading(message) {{
                document.getElementById('loadingText').textContent = message || 'Saving changes...';
                document.getElementById('loadingOverlay').classList.add('active');
            }}
            
            function confirmSave() {{
                if (currentEditPlayerId) {{
                    const form = document.getElementById('form-' + currentEditPlayerId);
                    const name = form.querySelector('input[name="name"]').value;
                    const phone = form.querySelector('input[name="phone"]').value;
                    
                    document.getElementById('editPlayerId').value = currentEditPlayerId;
                    document.getElementById('editPlayerName').value = name;
                    document.getElementById('editPlayerPhone').value = phone;
                    
                    // Close modal and show loading
                    closeSaveModal();
                    showLoading('Saving changes...');
                    
                    document.getElementById('editPlayerForm').submit();
                }}
            }}
            
            function showRemoveModal(playerId, playerName) {{
                currentRemovePlayerId = playerId;
                document.getElementById('removeModalText').textContent = 
                    'Are you sure you want to remove ' + playerName + ' from the league? Their historical scores will be preserved.';
                document.getElementById('removeModal').classList.add('active');
            }}
            
            function closeRemoveModal() {{
                document.getElementById('removeModal').classList.remove('active');
                currentRemovePlayerId = null;
            }}
            
            function confirmRemove() {{
                if (currentRemovePlayerId) {{
                    document.getElementById('removePlayerId').value = currentRemovePlayerId;
                    
                    // Close modal and show loading
                    closeRemoveModal();
                    showLoading('Removing player...');
                    
                    document.getElementById('removePlayerForm').submit();
                }}
            }}
            
            // Rename league functions
            function showRenameModal() {{
                const newName = document.getElementById('leagueDisplayName').value.trim();
                if (!newName) {{
                    alert('Please enter a league name');
                    return;
                }}
                document.getElementById('renameModalText').textContent = 
                    'Are you sure you want to rename this league to "' + newName + '"?';
                document.getElementById('renameModal').classList.add('active');
            }}
            
            function closeRenameModal() {{
                document.getElementById('renameModal').classList.remove('active');
            }}
            
            function confirmRename() {{
                const newName = document.getElementById('leagueDisplayName').value.trim();
                document.getElementById('renameDisplayName').value = newName;
                
                // Close modal and show loading
                closeRenameModal();
                showLoading('Renaming league...');
                
                document.getElementById('renameLeagueForm').submit();
            }}
            
            // Delete League functions
            const leagueNameToConfirm = "{league['display_name']}";
            
            function showDeleteLeagueModal() {{
                document.getElementById('deleteLeagueModal').classList.add('active');
                document.getElementById('deleteLeagueConfirmName').value = '';
                document.getElementById('confirmDeleteBtn').disabled = true;
                
                // Clear any previous error
                const existingError = document.getElementById('deleteNameError');
                if (existingError) existingError.remove();
                
                const input = document.getElementById('deleteLeagueConfirmName');
                input.style.borderColor = '';
                
                // Add input listener to show feedback as user types
                input.addEventListener('input', function() {{
                    const inputName = this.value.trim();
                    const matches = (inputName === leagueNameToConfirm);
                    document.getElementById('confirmDeleteBtn').disabled = !matches;
                    
                    // Show visual feedback
                    if (inputName.length > 0) {{
                        if (matches) {{
                            this.style.borderColor = '{COLORS['success']}';
                            const err = document.getElementById('deleteNameError');
                            if (err) err.remove();
                        }} else {{
                            this.style.borderColor = '{COLORS['error']}';
                            // Show hint if close but not exact
                            let errorMsg = document.getElementById('deleteNameError');
                            if (!errorMsg) {{
                                errorMsg = document.createElement('p');
                                errorMsg.id = 'deleteNameError';
                                errorMsg.style.color = '{COLORS['error']}';
                                errorMsg.style.fontSize = '0.85em';
                                errorMsg.style.marginTop = '4px';
                                this.parentNode.appendChild(errorMsg);
                            }}
                            if (leagueNameToConfirm.toLowerCase().startsWith(inputName.toLowerCase())) {{
                                errorMsg.textContent = 'Keep typing...';
                                errorMsg.style.color = '{COLORS['text_muted']}';
                            }} else {{
                                errorMsg.textContent = 'Name does not match';
                                errorMsg.style.color = '{COLORS['error']}';
                            }}
                        }}
                    }} else {{
                        this.style.borderColor = '';
                        const err = document.getElementById('deleteNameError');
                        if (err) err.remove();
                    }}
                }});
            }}
            
            function closeDeleteLeagueModal() {{
                document.getElementById('deleteLeagueModal').classList.remove('active');
            }}
            
            // Activate League functions
            function showActivateModal() {{
                document.getElementById('activateModal').classList.add('active');
                // Reset to passcode gate view
                document.getElementById('activatePasscodeGate').style.display = 'block';
                document.getElementById('activateSteps').style.display = 'none';
                document.getElementById('activatePasscode').value = '';
            }}
            
            function closeActivateModal() {{
                document.getElementById('activateModal').classList.remove('active');
            }}
            
            function checkActivatePasscode() {{
                const passcode = document.getElementById('activatePasscode').value;
                if (passcode === 'monkeybottom') {{
                    document.getElementById('activatePasscodeGate').style.display = 'none';
                    document.getElementById('activateSteps').style.display = 'block';
                    // Generate code phrase after unlocking
                    generateNewCode();
                }} else {{
                    alert('Incorrect passcode. Contact support for access.');
                }}
            }}
            
            function generateNewCode() {{
                fetch('/dashboard/league/{league['id']}/generate-code', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }}
                }})
                .then(response => response.json())
                .then(data => {{
                    if (data.success) {{
                        const codeEl = document.getElementById('verificationCode');
                        if (codeEl) {{
                            // For Discord, keep the /wordle-link prefix
                            const channelType = '{channel_type}';
                            if (channelType === 'discord') {{
                                codeEl.textContent = '/wordle-link ' + data.code;
                            }} else {{
                                codeEl.textContent = data.code;
                            }}
                        }}
                    }} else {{
                        alert('Error generating code: ' + data.error);
                    }}
                }})
                .catch(error => alert('Error: ' + error));
            }}
            
            function checkActivationStatus() {{
                fetch('/dashboard/league/{league['id']}/check-status')
                .then(response => response.json())
                .then(data => {{
                    if (data.active) {{
                        window.location.reload();
                    }} else {{
                        alert('League not yet activated. Make sure you\\'ve added the bot to your group and sent the verification code.');
                    }}
                }})
                .catch(error => alert('Error: ' + error));
            }}
            
            function confirmDeleteLeague() {{
                const inputName = document.getElementById('deleteLeagueConfirmName').value.trim();
                if (inputName !== leagueNameToConfirm) {{
                    // Show inline error message
                    const input = document.getElementById('deleteLeagueConfirmName');
                    input.style.borderColor = '{COLORS['error']}';
                    
                    // Show/create error message
                    let errorMsg = document.getElementById('deleteNameError');
                    if (!errorMsg) {{
                        errorMsg = document.createElement('p');
                        errorMsg.id = 'deleteNameError';
                        errorMsg.style.color = '{COLORS['error']}';
                        errorMsg.style.fontSize = '0.85em';
                        errorMsg.style.marginTop = '4px';
                        input.parentNode.appendChild(errorMsg);
                    }}
                    errorMsg.textContent = 'League name does not match. Please type "' + leagueNameToConfirm + '" exactly.';
                    
                    // Shake the input
                    input.style.animation = 'shake 0.5s';
                    setTimeout(() => input.style.animation = '', 500);
                    return;
                }}
                
                closeDeleteLeagueModal();
                showLoading('Deleting league...');
                
                // Submit delete request
                fetch('/dashboard/league/{league['id']}/delete', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }}
                }})
                .then(response => response.json())
                .then(data => {{
                    if (data.success) {{
                        window.location.href = '/dashboard?message=' + encodeURIComponent('League deleted successfully');
                    }} else {{
                        hideLoading();
                        alert('Error deleting league: ' + data.error);
                    }}
                }})
                .catch(error => {{
                    hideLoading();
                    alert('Error deleting league: ' + error);
                }});
            }}
            
            // AI Settings functions
            const severityLabels = ['Savage 🔥', 'Spicy 🌶️', 'Playful 😄', 'Gentle 💚'];
            const severityNames = ['Savage', 'Spicy', 'Playful', 'Gentle'];
            const originalAISettings = {{
                perfect: {str(league.get('ai_perfect_score_congrats', False)).lower()},
                failure: {str(league.get('ai_failure_roast', True)).lower()},
                sunday: {str(league.get('ai_sunday_race_update', True)).lower()},
                daily: {str(league.get('ai_daily_loser_roast', False)).lower()},
                severity: {league.get('ai_message_severity', 2)},
                perfect_score_severity: {league.get('ai_perfect_score_severity', 2)},
                failure_roast_severity: {league.get('ai_failure_roast_severity', 2)},
                daily_loser_severity: {league.get('ai_daily_loser_severity', 2)}
            }};
            
            // Track what's actually saved to DB (updated when message config saves)
            const savedToDbSettings = {{
                perfect_score_severity: {league.get('ai_perfect_score_severity', 2)},
                failure_roast_severity: {league.get('ai_failure_roast_severity', 2)},
                daily_loser_severity: {league.get('ai_daily_loser_severity', 2)}
            }};
            
            // Player data for config modal
            const players = {str([{'id': p['id'], 'name': p['name']} for p in players])};
            
            // Message config state
            let currentMessageType = null;
            let messagePlayerSettings = {str(player_ai_settings).replace('True', 'true').replace('False', 'false').replace('None', 'null')};
            // Track which player settings have been saved to DB (to avoid showing as pending in main save)
            let savedPlayerSettings = JSON.parse(JSON.stringify(messagePlayerSettings));
            
            function openMessageConfig(messageType, title) {{
                currentMessageType = messageType;
                document.getElementById('messageConfigTitle').textContent = 'Configure: ' + title;
                
                // Set severity slider to current value
                const severityKey = messageType + '_severity';
                const currentSeverity = originalAISettings[severityKey] || 2;
                document.getElementById('configSeverity').value = currentSeverity;
                updateConfigSeverityLabel(currentSeverity);
                
                // Build player list
                const playerList = document.getElementById('playerConfigList');
                playerList.innerHTML = '';
                
                players.forEach(player => {{
                    const settings = messagePlayerSettings[messageType + '_' + player.id] || {{enabled: true, severity: null}};
                    const div = document.createElement('div');
                    div.className = 'player-config-item';
                    div.innerHTML = `
                        <input type="checkbox" id="player_${{player.id}}_enabled" ${{settings.enabled ? 'checked' : ''}}>
                        <span class="player-name">${{player.name}}</span>
                        <select id="player_${{player.id}}_severity">
                            <option value="" ${{settings.severity === null ? 'selected' : ''}}>Default</option>
                            <option value="1" ${{settings.severity === 1 ? 'selected' : ''}}>Savage 🔥</option>
                            <option value="2" ${{settings.severity === 2 ? 'selected' : ''}}>Spicy 🌶️</option>
                            <option value="3" ${{settings.severity === 3 ? 'selected' : ''}}>Playful 😄</option>
                            <option value="4" ${{settings.severity === 4 ? 'selected' : ''}}>Gentle 💚</option>
                        </select>
                    `;
                    playerList.appendChild(div);
                }});
                
                // Set initial preview
                updatePreview(currentSeverity);
                
                document.getElementById('messageConfigModal').classList.add('active');
            }}
            
            function closeMessageConfig() {{
                document.getElementById('messageConfigModal').classList.remove('active');
                currentMessageType = null;
            }}
            
            // Example messages for each message type and severity
            const toneExamples = {{
                'failure_roast': {{
                    1: '"Even autocorrect gave up on you today. 💀 Maybe try a coloring book instead?"',
                    2: '"Really said \\'six guesses? I don\\'t need any of them\\' 😂🔥 Someone get this man a vowel!"',
                    3: '"Aww, not your day huh? 😅 Tomorrow\\'s a fresh start - sleep with a dictionary under your pillow? 📖"',
                    4: '"Tough one today! 💪 Those tricky words get us all. Shake it off - you\\'ll crush it tomorrow! 🌟"'
                }},
                'perfect_score': {{
                    1: '"Nice score... IF it\\'s real 👀🤔 Should we check your browser history? Asking for a friend..."',
                    2: '"Impressive! 🤨 Either you\\'re a genius or... well, we won\\'t say it. But we\\'re thinking it 👀"',
                    3: '"Amazing score! 🎯 You\\'re on fire today... almost suspiciously so 😉🔥"',
                    4: '"WOW! Incredible score! 🎉🏆 You absolutely crushed it - pure skill! So impressed!"'
                }},
                'daily_loser': {{
                    1: '"Congrats on finding rock bottom! 💀 The word wasn\\'t THAT hard... for most people 🔥"',
                    2: '"Today\\'s biggest L goes to... 😂 Maybe Wordle just isn\\'t your thing?"',
                    3: '"Someone had to come in last! 😅 Hey, at least you showed up - that counts for something!"',
                    4: '"Not your best day, but we still love you! 💚 Tomorrow is a new opportunity!"'
                }}
            }};
            
            function updateConfigSeverityLabel(value) {{
                document.getElementById('configSeverityLabel').textContent = severityLabels[value - 1];
                updatePreview(value);
            }}
            
            function updatePreview(severity) {{
                if (currentMessageType && toneExamples[currentMessageType]) {{
                    document.getElementById('previewText').textContent = toneExamples[currentMessageType][severity];
                }}
            }}
            
            // Pending message config changes (stored until confirmed)
            let pendingConfigChanges = null;
            
            function showMessageConfigConfirm() {{
                if (!currentMessageType) return;
                
                // Build changes summary
                const changes = [];
                const severity = parseInt(document.getElementById('configSeverity').value);
                const originalSeverity = originalAISettings[currentMessageType + '_severity'] || 2;
                
                if (severity !== originalSeverity) {{
                    changes.push('🎚️ Default Tone: ' + severityLabels[severity - 1]);
                }}
                
                // Check player changes
                let enabledCount = 0;
                let playerChanges = [];
                players.forEach(player => {{
                    const enabled = document.getElementById('player_' + player.id + '_enabled').checked;
                    const severityVal = document.getElementById('player_' + player.id + '_severity').value;
                    const existingSettings = messagePlayerSettings[currentMessageType + '_' + player.id] || {{enabled: true, severity: null}};
                    
                    if (enabled !== existingSettings.enabled) {{
                        playerChanges.push(player.name + ': ' + (enabled ? '✅ Enabled' : '❌ Excluded'));
                    }}
                    if ((severityVal || null) !== (existingSettings.severity ? String(existingSettings.severity) : null)) {{
                        if (severityVal) {{
                            playerChanges.push(player.name + ': Tone → ' + severityLabels[parseInt(severityVal) - 1]);
                        }} else {{
                            playerChanges.push(player.name + ': Tone → Default');
                        }}
                    }}
                    if (enabled) enabledCount++;
                }});
                
                if (playerChanges.length > 0) {{
                    changes.push('👥 Player changes:<br>&nbsp;&nbsp;• ' + playerChanges.join('<br>&nbsp;&nbsp;• '));
                }}
                
                if (changes.length === 0) {{
                    alert('No changes to save.');
                    return;
                }}
                
                // Store pending changes
                pendingConfigChanges = {{
                    messageType: currentMessageType,
                    severity: severity,
                    enabledCount: enabledCount
                }};
                
                document.getElementById('messageConfigChanges').innerHTML = changes.join('<br>');
                document.getElementById('messageConfigConfirmModal').classList.add('active');
            }}
            
            function closeMessageConfigConfirm() {{
                document.getElementById('messageConfigConfirmModal').classList.remove('active');
                pendingConfigChanges = null;
            }}
            
            function confirmMessageConfig() {{
                if (!pendingConfigChanges) return;
                
                const messageType = pendingConfigChanges.messageType;
                const severity = pendingConfigChanges.severity;
                const enabledCount = pendingConfigChanges.enabledCount;
                
                // Build player settings for this message type
                const playerSettingsToSave = {{}};
                players.forEach(player => {{
                    const enabled = document.getElementById('player_' + player.id + '_enabled').checked;
                    const severityVal = document.getElementById('player_' + player.id + '_severity').value;
                    playerSettingsToSave[messageType + '_' + player.id] = {{
                        enabled: enabled,
                        severity: severityVal ? parseInt(severityVal) : null
                    }};
                }});
                
                // Show loading
                closeMessageConfigConfirm();
                closeMessageConfig();
                showLoading('Saving message settings...');
                
                // Save directly to database via AJAX
                fetch('/dashboard/league/{league['id']}/message-config', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json'
                    }},
                    body: JSON.stringify({{
                        message_type: messageType,
                        severity: severity,
                        player_settings: playerSettingsToSave
                    }})
                }})
                .then(response => response.json())
                .then(data => {{
                    hideLoading();
                    if (data.success) {{
                        // Update local state
                        originalAISettings[messageType + '_severity'] = severity;
                        // Also update savedToDbSettings so main save button knows this is already saved
                        savedToDbSettings[messageType + '_severity'] = severity;
                        document.getElementById(messageType + '_tone_label').textContent = severityNames[severity - 1];
                        
                        // Update player settings in memory
                        Object.assign(messagePlayerSettings, playerSettingsToSave);
                        // Also mark these as saved to DB
                        Object.assign(savedPlayerSettings, playerSettingsToSave);
                        
                        // Update players label
                        const playersLabel = enabledCount === players.length ? 'All' : enabledCount + '/' + players.length;
                        document.getElementById(messageType + '_players_label').textContent = playersLabel;
                        
                        // Show success toast
                        showToast('Message settings saved!');
                    }} else {{
                        alert('Error saving settings: ' + (data.error || 'Unknown error'));
                    }}
                }})
                .catch(error => {{
                    hideLoading();
                    alert('Error saving settings: ' + error);
                }});
            }}
            
            function showToast(message) {{
                const toast = document.createElement('div');
                toast.className = 'toast';
                toast.textContent = message;
                document.body.appendChild(toast);
                setTimeout(() => toast.classList.add('show'), 10);
                setTimeout(() => {{
                    toast.classList.remove('show');
                    setTimeout(() => toast.remove(), 300);
                }}, 2500);
            }}
            
            function hideLoading() {{
                document.getElementById('loadingOverlay').classList.remove('active');
            }}
            
            function saveAISettings() {{
                // Build changes summary
                const changes = [];
                const perfect = document.getElementById('ai_perfect_score').checked;
                const failure = document.getElementById('ai_failure_roast').checked;
                const sunday = document.getElementById('ai_sunday_race').checked;
                const daily = document.getElementById('ai_daily_loser').checked;
                
                if (perfect !== originalAISettings.perfect) {{
                    changes.push('🎯 Perfect Score Congrats: ' + (perfect ? 'ON' : 'OFF'));
                }}
                if (failure !== originalAISettings.failure) {{
                    changes.push('🔥 Failure Roast: ' + (failure ? 'ON' : 'OFF'));
                }}
                if (sunday !== originalAISettings.sunday) {{
                    changes.push('📊 Sunday Race Update: ' + (sunday ? 'ON' : 'OFF'));
                }}
                if (daily !== originalAISettings.daily) {{
                    changes.push('😈 Daily Loser Roast: ' + (daily ? 'ON' : 'OFF'));
                }}
                
                // Check for per-message severity changes (compare against what's saved to DB, not page load)
                if (originalAISettings.perfect_score_severity !== savedToDbSettings.perfect_score_severity) {{
                    changes.push('🎯 Perfect Score Tone: ' + severityNames[originalAISettings.perfect_score_severity - 1]);
                }}
                if (originalAISettings.failure_roast_severity !== savedToDbSettings.failure_roast_severity) {{
                    changes.push('🔥 Failure Roast Tone: ' + severityNames[originalAISettings.failure_roast_severity - 1]);
                }}
                if (originalAISettings.daily_loser_severity !== savedToDbSettings.daily_loser_severity) {{
                    changes.push('😈 Daily Loser Tone: ' + severityNames[originalAISettings.daily_loser_severity - 1]);
                }}
                
                // Check for player setting changes (compare against what's saved to DB)
                let hasUnsavedPlayerChanges = false;
                for (const key of Object.keys(messagePlayerSettings)) {{
                    if (JSON.stringify(messagePlayerSettings[key]) !== JSON.stringify(savedPlayerSettings[key])) {{
                        hasUnsavedPlayerChanges = true;
                        break;
                    }}
                }}
                if (hasUnsavedPlayerChanges) {{
                    changes.push('👥 Player settings updated');
                }}
                
                if (changes.length === 0) {{
                    alert('No changes to save.');
                    return;
                }}
                
                document.getElementById('aiSettingsChanges').innerHTML = changes.join('<br>');
                document.getElementById('aiSettingsModal').classList.add('active');
            }}
            
            function closeAISettingsModal() {{
                document.getElementById('aiSettingsModal').classList.remove('active');
            }}
            
            function confirmAISettings() {{
                // Get checkbox values
                document.getElementById('aiPerfectScoreInput').value = document.getElementById('ai_perfect_score').checked ? 'true' : 'false';
                document.getElementById('aiFailureRoastInput').value = document.getElementById('ai_failure_roast').checked ? 'true' : 'false';
                document.getElementById('aiSundayRaceInput').value = document.getElementById('ai_sunday_race').checked ? 'true' : 'false';
                document.getElementById('aiDailyLoserInput').value = document.getElementById('ai_daily_loser').checked ? 'true' : 'false';
                
                // Add per-message severity values
                document.getElementById('aiSeverityInput').value = JSON.stringify({{
                    perfect_score: originalAISettings.perfect_score_severity,
                    failure_roast: originalAISettings.failure_roast_severity,
                    daily_loser: originalAISettings.daily_loser_severity,
                    player_settings: messagePlayerSettings
                }});
                
                closeAISettingsModal();
                showLoading('Saving AI settings...');
                document.getElementById('aiSettingsForm').submit();
            }}
            
            // Close modals on escape key
            document.addEventListener('keydown', function(e) {{
                if (e.key === 'Escape') {{
                    closeSaveModal();
                    closeRemoveModal();
                    closeRenameModal();
                    closeAISettingsModal();
                    closeMessageConfig();
                    closeMessageConfigConfirm();
                }}
            }});
            
            // Close modals on overlay click
            document.getElementById('saveModal').addEventListener('click', function(e) {{
                if (e.target === this) closeSaveModal();
            }});
            document.getElementById('removeModal').addEventListener('click', function(e) {{
                if (e.target === this) closeRemoveModal();
            }});
            document.getElementById('renameModal').addEventListener('click', function(e) {{
                if (e.target === this) closeRenameModal();
            }});
            document.getElementById('aiSettingsModal').addEventListener('click', function(e) {{
                if (e.target === this) closeAISettingsModal();
            }});
        </script>
    </body>
    </html>
    """


def get_league_players(league_id):
    """Get all players in a league"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT id, name, phone_number, COALESCE(pending_activation, FALSE),
                   slack_user_id, discord_user_id
            FROM players
            WHERE league_id = %s AND active = TRUE
            ORDER BY name
        """, (league_id,))
        
        players = []
        for row in cursor.fetchall():
            players.append({
                'id': row[0],
                'name': row[1],
                'phone': row[2],
                'pending_activation': row[3],
                'slack_user_id': row[4],
                'discord_user_id': row[5]
            })
        return players
    finally:
        cursor.close()
        conn.close()


def get_ai_player_settings(league_id, message_type):
    """Get AI settings for all players in a league for a specific message type"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get all active players and their AI settings (if any)
        cursor.execute("""
            SELECT p.id, p.name, 
                   COALESCE(aps.enabled, TRUE) as enabled,
                   aps.severity_override
            FROM players p
            LEFT JOIN ai_player_settings aps 
                ON p.id = aps.player_id 
                AND aps.league_id = %s 
                AND aps.message_type = %s
            WHERE p.league_id = %s AND p.active = TRUE
            ORDER BY p.name
        """, (league_id, message_type, league_id))
        
        players = []
        for row in cursor.fetchall():
            players.append({
                'id': row[0],
                'name': row[1],
                'enabled': row[2],
                'severity_override': row[3]  # NULL means use default
            })
        return players
    except Exception as e:
        logging.error(f"Error getting AI player settings: {e}")
        return []
    finally:
        cursor.close()
        conn.close()

def get_league_info(league_id):
    """Get league information including AI messaging settings and channel type"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT id, name, display_name, twilio_conversation_sid,
                   ai_perfect_score_congrats, ai_failure_roast, 
                   ai_sunday_race_update, ai_daily_loser_roast,
                   ai_message_severity,
                   ai_perfect_score_severity, ai_failure_roast_severity, ai_daily_loser_severity,
                   slug, channel_type, slack_channel_id, discord_channel_id, verification_code
            FROM leagues
            WHERE id = %s
        """, (league_id,))
        
        row = cursor.fetchone()
        if row:
            return {
                'id': row[0],
                'name': row[1],
                'display_name': row[2],
                'conversation_sid': row[3],
                'ai_perfect_score_congrats': row[4] if row[4] is not None else False,
                'ai_failure_roast': row[5] if row[5] is not None else True,
                'ai_sunday_race_update': row[6] if row[6] is not None else True,
                'ai_daily_loser_roast': row[7] if row[7] is not None else False,
                'ai_message_severity': row[8] if row[8] is not None else 2,
                'ai_perfect_score_severity': row[9] if row[9] is not None else 2,
                'ai_failure_roast_severity': row[10] if row[10] is not None else 2,
                'ai_daily_loser_severity': row[11] if row[11] is not None else 2,
                'slug': row[12],
                'channel_type': row[13] or 'sms',
                'slack_channel_id': row[14],
                'discord_channel_id': row[15],
                'verification_code': row[16]
            }
        return None
    finally:
        cursor.close()
        conn.close()
