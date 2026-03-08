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

def get_user_menu_html(user_name, user_email, show_dashboard_link=False, user_role='user'):
    """Return the user icon dropdown menu HTML"""
    dashboard_link = f'<a href="/dashboard">Dashboard</a>' if show_dashboard_link else ''
    admin_link = f'<a href="/admin/dashboard" style="color: {COLORS["accent_orange"]};">Admin</a>' if user_role == 'admin' else ''
    return f'''
        <div class="user-menu">
            <div class="user-menu-btn" onclick="toggleUserMenu(event)">
                <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M12 12c2.7 0 4.8-2.1 4.8-4.8S14.7 2.4 12 2.4 7.2 4.5 7.2 7.2 9.3 12 12 12zm0 2.4c-3.2 0-9.6 1.6-9.6 4.8v2.4h19.2v-2.4c0-3.2-6.4-4.8-9.6-4.8z"/></svg>
            </div>
            <div class="user-dropdown" id="userDropdown">
                <div class="user-dropdown-name">{user_email}</div>
                {dashboard_link}
                {admin_link}
                <a href="/dashboard/profile">Profile</a>
                <a href="/auth/logout" class="logout-link">Logout</a>
            </div>
        </div>
    '''


def get_user_menu_script():
    """Return the JS for toggling the user dropdown"""
    return '''
        function toggleUserMenu(e) {
            e.stopPropagation();
            document.getElementById('userDropdown').classList.toggle('active');
        }
        document.addEventListener('click', function(e) {
            var dd = document.getElementById('userDropdown');
            if (dd && !e.target.closest('.user-menu')) dd.classList.remove('active');
        });
    '''


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
            justify-content: flex-end;
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
        .user-menu {{
            position: relative;
        }}
        .user-menu-btn {{
            background: {COLORS['bg_card']};
            border: 1px solid #444;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            transition: border-color 0.2s, background 0.2s;
        }}
        .user-menu-btn:hover {{ border-color: {COLORS['accent']}; background: {COLORS['bg_dark']}; }}
        .user-menu-btn svg {{ width: 20px; height: 20px; fill: {COLORS['text']}; }}
        .user-dropdown {{
            display: none;
            position: absolute;
            top: 48px;
            right: 0;
            background: {COLORS['bg_card']};
            border: 1px solid #444;
            border-radius: 10px;
            min-width: 180px;
            box-shadow: 0 8px 24px rgba(0,0,0,0.4);
            z-index: 1000;
            overflow: hidden;
        }}
        .user-dropdown.active {{ display: block; }}
        .user-dropdown a {{
            display: block;
            padding: 14px 20px;
            color: {COLORS['text']};
            text-decoration: none;
            font-size: 0.95em;
            transition: background 0.15s;
        }}
        .user-dropdown a:hover {{ background: {COLORS['bg_dark']}; }}
        .user-dropdown a.logout-link {{ color: {COLORS['accent_orange']}; border-top: 1px solid #333; }}
        .user-dropdown-name {{
            padding: 12px 20px;
            color: {COLORS['text_muted']};
            font-size: 0.85em;
            border-bottom: 1px solid #333;
        }}
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
    
    league_list_html = ""
    if leagues:
        for league in leagues:
            ct = league.get('channel_type', 'sms')
            if ct == 'sms':
                channel_icon = f'<span title="SMS" style="display:inline-flex;align-items:center;background:#4CAF5020;color:#4CAF50;padding:2px 8px;border-radius:10px;font-size:0.75em;font-weight:600;margin-left:8px;vertical-align:middle;">&#9993; SMS</span>'
            elif ct == 'slack':
                channel_icon = f'<span title="Slack" style="display:inline-flex;align-items:center;background:#E01E5A20;color:#E01E5A;padding:2px 8px;border-radius:10px;font-size:0.75em;font-weight:600;margin-left:8px;vertical-align:middle;">&#9830; Slack</span>'
            elif ct == 'discord':
                channel_icon = f'<span title="Discord" style="display:inline-flex;align-items:center;background:#5865F220;color:#5865F2;padding:2px 8px;border-radius:10px;font-size:0.75em;font-weight:600;margin-left:8px;vertical-align:middle;">&#9670; Discord</span>'
            else:
                channel_icon = ''
            league_list_html += f"""
            <div style="display: flex; justify-content: space-between; align-items: center; padding: 12px 16px; background: {COLORS['bg_dark']}; border-radius: 8px; margin-bottom: 8px;">
                <div>
                    <strong style="color: {COLORS['text']};">{league['display_name']}</strong>
                    {channel_icon}
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
                    {get_user_menu_html(user['name'], user['email'], show_dashboard_link=True, user_role=user.get('role', 'user'))}
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
            {get_user_menu_script()}
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
        if is_active:
            status_text = '✓ Active'
        else:
            status_text = '⚠ Inactive' if channel_type == 'sms' else '⚠ Setup Required'
        
        # Build subtitle based on channel type
        if channel_type == 'slack' and league.get('channel_name'):
            meta_text = f"Channel: #{league['channel_name']}"
        elif channel_type == 'discord' and league.get('channel_name'):
            meta_text = f"Channel: #{league['channel_name']}"
        else:
            meta_text = ""
        
        meta_html = f'<div class="meta">{meta_text}</div>' if meta_text else ''
        
        return f"""
        <div class="league-card">
            <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                <h3>{league['display_name']}</h3>
                <span style="background: {status_color}; color: #000; padding: 3px 8px; border-radius: 10px; font-size: 0.7em; font-weight: 600; white-space: nowrap;">{status_text}</span>
            </div>
            {meta_html}
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
                    {get_user_menu_html(user['name'], user['email'], user_role=user.get('role', 'user'))}
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
            {get_user_menu_script()}
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
                    {get_user_menu_html(user['name'], user['email'], show_dashboard_link=True, user_role=user.get('role', 'user'))}
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
            {get_user_menu_script()}
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


def generate_player_revert_html(league, alltime_player_reverts):
    """Generate HTML for individual player revert buttons"""
    if not alltime_player_reverts:
        return ''
    
    html = ''
    for pr in alltime_player_reverts:
        html += f'''<div style="background: {COLORS['success']}15; border: 1px solid {COLORS['success']}; padding: 10px 12px; border-radius: 6px; margin-top: 8px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
            <div>
                <span style="color: {COLORS['success']}; font-weight: 600; font-size: 0.9em;">↩️ {pr['player_name']}</span>
                <span style="color: {COLORS['text_muted']}; font-size: 0.8em; margin-left: 8px;">Reset: {pr['reset_at']} · {pr['score_count']} scores</span>
            </div>
            <form method="POST" action="/dashboard/league/{league['id']}/revert-alltime-player" style="display:inline;">
                <input type="hidden" name="player_id" value="{pr['player_id']}">
                <button type="button" class="btn btn-small" style="background: {COLORS['success']}; color: white; font-size: 0.8em; padding: 4px 10px;" onclick="revertPlayer(this, '{pr['player_name']}', {pr['score_count']})">Revert</button>
            </form>
        </div>'''
    return html


def _render_players_section(league, players, player_rows, channel_type, identifier_label, identifier_placeholder, identifier_empty, is_chat_platform):
    """Render the Players section with optional Division Mode UI"""
    division_mode = league.get('division_mode', False)
    division_confirmed = league.get('division_confirmed_at') is not None
    division_locked = league.get('division_locked', False)
    league_id = league['id']
    
    # Division toggle onclick logic
    if division_mode:
        toggle_onclick = f"showDivisionOffModal(event, {str(division_locked).lower()})"
    else:
        # Show confirmation modal before enabling division mode
        toggle_onclick = "showEnableDivisionModal(event)"
    
    toggle_class = "division-toggle active" if division_mode else "division-toggle"
    
    # Player content: either division view or normal view
    if division_mode:
        player_content = _render_division_players(league, players, is_chat_platform)
    else:
        player_content = f'<div class="player-list">{player_rows}</div>'
    
    return f'''
    <div class="card section">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; margin-bottom: 16px;">
            <h2 style="margin: 0;">👥 Players ({len(players)})</h2>
            <div style="display: flex; align-items: center; gap: 12px;">
                <form method="POST" action="/dashboard/league/{league_id}/division-toggle" id="divisionToggleForm" style="display: inline;">
                    <label style="display: flex; align-items: center; gap: 8px; cursor: pointer; user-select: none;">
                        <span style="font-size: 0.85em; color: {COLORS['text_muted']};">Division Mode</span>
                        <div class="{toggle_class}" onclick="{toggle_onclick}">
                            <div class="division-toggle-knob"></div>
                        </div>
                    </label>
                </form>
            </div>
        </div>
        {player_content}
    </div>
    '''


def _render_division_players(league, players, is_chat_platform):
    """Render players in two division zones with drag-and-drop locked behind Edit button"""
    league_id = league['id']
    division_locked = league.get('division_locked', False)
    division_confirmed = league.get('division_confirmed_at') is not None
    
    identifier_empty = 'No phone'
    if is_chat_platform:
        identifier_empty = ''
    
    div1_players = [p for p in players if p.get('division') == 1]
    div2_players = [p for p in players if p.get('division') == 2]
    unassigned = [p for p in players if p.get('division') is None]
    
    def player_chip(player):
        pid = player['id']
        name = player['name']
        immunity = player.get('division_immunity', False)
        
        # Immunity highlight colors
        if immunity and player.get('division') == 1:
            bg = f"{COLORS['accent']}30"
            border = COLORS['accent']
            badge = f'<span style="font-size: 0.7em; color: {COLORS["accent"]}; margin-left: 6px;">IMMUNE</span>'
        elif immunity and player.get('division') == 2:
            bg = f"{COLORS['accent_orange']}30"
            border = COLORS['accent_orange']
            badge = f'<span style="font-size: 0.7em; color: {COLORS["accent_orange"]}; margin-left: 6px;">RELEGATED</span>'
        else:
            bg = COLORS['bg_dark']
            border = "transparent"
            badge = ""
        
        # Phone / identifier display
        phone = player.get('phone', '') or ''
        identifier_value = phone if not is_chat_platform else (player.get('slack_user_id') or player.get('discord_user_id') or '')
        identifier_display = phone or identifier_empty
        
        # Escape values for JavaScript
        name_escaped = name.replace("'", "&#39;").replace('"', "&quot;")
        identifier_escaped = identifier_value.replace("'", "&#39;").replace('"', "&quot;")
        
        # Per-player edit button (always visible, opens edit modal for name/phone)
        edit_btn = f'''<button onclick="editPlayer('{pid}', '{name_escaped}', '{identifier_escaped}')" 
            style="background: none; border: none; color: {COLORS['text_muted']}; cursor: pointer; padding: 4px 8px; font-size: 1.1em;"
            title="Edit player">✏️</button>'''
        
        # Drag handle (only visible in rearrange mode, hidden by default)
        drag_handle = f'<span class="div-drag-handle" style="color: {COLORS["text_muted"]}; font-size: 0.9em; cursor: grab; display: none; padding: 0 4px;">&#x2630;</span>'
        
        return f'''<div class="division-player" data-player-id="{pid}"
            style="background: {bg}; border: 1px solid {border}; border-radius: 8px; padding: 10px 14px; 
            margin-bottom: 6px; display: flex; align-items: center; justify-content: space-between;"
            ondragstart="dragStart(event)" ondragend="dragEnd(event)">
            <div style="flex: 1; min-width: 0; overflow: hidden;">
                <div style="font-weight: 500; color: {COLORS['text']};">{name}{badge}</div>
                <div style="color: {COLORS['text_muted']}; font-size: 0.9em; overflow: hidden; text-overflow: ellipsis;">{identifier_display}</div>
            </div>
            <div style="display: flex; gap: 4px; align-items: center;">
                {edit_btn}
                {drag_handle}
            </div>
        </div>'''
    
    div1_html = "".join(player_chip(p) for p in div1_players)
    div2_html = "".join(player_chip(p) for p in div2_players)
    
    if not div1_players:
        div1_html = f'<p style="color: {COLORS["text_muted"]}; text-align: center; padding: 20px;">Drag players here</p>'
    if not div2_players:
        div2_html = f'<p style="color: {COLORS["text_muted"]}; text-align: center; padding: 20px;">Drag players here</p>'
    
    # Locked message
    locked_msg = ""
    if division_locked:
        locked_msg = f'''<div style="background: {COLORS['bg_dark']}; padding: 10px 14px; border-radius: 8px; margin-bottom: 12px; border-left: 3px solid {COLORS['accent_orange']};">
            <p style="margin: 0; color: {COLORS['text_muted']}; font-size: 0.85em;">
                Divisions are locked. A week has been completed. Use <strong>Reset Season for Divisions</strong> to rearrange players (all weekly wins will be erased).
            </p>
        </div>'''
    
    # Confirm button (only show before confirmation)
    confirm_btn = ""
    if not division_confirmed:
        confirm_btn = f'''<div style="margin-top: 16px; text-align: center;">
            <button type="button" class="btn btn-primary" onclick="showFinalizeConfirmModal()" style="padding: 10px 24px;">
                Confirm Division Mode
            </button>
        </div>'''
    
    # Unified button bar for division management (same size, black text)
    btn_style = f'padding: 8px 16px; font-size: 0.85em; font-weight: 600; border: none; border-radius: 6px; cursor: pointer; color: #000; min-width: 140px; text-align: center;'
    
    edit_divisions_btn = ""
    if division_confirmed and not division_locked:
        edit_divisions_btn = f'''<button type="button" id="editDivisionsBtn" 
            style="background: {COLORS['accent']}; {btn_style}"
            onclick="showEditDivisionsModal()">Edit Divisions</button>'''
    
    done_editing_btn = f'''<button type="button" id="doneEditingDivisionsBtn" 
        style="background: {COLORS['accent_orange']}; {btn_style} display: none;"
        onclick="exitDivisionEditMode()">Done Editing</button>'''
    
    reset_btn = ""
    if division_confirmed:
        reset_btn = f'''<button type="button" id="resetDivisionsBtn"
            style="background: {COLORS['accent_orange']}; {btn_style}"
            onclick="showDivisionResetModal()">Reset Season</button>'''
    
    return f'''
    {locked_msg}
    <div style="display: flex; justify-content: flex-end; gap: 8px; margin-bottom: 10px; flex-wrap: wrap;">
        {edit_divisions_btn}
        {done_editing_btn}
        {reset_btn}
    </div>
    <div style="display: flex; flex-direction: column; gap: 16px;">
        <!-- Division I -->
        <div class="division-zone" id="division-1" data-division="1"
            ondragover="dragOver(event)" ondrop="dropPlayer(event)" ondragenter="dragEnter(event)" ondragleave="dragLeave(event)"
            style="border: 2px dashed {COLORS['accent']}50; border-radius: 10px; padding: 12px; min-height: 80px; transition: border-color 0.2s, background 0.2s;">
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 10px;">
                <span style="font-weight: 700; color: {COLORS['accent']}; font-size: 0.95em;">DIVISION I</span>
                <span style="color: {COLORS['text_muted']}; font-size: 0.8em;">({len(div1_players)} players)</span>
            </div>
            <div class="division-player-list" id="div1-players">
                {div1_html}
            </div>
        </div>
        
        <!-- Division II -->
        <div class="division-zone" id="division-2" data-division="2"
            ondragover="dragOver(event)" ondrop="dropPlayer(event)" ondragenter="dragEnter(event)" ondragleave="dragLeave(event)"
            style="border: 2px dashed {COLORS['accent_orange']}50; border-radius: 10px; padding: 12px; min-height: 80px; transition: border-color 0.2s, background 0.2s;">
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 10px;">
                <span style="font-weight: 700; color: {COLORS['accent_orange']}; font-size: 0.95em;">DIVISION II</span>
                <span style="color: {COLORS['text_muted']}; font-size: 0.8em;">({len(div2_players)} players)</span>
            </div>
            <div class="division-player-list" id="div2-players">
                {div2_html}
            </div>
        </div>
    </div>
    {confirm_btn}
    '''


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
    ai_monday_checked = 'checked' if league.get('ai_monday_recap') else ''
    
    # Get reset/revert statuses
    try:
        from league_reset import get_season_revert_status, get_season_winners_revert_status, get_alltime_revert_status, get_all_player_revert_statuses, ensure_reset_snapshots_table
        ensure_reset_snapshots_table()
        season_revert = get_season_revert_status(league['id'])
        season_winners_revert = get_season_winners_revert_status(league['id'])
        alltime_all_revert = get_alltime_revert_status(league['id'])
        alltime_player_reverts = get_all_player_revert_statuses(league['id'])
    except Exception:
        season_revert = {'can_revert': False, 'reset_at': None, 'message': None}
        season_winners_revert = {'can_revert': False, 'reset_at': None, 'message': None}
        alltime_all_revert = {'can_revert': False, 'reset_at': None, 'message': None}
        alltime_player_reverts = []
    
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
    is_chat_platform = channel_type in ('slack', 'discord')
    for player in players:
        pending_badge = f'<span style="background: {COLORS["accent_orange"]}; color: #000; padding: 2px 6px; border-radius: 8px; font-size: 0.7em; font-weight: 600; margin-left: 8px;">PENDING</span>' if player.get('pending_activation') else ''
        
        # Get the appropriate identifier based on channel type
        if channel_type == 'slack':
            identifier_value = player.get('slack_user_id') or ''
            identifier_display = ''
        elif channel_type == 'discord':
            identifier_value = player.get('discord_user_id') or ''
            identifier_display = ''
        else:
            identifier_value = player.get('phone') or ''
            identifier_display = player.get('phone') or identifier_empty
        
        # For Slack/Discord: read-only player (only Remove allowed)
        if is_chat_platform:
            player_rows += f"""
            <div style="background: {COLORS['bg_dark']}; border-radius: 8px; margin-bottom: 8px; padding: 12px 16px; display: flex; align-items: center; justify-content: space-between;" id="player-{player['id']}">
                <span style="font-weight: 500; color: {COLORS['text']};">{player['name']}{pending_badge}</span>
                <button type="button" class="btn btn-danger btn-small" style="padding: 4px 12px; margin-right: 4px;" onclick="showRemoveModal({player['id']}, '{player['name']}')" title="Remove player">Remove</button>
            </div>
            """
        else:
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
                            <input type="text" name="name" value="{player['name']}" class="edit-input" placeholder="Name" maxlength="14">
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
            
            /* Division Mode styles */
            .division-toggle {{
                width: 44px;
                height: 24px;
                background: #555;
                border-radius: 12px;
                position: relative;
                cursor: pointer;
                transition: background 0.3s;
            }}
            .division-toggle.active {{
                background: {COLORS['accent']};
            }}
            .division-toggle-knob {{
                width: 20px;
                height: 20px;
                background: white;
                border-radius: 50%;
                position: absolute;
                top: 2px;
                left: 2px;
                transition: transform 0.3s;
            }}
            .division-toggle.active .division-toggle-knob {{
                transform: translateX(20px);
            }}
            .division-zone.drag-over {{
                border-color: {COLORS['accent']} !important;
                background: {COLORS['accent']}10 !important;
            }}
            .division-player {{
                touch-action: none;
            }}
            .division-player.dragging {{
                opacity: 0.4;
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
                    {get_user_menu_html(user['name'], user['email'], show_dashboard_link=True, user_role=user.get('role', 'user'))}
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
                    {f'<span style="color: {COLORS["text_muted"]};">Channel: #{league["channel_name"]}</span>' if league.get('channel_name') else ''}
                    <span style="background: {COLORS['bg_dark']}; color: {COLORS['text']}; padding: 4px 10px; border-radius: 12px; font-size: 0.8em;">
                        {'📱 SMS' if channel_type == 'sms' else '💬 Slack' if channel_type == 'slack' else '🎮 Discord'}
                    </span>
                    <span style="background: {'#2ECC71' if (league.get('conversation_sid') if channel_type == 'sms' else league.get('slack_channel_id') if channel_type == 'slack' else league.get('discord_channel_id')) else COLORS['accent_orange']}; color: #000; padding: 4px 10px; border-radius: 12px; font-size: 0.8em; font-weight: 600;">
                        {('✓ Active' if (league.get('conversation_sid') if channel_type == 'sms' else league.get('slack_channel_id') if channel_type == 'slack' else league.get('discord_channel_id')) else ('⚠ Inactive' if channel_type == 'sms' else '⚠ Setup Required'))}
                    </span>
                    {f'<button type="button" class="btn btn-small" style="background: {COLORS["accent"]}; color: #000; padding: 6px 12px;" onclick="showActivateModal()">{'Activate' if channel_type == 'sms' else 'Connect Channel'}</button>' if not (league.get('conversation_sid') if channel_type == 'sms' else league.get('slack_channel_id') if channel_type == 'slack' else league.get('discord_channel_id')) else ''}
                    {f'<a href="https://app.wordplayleague.com/leagues/{league["slug"]}" target="_blank" style="color: {COLORS["accent"]}; font-size: 0.9em;">app.wordplayleague.com/leagues/{league["slug"]}</a>' if league.get('slug') else ''}
                </div>
                {f"""
                <div style="margin-top: 16px; padding: 12px; background: {COLORS['bg_dark']}; border-radius: 8px; border-left: 3px solid {COLORS['accent']};">
                    <p style="margin: 0 0 8px 0; color: {COLORS['text']}; font-weight: 600;">📋 How to Submit Scores</p>
                    <p style="margin: 0; color: {COLORS['text_muted']}; font-size: 0.9em;">Players type <code style="background: {COLORS['bg_card']}; padding: 2px 6px; border-radius: 4px;">/wordplay</code> and paste their full Wordle share (with emoji pattern).</p>
                </div>
                """ if channel_type == 'discord' and league.get('discord_channel_id') else ''}
                {f"""
                <div style="margin-top: 16px; padding: 16px; background: {COLORS['accent_orange']}15; border: 1px solid {COLORS['accent_orange']}50; border-radius: 8px;">
                    <p style="margin: 0 0 12px 0; color: {COLORS['text']}; font-weight: 600;">📋 Setup Steps to Connect Your Slack Channel</p>
                    {'<p style="margin: 0 0 8px 0; color: ' + COLORS['text_muted'] + '; font-size: 0.9em;">✅ <span style="color: #2ECC71; font-weight: 500;">WordPlay League app is installed in your workspace</span></p>' if league.get('slack_team_id') else '<p style="margin: 0 0 8px 0; color: ' + COLORS['text_muted'] + '; font-size: 0.9em;"><strong>1.</strong> Click <strong>Connect Channel</strong> above and install the WordPlay League app to your Slack workspace.</p>'}
                    <p style="margin: 0 0 8px 0; color: {COLORS['text_muted']}; font-size: 0.9em;"><strong>{'1' if league.get('slack_team_id') else '2'}.</strong> In your Slack channel, type <code style="background: {COLORS['bg_card']}; padding: 2px 6px; border-radius: 4px;">/invite @WordPlayLeague</code> to add the bot.</p>
                    <p style="margin: 0 0 8px 0; color: {COLORS['text_muted']}; font-size: 0.9em;"><strong>{'2' if league.get('slack_team_id') else '3'}.</strong> Click <strong>Connect Channel</strong> above to get a code phrase, then type it in the channel to activate.</p>
                    <p style="margin: 0; color: {COLORS['text_muted']}; font-size: 0.85em; font-style: italic;">💡 Lost your code phrase? Click <strong>Connect Channel</strong> again to generate a new one.</p>
                </div>
                """ if channel_type == 'slack' and not league.get('slack_channel_id') else ''}
                {f"""
                <div style="margin-top: 16px; padding: 16px; background: {COLORS['accent_orange']}15; border: 1px solid {COLORS['accent_orange']}50; border-radius: 8px;">
                    <p style="margin: 0 0 12px 0; color: {COLORS['text']}; font-weight: 600;">📋 Setup Steps to Connect Your Discord Channel</p>
                    <p style="margin: 0 0 8px 0; color: {COLORS['text_muted']}; font-size: 0.9em;"><strong>1.</strong> Click <strong>Connect Channel</strong> above to add the WordPlay League bot to your Discord server.</p>
                    <p style="margin: 0 0 8px 0; color: {COLORS['text_muted']}; font-size: 0.9em;"><strong>2.</strong> In your Discord channel, use <code style="background: {COLORS['bg_card']}; padding: 2px 6px; border-radius: 4px;">/wordle-link</code> followed by the code phrase to activate.</p>
                    <p style="margin: 0; color: {COLORS['text_muted']}; font-size: 0.85em; font-style: italic;">💡 Lost your code phrase? Click <strong>Connect Channel</strong> again to generate a new one.</p>
                </div>
                """ if channel_type == 'discord' and not league.get('discord_channel_id') else ''}
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
            {_render_players_section(league, players, player_rows, channel_type, identifier_label, identifier_placeholder, identifier_empty, is_chat_platform)}
            
            <!-- Add Player Section -->
            <div class="card section">
                <h2>➕ Add Player</h2>
                {f'<div style="background: {COLORS["accent_orange"]}20; border: 1px solid {COLORS["accent_orange"]}; color: {COLORS["text"]}; padding: 12px; border-radius: 8px; margin-bottom: 16px;"><strong>⚠️ Player Limit Reached:</strong> SMS leagues are limited to 9 players (Twilio group MMS maximum). Remove a player before adding a new one.</div>' if channel_type == 'sms' and len(players) >= 9 else ''}
                {'<p style="color: ' + COLORS['text_muted'] + '; margin-bottom: 12px; font-size: 0.9em;">Add players by name. Their ' + ('Slack' if channel_type == 'slack' else 'Discord') + ' account will be linked automatically when they post their first score.</p>' if channel_type in ('slack', 'discord') else ''}
                <form method="POST" action="/dashboard/league/{league['id']}/add-player" id="addPlayerForm" onsubmit="showLoading('Adding player...')" {f'style="opacity: 0.5; pointer-events: none;"' if channel_type == 'sms' and len(players) >= 9 else ''}>
                    {'<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">' if channel_type == 'sms' else '<div style="display: grid; grid-template-columns: 1fr; gap: 16px; max-width: 400px;">'}
                        <div class="form-group">
                            <label>Player Name</label>
                            <input type="text" name="name" required maxlength="14" placeholder="{'John Doe' if channel_type == 'sms' else 'Display Name (must match their ' + ('Slack' if channel_type == 'slack' else 'Discord') + ' name)'}" {f'disabled' if channel_type == 'sms' and len(players) >= 9 else ''}>
                        </div>
                        {f'<div class="form-group"><label>{identifier_label}</label><input type="text" name="identifier" required placeholder="{identifier_placeholder}" {"disabled" if len(players) >= 9 else ""}></div>' if channel_type == 'sms' else '<input type="hidden" name="identifier" value="">'}
                    </div>
                    <button type="submit" class="btn btn-primary" {f'disabled' if channel_type == 'sms' and len(players) >= 9 else ''}>Add Player</button>
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
                    
                    <div class="ai-toggle-item">
                        <div class="ai-toggle-header">
                            <label class="toggle-label">
                                <input type="checkbox" id="ai_monday_recap" {ai_monday_checked}>
                                <span class="toggle-text">
                                    <strong>📅 Monday Morning Recap</strong>
                                    <small>10am Monday recap: weekly winner, season clinch, streaks &amp; fun stats</small>
                                </span>
                            </label>
                        </div>
                        <div class="ai-toggle-meta">
                            <span class="tone-na">Tone: N/A (informational)</span>
                        </div>
                    </div>
                </div>
                
                <button type="button" class="btn btn-primary" onclick="saveAISettings()" style="margin-top: 16px;">Save AI Settings</button>
            </div>
            
            <!-- Data Reset & Revert -->
            <div class="card" style="border: 1px solid {COLORS['accent_orange']};">
                <h2 style="color: {COLORS['accent_orange']};">🔄 Data Reset &amp; Revert</h2>
                <p style="color: {COLORS['text_muted']}; margin-bottom: 20px;">Reset league data with the option to revert. Each reset type has its own grace period — once the grace period ends, the reset becomes permanent.</p>
                
                <!-- 1. Reset Current Season -->
                <div style="background: {COLORS['bg_dark']}; padding: 16px; border-radius: 8px; margin-bottom: 16px;">
                    <h3 style="margin: 0 0 8px 0; font-size: 1.05em;">📊 Reset Current Season Table</h3>
                    <p style="color: {COLORS['text_muted']}; font-size: 0.9em; margin-bottom: 12px;">
                        Clears all weekly winners in the current season, making it appear as a fresh season start.
                    </p>
                    <div style="background: {COLORS['bg_card']}; padding: 12px; border-radius: 6px; margin-bottom: 12px; border-left: 3px solid {COLORS['accent']};">
                        <p style="color: {COLORS['text_muted']}; font-size: 0.85em; margin: 0;">
                            <strong style="color: {COLORS['text']};">⏱️ Revert window:</strong> You can undo this reset until the next weekly winner is recorded (typically Monday). Once a new winner is added, the reset becomes permanent.
                        </p>
                    </div>
                    {'<div style="background: ' + COLORS['success'] + '15; border: 1px solid ' + COLORS['success'] + '; padding: 12px; border-radius: 6px; margin-bottom: 12px;"><p style="margin: 0 0 8px 0; color: ' + COLORS['success'] + '; font-weight: 600;">↩️ Revert Available</p><p style="color: ' + COLORS['text_muted'] + '; font-size: 0.85em; margin: 0 0 4px 0;">Reset on: ' + season_revert['reset_at'] + '</p><p style="color: ' + COLORS['text_muted'] + '; font-size: 0.85em; margin: 0 0 12px 0;">' + (season_revert['message'] or '') + '</p><form method="POST" action="/dashboard/league/' + str(league['id']) + '/revert-current-season" style="display:inline;"><button type="button" class="btn btn-small" style="background: ' + COLORS['success'] + '; color: white;" onclick="showResetModal(\'revertSeason\', \'Revert Current Season?\', \'This will restore all weekly winners that were cleared. The season table will return to its previous state.\', this.closest(\'form\'))">↩️ Revert Season Reset</button></form></div>' if season_revert['can_revert'] else ''}
                    <button type="button" class="btn btn-small" style="background: {COLORS['accent_orange']}; color: white;" onclick="showResetModal('resetSeason', '🔄 Reset Current Season Table?', 'This will clear all weekly winners in the current season. The season will appear as if it just started fresh.\\n\\nYou can revert this until a new weekly winner is recorded (Monday).', null, '/dashboard/league/{league['id']}/reset-current-season')">
                        Reset Current Season
                    </button>
                </div>
                
                <!-- 2. Reset Season Winners -->
                <div style="background: {COLORS['bg_dark']}; padding: 16px; border-radius: 8px; margin-bottom: 16px;">
                    <h3 style="margin: 0 0 8px 0; font-size: 1.05em;">🏆 Reset Season Winners</h3>
                    <p style="color: {COLORS['text_muted']}; font-size: 0.9em; margin-bottom: 12px;">
                        Clears all past season winners and resets the season counter back to Season 1. The current season's weekly winners are preserved.
                    </p>
                    <div style="background: {COLORS['bg_card']}; padding: 12px; border-radius: 6px; margin-bottom: 12px; border-left: 3px solid {COLORS['accent']};">
                        <p style="color: {COLORS['text_muted']}; font-size: 0.85em; margin: 0;">
                            <strong style="color: {COLORS['text']};">⏱️ Revert window:</strong> You can undo this reset as long as the current season is still in progress. Once a new season winner is crowned (a player reaches 4 weekly wins), the reset becomes permanent.
                        </p>
                    </div>
                    {'<div style="background: ' + COLORS['success'] + '15; border: 1px solid ' + COLORS['success'] + '; padding: 12px; border-radius: 6px; margin-bottom: 12px;"><p style="margin: 0 0 8px 0; color: ' + COLORS['success'] + '; font-weight: 600;">↩️ Revert Available</p><p style="color: ' + COLORS['text_muted'] + '; font-size: 0.85em; margin: 0 0 4px 0;">Reset on: ' + season_winners_revert['reset_at'] + '</p><p style="color: ' + COLORS['text_muted'] + '; font-size: 0.85em; margin: 0 0 12px 0;">' + (season_winners_revert['message'] or '') + '</p><form method="POST" action="/dashboard/league/' + str(league['id']) + '/revert-season-winners" style="display:inline;"><button type="button" class="btn btn-small" style="background: ' + COLORS['success'] + '; color: white;" onclick="showResetModal(\'revertSeasonWinners\', \'Revert Season Winners?\', \'This will restore all season winners and the season counter to their previous values.\', this.closest(\'form\'))">↩️ Revert Season Winners Reset</button></form></div>' if season_winners_revert['can_revert'] else ''}
                    <button type="button" class="btn btn-small" style="background: {COLORS['accent_orange']}; color: white;" onclick="showResetModal('resetSeasonWinners', '🔄 Reset Season Winners?', 'This will delete all season winners and reset the season counter to Season 1.\\n\\nThe current season\\'s weekly winners will be preserved.\\n\\nYou can revert this until a new season winner is crowned (someone reaches 4 weekly wins).', null, '/dashboard/league/{league['id']}/reset-season-winners')">
                        Reset Season Winners
                    </button>
                </div>
                
                <!-- 3. Reset All-Time Stats -->
                <div style="background: {COLORS['bg_dark']}; padding: 16px; border-radius: 8px;">
                    <h3 style="margin: 0 0 8px 0; font-size: 1.05em;">📈 Reset All-Time Stats</h3>
                    <p style="color: {COLORS['text_muted']}; font-size: 0.9em; margin-bottom: 12px;">
                        Clear all score history. Reset everyone at once, or pick a single player.
                    </p>
                    <div style="background: {COLORS['bg_card']}; padding: 12px; border-radius: 6px; margin-bottom: 12px; border-left: 3px solid {COLORS['accent']};">
                        <p style="color: {COLORS['text_muted']}; font-size: 0.85em; margin: 0;">
                            <strong style="color: {COLORS['text']};">⏱️ Revert window:</strong> All-time reverts are <strong>always available</strong>. When you revert, old scores are merged with any new scores recorded since the reset — nothing is lost.
                        </p>
                    </div>
                    
                    <!-- Reset All Players -->
                    {'<div style="background: ' + COLORS['success'] + '15; border: 1px solid ' + COLORS['success'] + '; padding: 12px; border-radius: 6px; margin-bottom: 12px;"><p style="margin: 0 0 8px 0; color: ' + COLORS['success'] + '; font-weight: 600;">↩️ Revert All Players Available</p><p style="color: ' + COLORS['text_muted'] + '; font-size: 0.85em; margin: 0 0 4px 0;">Reset on: ' + alltime_all_revert['reset_at'] + '</p><p style="color: ' + COLORS['text_muted'] + '; font-size: 0.85em; margin: 0 0 12px 0;">' + (alltime_all_revert['message'] or '') + '</p><form method="POST" action="/dashboard/league/' + str(league['id']) + '/revert-alltime-all" style="display:inline;"><button type="button" class="btn btn-small" style="background: ' + COLORS['success'] + '; color: white;" onclick="showResetModal(\'revertAlltimeAll\', \'Revert All-Time Stats?\', \'This will merge old scores back with any new scores recorded since the reset.\', this.closest(\'form\'))">↩️ Revert All Players</button></form></div>' if alltime_all_revert['can_revert'] else ''}
                    <button type="button" class="btn btn-small" style="background: {COLORS['accent_orange']}; color: white; margin-bottom: 12px;" onclick="showResetModal('resetAlltimeAll', '🔄 Reset All-Time Stats for ALL Players?', 'This will clear ALL score history for every player in the league.\\n\\nYou can always revert this — old scores will be merged with any new ones.', null, '/dashboard/league/{league['id']}/reset-alltime-all')">
                        Reset All Players
                    </button>
                    
                    <!-- Reset Single Player -->
                    <div style="border-top: 1px solid {COLORS['border']}; padding-top: 12px; margin-top: 4px;">
                        <p style="color: {COLORS['text']}; font-size: 0.9em; font-weight: 500; margin-bottom: 8px;">Reset a single player:</p>
                        <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
                            <select id="resetPlayerSelect" style="padding: 8px 12px; border-radius: 6px; border: 1px solid {COLORS['border']}; background: {COLORS['bg_card']}; color: {COLORS['text']}; font-size: 0.9em; min-width: 180px;">
                                <option value="">Select player...</option>
                                {''.join(f'<option value="{p["id"]}">{p["name"]}</option>' for p in players if p.get('active', True))}
                            </select>
                            <button type="button" class="btn btn-small" style="background: {COLORS['accent_orange']}; color: white;" onclick="resetSinglePlayer()">
                                Reset Player
                            </button>
                        </div>
                    </div>
                    
                    <!-- Individual Player Reverts -->
                    {generate_player_revert_html(league, alltime_player_reverts)}
                </div>
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
        
        <!-- Edit Player Modal (used in division mode) -->
        <div class="modal-overlay" id="editPlayerModal">
            <div class="modal">
                <h3>✏️ Edit Player</h3>
                <div class="form-group" style="margin-bottom: 12px;">
                    <label>Name</label>
                    <input type="text" id="editPlayerModalName" style="width: 100%;">
                </div>
                <div class="form-group" style="margin-bottom: 16px;">
                    <label>{identifier_label}</label>
                    <input type="text" id="editPlayerModalIdentifier" style="width: 100%;">
                </div>
                <div class="modal-actions">
                    <button type="button" class="btn btn-secondary btn-small" onclick="closeEditPlayerModal()">Cancel</button>
                    <button type="button" class="btn btn-danger btn-small" onclick="editPlayerRemove()">Remove</button>
                    <button type="button" class="btn btn-primary btn-small" onclick="editPlayerSave()">Save</button>
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
        
        <!-- Reset Confirmation Modal -->
        <div class="modal-overlay" id="resetModal">
            <div class="modal">
                <h3 id="resetModalTitle">Confirm Reset</h3>
                <p id="resetModalText" style="white-space: pre-line;"></p>
                <div class="modal-actions">
                    <button type="button" class="btn btn-secondary btn-small" onclick="closeResetModal()">Cancel</button>
                    <button type="button" class="btn btn-small" id="resetModalConfirmBtn" style="background: {COLORS['accent_orange']}; color: white;" onclick="confirmReset()">Yes, Reset</button>
                </div>
            </div>
        </div>
        
        <!-- Hidden forms for reset actions -->
        <form id="resetSeasonForm" method="POST" action="/dashboard/league/{league['id']}/reset-current-season" style="display:none;"></form>
        <form id="resetSeasonWinnersForm" method="POST" action="/dashboard/league/{league['id']}/reset-season-winners" style="display:none;"></form>
        <form id="resetAlltimeAllForm" method="POST" action="/dashboard/league/{league['id']}/reset-alltime-all" style="display:none;"></form>
        <form id="resetAlltimePlayerForm" method="POST" action="/dashboard/league/{league['id']}/reset-alltime-player" style="display:none;">
            <input type="hidden" name="player_id" id="resetAlltimePlayerId">
        </form>
        
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
            <input type="hidden" name="ai_monday_recap" id="aiMondayRecapInput">
            <input type="hidden" name="ai_message_severity" id="aiSeverityInput">
        </form>
        
        <script>
            {get_user_menu_script()}
            // Auto-hide alerts after 5 seconds
            setTimeout(function() {{
                document.querySelectorAll('.alert-success, .alert-error').forEach(function(alert) {{
                    alert.classList.add('fade-out');
                    setTimeout(function() {{ alert.remove(); }}, 500);
                }});
            }}, 5000);
            
            let currentEditPlayerId = null;
            let currentRemovePlayerId = null;
            let editPlayerModalId = null;
            
            function editPlayer(playerId, playerName, playerIdentifier) {{
                editPlayerModalId = playerId;
                document.getElementById('editPlayerModalName').value = playerName;
                document.getElementById('editPlayerModalIdentifier').value = playerIdentifier || '';
                document.getElementById('editPlayerModal').classList.add('active');
            }}
            
            function closeEditPlayerModal() {{
                document.getElementById('editPlayerModal').classList.remove('active');
                editPlayerModalId = null;
            }}
            
            function editPlayerSave() {{
                if (editPlayerModalId) {{
                    const name = document.getElementById('editPlayerModalName').value;
                    const identifier = document.getElementById('editPlayerModalIdentifier').value;
                    
                    document.getElementById('editPlayerId').value = editPlayerModalId;
                    document.getElementById('editPlayerName').value = name;
                    document.getElementById('editPlayerPhone').value = identifier;
                    
                    closeEditPlayerModal();
                    showLoading('Saving changes...');
                    document.getElementById('editPlayerForm').submit();
                }}
            }}
            
            function editPlayerRemove() {{
                if (editPlayerModalId) {{
                    const pid = editPlayerModalId;
                    const name = document.getElementById('editPlayerModalName').value;
                    closeEditPlayerModal();
                    showRemoveModal(pid, name);
                }}
            }}
            
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
                    const identifier = form.querySelector('input[name="identifier"]').value;
                    
                    document.getElementById('editPlayerId').value = currentEditPlayerId;
                    document.getElementById('editPlayerName').value = name;
                    document.getElementById('editPlayerPhone').value = identifier;
                    
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
                if (passcode === 'SlackTest182') {{
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
            
            // Reset & Revert functions
            let pendingResetForm = null;
            let pendingResetAction = null;
            
            function showResetModal(id, title, message, form, actionUrl) {{
                document.getElementById('resetModalTitle').textContent = title;
                document.getElementById('resetModalText').textContent = message;
                
                // Determine button style based on revert vs reset
                const confirmBtn = document.getElementById('resetModalConfirmBtn');
                if (id.startsWith('revert')) {{
                    confirmBtn.style.background = '{COLORS['success']}';
                    confirmBtn.textContent = 'Yes, Revert';
                }} else {{
                    confirmBtn.style.background = '{COLORS['accent_orange']}';
                    confirmBtn.textContent = 'Yes, Reset';
                }}
                
                if (form) {{
                    pendingResetForm = form;
                    pendingResetAction = null;
                }} else {{
                    pendingResetForm = null;
                    pendingResetAction = actionUrl;
                }}
                
                document.getElementById('resetModal').classList.add('active');
            }}
            
            function closeResetModal() {{
                document.getElementById('resetModal').classList.remove('active');
                pendingResetForm = null;
                pendingResetAction = null;
            }}
            
            function confirmReset() {{
                // Save references before closeResetModal nulls them
                const form = pendingResetForm;
                const action = pendingResetAction;
                closeResetModal();
                showLoading('Processing...');
                
                if (form) {{
                    form.submit();
                }} else if (action) {{
                    // Create and submit a form for the action URL
                    const newForm = document.createElement('form');
                    newForm.method = 'POST';
                    newForm.action = action;
                    document.body.appendChild(newForm);
                    newForm.submit();
                }}
            }}
            
            function resetSinglePlayer() {{
                const select = document.getElementById('resetPlayerSelect');
                const playerId = select.value;
                const playerName = select.options[select.selectedIndex].text;
                
                if (!playerId) {{
                    alert('Please select a player first.');
                    return;
                }}
                
                document.getElementById('resetAlltimePlayerId').value = playerId;
                showResetModal(
                    'resetPlayer',
                    '🔄 Reset All-Time Stats for ' + playerName + '?',
                    'This will clear ALL score history for ' + playerName + '.\\n\\nYou can always revert this — old scores will be merged with any new ones.',
                    document.getElementById('resetAlltimePlayerForm')
                );
            }}
            
            function revertPlayer(btn, playerName, scoreCount) {{
                const form = btn.closest('form');
                showResetModal(
                    'revertPlayer',
                    'Revert ' + playerName + '?',
                    'This will merge ' + scoreCount + ' old scores back with any new scores recorded since the reset.',
                    form
                );
            }}
            
            // AI Settings functions
            const severityLabels = ['Savage 🔥', 'Spicy 🌶️', 'Playful 😄', 'Gentle 💚'];
            const severityNames = ['Savage', 'Spicy', 'Playful', 'Gentle'];
            const originalAISettings = {{
                perfect: {str(league.get('ai_perfect_score_congrats', False)).lower()},
                failure: {str(league.get('ai_failure_roast', True)).lower()},
                sunday: {str(league.get('ai_sunday_race_update', True)).lower()},
                daily: {str(league.get('ai_daily_loser_roast', False)).lower()},
                monday: {str(league.get('ai_monday_recap', True)).lower()},
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
                const monday = document.getElementById('ai_monday_recap').checked;
                
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
                if (monday !== originalAISettings.monday) {{
                    changes.push('📅 Monday Morning Recap: ' + (monday ? 'ON' : 'OFF'));
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
                document.getElementById('aiMondayRecapInput').value = document.getElementById('ai_monday_recap').checked ? 'true' : 'false';
                
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
                    closeEditPlayerModal();
                }}
            }});
            
            // Close modals on overlay click
            document.getElementById('saveModal').addEventListener('click', function(e) {{
                if (e.target === this) closeSaveModal();
            }});
            document.getElementById('editPlayerModal').addEventListener('click', function(e) {{
                if (e.target === this) closeEditPlayerModal();
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
            
            // ============================================================
            // Division Mode: Drag and Drop (gated behind Edit mode)
            // ============================================================
            let draggedPlayer = null;
            let divisionEditMode = {'true' if not league.get('division_confirmed_at') else 'false'};
            // Pre-confirmation: always in edit mode so user can arrange freely
            
            // On page load, if pre-confirmation, enable dragging immediately
            if (divisionEditMode) {{
                setTimeout(function() {{ enterDivisionEditMode(true); }}, 100);
            }}
            
            function enterDivisionEditMode(silent) {{
                divisionEditMode = true;
                // Show drag handles, make players draggable
                document.querySelectorAll('.division-player').forEach(function(el) {{
                    el.setAttribute('draggable', 'true');
                    el.style.cursor = 'grab';
                    var handle = el.querySelector('.div-drag-handle');
                    if (handle) handle.style.display = 'inline';
                }});
                // Toggle buttons
                var editBtn = document.getElementById('editDivisionsBtn');
                var doneBtn = document.getElementById('doneEditingDivisionsBtn');
                if (editBtn) editBtn.style.display = 'none';
                if (doneBtn && !silent) doneBtn.style.display = 'inline-block';
            }}
            
            function exitDivisionEditMode() {{
                // Show confirmation modal before exiting
                const modal = document.getElementById('resetModal');
                document.getElementById('resetModalTitle').textContent = 'Division Changes Saved';
                document.getElementById('resetModalText').textContent = 
                    'Your division player assignments have been saved. Players are now locked from rearranging until you click Edit Divisions again.';
                const confirmBtn = document.getElementById('resetModalConfirmBtn');
                confirmBtn.textContent = 'OK';
                confirmBtn.style.background = '{COLORS['accent']}';
                confirmBtn.style.color = '#000';
                pendingResetForm = null;
                pendingResetAction = null;
                confirmBtn.onclick = function() {{
                    modal.classList.remove('active');
                    confirmBtn.onclick = function() {{ confirmReset(); }};
                    _finishExitDivisionEditMode();
                }};
                modal.classList.add('active');
            }}
            
            function _finishExitDivisionEditMode() {{
                divisionEditMode = false;
                document.querySelectorAll('.division-player').forEach(function(el) {{
                    el.removeAttribute('draggable');
                    el.style.cursor = 'default';
                    var handle = el.querySelector('.div-drag-handle');
                    if (handle) handle.style.display = 'none';
                }});
                var editBtn = document.getElementById('editDivisionsBtn');
                var doneBtn = document.getElementById('doneEditingDivisionsBtn');
                if (editBtn) editBtn.style.display = 'inline-block';
                if (doneBtn) doneBtn.style.display = 'none';
            }}
            
            function showEditDivisionsModal() {{
                const modal = document.getElementById('resetModal');
                document.getElementById('resetModalTitle').textContent = 'Edit Division Assignments';
                document.getElementById('resetModalText').textContent = 
                    'You can rearrange players between divisions until a week completes with weekly winners recorded in both divisions. ' +
                    'After that point, players will be locked in place unless you use "Reset Season for Divisions" (which erases all weekly wins for the current division season).';
                const confirmBtn = document.getElementById('resetModalConfirmBtn');
                confirmBtn.textContent = 'Edit Divisions';
                confirmBtn.style.background = '{COLORS['accent']}';
                confirmBtn.style.color = '#000';
                pendingResetForm = null;
                pendingResetAction = null;
                // Override confirm to enter edit mode, then restore default handler
                confirmBtn.onclick = function() {{
                    modal.classList.remove('active');
                    enterDivisionEditMode(false);
                    // Restore default handler for other modals
                    confirmBtn.onclick = function() {{ confirmReset(); }};
                }};
                modal.classList.add('active');
            }}
            
            function dragStart(e) {{
                if (!divisionEditMode) {{ e.preventDefault(); return; }}
                draggedPlayer = e.target.closest('.division-player');
                if (draggedPlayer) {{
                    draggedPlayer.classList.add('dragging');
                    e.dataTransfer.effectAllowed = 'move';
                    e.dataTransfer.setData('text/plain', draggedPlayer.dataset.playerId);
                }}
            }}
            
            function dragEnd(e) {{
                if (draggedPlayer) {{
                    draggedPlayer.classList.remove('dragging');
                    draggedPlayer = null;
                }}
                document.querySelectorAll('.division-zone').forEach(z => z.classList.remove('drag-over'));
            }}
            
            function dragOver(e) {{
                if (!divisionEditMode) return;
                e.preventDefault();
                e.dataTransfer.dropEffect = 'move';
            }}
            
            function dragEnter(e) {{
                if (!divisionEditMode) return;
                e.preventDefault();
                const zone = e.target.closest('.division-zone');
                if (zone) zone.classList.add('drag-over');
            }}
            
            function dragLeave(e) {{
                const zone = e.target.closest('.division-zone');
                if (zone && !zone.contains(e.relatedTarget)) {{
                    zone.classList.remove('drag-over');
                }}
            }}
            
            function dropPlayer(e) {{
                e.preventDefault();
                if (!divisionEditMode) return;
                const zone = e.target.closest('.division-zone');
                if (!zone || !draggedPlayer) return;
                
                zone.classList.remove('drag-over');
                const division = parseInt(zone.dataset.division);
                const playerId = draggedPlayer.dataset.playerId;
                
                // Move the DOM element
                const playerList = zone.querySelector('.division-player-list');
                const placeholder = playerList.querySelector('p');
                if (placeholder) placeholder.remove();
                playerList.appendChild(draggedPlayer);
                
                updateDivisionCounts();
                
                // Save to server
                fetch('/dashboard/league/{league['id']}/division-assign', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ player_id: parseInt(playerId), division: division }})
                }})
                .then(r => r.json())
                .then(data => {{
                    if (!data.success) {{
                        showToast('Error: ' + (data.error || 'Failed to move player'));
                        location.reload();
                    }}
                }})
                .catch(err => {{
                    showToast('Error moving player');
                    location.reload();
                }});
            }}
            
            function updateDivisionCounts() {{
                const div1 = document.querySelectorAll('#div1-players .division-player').length;
                const div2 = document.querySelectorAll('#div2-players .division-player').length;
                const div1Label = document.querySelector('#division-1 span:last-child');
                const div2Label = document.querySelector('#division-2 span:last-child');
                if (div1Label) div1Label.textContent = '(' + div1 + ' players)';
                if (div2Label) div2Label.textContent = '(' + div2 + ' players)';
            }}
            
            // Touch support for mobile drag-and-drop
            (function() {{
                let touchPlayer = null;
                let touchClone = null;
                let touchOffsetX = 0;
                let touchOffsetY = 0;
                
                document.addEventListener('touchstart', function(e) {{
                    if (!divisionEditMode) return;
                    const player = e.target.closest('.division-player[draggable]');
                    if (!player) return;
                    
                    touchPlayer = player;
                    const rect = player.getBoundingClientRect();
                    touchOffsetX = e.touches[0].clientX - rect.left;
                    touchOffsetY = e.touches[0].clientY - rect.top;
                    
                    touchClone = player.cloneNode(true);
                    touchClone.style.position = 'fixed';
                    touchClone.style.zIndex = '9999';
                    touchClone.style.width = rect.width + 'px';
                    touchClone.style.opacity = '0.8';
                    touchClone.style.pointerEvents = 'none';
                    document.body.appendChild(touchClone);
                    
                    player.classList.add('dragging');
                }}, {{ passive: true }});
                
                document.addEventListener('touchmove', function(e) {{
                    if (!touchClone) return;
                    e.preventDefault();
                    
                    const x = e.touches[0].clientX - touchOffsetX;
                    const y = e.touches[0].clientY - touchOffsetY;
                    touchClone.style.left = x + 'px';
                    touchClone.style.top = y + 'px';
                    
                    document.querySelectorAll('.division-zone').forEach(zone => {{
                        const r = zone.getBoundingClientRect();
                        if (e.touches[0].clientX >= r.left && e.touches[0].clientX <= r.right &&
                            e.touches[0].clientY >= r.top && e.touches[0].clientY <= r.bottom) {{
                            zone.classList.add('drag-over');
                        }} else {{
                            zone.classList.remove('drag-over');
                        }}
                    }});
                }}, {{ passive: false }});
                
                document.addEventListener('touchend', function(e) {{
                    if (!touchPlayer || !touchClone) return;
                    
                    const touch = e.changedTouches[0];
                    document.querySelectorAll('.division-zone').forEach(zone => {{
                        const r = zone.getBoundingClientRect();
                        if (touch.clientX >= r.left && touch.clientX <= r.right &&
                            touch.clientY >= r.top && touch.clientY <= r.bottom) {{
                            const division = parseInt(zone.dataset.division);
                            const playerId = touchPlayer.dataset.playerId;
                            const playerList = zone.querySelector('.division-player-list');
                            const placeholder = playerList.querySelector('p');
                            if (placeholder) placeholder.remove();
                            playerList.appendChild(touchPlayer);
                            updateDivisionCounts();
                            
                            fetch('/dashboard/league/{league['id']}/division-assign', {{
                                method: 'POST',
                                headers: {{ 'Content-Type': 'application/json' }},
                                body: JSON.stringify({{ player_id: parseInt(playerId), division: division }})
                            }})
                            .then(r => r.json())
                            .then(data => {{
                                if (!data.success) {{
                                    showToast('Error: ' + (data.error || 'Failed'));
                                    location.reload();
                                }}
                            }});
                        }}
                        zone.classList.remove('drag-over');
                    }});
                    
                    touchPlayer.classList.remove('dragging');
                    touchClone.remove();
                    touchPlayer = null;
                    touchClone = null;
                }});
            }})();
            
            // ============================================================
            // Division Mode: Modals
            // ============================================================
            function showEnableDivisionModal(event) {{
                if (event) event.preventDefault();
                const modal = document.getElementById('resetModal');
                document.getElementById('resetModalTitle').textContent = 'Enable Division Mode?';
                document.getElementById('resetModalText').textContent = 
                    'This will enable Division Mode and split players into two divisions. You can rearrange players before confirming. ' +
                    'The league page will not change until you click Confirm Division Mode.';
                const confirmBtn = document.getElementById('resetModalConfirmBtn');
                confirmBtn.textContent = 'Enable';
                confirmBtn.style.background = '{COLORS['accent']}';
                pendingResetForm = document.getElementById('divisionToggleForm');
                pendingResetAction = null;
                modal.classList.add('active');
            }}
            
            function showFinalizeConfirmModal() {{
                const modal = document.getElementById('resetModal');
                document.getElementById('resetModalTitle').textContent = 'Publish Divisions?';
                document.getElementById('resetModalText').textContent = 
                    'This will publish the division setup to your league page. Players will see the two divisions with their current assignments. ' +
                    'After a week completes, divisions become locked and cannot be turned off without resetting the season.';
                const confirmBtn = document.getElementById('resetModalConfirmBtn');
                confirmBtn.textContent = 'Publish';
                confirmBtn.style.background = '{COLORS['accent']}';
                pendingResetForm = null;
                pendingResetAction = '/dashboard/league/{league['id']}/division-confirm';
                modal.classList.add('active');
            }}
            
            function showDivisionOffModal(event, isLocked) {{
                if (event) event.preventDefault();
                const modal = document.getElementById('resetModal');
                document.getElementById('resetModalTitle').textContent = 'Turn Off Division Mode?';
                
                // Conditional message based on whether weeks have completed
                if (isLocked) {{
                    document.getElementById('resetModalText').textContent = 
                        'Divisions have completed at least one week. Turning off Division Mode will:\\n\\n' +
                        '• Reset the current season (all weekly winners will be cleared)\\n' +
                        '• Merge all players back into a single league\\n' +
                        '• Mark incomplete division seasons as "Closed"\\n' +
                        '• Past season winners will remain unchanged\\n\\n' +
                        'The league will continue with the higher season number from the two divisions.';
                }} else {{
                    document.getElementById('resetModalText').textContent = 
                        'This will disable Division Mode and restore players to a single league. Current weekly winners will remain.';
                }}
                
                const confirmBtn = document.getElementById('resetModalConfirmBtn');
                confirmBtn.textContent = 'Confirm';
                confirmBtn.style.background = '{COLORS['accent']}';
                pendingResetForm = document.getElementById('divisionToggleForm');
                pendingResetAction = null;
                modal.classList.add('active');
            }}
            
            function showDivisionLockedModal(event) {{
                if (event) event.preventDefault();
                const modal = document.getElementById('resetModal');
                document.getElementById('resetModalTitle').textContent = 'Division Mode is Locked';
                document.getElementById('resetModalText').textContent = 
                    'Divisions have already completed a week. You cannot turn off Division Mode without resetting. ' +
                    'Use "Reset Season for Divisions" to start fresh and rearrange players.';
                pendingResetForm = null;
                pendingResetAction = null;
                // Override confirm to just close
                modal.classList.add('active');
            }}
            
            function showDivisionResetModal() {{
                const modal = document.getElementById('resetModal');
                document.getElementById('resetModalTitle').textContent = 'Reset Season for Divisions?';
                document.getElementById('resetModalText').textContent = 
                    'This will wipe in-progress weekly wins for the current season and advance both divisions to a new season. ' +
                    'All completed season winners are preserved. ' +
                    'You will be able to rearrange players between divisions after this reset.';
                pendingResetForm = null;
                pendingResetAction = '/dashboard/league/{league['id']}/division-reset';
                modal.classList.add('active');
            }}
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
                   slack_user_id, discord_user_id,
                   division, division_immunity, division_joined_week
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
                'discord_user_id': row[5],
                'division': row[6],
                'division_immunity': row[7] or False,
                'division_joined_week': row[8]
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
                   slug, channel_type, slack_channel_id, discord_channel_id, verification_code,
                   slack_bot_token, slack_team_id, ai_monday_recap,
                   division_mode, division_confirmed_at, division_locked
            FROM leagues
            WHERE id = %s
        """, (league_id,))
        
        row = cursor.fetchone()
        if row:
            league_data = {
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
                'verification_code': row[16],
                'slack_bot_token': row[17],
                'slack_team_id': row[18],
                'ai_monday_recap': row[19] if row[19] is not None else True,
                'division_mode': row[20] or False,
                'division_confirmed_at': row[21],
                'division_locked': row[22] or False,
                'channel_name': None
            }
            
            # Look up Slack channel name if applicable
            if league_data['channel_type'] == 'slack' and league_data['slack_channel_id'] and league_data['slack_bot_token']:
                try:
                    from slack_integration import get_slack_channel_info
                    channel_info = get_slack_channel_info(league_data['slack_bot_token'], league_data['slack_channel_id'])
                    league_data['channel_name'] = channel_info.get('name')
                except Exception as e:
                    logging.error(f"Error fetching Slack channel name for league {league_id}: {e}")
            
            return league_data
        return None
    finally:
        cursor.close()
        conn.close()


def render_admin_dashboard(user, leagues):
    """Render the admin dashboard showing all leagues across all users"""
    
    # Build league rows with data attributes for sorting
    league_rows = ''
    for lg in leagues:
        # Determine active status
        channel_type = lg.get('channel_type') or 'sms'
        if channel_type == 'sms':
            is_active = lg.get('conversation_sid') is not None
        elif channel_type == 'slack':
            is_active = lg.get('slack_channel_id') is not None
        elif channel_type == 'discord':
            is_active = lg.get('discord_channel_id') is not None
        else:
            is_active = False
        
        status_color = COLORS['success'] if is_active else COLORS['error']
        status_text = 'Active' if is_active else 'Inactive'
        
        # Channel type badge color
        type_colors = {'sms': '#4CAF50', 'slack': '#E01E5A', 'discord': '#5865F2'}
        type_color = type_colors.get(channel_type, COLORS['text_muted'])
        type_label = channel_type.upper()
        
        # Format created date
        created_at = lg.get('created_at')
        if created_at:
            created_str = created_at.strftime('%b %d, %Y')
            created_sort = created_at.strftime('%Y%m%d%H%M%S')
        else:
            created_str = '-'
            created_sort = '00000000000000'
        
        league_rows += f'''
            <tr onclick="window.location='/admin/league/{lg['id']}'" style="cursor: pointer; transition: background 0.15s;"
                data-id="{lg['id']}" data-name="{lg['display_name']}" data-status="{'1' if is_active else '0'}"
                data-type="{channel_type}" data-created="{created_sort}" data-owner="{lg.get('owner_email', 'Unknown')}"
                data-players="{lg.get('player_count', 0)}"
                data-inbound="{lg.get('twilio_inbound', '-')}" data-outbound="{lg.get('twilio_outbound', '-')}" data-cost="0">
                <td class="col-id" style="padding: 14px 16px; border-bottom: 1px solid {COLORS['border']}; color: {COLORS['text_muted']}; font-size: 0.9em;">#{lg['id']}</td>
                <td class="col-name frozen-col" style="padding: 14px 16px; border-bottom: 1px solid {COLORS['border']}; font-weight: 500;">{lg['display_name']}</td>
                <td class="col-status" style="padding: 14px 16px; border-bottom: 1px solid {COLORS['border']};"><span style="color: {status_color}; font-weight: 500;">{status_text}</span></td>
                <td class="col-type" style="padding: 14px 16px; border-bottom: 1px solid {COLORS['border']};"><span style="background: {type_color}20; color: {type_color}; padding: 3px 10px; border-radius: 12px; font-size: 0.8em; font-weight: 600;">{type_label}</span></td>
                <td class="col-created" style="padding: 14px 16px; border-bottom: 1px solid {COLORS['border']}; color: {COLORS['text_muted']}; font-size: 0.9em;">{created_str}</td>
                <td class="col-owner" style="padding: 14px 16px; border-bottom: 1px solid {COLORS['border']}; color: {COLORS['text_muted']}; font-size: 0.9em;">{lg.get('owner_email', 'Unknown')}</td>
                <td class="col-players" style="padding: 14px 16px; border-bottom: 1px solid {COLORS['border']}; color: {COLORS['text_muted']}; font-size: 0.9em;">{lg.get('player_count', 0)}</td>
                <td class="col-inbound" style="padding: 14px 16px; border-bottom: 1px solid {COLORS['border']}; color: {COLORS['text_muted']}; font-size: 0.9em; text-align: center;">{lg.get('twilio_inbound', '-')}</td>
                <td class="col-outbound" style="padding: 14px 16px; border-bottom: 1px solid {COLORS['border']}; color: {COLORS['text_muted']}; font-size: 0.9em; text-align: center;">{lg.get('twilio_outbound', '-')}</td>
                <td class="col-cost" style="padding: 14px 16px; border-bottom: 1px solid {COLORS['border']}; color: {COLORS['text_muted']}; font-size: 0.9em; text-align: center;">-</td>
            </tr>
        '''
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Admin - WordPlayLeague.com</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            {get_base_styles()}
            .table-wrap {{
                position: relative;
                overflow-x: auto;
            }}
            .admin-table {{
                width: 100%;
                border-collapse: collapse;
                min-width: 800px;
            }}
            .admin-table th {{
                text-align: left;
                padding: 12px 16px;
                color: {COLORS['text_muted']};
                font-size: 0.85em;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                border-bottom: 2px solid {COLORS['border']};
                cursor: pointer;
                user-select: none;
                white-space: nowrap;
                position: relative;
            }}
            .admin-table th:hover {{
                color: {COLORS['accent']};
            }}
            .admin-table th .sort-arrow {{
                margin-left: 4px;
                font-size: 0.75em;
                opacity: 0.4;
            }}
            .admin-table th.sort-active .sort-arrow {{
                opacity: 1;
                color: {COLORS['accent']};
            }}
            .admin-table tbody tr:hover {{
                background: {COLORS['bg_dark']};
            }}
            /* Frozen League Name column */
            .frozen-col {{
                position: sticky;
                left: 0;
                z-index: 2;
                background: {COLORS['bg_card']};
            }}
            .admin-table tbody tr:hover .frozen-col {{
                background: {COLORS['bg_dark']};
            }}
            .frozen-col-header {{
                position: sticky;
                left: 0;
                z-index: 3;
                background: {COLORS['bg_card']};
            }}
            .stat-card {{
                background: {COLORS['bg_card']};
                border-radius: 10px;
                padding: 20px;
                border: 1px solid {COLORS['border']};
                text-align: center;
            }}
            .stat-number {{
                font-size: 2em;
                font-weight: 700;
                color: {COLORS['accent']};
            }}
            .stat-label {{
                color: {COLORS['text_muted']};
                font-size: 0.85em;
                margin-top: 4px;
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
                    {get_user_menu_html(user['name'], user['email'], show_dashboard_link=True, user_role=user.get('role', 'user'))}
                </div>
            </div>
            
            <a href="/dashboard" class="back-link">&larr; Back to Dashboard</a>
            
            <div class="card">
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
                    <div>
                        <h2 style="color: {COLORS['accent_orange']}; margin-bottom: 4px;">&#9881; Admin Dashboard</h2>
                        <p style="color: {COLORS['text_muted']}; margin: 0;">Monitor all leagues across every account.</p>
                    </div>
                    <a href="/admin/newsletter" style="background: {COLORS['accent_orange']}; color: #000; padding: 10px 20px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 0.9em;">📰 Newsletter</a>
                </div>
            </div>
            
            <!-- Stats Row -->
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 16px; margin-bottom: 24px;">
                <div class="stat-card">
                    <div class="stat-number">{len(leagues)}</div>
                    <div class="stat-label">Total Leagues</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{len([l for l in leagues if (l.get('conversation_sid') if (l.get('channel_type') or 'sms') == 'sms' else l.get('slack_channel_id') if (l.get('channel_type') or 'sms') == 'slack' else l.get('discord_channel_id'))])}</div>
                    <div class="stat-label">Active</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{len([l for l in leagues if (l.get('channel_type') or 'sms') == 'sms'])}</div>
                    <div class="stat-label">SMS</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{len([l for l in leagues if (l.get('channel_type') or 'sms') == 'slack'])}</div>
                    <div class="stat-label">Slack</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{len([l for l in leagues if (l.get('channel_type') or 'sms') == 'discord'])}</div>
                    <div class="stat-label">Discord</div>
                </div>
            </div>
            
            <!-- Leagues Table -->
            <div class="card" style="padding: 0;">
                <div class="table-wrap">
                    <table class="admin-table" id="leaguesTable">
                        <thead>
                            <tr>
                                <th data-sort="id" onclick="sortTable('id')">ID <span class="sort-arrow">&#9650;</span></th>
                                <th class="frozen-col-header" data-sort="name" onclick="sortTable('name')">League Name <span class="sort-arrow">&#9650;</span></th>
                                <th data-sort="status" onclick="sortTable('status')">Status <span class="sort-arrow">&#9650;</span></th>
                                <th data-sort="type" onclick="sortTable('type')">Type <span class="sort-arrow">&#9650;</span></th>
                                <th data-sort="created" onclick="sortTable('created')">Created <span class="sort-arrow">&#9650;</span></th>
                                <th data-sort="owner" onclick="sortTable('owner')">Owner <span class="sort-arrow">&#9650;</span></th>
                                <th data-sort="players" onclick="sortTable('players')">Players <span class="sort-arrow">&#9650;</span></th>
                                <th data-sort="inbound" onclick="sortTable('inbound')" style="text-align: center;">Inbound <span class="sort-arrow">&#9650;</span></th>
                                <th data-sort="outbound" onclick="sortTable('outbound')" style="text-align: center;">Outbound <span class="sort-arrow">&#9650;</span></th>
                                <th data-sort="cost" onclick="sortTable('cost')" style="text-align: center;">Cost <span class="sort-arrow">&#9650;</span></th>
                            </tr>
                        </thead>
                        <tbody>
                            {league_rows if league_rows else f'<tr><td colspan="10" style="padding: 24px; text-align: center; color: {COLORS["text_muted"]};">No leagues found</td></tr>'}
                        </tbody>
                        <tfoot>
                            <tr id="totalsRow" style="background-color: {COLORS['bg_card']}; border-top: 2px solid {COLORS['border']};">
                                <td colspan="7" style="padding: 14px 16px; font-weight: bold; color: {COLORS['text']}; text-align: right;">Totals</td>
                                <td class="total-inbound" style="padding: 14px 16px; font-weight: bold; color: #00E8DA; text-align: center;">...</td>
                                <td class="total-outbound" style="padding: 14px 16px; font-weight: bold; color: #00E8DA; text-align: center;">...</td>
                                <td class="total-cost" style="padding: 14px 16px; font-weight: bold; color: #FFA64D; text-align: center;">...</td>
                            </tr>
                        </tfoot>
                    </table>
                </div>
            </div>
        </div>
        
        <script>
            {get_user_menu_script()}
            
            // Sortable table logic
            var currentSort = '';
            var sortAsc = true;
            
            function sortTable(key) {{
                var table = document.getElementById('leaguesTable');
                var tbody = table.querySelector('tbody');
                var rows = Array.from(tbody.querySelectorAll('tr'));
                
                if (rows.length === 0) return;
                
                // Toggle direction if same column clicked again
                if (currentSort === key) {{
                    sortAsc = !sortAsc;
                }} else {{
                    currentSort = key;
                    sortAsc = true;
                }}
                
                // Update header arrows
                var ths = table.querySelectorAll('th');
                ths.forEach(function(th) {{
                    th.classList.remove('sort-active');
                    var arrow = th.querySelector('.sort-arrow');
                    if (arrow) arrow.innerHTML = '&#9650;';
                }});
                var activeTh = table.querySelector('th[data-sort="' + key + '"]');
                if (activeTh) {{
                    activeTh.classList.add('sort-active');
                    var arrow = activeTh.querySelector('.sort-arrow');
                    if (arrow) arrow.innerHTML = sortAsc ? '&#9650;' : '&#9660;';
                }}
                
                rows.sort(function(a, b) {{
                    var aVal = a.getAttribute('data-' + key) || '';
                    var bVal = b.getAttribute('data-' + key) || '';
                    
                    // Numeric sort for id, players, inbound, outbound, cost
                    if (key === 'id' || key === 'players' || key === 'inbound' || key === 'outbound' || key === 'cost') {{
                        aVal = parseFloat(aVal) || 0;
                        bVal = parseFloat(bVal) || 0;
                        return sortAsc ? aVal - bVal : bVal - aVal;
                    }}
                    if (key === 'status' || key === 'created') {{
                        // status: 0/1, created: YYYYMMDDHHMMSS
                        aVal = aVal.toString();
                        bVal = bVal.toString();
                        if (aVal < bVal) return sortAsc ? -1 : 1;
                        if (aVal > bVal) return sortAsc ? 1 : -1;
                        return 0;
                    }}
                    
                    // String sort for name, type, owner
                    aVal = aVal.toLowerCase();
                    bVal = bVal.toLowerCase();
                    if (aVal < bVal) return sortAsc ? -1 : 1;
                    if (aVal > bVal) return sortAsc ? 1 : -1;
                    return 0;
                }});
                
                rows.forEach(function(row) {{
                    tbody.appendChild(row);
                }});
            }}
            
            // Async Twilio usage loading
            (function() {{
                var inboundCells = document.querySelectorAll('.col-inbound');
                var outboundCells = document.querySelectorAll('.col-outbound');
                var costCells = document.querySelectorAll('.col-cost');
                // Show loading dots
                inboundCells.forEach(function(c) {{ if (c.tagName === 'TD') c.innerHTML = '<span style="color:#555;">...</span>'; }});
                outboundCells.forEach(function(c) {{ if (c.tagName === 'TD') c.innerHTML = '<span style="color:#555;">...</span>'; }});
                costCells.forEach(function(c) {{ if (c.tagName === 'TD') c.innerHTML = '<span style="color:#555;">...</span>'; }});
                
                fetch('/admin/api/twilio-usage')
                    .then(function(r) {{ return r.json(); }})
                    .then(function(data) {{
                        if (data.error) {{
                            inboundCells.forEach(function(c) {{ if (c.tagName === 'TD') c.textContent = '-'; }});
                            outboundCells.forEach(function(c) {{ if (c.tagName === 'TD') c.textContent = '-'; }});
                            costCells.forEach(function(c) {{ if (c.tagName === 'TD') c.textContent = '-'; }});
                            return;
                        }}
                        // Per-league inbound/outbound from Conversations API
                        var rows = document.querySelectorAll('#leaguesTable tbody tr');
                        rows.forEach(function(row) {{
                            var lid = row.getAttribute('data-id');
                            var usage = data.usage ? data.usage[lid] : null;
                            var inCell = row.querySelector('.col-inbound');
                            var outCell = row.querySelector('.col-outbound');
                            var costCell = row.querySelector('.col-cost');
                            if (usage && inCell && outCell) {{
                                inCell.textContent = usage.inbound;
                                var billed = (typeof usage.outbound_billed === 'number') ? usage.outbound_billed : usage.outbound;
                                outCell.textContent = billed;
                                row.setAttribute('data-inbound', usage.inbound);
                                row.setAttribute('data-outbound', billed);
                                // Estimate per-league cost (MMS rates, no static fees)
                                if (costCell && typeof usage.inbound === 'number') {{
                                    var leagueCost = (usage.inbound * 0.0165) + (billed * 0.022);
                                    costCell.textContent = '$' + leagueCost.toFixed(2);
                                    row.setAttribute('data-cost', leagueCost.toFixed(2));
                                }}
                            }} else if (inCell && outCell) {{
                                inCell.textContent = '-';
                                outCell.textContent = '-';
                                if (costCell) costCell.textContent = '-';
                            }}
                        }});
                        // Account-wide totals from Twilio Usage API (actual billed amounts)
                        var totals = data.account_total;
                        var ti = document.querySelector('.total-inbound');
                        var to2 = document.querySelector('.total-outbound');
                        var tc = document.querySelector('.total-cost');
                        if (totals) {{
                            if (ti) ti.textContent = totals.inbound;
                            if (to2) to2.textContent = totals.outbound;
                            if (tc) {{
                                var costStr = '$' + (totals.cost || 0).toFixed(2);
                                var bd = totals.breakdown;
                                if (bd) {{
                                    var tip = 'MMS Messages: $' + (bd.mms_messages || 0).toFixed(2) + '\\nCarrier Fees: $' + (bd.carrier_fees || 0).toFixed(2) + '\\nA2P Registration: $' + (bd.a2p_registration || 0).toFixed(2);
                                    tc.innerHTML = '<span title="' + tip + '" style="cursor:help;border-bottom:1px dotted #888;">' + costStr + '</span>';
                                }} else {{
                                    tc.textContent = costStr;
                                }}
                            }}
                        }}
                    }})
                    .catch(function() {{
                        inboundCells.forEach(function(c) {{ if (c.tagName === 'TD') c.textContent = '-'; }});
                        outboundCells.forEach(function(c) {{ if (c.tagName === 'TD') c.textContent = '-'; }});
                        costCells.forEach(function(c) {{ if (c.tagName === 'TD') c.textContent = '-'; }});
                        var ti = document.querySelector('.total-inbound');
                        var to2 = document.querySelector('.total-outbound');
                        var tc = document.querySelector('.total-cost');
                        if (ti) ti.textContent = '-';
                        if (to2) to2.textContent = '-';
                        if (tc) tc.textContent = '-';
                    }});
            }})();
        </script>
    </body>
    </html>
    """


def render_admin_league_detail(user, league):
    """Render the admin league detail view"""
    
    channel_type = league.get('channel_type') or 'sms'
    is_active = league.get('is_active', False)
    status_color = COLORS['success'] if is_active else COLORS['error']
    status_text = 'Active' if is_active else 'Inactive'
    
    type_colors = {'sms': '#4CAF50', 'slack': '#E01E5A', 'discord': '#5865F2'}
    type_color = type_colors.get(channel_type, COLORS['text_muted'])
    
    # Build player rows
    player_rows = ''
    for p in league.get('players', []):
        active_badge = f'<span style="color: {COLORS["success"]};">Active</span>' if p['active'] else f'<span style="color: {COLORS["error"]};">Removed</span>'
        identifier = p.get('phone') or p.get('slack_user_id') or p.get('discord_user_id') or '-'
        player_rows += f'''
            <tr>
                <td style="padding: 10px 14px; border-bottom: 1px solid {COLORS['border']};">{p['name']}</td>
                <td style="padding: 10px 14px; border-bottom: 1px solid {COLORS['border']}; color: {COLORS['text_muted']}; font-size: 0.9em;">{identifier}</td>
                <td style="padding: 10px 14px; border-bottom: 1px solid {COLORS['border']};">{active_badge}</td>
            </tr>
        '''
    
    # Public league URL
    public_url = f'https://app.wordplayleague.com/leagues/{league["slug"]}' if league.get('slug') else 'No slug'
    
    # Recent messages link
    recent_msgs_html = ''
    if channel_type == 'sms' and league.get('conversation_sid'):
        recent_msgs_html = f'''
            <div class="detail-row">
                <span class="detail-label">Recent Messages (SMS)</span>
                <span class="detail-value"><a href="/recent-messages/{league['id']}" target="_blank" style="color: {COLORS['accent']};">View Last 20 Messages</a></span>
            </div>
        '''
    
    # AI settings summary
    ai_features = []
    if league.get('ai_perfect_score'): ai_features.append('Perfect Score Congrats')
    if league.get('ai_failure_roast'): ai_features.append('Failure Roast')
    if league.get('ai_sunday_race'): ai_features.append('Sunday Race Update')
    if league.get('ai_daily_loser'): ai_features.append('Daily Loser Roast')
    if league.get('ai_monday_recap'): ai_features.append('Monday Recap')
    ai_summary = ', '.join(ai_features) if ai_features else 'None enabled'
    
    # Channel-specific detail rows
    channel_details = ''
    if channel_type == 'sms' and league.get('conversation_sid'):
        channel_details = f'''
            <div class="detail-row">
                <span class="detail-label">Conversation SID</span>
                <span class="detail-value" style="font-size: 0.85em;">{league.get('conversation_sid', '-')}</span>
            </div>
        '''
    elif channel_type == 'slack':
        channel_details = f'''
            <div class="detail-row">
                <span class="detail-label">Slack Team ID</span>
                <span class="detail-value" style="font-size: 0.85em;">{league.get('slack_team_id', '-')}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Slack Channel ID</span>
                <span class="detail-value" style="font-size: 0.85em;">{league.get('slack_channel_id', '-')}</span>
            </div>
        '''
    elif channel_type == 'discord':
        channel_details = f'''
            <div class="detail-row">
                <span class="detail-label">Discord Channel ID</span>
                <span class="detail-value" style="font-size: 0.85em;">{league.get('discord_channel_id', '-')}</span>
            </div>
        '''
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Admin - {league['display_name']} - WordPlayLeague.com</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            {get_base_styles()}
            .detail-row {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 12px 0;
                border-bottom: 1px solid {COLORS['border']};
            }}
            .detail-row:last-child {{ border-bottom: none; }}
            .detail-label {{
                color: {COLORS['text_muted']};
                font-size: 0.9em;
                min-width: 140px;
            }}
            .detail-value {{
                color: {COLORS['text']};
                font-weight: 500;
                text-align: right;
                word-break: break-all;
            }}
            .admin-table {{
                width: 100%;
                border-collapse: collapse;
            }}
            .admin-table th {{
                text-align: left;
                padding: 10px 14px;
                color: {COLORS['text_muted']};
                font-size: 0.85em;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                border-bottom: 2px solid {COLORS['border']};
            }}
            .admin-table tr:hover {{
                background: {COLORS['bg_dark']};
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
                    {get_user_menu_html(user['name'], user['email'], show_dashboard_link=True, user_role=user.get('role', 'user'))}
                </div>
            </div>
            
            <a href="/admin/dashboard" class="back-link">&larr; Back to Admin Dashboard</a>
            
            <!-- League Header -->
            <div class="card">
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
                    <div>
                        <h2 style="margin-bottom: 4px;">{league['display_name']}</h2>
                        <span style="color: {COLORS['text_muted']}; font-size: 0.9em;">League #{league['id']} &middot; {league.get('name', '')}</span>
                    </div>
                    <div style="display: flex; gap: 10px; align-items: center;">
                        <span style="color: {status_color}; font-weight: 600; font-size: 0.95em;">{status_text}</span>
                        <span style="background: {type_color}20; color: {type_color}; padding: 4px 12px; border-radius: 12px; font-size: 0.85em; font-weight: 600;">{channel_type.upper()}</span>
                    </div>
                </div>
            </div>
            
            <!-- League Details -->
            <div class="card">
                <h3 style="color: {COLORS['accent']}; margin-bottom: 16px;">League Details</h3>
                <div class="detail-row">
                    <span class="detail-label">League ID</span>
                    <span class="detail-value">#{league['id']}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Status</span>
                    <span class="detail-value" style="color: {status_color};">{status_text}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Channel Type</span>
                    <span class="detail-value">{channel_type.upper()}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Created</span>
                    <span class="detail-value">{league.get('created_at', 'Unknown')}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Created By</span>
                    <span class="detail-value">{league.get('owner_email', 'Unknown')}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Players</span>
                    <span class="detail-value">{league.get('player_count', 0)} active</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Public Page</span>
                    <span class="detail-value"><a href="{public_url}" target="_blank" style="color: {COLORS['accent']};">{public_url}</a></span>
                </div>
                {recent_msgs_html}
                <div class="detail-row">
                    <span class="detail-label">Slug</span>
                    <span class="detail-value">{league.get('slug', '-')}</span>
                </div>
                {channel_details}
            </div>
            
            <!-- AI Settings -->
            <div class="card">
                <h3 style="color: {COLORS['accent']}; margin-bottom: 16px;">AI Message Settings</h3>
                <div class="detail-row">
                    <span class="detail-label">Active Features</span>
                    <span class="detail-value">{ai_summary}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Severity Level</span>
                    <span class="detail-value">{league.get('ai_severity', 'N/A')}</span>
                </div>
            </div>
            
            <!-- Players -->
            <div class="card" style="padding: 0; overflow-x: auto;">
                <div style="padding: 16px 16px 0 16px;">
                    <h3 style="color: {COLORS['accent']}; margin-bottom: 4px;">Players ({league.get('player_count', 0)} active, {len(league.get('players', []))} total)</h3>
                </div>
                <table class="admin-table">
                    <thead>
                        <tr>
                            <th>Name</th>
                            <th>Identifier</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {player_rows if player_rows else f'<tr><td colspan="3" style="padding: 20px; text-align: center; color: {COLORS["text_muted"]};">No players</td></tr>'}
                    </tbody>
                </table>
            </div>
        </div>
        
        <script>
            {get_user_menu_script()}
        </script>
    </body>
    </html>
    """


def render_admin_newsletter(user, templates, recipients, selected_template='', sent_count=None, error=None):
    """Render the admin newsletter management page"""
    
    recipient_count = len(recipients)
    
    # Build template cards
    template_cards = ''
    for key, tmpl in templates.items():
        is_selected = key == selected_template
        border_color = COLORS['accent'] if is_selected else COLORS['border']
        bg = f"rgba(0, 232, 218, 0.05)" if is_selected else COLORS['bg_card']
        
        template_cards += f'''
        <div class="template-card" style="background: {bg}; border: 2px solid {border_color}; border-radius: 12px; padding: 20px; margin-bottom: 16px;">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 12px;">
                <div style="flex: 1; min-width: 200px;">
                    <h3 style="color: {COLORS['accent']}; margin: 0 0 6px;">{tmpl['name']}</h3>
                    <p style="color: {COLORS['text_muted']}; margin: 0 0 4px; font-size: 0.9em;">Subject: <strong style="color: {COLORS['text']};">{tmpl['subject']}</strong></p>
                </div>
                <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                    <a href="/admin/newsletter/preview/{key}" target="_blank" 
                       style="background: {COLORS['bg_dark']}; color: {COLORS['text']}; padding: 8px 16px; border-radius: 6px; text-decoration: none; font-size: 0.85em; font-weight: 600; border: 1px solid {COLORS['border']};">
                        👁 Preview
                    </a>
                    <form method="POST" action="/admin/newsletter/send-test" style="display: inline;">
                        <input type="hidden" name="template_key" value="{key}">
                        <button type="submit" style="background: {COLORS['accent_orange']}; color: #000; padding: 8px 16px; border-radius: 6px; font-size: 0.85em; font-weight: 600; border: none; cursor: pointer;">
                            📧 Send Test to Me
                        </button>
                    </form>
                    <form method="POST" action="/admin/newsletter/send" style="display: inline;" 
                          onsubmit="return confirm('Send this newsletter to ALL {recipient_count} recipients? This cannot be undone.');">
                        <input type="hidden" name="template_key" value="{key}">
                        <button type="submit" style="background: {COLORS['accent']}; color: #000; padding: 8px 16px; border-radius: 6px; font-size: 0.85em; font-weight: 600; border: none; cursor: pointer;">
                            🚀 Send to All ({recipient_count})
                        </button>
                    </form>
                </div>
            </div>
        </div>
        '''
    
    # Success / error banners
    banner = ''
    if sent_count is not None and not error:
        banner = f'<div style="background: rgba(46, 204, 113, 0.15); border: 1px solid #2ECC71; border-radius: 8px; padding: 14px 18px; margin-bottom: 20px; color: #2ECC71; font-weight: 500;">✅ Newsletter sent to {sent_count} recipient(s)!</div>'
    if error:
        banner = f'<div style="background: rgba(255, 92, 92, 0.15); border: 1px solid #ff5c5c; border-radius: 8px; padding: 14px 18px; margin-bottom: 20px; color: #ff5c5c; font-weight: 500;">{error}</div>'
    
    # Recipient list (collapsed)
    recipient_rows = ''
    for r in recipients[:50]:
        recipient_rows += f'''<tr>
            <td style="padding: 6px 14px; border-bottom: 1px solid {COLORS['border']}; color: {COLORS['text']};">{r['email']}</td>
            <td style="padding: 6px 14px; border-bottom: 1px solid {COLORS['border']}; color: {COLORS['text_muted']};">{r.get('first_name') or '-'}</td>
        </tr>'''
    
    more_text = f'<p style="color: {COLORS["text_muted"]}; font-size: 0.85em; padding: 10px 14px;">...and {recipient_count - 50} more</p>' if recipient_count > 50 else ''
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Newsletter - Admin - WordPlayLeague.com</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            {get_base_styles()}
            .template-card:hover {{
                border-color: {COLORS['accent']} !important;
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
                    {get_user_menu_html(user['name'], user['email'], show_dashboard_link=True, user_role=user.get('role', 'user'))}
                </div>
            </div>
            
            <a href="/admin/dashboard" class="back-link">&larr; Back to Admin Dashboard</a>
            
            {banner}
            
            <div class="card">
                <h2 style="color: {COLORS['accent_orange']};">📰 Newsletter</h2>
                <p style="color: {COLORS['text_muted']}; margin-bottom: 4px;">Send feature update emails to all registered users.</p>
                <p style="color: {COLORS['text_muted']}; font-size: 0.9em;">
                    <strong style="color: {COLORS['text']};">{recipient_count}</strong> verified users will receive the email.
                </p>
            </div>
            
            <!-- Templates -->
            <div class="card">
                <h3 style="color: {COLORS['accent']}; margin-bottom: 16px;">Available Templates</h3>
                {template_cards if template_cards else f'<p style="color: {COLORS["text_muted"]};">No templates available. Add templates in email_utils.py → get_newsletter_templates()</p>'}
            </div>
            
            <!-- Recipients -->
            <details style="margin-bottom: 24px;">
                <summary style="cursor: pointer; color: {COLORS['accent']}; font-weight: 600; padding: 12px 0;">View Recipients ({recipient_count})</summary>
                <div class="card" style="padding: 0; margin-top: 8px;">
                    <table style="width: 100%; border-collapse: collapse;">
                        <thead>
                            <tr>
                                <th style="text-align: left; padding: 10px 14px; color: {COLORS['text_muted']}; font-size: 0.85em; border-bottom: 2px solid {COLORS['border']};">Email</th>
                                <th style="text-align: left; padding: 10px 14px; color: {COLORS['text_muted']}; font-size: 0.85em; border-bottom: 2px solid {COLORS['border']};">First Name</th>
                            </tr>
                        </thead>
                        <tbody>
                            {recipient_rows}
                        </tbody>
                    </table>
                    {more_text}
                </div>
            </details>
        </div>
        
        <script>
            {get_user_menu_script()}
        </script>
    </body>
    </html>
    """
