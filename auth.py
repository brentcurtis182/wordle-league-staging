#!/usr/bin/env python3
"""
Authentication system for Wordle League
Handles user registration, login, logout, and session management
"""

import os
import logging
import secrets
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify, redirect, url_for, session, make_response
import psycopg2
from werkzeug.security import generate_password_hash, check_password_hash

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_db_connection():
    """Get PostgreSQL database connection"""
    database_url = os.environ.get('DATABASE_URL')
    if database_url:
        conn = psycopg2.connect(database_url)
    else:
        conn = psycopg2.connect(
            host=os.environ.get('PGHOST'),
            database=os.environ.get('PGDATABASE'),
            user=os.environ.get('PGUSER'),
            password=os.environ.get('PGPASSWORD'),
            port=os.environ.get('PGPORT', 5432)
        )
    
    # Set statement timeout to 20 seconds to prevent hanging queries
    cursor = conn.cursor()
    cursor.execute("SET statement_timeout = '20s'")
    cursor.close()
    return conn

def create_auth_tables():
    """Create users and user_leagues tables if they don't exist"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Create users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                first_name VARCHAR(100),
                last_name VARCHAR(100),
                phone VARCHAR(20),
                sms_consent BOOLEAN DEFAULT FALSE,
                sms_consent_date TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE
            )
        """)
        
        # Add new columns if they don't exist (for existing tables)
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS first_name VARCHAR(100)")
            cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_name VARCHAR(100)")
            cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS phone VARCHAR(20)")
            cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS sms_consent BOOLEAN DEFAULT FALSE")
            cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS sms_consent_date TIMESTAMP")
            cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login TIMESTAMP")
            cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE")
        except:
            pass  # Columns may already exist
        
        # Create user_leagues table (links users to leagues they manage)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_leagues (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                league_id INTEGER NOT NULL REFERENCES leagues(id) ON DELETE CASCADE,
                role VARCHAR(50) DEFAULT 'owner',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, league_id)
            )
        """)
        
        # Create sessions table for persistent login
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_sessions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                session_token VARCHAR(255) UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                is_valid BOOLEAN DEFAULT TRUE
            )
        """)
        
        # Create password reset tokens table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                token VARCHAR(255) UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                used BOOLEAN DEFAULT FALSE
            )
        """)
        
        # Add email verification columns
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified BOOLEAN DEFAULT FALSE")
            cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verify_token VARCHAR(255)")
            cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verify_expires TIMESTAMP")
            # Mark all existing users as verified (created before email verification feature)
            cursor.execute("""
                UPDATE users SET email_verified = TRUE, email_verify_token = NULL, email_verify_expires = NULL
                WHERE created_at < '2026-02-08' AND email_verified = FALSE
            """)
        except:
            pass
        
        # Add Google OAuth column
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS google_id VARCHAR(255) UNIQUE")
        except:
            pass
        
        # Add role column for super_admin support
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(50) DEFAULT 'user'")
            cursor.execute("UPDATE users SET role = 'admin' WHERE id = 1 AND (role IS NULL OR role = 'user')")
        except:
            pass
        
        conn.commit()
        logging.info("✅ Auth tables created successfully!")
        return True
        
    except Exception as e:
        logging.error(f"Error creating auth tables: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()

def register_user(email, password, first_name=None, last_name=None, phone=None, sms_consent=False):
    """Register a new user"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if email already exists
        cursor.execute("SELECT id FROM users WHERE email = %s", (email.lower(),))
        if cursor.fetchone():
            return {'success': False, 'error': 'Email already registered'}
        
        # Hash password and create user
        password_hash = generate_password_hash(password)
        
        # Clean phone number
        if phone:
            import re
            phone = re.sub(r'\D', '', phone)
        
        # Generate email verification token
        verify_token = secrets.token_urlsafe(48)
        verify_expires = datetime.utcnow() + timedelta(hours=24)
        
        cursor.execute("""
            INSERT INTO users (email, password_hash, first_name, last_name, phone, sms_consent, sms_consent_date,
                               email_verified, email_verify_token, email_verify_expires)
            VALUES (%s, %s, %s, %s, %s, %s, %s, FALSE, %s, %s)
            RETURNING id
        """, (email.lower(), password_hash, first_name, last_name, phone, sms_consent, 
              datetime.now() if sms_consent else None, verify_token, verify_expires))
        
        user_id = cursor.fetchone()[0]
        conn.commit()
        
        # Send verification email
        try:
            from email_utils import send_verification_email
            send_verification_email(email.lower(), verify_token, first_name)
        except Exception as email_err:
            logging.error(f"Failed to send verification email: {email_err}")
        
        logging.info(f"✅ User registered: {email}")
        return {'success': True, 'user_id': user_id}
        
    except Exception as e:
        logging.error(f"Error registering user: {e}")
        conn.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        cursor.close()
        conn.close()

def login_user(email, password):
    """Authenticate user and create session"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Find user by email
        # Try with email_verified column, fall back without it
        try:
            cursor.execute("""
                SELECT id, password_hash, name, is_active, email_verified
                FROM users WHERE email = %s
            """, (email.lower(),))
            result = cursor.fetchone()
            has_verified_col = True
        except Exception:
            conn.rollback()
            cursor.execute("""
                SELECT id, password_hash, name, is_active
                FROM users WHERE email = %s
            """, (email.lower(),))
            result = cursor.fetchone()
            has_verified_col = False
        
        if not result:
            return {'success': False, 'error': 'Invalid email or password'}
        
        if has_verified_col:
            user_id, password_hash, name, is_active, email_verified = result
        else:
            user_id, password_hash, name, is_active = result
            email_verified = None  # Treat as verified
        
        if not is_active:
            return {'success': False, 'error': 'Account is disabled'}
        
        # Verify password
        if not check_password_hash(password_hash, password):
            return {'success': False, 'error': 'Invalid email or password'}
        
        # Check email verification (only block if explicitly FALSE, not NULL)
        if email_verified is False:
            return {'success': False, 'error': 'email_not_verified', 'email': email.lower()}
        
        # Create session token
        session_token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(days=30)  # 30 day session
        
        cursor.execute("""
            INSERT INTO user_sessions (user_id, session_token, expires_at)
            VALUES (%s, %s, %s)
        """, (user_id, session_token, expires_at))
        
        # Update last login
        cursor.execute("""
            UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = %s
        """, (user_id,))
        
        conn.commit()
        
        logging.info(f"✅ User logged in: {email}")
        return {
            'success': True,
            'user_id': user_id,
            'name': name,
            'email': email.lower(),
            'session_token': session_token
        }
        
    except Exception as e:
        logging.error(f"Error logging in user: {e}")
        conn.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        cursor.close()
        conn.close()

def validate_session(session_token):
    """Validate a session token and return user info"""
    if not session_token:
        logging.info("validate_session: No session token provided")
        return None
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # First check if session exists at all
        cursor.execute("""
            SELECT s.user_id, s.is_valid, s.expires_at, u.is_active, u.id, u.email, u.first_name, u.last_name
            FROM user_sessions s
            LEFT JOIN users u ON s.user_id = u.id
            WHERE s.session_token = %s
        """, (session_token,))
        
        debug_result = cursor.fetchone()
        if debug_result:
            logging.info(f"validate_session: Found session - user_id={debug_result[0]}, is_valid={debug_result[1]}, expires_at={debug_result[2]}, user_is_active={debug_result[3]}")
        else:
            logging.warning(f"validate_session: No session found for token {session_token[:20]}...")
            return None
        
        # Now do the actual validation
        cursor.execute("""
            SELECT u.id, u.email, u.first_name, u.last_name, u.role
            FROM user_sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.session_token = %s 
              AND s.is_valid = TRUE 
              AND s.expires_at > CURRENT_TIMESTAMP
              AND u.is_active = TRUE
        """, (session_token,))
        
        result = cursor.fetchone()
        if result:
            first_name = result[2] or ''
            last_name = result[3] or ''
            full_name = f"{first_name} {last_name}".strip() or result[1]  # Fall back to email
            role = result[4] or 'user'
            logging.info(f"validate_session: Valid session for user {result[1]}")
            return {'id': result[0], 'email': result[1], 'name': full_name, 'first_name': first_name, 'role': role}
        
        logging.warning(f"validate_session: Session exists but validation failed")
        return None
        
    except Exception as e:
        logging.error(f"Error validating session: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return None
    finally:
        cursor.close()
        conn.close()

def logout_user(session_token):
    """Invalidate a session token"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            UPDATE user_sessions SET is_valid = FALSE WHERE session_token = %s
        """, (session_token,))
        conn.commit()
        return True
    except Exception as e:
        logging.error(f"Error logging out: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()

def get_user_leagues(user_id):
    """Get all leagues a user manages"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT l.id, l.name, l.display_name, ul.role, l.twilio_conversation_sid, l.slug,
                   l.channel_type, l.slack_channel_id, l.discord_channel_id,
                   l.slack_bot_token
            FROM user_leagues ul
            JOIN leagues l ON ul.league_id = l.id
            WHERE ul.user_id = %s
            ORDER BY l.name
        """, (user_id,))
        
        leagues = []
        for row in cursor.fetchall():
            league_data = {
                'id': row[0],
                'name': row[1],
                'display_name': row[2],
                'role': row[3],
                'conversation_sid': row[4],
                'slug': row[5],
                'channel_type': row[6] or 'sms',
                'slack_channel_id': row[7],
                'discord_channel_id': row[8],
                'slack_bot_token': row[9],
                'channel_name': None
            }
            
            # Look up Slack channel name if applicable
            if league_data['channel_type'] == 'slack' and league_data['slack_channel_id'] and league_data['slack_bot_token']:
                try:
                    from slack_integration import get_slack_channel_info
                    channel_info = get_slack_channel_info(league_data['slack_bot_token'], league_data['slack_channel_id'])
                    league_data['channel_name'] = channel_info.get('name')
                except Exception as e:
                    logging.error(f"Error fetching Slack channel name: {e}")
            
            leagues.append(league_data)
        return leagues
        
    except Exception as e:
        logging.error(f"Error getting user leagues: {e}")
        return []
    finally:
        cursor.close()
        conn.close()

def assign_league_to_user(user_id, league_id, role='owner'):
    """Assign a league to a user"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO user_leagues (user_id, league_id, role)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id, league_id) DO UPDATE SET role = %s
        """, (user_id, league_id, role, role))
        conn.commit()
        return True
    except Exception as e:
        logging.error(f"Error assigning league: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()

def login_required(f):
    """Decorator to require login for a route"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check for session token in cookie or header
        session_token = request.cookies.get('session_token') or request.headers.get('X-Session-Token')
        
        user = validate_session(session_token)
        if not user:
            # For API requests, return JSON error
            if request.is_json or request.headers.get('Accept') == 'application/json':
                return jsonify({'error': 'Authentication required'}), 401
            # For browser requests, redirect to login
            return redirect('/auth/login')
        
        # Add user to request context
        request.user = user
        return f(*args, **kwargs)
    return decorated_function

def get_user_details(user_id):
    """Get full user details for profile page"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        try:
            cursor.execute("""
                SELECT id, email, first_name, last_name, phone, sms_consent, created_at, last_login, password_hash, google_id
                FROM users WHERE id = %s
            """, (user_id,))
            result = cursor.fetchone()
            has_extra_cols = True
        except Exception:
            conn.rollback()
            cursor.execute("""
                SELECT id, email, first_name, last_name, phone, sms_consent, created_at, last_login
                FROM users WHERE id = %s
            """, (user_id,))
            result = cursor.fetchone()
            has_extra_cols = False
        
        if not result:
            return None
        
        details = {
            'id': result[0],
            'email': result[1],
            'first_name': result[2] or '',
            'last_name': result[3] or '',
            'phone': result[4] or '',
            'sms_consent': result[5],
            'created_at': result[6],
            'last_login': result[7],
            'has_password': bool(result[8]) if has_extra_cols else True,
            'has_google': bool(result[9]) if has_extra_cols else False
        }
        return details
    except Exception as e:
        logging.error(f"Error getting user details: {e}")
        return None
    finally:
        cursor.close()
        conn.close()

def change_password(user_id, current_password, new_password):
    """Change user's password after verifying current password"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT password_hash FROM users WHERE id = %s", (user_id,))
        result = cursor.fetchone()
        if not result:
            return {'success': False, 'error': 'User not found'}
        
        existing_hash = result[0]
        
        # If user has a password, verify current one. If no password (Google-only), allow setting one.
        if existing_hash:
            if not current_password:
                return {'success': False, 'error': 'Current password is required'}
            if not check_password_hash(existing_hash, current_password):
                return {'success': False, 'error': 'Current password is incorrect'}
        
        new_hash = generate_password_hash(new_password)
        cursor.execute("UPDATE users SET password_hash = %s WHERE id = %s", (new_hash, user_id))
        conn.commit()
        
        logging.info(f"Password changed for user {user_id}")
        return {'success': True}
    except Exception as e:
        logging.error(f"Error changing password: {e}")
        conn.rollback()
        return {'success': False, 'error': 'An error occurred'}
    finally:
        cursor.close()
        conn.close()

def update_profile(user_id, first_name=None, last_name=None, email=None, phone=None):
    """Update user profile fields"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # If email is changing, check it's not taken
        if email:
            cursor.execute("SELECT id FROM users WHERE email = %s AND id != %s", (email.lower(), user_id))
            if cursor.fetchone():
                return {'success': False, 'error': 'Email already in use by another account'}
        
        updates = []
        params = []
        
        if first_name is not None:
            updates.append("first_name = %s")
            params.append(first_name)
        if last_name is not None:
            updates.append("last_name = %s")
            params.append(last_name)
        if email is not None:
            updates.append("email = %s")
            params.append(email.lower())
        if phone is not None:
            import re
            phone = re.sub(r'\D', '', phone) if phone else ''
            updates.append("phone = %s")
            params.append(phone)
        
        if not updates:
            return {'success': True}
        
        params.append(user_id)
        cursor.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = %s", params)
        conn.commit()
        
        logging.info(f"Profile updated for user {user_id}")
        return {'success': True}
    except Exception as e:
        logging.error(f"Error updating profile: {e}")
        conn.rollback()
        return {'success': False, 'error': 'An error occurred'}
    finally:
        cursor.close()
        conn.close()

def logout_all_sessions(user_id, except_token=None):
    """Invalidate all sessions for a user, optionally keeping the current one"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        if except_token:
            cursor.execute("""
                UPDATE user_sessions SET is_valid = FALSE 
                WHERE user_id = %s AND session_token != %s AND is_valid = TRUE
            """, (user_id, except_token))
        else:
            cursor.execute("""
                UPDATE user_sessions SET is_valid = FALSE 
                WHERE user_id = %s AND is_valid = TRUE
            """, (user_id,))
        
        count = cursor.rowcount
        conn.commit()
        logging.info(f"Invalidated {count} sessions for user {user_id}")
        return {'success': True, 'sessions_invalidated': count}
    except Exception as e:
        logging.error(f"Error logging out all sessions: {e}")
        conn.rollback()
        return {'success': False, 'error': 'An error occurred'}
    finally:
        cursor.close()
        conn.close()

def get_active_session_count(user_id):
    """Get count of active sessions for a user"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT COUNT(*) FROM user_sessions 
            WHERE user_id = %s AND is_valid = TRUE AND expires_at > CURRENT_TIMESTAMP
        """, (user_id,))
        return cursor.fetchone()[0]
    except Exception as e:
        logging.error(f"Error counting sessions: {e}")
        return 0
    finally:
        cursor.close()
        conn.close()

def delete_account(user_id, password):
    """Delete a user account after password verification"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT password_hash FROM users WHERE id = %s", (user_id,))
        result = cursor.fetchone()
        if not result:
            return {'success': False, 'error': 'User not found'}
        
        if not check_password_hash(result[0], password):
            return {'success': False, 'error': 'Password is incorrect'}
        
        # Invalidate all sessions
        cursor.execute("UPDATE user_sessions SET is_valid = FALSE WHERE user_id = %s", (user_id,))
        
        # Remove league associations
        cursor.execute("DELETE FROM user_leagues WHERE user_id = %s", (user_id,))
        
        # Deactivate account (soft delete - preserves data integrity)
        cursor.execute("UPDATE users SET is_active = FALSE, email = %s WHERE id = %s", 
                       (f"deleted_{user_id}@deleted.account", user_id))
        
        conn.commit()
        logging.info(f"Account deleted (deactivated) for user {user_id}")
        return {'success': True}
    except Exception as e:
        logging.error(f"Error deleting account: {e}")
        conn.rollback()
        return {'success': False, 'error': 'An error occurred'}
    finally:
        cursor.close()
        conn.close()

def request_password_reset(email):
    """Generate a password reset token and send reset email"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT id, first_name FROM users WHERE email = %s AND is_active = TRUE", (email.lower(),))
        result = cursor.fetchone()
        if not result:
            # Don't reveal whether email exists
            return {'success': True}
        
        user_id, first_name = result[0], result[1]
        
        # Invalidate any existing reset tokens for this user
        cursor.execute("UPDATE password_reset_tokens SET used = TRUE WHERE user_id = %s AND used = FALSE", (user_id,))
        
        # Generate new token (1 hour expiry)
        token = secrets.token_urlsafe(48)
        expires_at = datetime.utcnow() + timedelta(hours=1)
        
        cursor.execute("""
            INSERT INTO password_reset_tokens (user_id, token, expires_at)
            VALUES (%s, %s, %s)
        """, (user_id, token, expires_at))
        
        conn.commit()
        
        # Send the email
        from email_utils import send_password_reset_email
        send_password_reset_email(email.lower(), token, first_name)
        
        logging.info(f"Password reset requested for user {user_id}")
        return {'success': True}
    except Exception as e:
        logging.error(f"Error requesting password reset: {e}")
        conn.rollback()
        return {'success': True}  # Don't reveal errors
    finally:
        cursor.close()
        conn.close()


def validate_reset_token(token):
    """Validate a password reset token and return user info"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT prt.user_id, u.email, u.first_name
            FROM password_reset_tokens prt
            JOIN users u ON prt.user_id = u.id
            WHERE prt.token = %s AND prt.used = FALSE AND prt.expires_at > CURRENT_TIMESTAMP
        """, (token,))
        
        result = cursor.fetchone()
        if not result:
            return None
        
        return {'user_id': result[0], 'email': result[1], 'first_name': result[2]}
    except Exception as e:
        logging.error(f"Error validating reset token: {e}")
        return None
    finally:
        cursor.close()
        conn.close()


def reset_password_with_token(token, new_password):
    """Reset password using a valid reset token"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT user_id FROM password_reset_tokens
            WHERE token = %s AND used = FALSE AND expires_at > CURRENT_TIMESTAMP
        """, (token,))
        
        result = cursor.fetchone()
        if not result:
            return {'success': False, 'error': 'Invalid or expired reset link. Please request a new one.'}
        
        user_id = result[0]
        new_hash = generate_password_hash(new_password)
        
        cursor.execute("UPDATE users SET password_hash = %s WHERE id = %s", (new_hash, user_id))
        cursor.execute("UPDATE password_reset_tokens SET used = TRUE WHERE token = %s", (token,))
        
        conn.commit()
        logging.info(f"Password reset completed for user {user_id}")
        return {'success': True}
    except Exception as e:
        logging.error(f"Error resetting password: {e}")
        conn.rollback()
        return {'success': False, 'error': 'An error occurred'}
    finally:
        cursor.close()
        conn.close()


def generate_verification_token(user_id):
    """Generate and store an email verification token for a user"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        token = secrets.token_urlsafe(48)
        expires_at = datetime.utcnow() + timedelta(hours=24)
        
        cursor.execute("""
            UPDATE users SET email_verify_token = %s, email_verify_expires = %s
            WHERE id = %s
        """, (token, expires_at, user_id))
        
        conn.commit()
        return token
    except Exception as e:
        logging.error(f"Error generating verification token: {e}")
        conn.rollback()
        return None
    finally:
        cursor.close()
        conn.close()


def verify_email(token):
    """Verify a user's email using their verification token"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT id, email FROM users
            WHERE email_verify_token = %s AND email_verify_expires > CURRENT_TIMESTAMP AND email_verified = FALSE
        """, (token,))
        
        result = cursor.fetchone()
        if not result:
            return {'success': False, 'error': 'Invalid or expired verification link.'}
        
        user_id = result[0]
        cursor.execute("""
            UPDATE users SET email_verified = TRUE, email_verify_token = NULL, email_verify_expires = NULL
            WHERE id = %s
        """, (user_id,))
        
        conn.commit()
        logging.info(f"Email verified for user {user_id}")
        return {'success': True}
    except Exception as e:
        logging.error(f"Error verifying email: {e}")
        conn.rollback()
        return {'success': False, 'error': 'An error occurred'}
    finally:
        cursor.close()
        conn.close()


def resend_verification_email(email):
    """Resend verification email for an unverified user"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT id, first_name, email_verified FROM users WHERE email = %s", (email.lower(),))
        result = cursor.fetchone()
        if not result:
            return {'success': True}  # Don't reveal
        
        user_id, first_name, verified = result
        if verified:
            return {'success': True}
        
        token = secrets.token_urlsafe(48)
        expires_at = datetime.utcnow() + timedelta(hours=24)
        
        cursor.execute("""
            UPDATE users SET email_verify_token = %s, email_verify_expires = %s
            WHERE id = %s
        """, (token, expires_at, user_id))
        conn.commit()
        
        from email_utils import send_verification_email
        send_verification_email(email.lower(), token, first_name)
        
        return {'success': True}
    except Exception as e:
        logging.error(f"Error resending verification: {e}")
        conn.rollback()
        return {'success': True}
    finally:
        cursor.close()
        conn.close()


def get_google_oauth_url():
    """Generate Google OAuth authorization URL"""
    client_id = os.environ.get('GOOGLE_CLIENT_ID', '')
    app_url = os.environ.get('APP_URL', 'https://app.wordplayleague.com')
    redirect_uri = f"{app_url}/auth/google/callback"
    
    import urllib.parse
    params = urllib.parse.urlencode({
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': 'openid email profile',
        'access_type': 'offline',
        'prompt': 'select_account'
    })
    return f"https://accounts.google.com/o/oauth2/v2/auth?{params}"


def google_oauth_callback(code):
    """Exchange Google auth code for user info, create/link account, and return session"""
    import requests
    
    client_id = os.environ.get('GOOGLE_CLIENT_ID', '')
    client_secret = os.environ.get('GOOGLE_CLIENT_SECRET', '')
    app_url = os.environ.get('APP_URL', 'https://app.wordplayleague.com')
    redirect_uri = f"{app_url}/auth/google/callback"
    
    # Exchange code for tokens
    token_response = requests.post('https://oauth2.googleapis.com/token', data={
        'code': code,
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code'
    }, timeout=10)
    
    if token_response.status_code != 200:
        logging.error(f"Google token exchange failed: {token_response.text}")
        return {'success': False, 'error': 'Failed to authenticate with Google'}
    
    token_data = token_response.json()
    access_token = token_data.get('access_token')
    
    # Get user info from Google
    userinfo_response = requests.get('https://www.googleapis.com/oauth2/v2/userinfo', 
        headers={'Authorization': f'Bearer {access_token}'}, timeout=10)
    
    if userinfo_response.status_code != 200:
        logging.error(f"Google userinfo failed: {userinfo_response.text}")
        return {'success': False, 'error': 'Failed to get user info from Google'}
    
    google_user = userinfo_response.json()
    google_id = google_user.get('id')
    email = google_user.get('email', '').lower()
    first_name = google_user.get('given_name', '')
    last_name = google_user.get('family_name', '')
    
    if not email:
        return {'success': False, 'error': 'No email returned from Google'}
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if user exists by google_id
        cursor.execute("SELECT id, email, first_name FROM users WHERE google_id = %s", (google_id,))
        user = cursor.fetchone()
        
        if user:
            # Existing Google user — log them in
            user_id = user[0]
            logging.info(f"Google OAuth login for existing user: {email}")
        else:
            # Check if user exists by email (link Google to existing account)
            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            existing = cursor.fetchone()
            
            if existing:
                # Link Google ID to existing account and mark email as verified
                user_id = existing[0]
                cursor.execute("UPDATE users SET google_id = %s, email_verified = TRUE WHERE id = %s", (google_id, user_id))
                conn.commit()
                logging.info(f"Linked Google account to existing user: {email}")
            else:
                # Create new user (no password needed, email auto-verified)
                cursor.execute("""
                    INSERT INTO users (email, password_hash, first_name, last_name, google_id, email_verified, is_active)
                    VALUES (%s, %s, %s, %s, %s, TRUE, TRUE)
                    RETURNING id
                """, (email, '', first_name, last_name, google_id))
                user_id = cursor.fetchone()[0]
                conn.commit()
                logging.info(f"Created new user via Google OAuth: {email}")
        
        # Create session
        session_token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(days=30)
        
        cursor.execute("""
            INSERT INTO user_sessions (user_id, session_token, expires_at)
            VALUES (%s, %s, %s)
        """, (user_id, session_token, expires_at))
        
        cursor.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = %s", (user_id,))
        conn.commit()
        
        return {'success': True, 'session_token': session_token}
        
    except Exception as e:
        logging.error(f"Google OAuth error: {e}")
        conn.rollback()
        return {'success': False, 'error': 'An error occurred during Google sign-in'}
    finally:
        cursor.close()
        conn.close()


def can_manage_league(user_id, league_id):
    """Check if a user can manage a specific league"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT role FROM user_leagues
            WHERE user_id = %s AND league_id = %s
        """, (user_id, league_id))
        
        result = cursor.fetchone()
        return result is not None
        
    except Exception as e:
        logging.error(f"Error checking league access: {e}")
        return False
    finally:
        cursor.close()
        conn.close()
