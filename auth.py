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
        return psycopg2.connect(database_url)
    else:
        return psycopg2.connect(
            host=os.environ.get('PGHOST'),
            database=os.environ.get('PGDATABASE'),
            user=os.environ.get('PGUSER'),
            password=os.environ.get('PGPASSWORD'),
            port=os.environ.get('PGPORT', 5432)
        )

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
        
        cursor.execute("""
            INSERT INTO users (email, password_hash, first_name, last_name, phone, sms_consent, sms_consent_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (email.lower(), password_hash, first_name, last_name, phone, sms_consent, 
              datetime.now() if sms_consent else None))
        
        user_id = cursor.fetchone()[0]
        conn.commit()
        
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
        cursor.execute("""
            SELECT id, password_hash, name, is_active
            FROM users WHERE email = %s
        """, (email.lower(),))
        
        result = cursor.fetchone()
        if not result:
            return {'success': False, 'error': 'Invalid email or password'}
        
        user_id, password_hash, name, is_active = result
        
        if not is_active:
            return {'success': False, 'error': 'Account is disabled'}
        
        # Verify password
        if not check_password_hash(password_hash, password):
            return {'success': False, 'error': 'Invalid email or password'}
        
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
            SELECT u.id, u.email, u.first_name, u.last_name
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
            logging.info(f"validate_session: Valid session for user {result[1]}")
            return {'id': result[0], 'email': result[1], 'name': full_name, 'first_name': first_name}
        
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
                   l.channel_type, l.slack_channel_id, l.discord_channel_id
            FROM user_leagues ul
            JOIN leagues l ON ul.league_id = l.id
            WHERE ul.user_id = %s
            ORDER BY l.name
        """, (user_id,))
        
        leagues = []
        for row in cursor.fetchall():
            leagues.append({
                'id': row[0],
                'name': row[1],
                'display_name': row[2],
                'role': row[3],
                'conversation_sid': row[4],
                'slug': row[5],
                'channel_type': row[6] or 'sms',
                'slack_channel_id': row[7],
                'discord_channel_id': row[8]
            })
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
