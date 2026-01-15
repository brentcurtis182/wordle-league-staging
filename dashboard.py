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
}

def get_base_styles():
    """Return base CSS styles for all dashboard pages"""
    return f"""
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
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
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 20px 0;
            border-bottom: 1px solid #333;
            margin-bottom: 30px;
        }}
        .logo {{
            font-size: 1.5em;
            font-weight: bold;
            color: {COLORS['accent']};
        }}
        .logo span {{ color: {COLORS['accent_orange']}; }}
        .nav-links a {{
            color: {COLORS['text']};
            text-decoration: none;
            margin-left: 20px;
            padding: 8px 16px;
            border-radius: 6px;
            transition: background 0.2s;
        }}
        .nav-links a:hover {{ background: {COLORS['bg_card']}; }}
        .nav-links a.logout {{ color: {COLORS['accent_orange']}; }}
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
            border: 1px solid #333;
            transition: border-color 0.2s;
        }}
        .league-card:hover {{ border-color: {COLORS['accent']}; }}
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
        <title>Login - Wordplay League</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            {get_base_styles()}
            .auth-container {{
                max-width: 400px;
                margin: 80px auto;
                padding: 20px;
            }}
            .auth-card {{
                background: {COLORS['bg_card']};
                border-radius: 16px;
                padding: 40px;
                border: 1px solid #333;
            }}
            .auth-card h1 {{
                text-align: center;
                margin-bottom: 8px;
                color: {COLORS['accent']};
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
        </style>
    </head>
    <body>
        <div class="auth-container">
            <div class="auth-card">
                <h1>🎯 Wordplay League</h1>
                <p class="subtitle">Sign in to manage your leagues</p>
                
                {'<div class="alert alert-error">' + error + '</div>' if error else ''}
                {'<div class="alert alert-success">' + success + '</div>' if success else ''}
                
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
                
                <div class="auth-footer">
                    Don't have an account? <a href="/auth/register">Sign up</a>
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
        <title>Sign Up - Wordplay League</title>
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
                padding: 40px;
                border: 1px solid #333;
            }}
            .auth-card h1 {{
                text-align: center;
                margin-bottom: 8px;
                color: {COLORS['accent']};
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
        </style>
    </head>
    <body>
        <div class="auth-container">
            <div class="auth-card">
                <h1>🎯 Wordplay League</h1>
                <p class="subtitle">Sign Up</p>
                
                {'<div class="alert alert-error">' + error + '</div>' if error else ''}
                
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
    """Render the main dashboard"""
    league_cards = ""
    for league in leagues:
        wix_path = get_league_wix_url(league['id'])
        league_cards += f"""
        <div class="league-card">
            <h3>{league['display_name']}</h3>
            <div class="meta">ID: {league['id']} • Role: {league['role']}</div>
            <div class="actions">
                <a href="/dashboard/league/{league['id']}" class="btn btn-primary btn-small">Manage</a>
                <a href="https://www.wordplayleague.com/{wix_path}" target="_blank" class="btn btn-secondary btn-small">View</a>
            </div>
        </div>
        """
    
    if not leagues:
        league_cards = """
        <div class="card" style="text-align: center; padding: 40px;">
            <p style="color: #818384; margin-bottom: 20px;">You don't have any leagues yet.</p>
            <a href="/dashboard/create-league" class="btn btn-primary">Create Your First League</a>
        </div>
        """
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Dashboard - Wordplay League</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>{get_base_styles()}</style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="logo">🎯 Wordplay <span>League</span></div>
                <div class="nav-links">
                    <a href="/dashboard">Dashboard</a>
                    <a href="/auth/logout" class="logout">Logout</a>
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
            </div>
            
            <div class="league-grid">
                {league_cards}
            </div>
        </div>
    </body>
    </html>
    """


def render_league_management(user, league, players, message=None, error=None):
    """Render the league management page"""
    
    # Pre-compute AI settings checkbox states
    ai_perfect_checked = 'checked' if league.get('ai_perfect_score_congrats') else ''
    ai_failure_checked = 'checked' if league.get('ai_failure_roast') else ''
    ai_sunday_checked = 'checked' if league.get('ai_sunday_race_update') else ''
    ai_daily_checked = 'checked' if league.get('ai_daily_loser_roast') else ''
    
    player_rows = ""
    for player in players:
        player_rows += f"""
        <div class="player-item" id="player-{player['id']}">
            <!-- Read-only view -->
            <div class="player-view" id="view-{player['id']}">
                <div class="player-info">
                    <div class="name">{player['name']}</div>
                    <div class="phone">{player['phone'] or 'No phone'}</div>
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
                        <input type="tel" name="phone" value="{player['phone'] or ''}" class="edit-input" placeholder="Phone">
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
            }}
            .player-view {{
                display: flex;
                justify-content: space-between;
                align-items: center;
            }}
            .player-info {{
                flex: 1;
            }}
            .player-info .name {{
                font-weight: 500;
                color: {COLORS['text']};
            }}
            .player-info .phone {{
                color: {COLORS['text_muted']};
                font-size: 0.9em;
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
            }}
            .edit-input {{
                padding: 10px 12px;
                border-radius: 6px;
                border: 1px solid #444;
                background: {COLORS['bg_card']};
                color: {COLORS['text']};
                font-size: 0.95em;
            }}
            .edit-input:focus {{
                outline: none;
                border-color: {COLORS['accent']};
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
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="logo">🎯 Wordplay <span>League</span></div>
                <div class="nav-links">
                    <a href="/dashboard">Dashboard</a>
                    <a href="/auth/logout" class="logout">Logout</a>
                </div>
            </div>
            
            <a href="/dashboard" class="back-link">← Back to Dashboard</a>
            
            {'<div class="alert alert-success">' + message + '</div>' if message else ''}
            {'<div class="alert alert-error">' + error + '</div>' if error else ''}
            
            <div class="card">
                <h2>⚙️ {league['display_name']}</h2>
                <p style="color: {COLORS['text_muted']};">League ID: {league['id']}</p>
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
                <form method="POST" action="/dashboard/league/{league['id']}/add-player">
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
                        <div class="form-group">
                            <label>Player Name</label>
                            <input type="text" name="name" required placeholder="John Doe">
                        </div>
                        <div class="form-group">
                            <label>Phone Number</label>
                            <input type="tel" name="phone" required placeholder="18585551234">
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
                        <label class="toggle-label">
                            <input type="checkbox" id="ai_perfect_score" {ai_perfect_checked}>
                            <span class="toggle-text">
                                <strong>🎯 Perfect Score Congrats</strong>
                                <small>Celebrate 1/6 or 2/6 scores with playful "cheating" jokes and whale emojis</small>
                            </span>
                        </label>
                    </div>
                    
                    <div class="ai-toggle-item">
                        <label class="toggle-label">
                            <input type="checkbox" id="ai_failure_roast" {ai_failure_checked}>
                            <span class="toggle-text">
                                <strong>🔥 Failure Roast</strong>
                                <small>Roast players who fail with X/6 (savage but playful)</small>
                            </span>
                        </label>
                    </div>
                    
                    <div class="ai-toggle-item">
                        <label class="toggle-label">
                            <input type="checkbox" id="ai_sunday_race" {ai_sunday_checked}>
                            <span class="toggle-text">
                                <strong>📊 Sunday Race Update</strong>
                                <small>10am Sunday summary showing who can still win the week</small>
                            </span>
                        </label>
                    </div>
                    
                    <div class="ai-toggle-item">
                        <label class="toggle-label">
                            <input type="checkbox" id="ai_daily_loser" {ai_daily_checked}>
                            <span class="toggle-text">
                                <strong>😈 Daily Loser Roast</strong>
                                <small>When all players post, roast the worst scorer using the Wordle word</small>
                            </span>
                        </label>
                    </div>
                </div>
                
                <button type="button" class="btn btn-primary" onclick="saveAISettings()" style="margin-top: 16px;">Save AI Settings</button>
            </div>
            
            <!-- View League Link -->
            <div class="card">
                <h2>🔗 Public League Page</h2>
                <p style="margin-bottom: 16px; color: {COLORS['text_muted']};">Share this link with your league members:</p>
                <a href="https://www.wordplayleague.com/{get_league_wix_url(league['id'])}" target="_blank" class="btn btn-secondary">
                    View Public Page →
                </a>
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
                background: {COLORS['bg_main']};
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
                margin-top: 2px;
                accent-color: {COLORS['accent']};
                cursor: pointer;
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
        </form>
        
        <script>
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
            
            // AI Settings functions
            function saveAISettings() {{
                // Get checkbox values
                document.getElementById('aiPerfectScoreInput').value = document.getElementById('ai_perfect_score').checked ? 'true' : 'false';
                document.getElementById('aiFailureRoastInput').value = document.getElementById('ai_failure_roast').checked ? 'true' : 'false';
                document.getElementById('aiSundayRaceInput').value = document.getElementById('ai_sunday_race').checked ? 'true' : 'false';
                document.getElementById('aiDailyLoserInput').value = document.getElementById('ai_daily_loser').checked ? 'true' : 'false';
                
                showLoading('Saving AI settings...');
                document.getElementById('aiSettingsForm').submit();
            }}
            
            // Close modals on escape key
            document.addEventListener('keydown', function(e) {{
                if (e.key === 'Escape') {{
                    closeSaveModal();
                    closeRemoveModal();
                    closeRenameModal();
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
            SELECT id, name, phone_number
            FROM players
            WHERE league_id = %s AND active = TRUE
            ORDER BY name
        """, (league_id,))
        
        players = []
        for row in cursor.fetchall():
            players.append({
                'id': row[0],
                'name': row[1],
                'phone': row[2]
            })
        return players
    finally:
        cursor.close()
        conn.close()


def get_league_info(league_id):
    """Get league information including AI messaging settings"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT id, name, display_name, twilio_conversation_sid,
                   ai_perfect_score_congrats, ai_failure_roast, 
                   ai_sunday_race_update, ai_daily_loser_roast
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
                'ai_daily_loser_roast': row[7] if row[7] is not None else False
            }
        return None
    finally:
        cursor.close()
        conn.close()
