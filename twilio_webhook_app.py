#!/usr/bin/env python3
"""
Twilio Webhook Flask App for Wordle League
Receives SMS messages from Twilio and extracts Wordle scores
"""

import os
import re
import logging
from datetime import datetime, date, timedelta
from flask import Flask, request, jsonify, redirect, make_response, send_from_directory
from twilio.twiml.messaging_response import MessagingResponse
import psycopg2

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'wordle-league-secret-key-change-in-production')


def run_pipeline_with_retry(league_id, max_retries=3):
    """Run the update pipeline with retry logic and exponential backoff"""
    import time
    from update_pipeline import run_update_pipeline
    
    for attempt in range(max_retries):
        try:
            logging.info(f"[Pipeline] Attempt {attempt + 1}/{max_retries} for league {league_id}...")
            result_data = run_update_pipeline(league_id)
            
            if result_data.get('success'):
                logging.info(f"[Pipeline] ✅ Completed successfully for league {league_id}")
                return True
            else:
                logging.error(f"[Pipeline] ❌ Failed for league {league_id}: {result_data.get('errors')}")
                
        except Exception as e:
            logging.error(f"[Pipeline] ❌ Error on attempt {attempt + 1} for league {league_id}: {e}")
        
        # Exponential backoff: 2s, 4s, 8s
        if attempt < max_retries - 1:
            wait_time = 2 ** (attempt + 1)
            logging.info(f"[Pipeline] Retrying in {wait_time} seconds...")
            time.sleep(wait_time)
    
    logging.error(f"[Pipeline] ❌ All {max_retries} attempts failed for league {league_id}")
    return False

# Twilio credentials
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')

# Phone mappings are now loaded from database dynamically
# This cache is refreshed periodically to avoid constant DB queries
_phone_mappings_cache = {}
_phone_mappings_cache_time = None
PHONE_MAPPINGS_CACHE_SECONDS = 60  # Refresh cache every 60 seconds

def get_phone_mappings_from_db():
    """Load phone-to-player mappings from database for all leagues"""
    global _phone_mappings_cache, _phone_mappings_cache_time
    
    from datetime import datetime
    
    # Return cached version if still valid
    if _phone_mappings_cache_time and (datetime.now() - _phone_mappings_cache_time).seconds < PHONE_MAPPINGS_CACHE_SECONDS:
        return _phone_mappings_cache
    
    try:
        conn = get_db_connection()
        if not conn:
            logging.error("Could not connect to database for phone mappings")
            return _phone_mappings_cache  # Return stale cache if available
        
        cursor = conn.cursor()
        cursor.execute("""
            SELECT league_id, phone_number, name 
            FROM players 
            WHERE active = TRUE AND phone_number IS NOT NULL
            ORDER BY league_id, name
        """)
        
        mappings = {}
        for row in cursor.fetchall():
            league_id, phone, name = row
            if league_id not in mappings:
                mappings[league_id] = {}
            # Store phone without formatting
            clean_phone = ''.join(c for c in phone if c.isdigit())
            mappings[league_id][clean_phone] = name
        
        cursor.close()
        conn.close()
        
        _phone_mappings_cache = mappings
        _phone_mappings_cache_time = datetime.now()
        logging.info(f"Refreshed phone mappings cache: {len(mappings)} leagues")
        return mappings
        
    except Exception as e:
        logging.error(f"Error loading phone mappings from DB: {e}")
        return _phone_mappings_cache  # Return stale cache on error

def get_db_connection():
    """Get PostgreSQL database connection"""
    try:
        # Try DATABASE_URL first (Railway style), then fall back to individual vars
        database_url = os.environ.get('DATABASE_URL')
        
        if database_url:
            logging.info(f"Connecting via DATABASE_URL")
            conn = psycopg2.connect(database_url)
        else:
            # Fall back to individual environment variables
            pghost = os.environ.get('PGHOST')
            pgdb = os.environ.get('PGDATABASE')
            pguser = os.environ.get('PGUSER')
            pgport = os.environ.get('PGPORT', 5432)
            
            logging.info(f"Connecting to PostgreSQL: host={pghost}, db={pgdb}, user={pguser}, port={pgport}")
            
            conn = psycopg2.connect(
                host=pghost,
                database=pgdb,
                user=pguser,
                password=os.environ.get('PGPASSWORD'),
                port=pgport
            )
        
        logging.info("Database connection successful!")
        return conn
    except Exception as e:
        logging.error(f"Database connection error: {e}")
        return None

def get_player_from_phone(phone_number, league_id):
    """Get player name from phone number for a specific league"""
    if not phone_number:
        return None
    
    # Get current phone mappings from database
    phone_mappings = get_phone_mappings_from_db()
    
    # Normalize phone number by removing non-digits
    digits_only = ''.join(c for c in phone_number if c.isdigit())
    
    # Try with and without leading 1 (country code)
    if league_id in phone_mappings:
        # Try direct match with digits
        if digits_only in phone_mappings[league_id]:
            return phone_mappings[league_id][digits_only]
        
        # Try adding leading 1 if it's missing and length is 10
        if len(digits_only) == 10:
            with_country_code = "1" + digits_only
            if with_country_code in phone_mappings[league_id]:
                return phone_mappings[league_id][with_country_code]
        
        # Try without leading 1 if it has one and length is 11
        if len(digits_only) == 11 and digits_only[0] == "1":
            without_country_code = digits_only[1:]
            if without_country_code in phone_mappings[league_id]:
                return phone_mappings[league_id][without_country_code]
    
    return None

def get_todays_wordle_number():
    """Calculate today's Wordle number based on reference date in Pacific Time"""
    from datetime import timezone, timedelta
    
    # Wordle #1503 = July 31, 2025
    ref_date = date(2025, 7, 31)
    ref_wordle = 1503
    
    # Get current time in Pacific Time (UTC-8 or UTC-7 depending on DST)
    # For simplicity, use UTC-8 (PST)
    pacific_tz = timezone(timedelta(hours=-8))
    now_pacific = datetime.now(pacific_tz)
    today_pacific = now_pacific.date()
    
    days_since_ref = (today_pacific - ref_date).days
    return ref_wordle + days_since_ref

def extract_wordle_score(message_body):
    """
    Extract Wordle score from SMS message
    Handles both multi-line and single-line emoji patterns (Twilio format)
    Returns: (wordle_number, score, emoji_pattern) or (None, None, None)
    """
    # Regex to match Wordle scores: "Wordle 1,234 3/6" or "Wordle 1234 X/6"
    wordle_regex = re.compile(r'Wordle\s+([\d,]+)\s+([1-6X])/6', re.IGNORECASE)
    
    match = wordle_regex.search(message_body)
    if not match:
        return None, None, None
    
    # Extract wordle number (remove commas)
    wordle_num_str = match.group(1).replace(',', '')
    try:
        wordle_num = int(wordle_num_str)
    except ValueError:
        logging.warning(f"Could not convert Wordle number: {wordle_num_str}")
        return None, None, None
    
    # CRITICAL: Validate Wordle number is today or yesterday only
    from datetime import date, timedelta
    ref_date = date(2021, 6, 19)
    ref_wordle = 0
    today = date.today()
    days_since_ref = (today - ref_date).days
    today_wordle = ref_wordle + days_since_ref
    yesterday_wordle = today_wordle - 1
    
    if wordle_num == today_wordle:
        logging.info(f"✓ VALIDATED: Wordle #{wordle_num} is today's")
    elif wordle_num == yesterday_wordle:
        logging.info(f"✓ VALIDATED: Wordle #{wordle_num} is yesterday's (late submission)")
    else:
        logging.warning(f"✗ REJECTED: Wordle #{wordle_num} is neither today's ({today_wordle}) nor yesterday's ({yesterday_wordle})")
        return None, None, None
    
    # Extract score
    score_str = match.group(2)
    if score_str.upper() == 'X':
        score = 7  # X = 7 in our system
    else:
        score = int(score_str)
    
    # Extract emoji pattern - HANDLE BOTH FORMATS
    emoji_pattern = None
    
    # Method 1: Check for multi-line format (like Google Voice)
    lines = message_body.split('\n')
    emoji_lines = []
    
    for line in lines:
        # Check for Wordle emoji colors
        if any(emoji in line for emoji in ['🟩', '⬛', '⬜', '🟨']):
            # Skip the score line itself (e.g., "Wordle 1,618 4/6")
            if not re.search(r'Wordle\s+[\d,]+\s+[1-6X]/6', line):
                # Extract ONLY emoji characters from this line
                emoji_only = ''.join(char for char in line if char in ['🟩', '⬛', '⬜', '🟨'])
                if emoji_only:
                    emoji_lines.append(emoji_only)
    
    if emoji_lines:
        # Multi-line format found
        emoji_pattern = '\n'.join(emoji_lines)
        logging.info(f"Extracted multi-line emoji pattern with {len(emoji_lines)} lines")
    else:
        # Method 2: Single-line format (Twilio SMS)
        # Extract everything after the score
        after_score = message_body[match.end():].strip()
        
        # Extract only emoji characters
        emoji_chars = []
        for char in after_score:
            if char in ['🟩', '⬛', '⬜', '🟨']:
                emoji_chars.append(char)
        
        # Group into rows of 5
        if emoji_chars:
            rows = []
            for i in range(0, len(emoji_chars), 5):
                row = ''.join(emoji_chars[i:i+5])
                if len(row) == 5:  # Only add complete rows
                    rows.append(row)
            
            if rows:
                emoji_pattern = '\n'.join(rows)
                logging.info(f"Extracted single-line emoji pattern, converted to {len(rows)} rows")
    
    return wordle_num, score, emoji_pattern

def get_player_id(player_name, league_id, conn):
    """Get player ID from database"""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id FROM players 
            WHERE name = %s AND league_id = %s
        """, (player_name, league_id))
        
        result = cursor.fetchone()
        cursor.close()
        
        if result:
            return result[0]
        return None
    except Exception as e:
        logging.error(f"Error getting player ID: {e}")
        return None

def get_todays_wordle_word():
    """Fetch today's Wordle word by scraping or from API"""
    try:
        import requests
        import json
        from datetime import datetime
        import pytz
        
        # Get today's Wordle number using the same reference as get_todays_wordle_number()
        pacific = pytz.timezone('America/Los_Angeles')
        today = datetime.now(pacific).date()
        # Use same reference as rest of app: Wordle #1503 = July 31, 2025
        ref_date = date(2025, 7, 31)
        ref_wordle = 1503
        days_since_ref = (today - ref_date).days
        todays_wordle_num = ref_wordle + days_since_ref
        
        logging.info(f"Fetching Wordle word for #{todays_wordle_num} (today: {today})")
        
        # Try Method 1: NYT official API with today's date format
        try:
            # NYT API uses date format YYYY-MM-DD
            date_str = today.strftime('%Y-%m-%d')
            url = f"https://www.nytimes.com/svc/wordle/v2/{date_str}.json"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                word = data.get('solution', '').upper()
                if word:
                    logging.info(f"Got Wordle word from NYT date API: {word}")
                    return word
        except Exception as e:
            logging.warning(f"NYT date API failed: {e}")
        
        # Try Method 2: NYT API with puzzle number
        try:
            url = f"https://www.nytimes.com/svc/wordle/v2/{todays_wordle_num}.json"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                word = data.get('solution', '').upper()
                if word:
                    logging.info(f"Got Wordle word from NYT number API: {word}")
                    return word
        except Exception as e:
            logging.warning(f"NYT number API failed: {e}")
        
        logging.warning("Could not fetch today's Wordle word from any source")
        return None
        
    except Exception as e:
        logging.error(f"Error fetching Wordle word: {e}")
        return None

def is_ai_message_enabled(league_id, message_type):
    """Check if a specific AI message type is enabled for a league
    
    message_type can be:
    - 'perfect_score' (ai_perfect_score_congrats)
    - 'failure_roast' (ai_failure_roast)
    - 'sunday_race' (ai_sunday_race_update)
    - 'daily_loser' (ai_daily_loser_roast)
    """
    try:
        conn = get_db_connection()
        if not conn:
            # Default to current hardcoded behavior if DB unavailable
            defaults = {
                'perfect_score': False,
                'failure_roast': True,
                'sunday_race': True,
                'daily_loser': False
            }
            return defaults.get(message_type, False)
        
        cursor = conn.cursor()
        
        column_map = {
            'perfect_score': 'ai_perfect_score_congrats',
            'failure_roast': 'ai_failure_roast',
            'sunday_race': 'ai_sunday_race_update',
            'daily_loser': 'ai_daily_loser_roast'
        }
        
        column = column_map.get(message_type)
        if not column:
            cursor.close()
            conn.close()
            return False
        
        cursor.execute(f"SELECT {column} FROM leagues WHERE id = %s", (league_id,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if result and result[0] is not None:
            return result[0]
        
        # Default values if column is NULL
        defaults = {
            'perfect_score': False,
            'failure_roast': True,
            'sunday_race': True,
            'daily_loser': False
        }
        return defaults.get(message_type, False)
        
    except Exception as e:
        logging.error(f"Error checking AI message setting: {e}")
        # Default to current behavior
        defaults = {
            'perfect_score': False,
            'failure_roast': True,
            'sunday_race': True,
            'daily_loser': False
        }
        return defaults.get(message_type, False)

def get_ai_message_severity(league_id, message_type=None):
    """Get the AI message severity setting for a league (1=savage, 2=spicy, 3=playful, 4=gentle)
    
    message_type can be: 'perfect_score', 'failure_roast', 'daily_loser'
    If message_type is provided, returns the per-message severity, otherwise returns global.
    """
    try:
        conn = get_db_connection()
        if not conn:
            return 2  # Default to spicy
        
        cursor = conn.cursor()
        
        if message_type:
            column_map = {
                'perfect_score': 'ai_perfect_score_severity',
                'failure_roast': 'ai_failure_roast_severity',
                'daily_loser': 'ai_daily_loser_severity'
            }
            column = column_map.get(message_type, 'ai_message_severity')
            cursor.execute(f"SELECT {column} FROM leagues WHERE id = %s", (league_id,))
        else:
            cursor.execute("SELECT ai_message_severity FROM leagues WHERE id = %s", (league_id,))
        
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if result and result[0] is not None:
            return result[0]
        return 2  # Default to spicy
        
    except Exception as e:
        logging.error(f"Error getting AI message severity: {e}")
        return 2

def get_player_ai_settings(league_id, player_id, message_type):
    """Get AI settings for a specific player and message type
    
    Returns: (enabled, severity_override) where severity_override is None if using default
    """
    try:
        conn = get_db_connection()
        if not conn:
            return (True, None)
        
        cursor = conn.cursor()
        cursor.execute("""
            SELECT enabled, severity_override 
            FROM ai_player_settings 
            WHERE league_id = %s AND player_id = %s AND message_type = %s
        """, (league_id, player_id, message_type))
        
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if result:
            return (result[0], result[1])
        return (True, None)  # Default: enabled, use league severity
        
    except Exception as e:
        logging.error(f"Error getting player AI settings: {e}")
        return (True, None)

def get_all_player_ai_settings(league_id):
    """Get all player AI settings for a league, returns dict keyed by 'message_type_player_id'"""
    try:
        conn = get_db_connection()
        if not conn:
            return {}
        
        cursor = conn.cursor()
        cursor.execute("""
            SELECT player_id, message_type, enabled, severity_override 
            FROM ai_player_settings 
            WHERE league_id = %s
        """, (league_id,))
        
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        
        settings = {}
        for row in results:
            player_id, message_type, enabled, severity_override = row
            key = f"{message_type}_{player_id}"
            settings[key] = {
                'enabled': enabled,
                'severity': severity_override
            }
        return settings
        
    except Exception as e:
        logging.error(f"Error getting all player AI settings: {e}")
        return {}

def get_severity_prompt(severity, message_type):
    """Get the appropriate prompt modifier based on severity level"""
    if message_type == 'roast':
        prompts = {
            1: "Be absolutely brutal and savage. No mercy. Roast them mercilessly like a comedy roast. Make it sting but still funny.",
            2: "Be harsh and spicy with your roast. Don't hold back much, but keep it playful underneath the burns.",
            3: "Be playful and teasing. Light roasting with good humor. More jokes than actual burns.",
            4: "Be gentle and encouraging despite the loss. Maybe a tiny tease but mostly supportive and kind."
        }
    elif message_type == 'congrats':
        prompts = {
            1: "Be VERY suspicious they're cheating. Congratulate them but heavily imply you don't believe it's legit. Playful accusations, side-eye emojis 👀🤔. Make it funny but skeptical.",
            2: "Be skeptical but impressed. Congratulate them while jokingly questioning if they cheated. Mix suspicion with genuine props. Use 🤨👀 type emojis.",
            3: "Be impressed and celebratory with just a tiny hint of playful suspicion. Mostly genuine congrats with a wink.",
            4: "Be genuinely impressed and wholesome. No suspicion at all - just pure, heartfelt congratulations for an amazing score! 🎉🏆"
        }
    else:
        return ""
    
    return prompts.get(severity, prompts[2])

def check_and_roast_daily_losers(league_id, wordle_num, conn):
    """Check if all players have posted, then roast the lowest scorer(s)"""
    try:
        cursor = conn.cursor()
        
        # Count active players in league
        cursor.execute("""
            SELECT COUNT(*) FROM players 
            WHERE league_id = %s AND active = TRUE
        """, (league_id,))
        total_players = cursor.fetchone()[0]
        
        # Count how many have posted today
        cursor.execute("""
            SELECT COUNT(*) FROM scores s
            JOIN players p ON s.player_id = p.id
            WHERE p.league_id = %s AND s.wordle_number = %s
        """, (league_id, wordle_num))
        posted_count = cursor.fetchone()[0]
        
        logging.info(f"League {league_id}: {posted_count}/{total_players} players posted for Wordle #{wordle_num}")
        
        # If not all players have posted, don't send message yet
        if posted_count < total_players:
            cursor.close()
            return
        
        # All players have posted! Find the lowest score(s)
        cursor.execute("""
            SELECT p.name, s.score 
            FROM scores s
            JOIN players p ON s.player_id = p.id
            WHERE p.league_id = %s AND s.wordle_number = %s
            ORDER BY s.score DESC
            LIMIT 1
        """, (league_id, wordle_num))
        
        worst_result = cursor.fetchone()
        if not worst_result:
            cursor.close()
            return
        
        worst_score = worst_result[1]
        
        # Get all players with the worst score (include player IDs for severity lookup)
        cursor.execute("""
            SELECT p.id, p.name 
            FROM scores s
            JOIN players p ON s.player_id = p.id
            WHERE p.league_id = %s AND s.wordle_number = %s AND s.score = %s
        """, (league_id, wordle_num, worst_score))
        
        loser_data = [(row[0], row[1]) for row in cursor.fetchall()]  # (player_id, name)
        cursor.close()
        
        if not loser_data:
            return
        
        # Check if we already sent a roast for this day (to avoid duplicates)
        # We'll use a simple check: if a message was sent in the last hour, skip
        # This prevents duplicate roasts if multiple people post at the same time
        
        # Send the roast!
        send_daily_loser_roast(loser_data, worst_score, league_id, wordle_num)
        
    except Exception as e:
        logging.error(f"Error checking daily losers: {e}")
        import traceback
        logging.error(traceback.format_exc())

def send_daily_loser_roast(loser_data, worst_score, league_id, wordle_num):
    """Send an AI-generated roast for the daily lowest scorer(s) with Wordle word puns
    
    loser_data: list of (player_id, player_name) tuples
    """
    try:
        from openai import OpenAI
        from twilio.rest import Client
        
        # Get environment variables
        twilio_sid = os.environ.get('TWILIO_ACCOUNT_SID')
        twilio_token = os.environ.get('TWILIO_AUTH_TOKEN')
        twilio_phone = os.environ.get('TWILIO_PHONE_NUMBER')
        
        # Initialize OpenAI client
        openai_client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
        
        # Map league_id to conversation SID
        conversation_sids = {
            1: 'CHb7aa3110769f42a19cea7a2be9c644d2',  # Warriorz
            3: 'CHc8f0c4a776f14bcd96e7c8838a6aec13',  # PAL
            4: 'CHed74f2e9f16240e9a578f96299c395ce',  # The Party
            7: 'CH4438ff5531514178bb13c5c0e96d5579',  # Belly Up
        }
        
        conversation_sid = conversation_sids.get(league_id)
        if not conversation_sid:
            logging.error(f"No conversation SID for league {league_id}")
            return
        
        # Get today's Wordle word (if available)
        wordle_word = get_todays_wordle_word()
        
        # Extract names from loser_data
        loser_names = [name for (player_id, name) in loser_data]
        
        # Format loser names
        if len(loser_names) == 1:
            losers_text = loser_names[0]
        elif len(loser_names) == 2:
            losers_text = f"{loser_names[0]} and {loser_names[1]}"
        else:
            losers_text = ", ".join(loser_names[:-1]) + f", and {loser_names[-1]}"
        
        # Generate AI roast message
        # Format score for context: 7 = failed (X/6), otherwise actual score
        score_display = "X/6 (failed)" if worst_score == 7 else f"{worst_score}/6"
        
        # Get per-message severity setting for this league (default)
        league_severity = get_ai_message_severity(league_id, 'daily_loser')
        
        # If multiple losers, check each player's individual severity and use the NICEST (highest number)
        # This ensures no one gets roasted harder than their personal setting allows
        severity = league_severity
        if len(loser_data) > 1:
            for player_id, player_name in loser_data:
                enabled, player_severity = get_player_ai_settings(league_id, player_id, 'daily_loser')
                if player_severity is not None and player_severity > severity:
                    severity = player_severity
                    logging.info(f"Using {player_name}'s gentler severity ({severity}) for daily loser roast")
        elif len(loser_data) == 1:
            # Single loser - check their individual setting
            player_id, player_name = loser_data[0]
            enabled, player_severity = get_player_ai_settings(league_id, player_id, 'daily_loser')
            if player_severity is not None:
                severity = player_severity
        severity_instruction = get_severity_prompt(severity, 'roast')
        
        if wordle_word:
            prompt = f"Everyone in the league has posted! Generate a roast for {losers_text} who had the worst score today (they got {score_display}). Today's Wordle word was '{wordle_word}' - weave this word SUBTLY into your roast using clever puns and wordplay. Do NOT state their score directly in the message - everyone already saw it. Do NOT highlight the Wordle word with asterisks, caps, or quotes - just use it naturally. Use varied emojis. Keep it under 280 characters. {severity_instruction}"
        else:
            prompt = f"Everyone in the league has posted! Generate a roast for {losers_text} who had the worst score today. Do NOT state their score directly - everyone already saw it. Use varied emojis. Keep it under 200 characters. {severity_instruction}"
        
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": f"You are a Wordle league bot. Create clever roasts with subtle wordplay. When given a Wordle word, weave it naturally into your message WITHOUT highlighting it - no asterisks, no caps, no quotes around the word. {severity_instruction}"},
                {"role": "user", "content": prompt}
            ],
            max_tokens=150,
            temperature=0.95  # Very high creativity for maximum fun
        )
        
        roast_message = response.choices[0].message.content.strip()
        logging.info(f"Generated daily loser roast: {roast_message}")
        
        # Send to conversation
        client = Client(twilio_sid, twilio_token)
        client.conversations.v1.conversations(conversation_sid).messages.create(
            body=roast_message,
            author=twilio_phone
        )
        
        logging.info(f"Sent daily loser roast to league {league_id} for {losers_text}")
        
    except Exception as e:
        logging.error(f"Error sending daily loser roast: {e}")
        import traceback
        logging.error(traceback.format_exc())

def send_perfect_score_congrats(player_name, score, league_id):
    """Send a congratulations message for 1/6 or 2/6 scores"""
    try:
        from openai import OpenAI
        from twilio.rest import Client
        
        # Get environment variables
        twilio_sid = os.environ.get('TWILIO_ACCOUNT_SID')
        twilio_token = os.environ.get('TWILIO_AUTH_TOKEN')
        twilio_phone = os.environ.get('TWILIO_PHONE_NUMBER')
        
        # Initialize OpenAI client
        openai_client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
        
        # Map league_id to conversation SID
        conversation_sids = {
            1: 'CHb7aa3110769f42a19cea7a2be9c644d2',  # Warriorz
            3: 'CHc8f0c4a776f14bcd96e7c8838a6aec13',  # PAL
            4: 'CHed74f2e9f16240e9a578f96299c395ce',  # The Party
            7: 'CH4438ff5531514178bb13c5c0e96d5579',  # Belly Up
        }
        
        conversation_sid = conversation_sids.get(league_id)
        if not conversation_sid:
            logging.error(f"No conversation SID for league {league_id}")
            return
        
        # Get per-message severity setting for this league
        severity = get_ai_message_severity(league_id, 'perfect_score')
        severity_instruction = get_severity_prompt(severity, 'congrats')
        
        # Generate AI congratulations message
        prompt = f"Generate a congratulations message for {player_name} who just got a {score}/6 on Wordle - an incredible score! Celebrate their achievement. Use fun emojis like 🎯🔥⭐🏆. DO NOT reveal the Wordle word. Keep it under 160 characters. {severity_instruction}"
        
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": f"You are a Wordle league bot. Celebrate amazing scores with fun emojis. {severity_instruction}"},
                {"role": "user", "content": prompt}
            ],
            max_tokens=100,
            temperature=0.9
        )
        
        congrats_message = response.choices[0].message.content.strip()
        logging.info(f"Generated perfect score congrats for {player_name}: {congrats_message}")
        
        # Send to conversation
        client = Client(twilio_sid, twilio_token)
        client.conversations.v1.conversations(conversation_sid).messages.create(
            body=congrats_message,
            author=twilio_phone
        )
        
        logging.info(f"Sent perfect score congrats to league {league_id} for {player_name}")
        
    except Exception as e:
        logging.error(f"Error sending perfect score congrats: {e}")
        import traceback
        logging.error(traceback.format_exc())

def send_failure_roast(player_name, league_id):
    """Send an AI-generated roast message when a player fails (X/6)"""
    try:
        from openai import OpenAI
        from twilio.rest import Client
        
        # Get environment variables
        twilio_sid = os.environ.get('TWILIO_ACCOUNT_SID')
        twilio_token = os.environ.get('TWILIO_AUTH_TOKEN')
        twilio_phone = os.environ.get('TWILIO_PHONE_NUMBER')
        
        # Initialize OpenAI client
        openai_client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
        
        # Map league_id to conversation SID
        conversation_sids = {
            1: 'CHb7aa3110769f42a19cea7a2be9c644d2',  # Warriorz
            3: 'CHc8f0c4a776f14bcd96e7c8838a6aec13',  # PAL
            4: 'CHed74f2e9f16240e9a578f96299c395ce',  # The Party
            7: 'CH4438ff5531514178bb13c5c0e96d5579',  # Belly Up
        }
        
        conversation_sid = conversation_sids.get(league_id)
        if not conversation_sid:
            logging.error(f"No conversation SID for league {league_id}")
            return
        
        # Get per-message severity setting for this league
        severity = get_ai_message_severity(league_id, 'failure_roast')
        severity_instruction = get_severity_prompt(severity, 'roast')
        
        # Generate AI roast message
        prompt = f"Roast {player_name} who just FAILED today's Wordle (X/6 - couldn't solve it in 6 tries!). Use creative wordplay and emojis. Keep it under 160 characters. DO NOT mention the actual Wordle word. {severity_instruction}"
        
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": f"You are a Wordle roast bot. Use puns, wordplay, and humor. Use emojis for emphasis. {severity_instruction}"},
                {"role": "user", "content": prompt}
            ],
            max_tokens=100,
            temperature=0.95  # Maximum creativity
        )
        
        roast_message = response.choices[0].message.content.strip()
        logging.info(f"Generated roast for {player_name}: {roast_message}")
        
        # Send to conversation
        client = Client(twilio_sid, twilio_token)
        client.conversations.v1.conversations(conversation_sid).messages.create(
            body=roast_message,
            author=twilio_phone
        )
        
        logging.info(f"Sent failure roast to league {league_id} for {player_name}")
        
    except Exception as e:
        logging.error(f"Error sending failure roast: {e}")
        import traceback
        logging.error(traceback.format_exc())

def save_score_to_db(player_name, wordle_num, score, emoji_pattern, league_id, conn):
    """Save score to PostgreSQL database"""
    try:
        # Get today's Wordle number for validation
        todays_wordle = get_todays_wordle_number()
        
        # Only accept today's Wordle
        if wordle_num != todays_wordle:
            logging.warning(f"Rejecting Wordle #{wordle_num} - only today's #{todays_wordle} allowed")
            return "old_score"
        
        # Get player ID
        player_id = get_player_id(player_name, league_id, conn)
        if not player_id:
            logging.error(f"Player '{player_name}' not found in league {league_id}")
            return "player_not_found"
        
        # Calculate date for this Wordle
        ref_date = date(2025, 7, 31)
        ref_wordle = 1503
        days_offset = wordle_num - ref_wordle
        wordle_date = ref_date + timedelta(days=days_offset)
        
        cursor = conn.cursor()
        
        # Check if score already exists
        cursor.execute("""
            SELECT score, emoji_pattern FROM scores 
            WHERE player_id = %s AND wordle_number = %s
        """, (player_id, wordle_num))
        
        existing_score = cursor.fetchone()
        
        now = datetime.now()
        
        if existing_score:
            # CRITICAL: Once a score is posted, it's LOCKED - never update
            # This prevents reactions or duplicate submissions from overwriting legitimate scores
            logging.info(f"Score already exists for {player_name}, Wordle #{wordle_num} - LOCKED (no updates allowed)")
            cursor.close()
            return "exists"
        else:
            # Insert new score into scores table
            cursor.execute("""
                INSERT INTO scores (player_id, wordle_number, score, date, emoji_pattern, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (player_id, wordle_num, score, wordle_date, emoji_pattern, now))
            
            # Also insert into latest_scores table for daily tracking
            cursor.execute("""
                INSERT INTO latest_scores (player_id, league_id, wordle_number, score, emoji_pattern, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (player_id) 
                DO UPDATE SET wordle_number = EXCLUDED.wordle_number, score = EXCLUDED.score, emoji_pattern = EXCLUDED.emoji_pattern, timestamp = EXCLUDED.timestamp, league_id = EXCLUDED.league_id
            """, (player_id, league_id, wordle_num, score, emoji_pattern, now))
            
            conn.commit()
            logging.info(f"Inserted new score for {player_name}, Wordle #{wordle_num}")
            cursor.close()
            
            # Check if this player is the last to post (for avoiding double-roast)
            is_last_to_post = False
            try:
                check_cursor = conn.cursor()
                # Count active players
                check_cursor.execute("""
                    SELECT COUNT(*) FROM players 
                    WHERE league_id = %s AND active = TRUE
                """, (league_id,))
                total_players = check_cursor.fetchone()[0]
                
                # Count how many have posted (including this one we just saved)
                check_cursor.execute("""
                    SELECT COUNT(*) FROM scores s
                    JOIN players p ON s.player_id = p.id
                    WHERE p.league_id = %s AND s.wordle_number = %s
                """, (league_id, wordle_num))
                posted_count = check_cursor.fetchone()[0]
                check_cursor.close()
                
                is_last_to_post = (posted_count >= total_players)
                logging.info(f"Player {player_name} is_last_to_post: {is_last_to_post} ({posted_count}/{total_players})")
            except Exception as e:
                logging.error(f"Error checking if last to post: {e}")
            
            # Auto-roast X/6 failures - check if enabled for this league
            # BUT skip if this player is the last to post - they'll be roasted in the daily loser message
            if score == 7:  # X/6 = 7 in our system
                if is_last_to_post:
                    logging.info(f"Skipping instant X/6 roast for {player_name} - they're last to post, will be included in daily loser roast")
                elif is_ai_message_enabled(league_id, 'failure_roast'):
                    try:
                        send_failure_roast(player_name, league_id)
                    except Exception as e:
                        logging.error(f"Failed to send roast message: {e}")
                else:
                    logging.info(f"Failure roast disabled for league {league_id}")
            
            # Perfect score congrats (1/6 or 2/6) - check if enabled for this league
            if score in [1, 2] and is_ai_message_enabled(league_id, 'perfect_score'):
                try:
                    send_perfect_score_congrats(player_name, score, league_id)
                except Exception as e:
                    logging.error(f"Failed to send perfect score message: {e}")
            
            # Daily loser roast when all players posted - check if enabled for this league
            if is_ai_message_enabled(league_id, 'daily_loser'):
                try:
                    check_and_roast_daily_losers(league_id, wordle_num, conn)
                except Exception as e:
                    logging.error(f"Failed to check/send daily loser roast: {e}")
            
            return "new"
            
    except Exception as e:
        logging.error(f"Error saving score: {e}")
        conn.rollback()
        return "error"

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle incoming messages from Twilio Conversations - SILENT MODE (no SMS responses)"""
    try:
        # DEBUG: Log all incoming data
        logging.info(f"Request content type: {request.content_type}")
        logging.info(f"Request is_json: {request.is_json}")
        logging.info(f"Form data keys: {list(request.form.keys())}")
        if request.is_json:
            logging.info(f"JSON data keys: {list(request.get_json().keys())}")
        
        # Twilio Conversations sends JSON payload, not form data
        # Try JSON first (Conversations), fall back to form data (simple SMS)
        if request.is_json:
            data = request.get_json()
            # Conversations webhook format
            from_number = data.get('Author', '')
            message_body = data.get('Body', '')
            event_type = data.get('EventType', '')
            
            logging.info(f"Conversations webhook: {event_type} from {from_number}")
        else:
            # Simple SMS format (fallback) - try multiple field names
            from_number = (request.form.get('From') or 
                          request.form.get('Author') or 
                          request.form.get('MessagingBinding.Address') or '')
            message_body = request.form.get('Body', '')
            logging.info(f"Simple SMS from {from_number}")
        
        logging.info(f"Message from {from_number}: {message_body[:100]}")
        
        # Ignore reaction messages (not actual score submissions)
        reaction_patterns = ['Emphasized', 'Loved', 'Liked', 'Laughed at', 'Reacted', 'Replied to', 'reacted with', 'reacted to']
        for pattern in reaction_patterns:
            if pattern in message_body:
                logging.info(f"Ignoring '{pattern}' reaction message")
                return '<?xml version="1.0" encoding="UTF-8"?><Response></Response>', 200
        
        # CRITICAL: Ignore messages with emoji reactions followed by "to" and quoted text
        # Format: "😮​ to " Wordle..." or similar emoji reactions
        import re
        if re.search(r'^[\U0001F300-\U0001F9FF\u2600-\u26FF\u2700-\u27BF].*\s+to\s+"', message_body, re.IGNORECASE):
            logging.info(f"Ignoring emoji reaction message (emoji + 'to \"')")
            return '<?xml version="1.0" encoding="UTF-8"?><Response></Response>', 200
        
        # Also ignore if message contains quotes around Wordle (someone reacting to a score)
        if ' to "Wordle' in message_body or 'to " Wordle' in message_body:
            logging.info(f"Ignoring quoted Wordle score (reaction to someone else's score)")
            return '<?xml version="1.0" encoding="UTF-8"?><Response></Response>', 200
        
        # Check for verification code (6-character alphanumeric, uppercase)
        # This is used to link a new group chat to a league
        stripped_message = message_body.strip().upper()
        if re.match(r'^[A-Z0-9]{6}$', stripped_message):
            logging.info(f"Potential verification code received: {stripped_message}")
            # Get conversation SID
            conv_sid = None
            if request.is_json:
                conv_sid = request.get_json().get('ConversationSid')
            else:
                conv_sid = request.form.get('ConversationSid')
            
            if conv_sid:
                # Check if this code matches any pending league activation
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, display_name FROM leagues 
                    WHERE verification_code = %s AND twilio_conversation_sid IS NULL
                """, (stripped_message,))
                league = cursor.fetchone()
                
                if league:
                    league_id, league_name = league
                    # Link the conversation to the league
                    cursor.execute("""
                        UPDATE leagues 
                        SET twilio_conversation_sid = %s, verification_code = NULL 
                        WHERE id = %s
                    """, (conv_sid, league_id))
                    
                    # Clear pending_activation flag for all players in this league
                    cursor.execute("""
                        UPDATE players 
                        SET pending_activation = FALSE 
                        WHERE league_id = %s
                    """, (league_id,))
                    
                    conn.commit()
                    
                    logging.info(f"✅ League {league_name} (id={league_id}) activated with conversation {conv_sid}")
                    
                    # Send confirmation message to the group
                    try:
                        from twilio.rest import Client
                        twilio_client = Client(os.environ.get('TWILIO_ACCOUNT_SID'), os.environ.get('TWILIO_AUTH_TOKEN'))
                        twilio_client.conversations.v1.conversations(conv_sid).messages.create(
                            body=f"🎉 Success! This group is now connected to {league_name}. Share your Wordle scores here and I'll track them automatically!"
                        )
                    except Exception as e:
                        logging.error(f"Error sending confirmation message: {e}")
                    
                    cursor.close()
                    conn.close()
                    return '<?xml version="1.0" encoding="UTF-8"?><Response></Response>', 200
                
                cursor.close()
                conn.close()
        
        # CRITICAL: Reject messages that don't start with "Wordle" (after stripping whitespace)
        # Legitimate submissions from NYT app always start with "Wordle"
        # Anything before "Wordle" is a reaction/comment
        stripped_message = message_body.strip()
        if not stripped_message.startswith('Wordle'):
            logging.info(f"Ignoring message that doesn't start with 'Wordle': {message_body[:50]}")
            return '<?xml version="1.0" encoding="UTF-8"?><Response></Response>', 200
        
        # Extract Wordle score
        wordle_num, score, emoji_pattern = extract_wordle_score(message_body)
        
        if not wordle_num or not score:
            logging.warning(f"No valid Wordle score found in message from {from_number}")
            # Return empty TwiML response (no SMS sent back)
            return '<?xml version="1.0" encoding="UTF-8"?><Response></Response>', 200
        
        # Map conversation SID to league ID
        # Get conversation SID from request
        conversation_sid = None
        if request.is_json:
            conversation_sid = request.get_json().get('ConversationSid')
        else:
            conversation_sid = request.form.get('ConversationSid')
        
        # Conversation to League mapping
        conversation_to_league = {
            'CHb7aa3110769f42a19cea7a2be9c644d2': 1,  # League 1: Warriorz
            'CHc8f0c4a776f14bcd96e7c8838a6aec13': 3,  # League 3: PAL
            'CHed74f2e9f16240e9a578f96299c395ce': 4,  # League 4: Party
            'CH4438ff5531514178bb13c5c0e96d5579': 7,  # League 7: BellyUp
        }
        
        # If no conversation SID or not mapped, log error and return
        league_id = conversation_to_league.get(conversation_sid)
        if not league_id:
            logging.error(f"Unknown conversation SID: {conversation_sid}")
            return '<?xml version="1.0" encoding="UTF-8"?><Response></Response>', 200
        logging.info(f"Conversation SID: {conversation_sid} -> League {league_id}")
        
        # Get player name from phone number
        player_name = get_player_from_phone(from_number, league_id)
        
        if not player_name:
            logging.error(f"❌ PLAYER NOT FOUND - Phone: {from_number}, League: {league_id}")
            logging.error(f"Available players in league {league_id}: {PHONE_MAPPINGS.get(league_id, {})}")
            # Return empty TwiML response (no SMS sent back)
            return '<?xml version="1.0" encoding="UTF-8"?><Response></Response>', 200
        
        logging.info(f"✅ Player identified: {player_name} (phone: {from_number}, league: {league_id})")
        
        # Save to database
        conn = get_db_connection()
        if not conn:
            logging.error("Database connection failed")
            # Return empty TwiML response (no SMS sent back)
            return '<?xml version="1.0" encoding="UTF-8"?><Response></Response>', 200
        
        result = save_score_to_db(player_name, wordle_num, score, emoji_pattern, league_id, conn)
        conn.close()
        
        # Log the result but don't send SMS
        if result == "new":
            logging.info(f"✅ Score recorded! {player_name}: Wordle #{wordle_num} - {score if score != 7 else 'X'}/6")
            
            # Trigger full update pipeline in background (async) with retry logic
            try:
                import threading
                def run_pipeline_async():
                    run_pipeline_with_retry(league_id, max_retries=3)
                
                thread = threading.Thread(target=run_pipeline_async, daemon=True)
                thread.start()
                logging.info(f"Pipeline triggered in background thread for league {league_id}")
            except Exception as pipeline_error:
                logging.error(f"Error starting pipeline thread: {pipeline_error}")
                # Don't fail the webhook if pipeline fails
                
        elif result == "updated":
            logging.info(f"✅ Score updated! {player_name}: Wordle #{wordle_num} - {score if score != 7 else 'X'}/6")
            
            # Also trigger full update in background with retry logic
            try:
                import threading
                def run_pipeline_async():
                    run_pipeline_with_retry(league_id, max_retries=3)
                
                thread = threading.Thread(target=run_pipeline_async, daemon=True)
                thread.start()
                logging.info(f"Pipeline triggered in background thread for league {league_id}")
            except Exception as pipeline_error:
                logging.error(f"Error starting pipeline thread: {pipeline_error}")
                
        elif result == "exists":
            logging.info(f"Score already exists for {player_name}: Wordle #{wordle_num}")
        elif result == "old_score":
            todays_wordle = get_todays_wordle_number()
            logging.warning(f"Old score rejected from {player_name}: Wordle #{wordle_num} (today is #{todays_wordle})")
        elif result == "player_not_found":
            logging.error(f"Player not found in database: {player_name}")
        else:
            logging.error(f"Error saving score for {player_name}")
        
        # Return empty TwiML response (no SMS sent back)
        return '<?xml version="1.0" encoding="UTF-8"?><Response></Response>', 200
        
    except Exception as e:
        logging.error(f"Webhook error: {e}")
        # Return empty TwiML response (no SMS sent back)
        return '<?xml version="1.0" encoding="UTF-8"?><Response></Response>', 200

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return {'status': 'healthy', 'timestamp': datetime.now().isoformat()}

# =============================================================================
# AUTH ROUTES - User Registration, Login, Logout
# =============================================================================

@app.route('/auth/login', methods=['GET', 'POST'])
def auth_login():
    """Login page and handler"""
    try:
        from auth import login_user, validate_session
        from dashboard import render_login_page
        
        # Check if already logged in - but handle errors gracefully
        session_token = request.cookies.get('session_token')
        try:
            if session_token and validate_session(session_token):
                return redirect('/dashboard')
        except Exception as e:
            logging.error(f"Session validation error: {e}")
            # Clear the bad cookie and continue to login page
            pass
        
        if request.method == 'GET':
            success = request.args.get('registered')
            return render_login_page(success='Account created! Please sign in.' if success else None)
        
        # POST - handle login
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        
        if not email or not password:
            return render_login_page(error='Please enter email and password')
        
        result = login_user(email, password)
        
        if result['success']:
            response = make_response(redirect('/dashboard'))
            logging.info(f"Setting session cookie: {result['session_token'][:20]}...")
            response.set_cookie('session_token', result['session_token'], 
                              max_age=30*24*60*60,  # 30 days
                              httponly=True,
                              samesite='Lax')
            return response
        else:
            return render_login_page(error=result['error'])
    except Exception as e:
        logging.error(f"Login route error: {e}")
        import traceback
        logging.error(traceback.format_exc())
        from dashboard import render_login_page
        return render_login_page(error='An unexpected error occurred. Please try again.')

@app.route('/auth/register', methods=['GET', 'POST'])
def auth_register():
    """Registration page and handler"""
    try:
        from auth import register_user, validate_session
        from dashboard import render_register_page
        
        # Check if already logged in - handle errors gracefully
        session_token = request.cookies.get('session_token')
        try:
            if session_token and validate_session(session_token):
                return redirect('/dashboard')
        except Exception as e:
            logging.error(f"Session validation error in register: {e}")
            pass
        
        if request.method == 'GET':
            return render_register_page()
        
        # POST - handle registration
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        phone = request.form.get('phone', '').strip()
        sms_consent = request.form.get('sms_consent') == '1'
        
        if not first_name or not last_name or not email or not password:
            return render_register_page(error='First name, last name, email, and password are required')
        
        if len(password) < 8:
            return render_register_page(error='Password must be at least 8 characters')
        
        if password != confirm_password:
            return render_register_page(error='Passwords do not match')
        
        result = register_user(email, password, first_name, last_name, phone, sms_consent)
        
        if result['success']:
            return redirect('/auth/login?registered=1')
        else:
            return render_register_page(error=result['error'])
    except Exception as e:
        logging.error(f"Register route error: {e}")
        import traceback
        logging.error(traceback.format_exc())
        from dashboard import render_register_page
        return render_register_page(error='An unexpected error occurred. Please try again.')

@app.route('/auth/logout')
def auth_logout():
    """Logout handler"""
    from auth import logout_user
    
    session_token = request.cookies.get('session_token')
    if session_token:
        logout_user(session_token)
    
    response = make_response(redirect('/auth/login'))
    response.delete_cookie('session_token')
    return response

# =============================================================================
# DASHBOARD ROUTES - League Management UI
# =============================================================================

@app.route('/dashboard')
def dashboard():
    """Main dashboard page"""
    from auth import validate_session, get_user_leagues
    from dashboard import render_dashboard
    
    session_token = request.cookies.get('session_token')
    logging.info(f"Dashboard: session_token present: {bool(session_token)}, token: {session_token[:20] if session_token else 'None'}...")
    user = validate_session(session_token)
    logging.info(f"Dashboard: user validated: {bool(user)}, user: {user}")
    
    if not user:
        logging.warning(f"Dashboard: No valid user, redirecting to login")
        return redirect('/auth/login')
    
    leagues = get_user_leagues(user['id'])
    message = request.args.get('message')
    error = request.args.get('error')
    
    return render_dashboard(user, leagues, message=message, error=error)

@app.route('/dashboard/create-league', methods=['GET', 'POST'])
def dashboard_create_league():
    """Create a new league"""
    from auth import validate_session, assign_league_to_user
    from dashboard import render_create_league
    
    session_token = request.cookies.get('session_token')
    user = validate_session(session_token)
    
    if not user:
        return redirect('/auth/login')
    
    if request.method == 'GET':
        return render_create_league(user)
    
    # POST - create the league
    league_name = request.form.get('league_name', '').strip()
    slug = request.form.get('slug', '').strip().lower()
    
    if not league_name or not slug:
        return render_create_league(user, error='League name and slug are required')
    
    # Validate slug format
    import re
    if not re.match(r'^[a-z0-9-]+$', slug):
        return render_create_league(user, error='Slug can only contain lowercase letters, numbers, and hyphens')
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if slug already exists
        cursor.execute("SELECT id FROM leagues WHERE slug = %s", (slug,))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return render_create_league(user, error=f'The slug "{slug}" is already taken. Please choose another.')
        
        # Check if league name already exists
        cursor.execute("SELECT id FROM leagues WHERE LOWER(display_name) = LOWER(%s)", (league_name,))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return render_create_league(user, error=f'A league named "{league_name}" already exists. Please choose another name.')
        
        # Get next available ID (since id column doesn't auto-increment)
        cursor.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM leagues")
        next_id = cursor.fetchone()[0]
        
        # Create the league (all AI messages default to OFF)
        cursor.execute("""
            INSERT INTO leagues (id, name, display_name, slug, ai_perfect_score_congrats, ai_failure_roast, ai_sunday_race_update, ai_daily_loser_roast)
            VALUES (%s, %s, %s, %s, false, false, false, false)
            RETURNING id
        """, (next_id, slug, league_name, slug))
        
        league_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()
        
        # Assign league to user as owner
        assign_league_to_user(user['id'], league_id, 'owner')
        
        logging.info(f"Created new league: {league_name} (id={league_id}, slug={slug}) by user {user['id']}")
        
        return redirect(f'/dashboard/league/{league_id}?message=League created! Now add players and connect your group chat.')
        
    except Exception as e:
        logging.error(f"Error creating league: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return render_create_league(user, error=f'Failed to create league: {str(e)}')

@app.route('/dashboard/league/<int:league_id>')
def dashboard_league(league_id):
    """League management page"""
    from auth import validate_session, can_manage_league
    from dashboard import render_league_management, get_league_players, get_league_info
    
    session_token = request.cookies.get('session_token')
    logging.info(f"League page: session_token present: {bool(session_token)}")
    user = validate_session(session_token)
    logging.info(f"League page: user validated: {bool(user)}")
    
    if not user:
        logging.warning(f"League page: No valid user, redirecting to login")
        return redirect('/auth/login')
    
    if not can_manage_league(user['id'], league_id):
        return redirect('/dashboard?error=You do not have access to this league')
    
    league = get_league_info(league_id)
    if not league:
        return redirect('/dashboard?error=League not found')
    
    players = get_league_players(league_id)
    player_ai_settings = get_all_player_ai_settings(league_id)
    message = request.args.get('message')
    error = request.args.get('error')
    
    return render_league_management(user, league, players, player_ai_settings=player_ai_settings, message=message, error=error)

@app.route('/static/<path:filename>')
def serve_static(filename):
    """Serve static files like images"""
    return send_from_directory('.', filename)

@app.route('/leagues/<slug>')
def public_league_page(slug):
    """Public league page - serves the leaderboard HTML (e.g., /leagues/warriorz)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, display_name, slug 
            FROM leagues 
            WHERE slug = %s
        """, (slug,))
        league = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not league:
            return "League not found", 404
        
        league_id = league[0]
        display_name = league[2] or league[1]
        
        # Generate the leaderboard HTML using existing pipeline
        from update_pipeline import generate_league_html
        html_content = generate_league_html(league_id)
        
        if html_content:
            # Inline the CSS and JS files so the page works standalone
            import os
            base_dir = os.path.dirname(os.path.abspath(__file__))
            
            with open(os.path.join(base_dir, 'styles.css'), 'r', encoding='utf-8') as f:
                styles_css = f.read()
            with open(os.path.join(base_dir, 'script.js'), 'r', encoding='utf-8') as f:
                script_js = f.read()
            with open(os.path.join(base_dir, 'tabs.js'), 'r', encoding='utf-8') as f:
                tabs_js = f.read()
            
            # Replace external references with inline content
            html_content = html_content.replace(
                '<link rel="stylesheet" href="styles.css"/>',
                f'<style>{styles_css}</style>'
            )
            html_content = html_content.replace(
                '<script src="script.js"></script>',
                f'<script>{script_js}</script>'
            )
            html_content = html_content.replace(
                '<script src="tabs.js"></script>',
                f'<script>{tabs_js}</script>'
            )
            
            return html_content
        else:
            return f"<h1>{display_name}</h1><p>No data available yet.</p>", 200
            
    except Exception as e:
        logging.error(f"Error serving public league page: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return "Error loading league", 500

@app.route('/dashboard/league/<int:league_id>/rename', methods=['POST'])
def dashboard_rename_league(league_id):
    """Rename a league"""
    from auth import validate_session, can_manage_league
    
    session_token = request.cookies.get('session_token')
    user = validate_session(session_token)
    
    if not user:
        return redirect('/auth/login')
    
    if not can_manage_league(user['id'], league_id):
        return redirect('/dashboard?error=You do not have access to this league')
    
    display_name = request.form.get('display_name', '').strip()
    if not display_name:
        return redirect(f'/dashboard/league/{league_id}?error=Display name is required')
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE leagues SET display_name = %s WHERE id = %s", (display_name, league_id))
        conn.commit()
        cursor.close()
        conn.close()
        
        # Regenerate HTML to reflect the name change
        from update_pipeline import run_update_pipeline
        run_update_pipeline(league_id)
        
        return redirect(f'/dashboard/league/{league_id}?message=League renamed successfully')
    except Exception as e:
        logging.error(f"Error renaming league: {e}")
        return redirect(f'/dashboard/league/{league_id}?error=Failed to rename league')

@app.route('/dashboard/league/<int:league_id>/add-player', methods=['POST'])
def dashboard_add_player(league_id):
    """Add a player to a league"""
    from auth import validate_session, can_manage_league
    
    session_token = request.cookies.get('session_token')
    user = validate_session(session_token)
    
    if not user:
        return redirect('/auth/login')
    
    if not can_manage_league(user['id'], league_id):
        return redirect('/dashboard?error=You do not have access to this league')
    
    name = request.form.get('name', '').strip()
    phone = request.form.get('phone', '').strip()
    
    # Clean phone number - remove non-digits
    phone = re.sub(r'\D', '', phone)
    
    if not name or not phone:
        return redirect(f'/dashboard/league/{league_id}?error=Name and phone are required')
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if phone already exists in this league
        cursor.execute("SELECT id FROM players WHERE league_id = %s AND phone_number = %s", (league_id, phone))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return redirect(f'/dashboard/league/{league_id}?error=Phone number already exists in this league')
        
        # Check if league is already active (has a conversation_sid)
        cursor.execute("SELECT twilio_conversation_sid FROM leagues WHERE id = %s", (league_id,))
        league_result = cursor.fetchone()
        is_active_league = league_result and league_result[0] is not None
        
        # Insert new player - mark as pending_activation if league is already active
        cursor.execute("""
            INSERT INTO players (name, phone_number, league_id, active, pending_activation)
            VALUES (%s, %s, %s, TRUE, %s)
        """, (name, phone, league_id, is_active_league))
        conn.commit()
        cursor.close()
        conn.close()
        
        # Clear phone mappings cache so new player is recognized immediately
        global _phone_mappings_cache_time
        _phone_mappings_cache_time = None
        
        # Regenerate HTML so player shows up on the league page
        from update_pipeline import run_update_pipeline
        run_update_pipeline(league_id)
        
        logging.info(f"Added player {name} ({phone}) to league {league_id} - pending_activation={is_active_league} - HTML regenerated")
        
        if is_active_league:
            return redirect(f'/dashboard/league/{league_id}?message=Player {name} added. Note: They won\'t receive messages until you re-link your group chat.')
        else:
            return redirect(f'/dashboard/league/{league_id}?message=Player {name} added successfully')
    except Exception as e:
        logging.error(f"Error adding player: {e}")
        return redirect(f'/dashboard/league/{league_id}?error=Failed to add player')

@app.route('/dashboard/league/<int:league_id>/edit-player', methods=['POST'])
def dashboard_edit_player(league_id):
    """Edit a player's name and/or phone number"""
    from auth import validate_session, can_manage_league
    
    session_token = request.cookies.get('session_token')
    user = validate_session(session_token)
    
    if not user:
        return redirect('/auth/login')
    
    if not can_manage_league(user['id'], league_id):
        return redirect('/dashboard?error=You do not have access to this league')
    
    player_id = request.form.get('player_id')
    new_name = request.form.get('name', '').strip()
    new_phone = request.form.get('phone', '').strip()
    
    if not player_id or not new_name:
        return redirect(f'/dashboard/league/{league_id}?error=Player ID and name are required')
    
    # Clean phone number
    new_phone = re.sub(r'\D', '', new_phone)
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get current player info
        cursor.execute("SELECT name, phone_number FROM players WHERE id = %s AND league_id = %s", (player_id, league_id))
        result = cursor.fetchone()
        if not result:
            cursor.close()
            conn.close()
            return redirect(f'/dashboard/league/{league_id}?error=Player not found')
        
        old_name, old_phone = result
        
        # Update player
        cursor.execute("""
            UPDATE players SET name = %s, phone_number = %s WHERE id = %s AND league_id = %s
        """, (new_name, new_phone if new_phone else None, player_id, league_id))
        conn.commit()
        cursor.close()
        conn.close()
        
        # Clear phone mappings cache
        global _phone_mappings_cache_time
        _phone_mappings_cache_time = None
        
        # Regenerate HTML to reflect changes
        from update_pipeline import run_update_pipeline
        run_update_pipeline(league_id)
        
        logging.info(f"Updated player {old_name} -> {new_name} in league {league_id}")
        return redirect(f'/dashboard/league/{league_id}?message=Player {new_name} updated successfully')
    except Exception as e:
        logging.error(f"Error updating player: {e}")
        return redirect(f'/dashboard/league/{league_id}?error=Failed to update player')

@app.route('/dashboard/league/<int:league_id>/remove-player', methods=['POST'])
def dashboard_remove_player(league_id):
    """Remove a player from a league (soft delete)"""
    from auth import validate_session, can_manage_league
    
    session_token = request.cookies.get('session_token')
    user = validate_session(session_token)
    
    if not user:
        return redirect('/auth/login')
    
    if not can_manage_league(user['id'], league_id):
        return redirect('/dashboard?error=You do not have access to this league')
    
    player_id = request.form.get('player_id')
    if not player_id:
        return redirect(f'/dashboard/league/{league_id}?error=Player ID is required')
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get player name for message
        cursor.execute("SELECT name FROM players WHERE id = %s AND league_id = %s", (player_id, league_id))
        result = cursor.fetchone()
        if not result:
            cursor.close()
            conn.close()
            return redirect(f'/dashboard/league/{league_id}?error=Player not found')
        
        player_name = result[0]
        
        # Soft delete - set active to FALSE
        cursor.execute("UPDATE players SET active = FALSE WHERE id = %s AND league_id = %s", (player_id, league_id))
        conn.commit()
        cursor.close()
        conn.close()
        
        # Clear phone mappings cache so removed player is no longer recognized
        global _phone_mappings_cache_time
        _phone_mappings_cache_time = None
        
        # Regenerate HTML
        from update_pipeline import run_update_pipeline
        run_update_pipeline(league_id)
        
        logging.info(f"Removed player {player_name} from league {league_id} - HTML regenerated")
        return redirect(f'/dashboard/league/{league_id}?message=Player {player_name} removed')
    except Exception as e:
        logging.error(f"Error removing player: {e}")
        return redirect(f'/dashboard/league/{league_id}?error=Failed to remove player')

@app.route('/dashboard/league/<int:league_id>/delete', methods=['POST'])
def dashboard_delete_league(league_id):
    """Delete a league and all associated data"""
    from auth import validate_session, can_manage_league
    
    session_token = request.cookies.get('session_token')
    user = validate_session(session_token)
    
    if not user:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    if not can_manage_league(user['id'], league_id):
        return jsonify({'success': False, 'error': 'You do not have access to this league'}), 403
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get league name for logging
        cursor.execute("SELECT name, display_name FROM leagues WHERE id = %s", (league_id,))
        league_row = cursor.fetchone()
        if not league_row:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'League not found'}), 404
        
        league_name = league_row[1] or league_row[0]
        
        # Get player IDs for this league first (scores table uses player_id, not league_id)
        cursor.execute("SELECT id FROM players WHERE league_id = %s", (league_id,))
        player_ids = [row[0] for row in cursor.fetchall()]
        
        # Delete in order
        # 1. Delete weekly winners
        cursor.execute("DELETE FROM weekly_winners WHERE league_id = %s", (league_id,))
        
        # 2. Delete latest scores  
        cursor.execute("DELETE FROM latest_scores WHERE league_id = %s", (league_id,))
        
        # 3. Delete scores (via player_ids since scores table doesn't have league_id)
        if player_ids:
            cursor.execute("DELETE FROM scores WHERE player_id = ANY(%s)", (player_ids,))
        
        # 4. Delete players
        cursor.execute("DELETE FROM players WHERE league_id = %s", (league_id,))
        
        # 5. Delete user_leagues associations
        cursor.execute("DELETE FROM user_leagues WHERE league_id = %s", (league_id,))
        
        # 6. Finally delete the league itself
        cursor.execute("DELETE FROM leagues WHERE id = %s", (league_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logging.info(f"Deleted league {league_name} (id={league_id}) by user {user['id']}")
        return jsonify({'success': True, 'message': f'League {league_name} deleted'})
        
    except Exception as e:
        logging.error(f"Error deleting league: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/dashboard/league/<int:league_id>/generate-code', methods=['POST'])
def dashboard_generate_code(league_id):
    """Generate a verification code for league activation"""
    from auth import validate_session, can_manage_league
    import random
    import string
    
    session_token = request.cookies.get('session_token')
    user = validate_session(session_token)
    
    if not user:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    if not can_manage_league(user['id'], league_id):
        return jsonify({'success': False, 'error': 'Access denied'}), 403
    
    try:
        # Generate a 6-character alphanumeric code (uppercase for easy reading)
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Store the code in the leagues table
        cursor.execute("""
            UPDATE leagues SET verification_code = %s WHERE id = %s
        """, (code, league_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logging.info(f"Generated verification code {code} for league {league_id}")
        return jsonify({'success': True, 'code': code})
        
    except Exception as e:
        logging.error(f"Error generating verification code: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/dashboard/league/<int:league_id>/check-status')
def dashboard_check_status(league_id):
    """Check if a league has been activated"""
    from auth import validate_session, can_manage_league
    
    session_token = request.cookies.get('session_token')
    user = validate_session(session_token)
    
    if not user:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    if not can_manage_league(user['id'], league_id):
        return jsonify({'success': False, 'error': 'Access denied'}), 403
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT twilio_conversation_sid FROM leagues WHERE id = %s", (league_id,))
        result = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        active = result and result[0] is not None
        return jsonify({'success': True, 'active': active})
        
    except Exception as e:
        logging.error(f"Error checking league status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/setup-verification-code-column', methods=['POST'])
def setup_verification_code_column():
    """One-time migration to add verification_code column to leagues table"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            ALTER TABLE leagues 
            ADD COLUMN IF NOT EXISTS verification_code VARCHAR(10)
        """)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'verification_code column added'})
    except Exception as e:
        logging.error(f"Error adding verification_code column: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/setup-pending-activation-column', methods=['POST'])
def setup_pending_activation_column():
    """One-time migration to add pending_activation column to players table"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            ALTER TABLE players 
            ADD COLUMN IF NOT EXISTS pending_activation BOOLEAN DEFAULT FALSE
        """)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'pending_activation column added to players'})
    except Exception as e:
        logging.error(f"Error adding pending_activation column: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/setup-ai-messaging-columns', methods=['POST'])
def setup_ai_messaging_columns():
    """One-time migration to add AI messaging toggle columns to leagues table"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Add 4 columns for AI messaging toggles
        columns = [
            ("ai_perfect_score_congrats", "FALSE"),
            ("ai_failure_roast", "TRUE"),
            ("ai_sunday_race_update", "TRUE"),
            ("ai_daily_loser_roast", "FALSE")
        ]
        
        results = []
        for col_name, default_val in columns:
            try:
                cursor.execute(f"""
                    ALTER TABLE leagues 
                    ADD COLUMN IF NOT EXISTS {col_name} BOOLEAN DEFAULT {default_val}
                """)
                results.append(f"Added {col_name}")
            except Exception as e:
                results.append(f"{col_name}: {str(e)}")
                conn.rollback()
        
        conn.commit()
        
        # Verify columns exist
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'leagues' AND column_name LIKE 'ai_%'
        """)
        ai_columns = [c[0] for c in cursor.fetchall()]
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'results': results,
            'ai_columns': ai_columns
        })
    except Exception as e:
        logging.error(f"Error setting up AI messaging columns: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/dashboard/league/<int:league_id>/ai-settings', methods=['POST'])
def dashboard_ai_settings(league_id):
    """Update AI messaging settings for a league"""
    from auth import validate_session, can_manage_league
    import json
    
    session_token = request.cookies.get('session_token')
    user = validate_session(session_token)
    
    if not user:
        return redirect('/auth/login')
    
    if not can_manage_league(user['id'], league_id):
        return redirect('/dashboard?error=You do not have access to this league')
    
    # Get checkbox values (they come as 'true' or 'false' strings)
    ai_perfect_score = request.form.get('ai_perfect_score_congrats') == 'true'
    ai_failure_roast = request.form.get('ai_failure_roast') == 'true'
    ai_sunday_race = request.form.get('ai_sunday_race_update') == 'true'
    ai_daily_loser = request.form.get('ai_daily_loser_roast') == 'true'
    
    # Parse per-message severity and player settings from JSON
    severity_data_str = request.form.get('ai_message_severity', '{}')
    try:
        severity_data = json.loads(severity_data_str) if severity_data_str.startswith('{') else {'perfect_score': int(severity_data_str), 'failure_roast': 2, 'daily_loser': 2}
    except:
        severity_data = {'perfect_score': 2, 'failure_roast': 2, 'daily_loser': 2}
    
    perfect_score_severity = severity_data.get('perfect_score', 2)
    failure_roast_severity = severity_data.get('failure_roast', 2)
    daily_loser_severity = severity_data.get('daily_loser', 2)
    player_settings = severity_data.get('player_settings', {})
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Update league-level settings
        cursor.execute("""
            UPDATE leagues 
            SET ai_perfect_score_congrats = %s,
                ai_failure_roast = %s,
                ai_sunday_race_update = %s,
                ai_daily_loser_roast = %s,
                ai_perfect_score_severity = %s,
                ai_failure_roast_severity = %s,
                ai_daily_loser_severity = %s
            WHERE id = %s
        """, (ai_perfect_score, ai_failure_roast, ai_sunday_race, ai_daily_loser, 
              perfect_score_severity, failure_roast_severity, daily_loser_severity, league_id))
        
        # Update player-specific settings
        for key, settings in player_settings.items():
            # key format: "message_type_player_id"
            parts = key.rsplit('_', 1)
            if len(parts) == 2:
                message_type = parts[0]
                player_id = int(parts[1])
                enabled = settings.get('enabled', True)
                severity_override = settings.get('severity') if settings.get('severity') else None
                
                # Upsert player settings
                cursor.execute("""
                    INSERT INTO ai_player_settings (league_id, player_id, message_type, enabled, severity_override, updated_at)
                    VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (league_id, player_id, message_type) 
                    DO UPDATE SET enabled = EXCLUDED.enabled, severity_override = EXCLUDED.severity_override, updated_at = CURRENT_TIMESTAMP
                """, (league_id, player_id, message_type, enabled, severity_override))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logging.info(f"Updated AI settings for league {league_id}: perfect={ai_perfect_score}, failure={ai_failure_roast}, sunday={ai_sunday_race}, daily_loser={ai_daily_loser}")
        return redirect(f'/dashboard/league/{league_id}?message=AI messaging settings updated')
    except Exception as e:
        logging.error(f"Error updating AI settings: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return redirect(f'/dashboard/league/{league_id}?error=Failed to update AI settings')

@app.route('/dashboard/league/<int:league_id>/message-config', methods=['POST'])
def dashboard_message_config(league_id):
    """Save message config (severity and player settings) for a specific message type"""
    from auth import validate_session, can_manage_league
    
    session_token = request.cookies.get('session_token')
    user = validate_session(session_token)
    
    if not user:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    if not can_manage_league(user['id'], league_id):
        return jsonify({'success': False, 'error': 'Access denied'}), 403
    
    data = request.get_json()
    message_type = data.get('message_type')
    severity = data.get('severity', 2)
    player_settings = data.get('player_settings', {})
    
    if not message_type:
        return jsonify({'success': False, 'error': 'Missing message_type'}), 400
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Update league-level severity for this message type
        severity_column = f"ai_{message_type}_severity"
        cursor.execute(f"""
            UPDATE leagues 
            SET {severity_column} = %s
            WHERE id = %s
        """, (severity, league_id))
        
        # Update player-specific settings
        for key, settings in player_settings.items():
            # key format: "message_type_player_id"
            parts = key.rsplit('_', 1)
            if len(parts) == 2:
                msg_type = parts[0]
                player_id = int(parts[1])
                enabled = settings.get('enabled', True)
                severity_override = settings.get('severity') if settings.get('severity') else None
                
                # Upsert player settings
                cursor.execute("""
                    INSERT INTO ai_player_settings (league_id, player_id, message_type, enabled, severity_override, updated_at)
                    VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (league_id, player_id, message_type) 
                    DO UPDATE SET enabled = EXCLUDED.enabled, severity_override = EXCLUDED.severity_override, updated_at = CURRENT_TIMESTAMP
                """, (league_id, player_id, msg_type, enabled, severity_override))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logging.info(f"Updated message config for league {league_id}, type={message_type}, severity={severity}")
        return jsonify({'success': True})
    except Exception as e:
        logging.error(f"Error updating message config: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/setup-ai-severity-column', methods=['POST'])
def setup_ai_severity_column():
    """One-time migration to add AI message severity column to leagues table"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Add severity column (1=savage, 2=spicy, 3=playful, 4=gentle) - default 2 (spicy)
        cursor.execute("""
            ALTER TABLE leagues 
            ADD COLUMN IF NOT EXISTS ai_message_severity INTEGER DEFAULT 2
        """)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'AI severity column added successfully'})
    except Exception as e:
        logging.error(f"Error adding AI severity column: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/setup-ai-per-message-settings', methods=['POST'])
def setup_ai_per_message_settings():
    """Migration to add per-message severity and player settings table"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Add per-message severity columns to leagues table
        cursor.execute("""
            ALTER TABLE leagues 
            ADD COLUMN IF NOT EXISTS ai_perfect_score_severity INTEGER DEFAULT 2
        """)
        cursor.execute("""
            ALTER TABLE leagues 
            ADD COLUMN IF NOT EXISTS ai_failure_roast_severity INTEGER DEFAULT 2
        """)
        cursor.execute("""
            ALTER TABLE leagues 
            ADD COLUMN IF NOT EXISTS ai_daily_loser_severity INTEGER DEFAULT 2
        """)
        
        # Create player AI settings table for exclusions and per-player overrides
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_player_settings (
                id SERIAL PRIMARY KEY,
                league_id INTEGER NOT NULL REFERENCES leagues(id),
                player_id INTEGER NOT NULL REFERENCES players(id),
                message_type VARCHAR(50) NOT NULL,
                enabled BOOLEAN DEFAULT TRUE,
                severity_override INTEGER DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(league_id, player_id, message_type)
            )
        """)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Per-message AI settings schema created'})
    except Exception as e:
        logging.error(f"Error setting up per-message AI settings: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/setup-league-slug', methods=['POST'])
def setup_league_slug():
    """Migration to add slug column to leagues table and set existing slugs"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Add slug column
        cursor.execute("""
            ALTER TABLE leagues 
            ADD COLUMN IF NOT EXISTS slug VARCHAR(100) UNIQUE
        """)
        
        # Set slugs for existing leagues
        existing_slugs = {
            1: 'warriorz',
            3: 'pal',
            4: 'party',
            7: 'bellyup'
        }
        
        for league_id, slug in existing_slugs.items():
            cursor.execute("""
                UPDATE leagues SET slug = %s WHERE id = %s AND slug IS NULL
            """, (slug, league_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Slug column added and existing leagues updated'})
    except Exception as e:
        logging.error(f"Error setting up league slug: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/setup-auth-tables', methods=['POST'])
def setup_auth_tables():
    """One-time setup endpoint to create auth tables"""
    try:
        from auth import create_auth_tables
        result = create_auth_tables()
        return jsonify({'success': result, 'message': 'Auth tables created' if result else 'Failed to create tables'})
    except Exception as e:
        logging.error(f"Error setting up auth tables: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/update-conversation-sids', methods=['POST'])
def update_conversation_sids():
    """One-time endpoint to update existing leagues with their conversation SIDs"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Mapping of league_id to conversation_sid
        league_sids = {
            1: 'CHb7aa3110769f42a19cea7a2be9c644d2',  # Warriorz
            3: 'CHc8f0c4a776f14bcd96e7c8838a6aec13',  # PAL
            4: 'CHed74f2e9f16240e9a578f96299c395ce',  # Party
            7: 'CH4438ff5531514178bb13c5c0e96d5579',  # BellyUp
        }
        
        for league_id, conversation_sid in league_sids.items():
            cursor.execute("""
                UPDATE leagues 
                SET twilio_conversation_sid = %s 
                WHERE id = %s
            """, (conversation_sid, league_id))
            logging.info(f"Updated league {league_id} with conversation_sid {conversation_sid}")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Updated 4 leagues with conversation SIDs'})
    except Exception as e:
        logging.error(f"Error updating conversation SIDs: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/assign-leagues-to-user', methods=['POST'])
def assign_leagues_to_user():
    """Admin endpoint to assign existing leagues to a user"""
    try:
        from auth import assign_league_to_user
        
        data = request.get_json()
        user_id = data.get('user_id')
        league_ids = data.get('league_ids', [])
        
        if not user_id or not league_ids:
            return jsonify({'success': False, 'error': 'user_id and league_ids required'}), 400
        
        for league_id in league_ids:
            assign_league_to_user(user_id, league_id, 'owner')
        
        return jsonify({'success': True, 'message': f'Assigned {len(league_ids)} leagues to user {user_id}'})
    except Exception as e:
        logging.error(f"Error assigning leagues: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/recent-messages/<int:league_id>', methods=['GET'])
def recent_messages(league_id):
    """Get recent messages from a league's Twilio conversation for quick checking"""
    try:
        from twilio.rest import Client
        
        conversation_sids = {
            1: 'CHb7aa3110769f42a19cea7a2be9c644d2',  # Warriorz
            3: 'CHc8f0c4a776f14bcd96e7c8838a6aec13',  # PAL
            4: 'CHed74f2e9f16240e9a578f96299c395ce',  # The Party
            7: 'CH4438ff5531514178bb13c5c0e96d5579',  # Belly Up
        }
        
        league_names = {1: 'Warriorz', 3: 'PAL', 4: 'The Party', 7: 'Belly Up'}
        
        conversation_sid = conversation_sids.get(league_id)
        if not conversation_sid:
            return f"<h2>League {league_id} not found</h2>", 404
        
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        
        # Fetch last 20 messages (most recent first)
        messages = client.conversations.v1.conversations(conversation_sid).messages.list(limit=20, order='desc')
        
        # Build HTML response
        html = f"""
        <html>
        <head>
            <title>Recent Messages - {league_names.get(league_id, f'League {league_id}')}</title>
            <style>
                body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 20px auto; padding: 0 20px; background: #1a1a1b; color: #d7dadc; }}
                h1 {{ color: #00E8DA; }}
                .message {{ background: #272729; padding: 15px; margin: 10px 0; border-radius: 8px; border-left: 4px solid #00E8DA; }}
                .message.wordle {{ border-left-color: #FFA64D; }}
                .author {{ font-weight: bold; color: #00E8DA; }}
                .time {{ color: #818384; font-size: 0.85em; }}
                .body {{ margin-top: 8px; white-space: pre-wrap; }}
                a {{ color: #00E8DA; }}
            </style>
        </head>
        <body>
            <h1>📱 Recent Messages - {league_names.get(league_id, f'League {league_id}')}</h1>
            <p><a href="/recent-messages/1">League 1</a> | <a href="/recent-messages/3">League 3</a> | <a href="/recent-messages/4">League 4</a> | <a href="/recent-messages/7">League 7</a></p>
            <p style="color: #818384;">Showing last 20 messages (newest first)</p>
        """
        
        for msg in messages:
            # Check if it's a Wordle score
            is_wordle = msg.body and msg.body.strip().startswith('Wordle')
            msg_class = 'message wordle' if is_wordle else 'message'
            
            # Format timestamp
            time_str = msg.date_created.strftime('%Y-%m-%d %H:%M:%S') if msg.date_created else 'Unknown'
            
            # Get author (phone number or participant identity)
            author = msg.author or 'Unknown'
            
            html += f"""
            <div class="{msg_class}">
                <span class="author">{author}</span>
                <span class="time"> - {time_str}</span>
                <div class="body">{msg.body or '[No body]'}</div>
            </div>
            """
        
        html += "</body></html>"
        return html, 200
        
    except Exception as e:
        logging.error(f"Error fetching recent messages: {e}")
        import traceback
        traceback.print_exc()
        return f"<h2>Error: {str(e)}</h2>", 500

@app.route('/daily-reset', methods=['GET', 'POST'])
def daily_reset_endpoint():
    """
    Endpoint for scheduled daily reset
    Should be called at midnight Pacific by external cron service
    """
    try:
        from scheduled_tasks import run_all_leagues_daily_reset
        logging.info("Daily reset triggered via endpoint")
        run_all_leagues_daily_reset()
        return {'status': 'success', 'message': 'Daily reset completed'}, 200
    except Exception as e:
        logging.error(f"Daily reset error: {e}")
        return {'status': 'error', 'message': str(e)}, 500

@app.route('/trigger-daily-loser-roast', methods=['GET', 'POST'])
def trigger_daily_loser_roast():
    """
    Manually trigger the daily loser roast check for all leagues.
    Checks if all players have posted, finds the worst scorer(s), and sends roast.
    """
    try:
        # Get league_id from request, or check all leagues
        if request.method == 'POST' and request.is_json:
            league_ids = request.get_json().get('league_ids', [1, 3, 4, 7])
        elif request.args.get('league_id'):
            league_ids = [int(request.args.get('league_id'))]
        else:
            league_ids = [1, 3, 4, 7]  # All active leagues
        
        wordle_num = get_todays_wordle_number()
        results = []
        
        conn = get_db_connection()
        if not conn:
            return {'status': 'error', 'message': 'Database connection failed'}, 500
        
        for league_id in league_ids:
            try:
                cursor = conn.cursor()
                
                # Count active players in league
                cursor.execute("""
                    SELECT COUNT(*) FROM players 
                    WHERE league_id = %s AND active = TRUE
                """, (league_id,))
                total_players = cursor.fetchone()[0]
                
                # Count how many have posted today
                cursor.execute("""
                    SELECT COUNT(*) FROM scores s
                    JOIN players p ON s.player_id = p.id
                    WHERE p.league_id = %s AND s.wordle_number = %s
                """, (league_id, wordle_num))
                posted_count = cursor.fetchone()[0]
                
                if posted_count < total_players:
                    results.append({
                        'league_id': league_id,
                        'status': 'waiting',
                        'posted': posted_count,
                        'total': total_players,
                        'message': f'Only {posted_count}/{total_players} players posted'
                    })
                    cursor.close()
                    continue
                
                # All players posted! Find worst score
                cursor.execute("""
                    SELECT p.name, s.score 
                    FROM scores s
                    JOIN players p ON s.player_id = p.id
                    WHERE p.league_id = %s AND s.wordle_number = %s
                    ORDER BY s.score DESC
                    LIMIT 1
                """, (league_id, wordle_num))
                
                worst_result = cursor.fetchone()
                if not worst_result:
                    results.append({'league_id': league_id, 'status': 'error', 'message': 'No scores found'})
                    cursor.close()
                    continue
                
                worst_score = worst_result[1]
                
                # Get all players with worst score
                cursor.execute("""
                    SELECT p.name 
                    FROM scores s
                    JOIN players p ON s.player_id = p.id
                    WHERE p.league_id = %s AND s.wordle_number = %s AND s.score = %s
                """, (league_id, wordle_num, worst_score))
                
                losers = [row[0] for row in cursor.fetchall()]
                cursor.close()
                
                # Send the roast!
                send_daily_loser_roast(losers, worst_score, league_id, wordle_num)
                
                results.append({
                    'league_id': league_id,
                    'status': 'roasted',
                    'losers': losers,
                    'worst_score': worst_score,
                    'message': f'Roasted {", ".join(losers)} with score {worst_score}'
                })
                
            except Exception as e:
                results.append({'league_id': league_id, 'status': 'error', 'message': str(e)})
        
        conn.close()
        return {'status': 'success', 'wordle_num': wordle_num, 'results': results}, 200
        
    except Exception as e:
        logging.error(f"Trigger daily loser roast error: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return {'status': 'error', 'message': str(e)}, 500

@app.route('/fix-jeremy', methods=['POST'])
def fix_jeremy():
    """Temporary endpoint to fix Jeremy's score for Wordle 1623"""
    try:
        from league_data_adapter import get_db_connection
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Find Jeremy
        cursor.execute("""
            SELECT id, name FROM players 
            WHERE league_id = 7 AND phone_number LIKE '%8587751124%'
        """)
        
        player = cursor.fetchone()
        if not player:
            return {'error': 'Jeremy not found'}, 404
        
        player_id = player[0]
        player_name = player[1]
        
        # Jeremy's correct score
        correct_score = 4
        correct_emoji = "🟩🟩⬛⬛⬛\n🟩🟩⬛⬛⬛\n🟩🟩🟩🟩⬛\n🟩🟩🟩🟩🟩"
        
        # Update scores table
        cursor.execute("""
            UPDATE scores
            SET score = %s, emoji_pattern = %s, timestamp = %s
            WHERE player_id = %s AND wordle_number = 1623
        """, (correct_score, correct_emoji, datetime.now(), player_id))
        
        # Update latest_scores table
        cursor.execute("""
            UPDATE latest_scores
            SET score = %s, emoji_pattern = %s, timestamp = %s
            WHERE player_id = %s AND wordle_number = 1623
        """, (correct_score, correct_emoji, datetime.now(), player_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logging.info(f"✅ Fixed {player_name} score to 4/6 for Wordle 1623")
        
        return {
            'success': True,
            'message': f'Fixed {player_name} score to 4/6 for Wordle 1623',
            'player_id': player_id
        }, 200
        
    except Exception as e:
        logging.error(f"Error fixing Jeremy's score: {e}")
        return {'error': str(e)}, 500

@app.route('/restore-today', methods=['POST'])
def restore_today():
    """Restore today's scores from Twilio logs"""
    try:
        from restore_todays_scores import restore_todays_scores
        logging.info("Restoring today's scores from Twilio...")
        count = restore_todays_scores()
        return {
            'success': True,
            'message': f'Restored {count} scores from Twilio',
            'scores_restored': count
        }, 200
    except Exception as e:
        logging.error(f"Error restoring scores: {e}")
        import traceback
        traceback.print_exc()
        return {'error': str(e)}, 500

@app.route('/restore-nov30', methods=['POST'])
def restore_nov30():
    """Restore Nov 30 scores for Matt and Rob"""
    try:
        from restore_nov30 import restore_scores
        logging.info("Restoring Nov 30 scores...")
        success = restore_scores()
        
        if success:
            # Trigger HTML regeneration
            from update_tables_cloud import run_full_update_for_league
            logging.info("Regenerating HTML...")
            run_full_update_for_league(league_id=6)
            
            return {
                'success': True,
                'message': 'Restored Nov 30 scores and regenerated HTML'
            }, 200
        else:
            return {
                'success': False,
                'message': 'No scores were restored'
            }, 200
    except Exception as e:
        logging.error(f"Error restoring Nov 30 scores: {e}")
        import traceback
        traceback.print_exc()
        return {'error': str(e)}, 500

@app.route('/reset-weekly-winners', methods=['POST'])
def reset_weekly_winners():
    """Clear ALL weekly winners and recalculate just last week"""
    try:
        from league_data_adapter import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Delete ALL weekly winners
        cursor.execute("DELETE FROM weekly_winners")
        deleted = cursor.rowcount
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logging.info(f"Deleted {deleted} weekly winner rows")
        
        # Now recalculate last week
        from calculate_weekly_winners import calculate_last_week_winners
        
        results = {}
        for league_id in [6, 7]:
            try:
                success = calculate_last_week_winners(league_id)
                results[f'league_{league_id}'] = 'success' if success else 'failed'
            except Exception as e:
                logging.error(f"Error calculating winners for league {league_id}: {e}")
                results[f'league_{league_id}'] = f'error: {str(e)}'
        
        return jsonify({
            'success': True,
            'deleted': deleted,
            'recalculated': results,
            'message': 'Reset weekly winners and recalculated last week'
        })
    except Exception as e:
        logging.error(f"Error resetting weekly winners: {e}")
        import traceback
        traceback.print_exc()
        return {'error': str(e)}, 500

@app.route('/create-tables', methods=['POST'])
def create_tables_endpoint():
    """Create missing database tables"""
    try:
        from create_missing_tables import create_tables
        create_tables()
        return jsonify({
            'success': True,
            'message': 'Tables created'
        })
    except Exception as e:
        logging.error(f"Error creating tables: {e}")
        import traceback
        traceback.print_exc()
        return {'error': str(e)}, 500

@app.route('/migrate-league1', methods=['POST'])
def migrate_league1_endpoint():
    """Run League 1 migration"""
    try:
        from migrate_league1 import migrate_league1
        migrate_league1()
        return jsonify({
            'success': True,
            'message': 'League 1 migration completed'
        })
    except Exception as e:
        logging.error(f"Error in migration: {e}")
        import traceback
        traceback.print_exc()
        return {'error': str(e)}, 500

@app.route('/check-players-table-constraints', methods=['GET'])
def check_players_table_constraints():
    """Check constraints on players table"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get table constraints
        cursor.execute("""
            SELECT conname, contype, pg_get_constraintdef(oid)
            FROM pg_constraint
            WHERE conrelid = 'players'::regclass
        """)
        
        constraints = []
        for row in cursor.fetchall():
            constraints.append({
                'name': row[0],
                'type': row[1],
                'definition': row[2]
            })
        
        cursor.close()
        conn.close()
        
        return jsonify({'constraints': constraints})
    except Exception as e:
        return {'error': str(e)}, 500

@app.route('/check-scores-table-constraints', methods=['GET'])
def check_scores_table_constraints():
    """Check constraints on scores table"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get table constraints
        cursor.execute("""
            SELECT conname, contype, pg_get_constraintdef(oid)
            FROM pg_constraint
            WHERE conrelid = 'scores'::regclass
        """)
        
        constraints = []
        for row in cursor.fetchall():
            constraints.append({
                'name': row[0],
                'type': row[1],
                'definition': row[2]
            })
        
        # Check for any existing League 1 scores with wordle_number 1507
        cursor.execute("""
            SELECT s.id, p.name, p.league_id, s.wordle_number, s.score
            FROM scores s
            JOIN players p ON s.player_id = p.id
            WHERE s.wordle_number = 1507
            ORDER BY p.league_id, p.name
        """)
        
        wordle_1507_scores = []
        for row in cursor.fetchall():
            wordle_1507_scores.append({
                'score_id': row[0],
                'player': row[1],
                'league_id': row[2],
                'wordle': row[3],
                'score': row[4]
            })
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'constraints': constraints,
            'wordle_1507_scores': wordle_1507_scores
        })
    except Exception as e:
        return {'error': str(e)}, 500

@app.route('/list-files', methods=['GET'])
def list_files():
    """List files in the deployment directory"""
    try:
        import os
        script_dir = os.path.dirname(os.path.abspath(__file__))
        files = os.listdir(script_dir)
        json_files = [f for f in files if f.endswith('.json')]
        
        return jsonify({
            'script_dir': script_dir,
            'total_files': len(files),
            'json_files': json_files,
            'all_files': files[:50]  # First 50 files
        })
    except Exception as e:
        return {'error': str(e)}, 500

@app.route('/test-insert-league1', methods=['POST'])
def test_insert_league1():
    """Test inserting one League 1 score"""
    try:
        import json
        from datetime import datetime, date, timedelta
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get League 1 players
        cursor.execute("SELECT id, name FROM players WHERE league_id = 1")
        players = {row[1]: row[0] for row in cursor.fetchall()}
        
        # Try to insert one test score
        test_score = {
            'player_name': 'Brent',
            'wordle_number': 1507,
            'score': 3,
            'date': '2025-08-04',
            'emoji_pattern': None,
            'timestamp': '2025-08-18 15:17:14'
        }
        
        player_id = players.get(test_score['player_name'])
        
        if not player_id:
            return jsonify({'error': f"Player {test_score['player_name']} not found", 'players': players})
        
        # Parse date
        date_obj = datetime.strptime(test_score['date'], '%Y-%m-%d').date()
        timestamp_obj = datetime.strptime(test_score['timestamp'], '%Y-%m-%d %H:%M:%S')
        
        # Try insert
        cursor.execute("""
            INSERT INTO scores (player_id, wordle_number, score, date, emoji_pattern, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            RETURNING id
        """, (player_id, test_score['wordle_number'], test_score['score'], date_obj, test_score['emoji_pattern'], timestamp_obj))
        
        result = cursor.fetchone()
        conn.commit()
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'inserted': result is not None,
            'player_id': player_id,
            'test_score': test_score,
            'result_id': result[0] if result else None
        })
        
    except Exception as e:
        logging.error(f"Error in test insert: {e}")
        import traceback
        traceback.print_exc()
        return {'error': str(e), 'traceback': traceback.format_exc()}, 500

@app.route('/test-insert-league3-players', methods=['POST'])
def test_insert_league3_players():
    """Test inserting League 3 players"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Insert league first
        cursor.execute("""
            INSERT INTO leagues (id, name, display_name)
            VALUES (3, 'PAL', 'PAL')
            ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, display_name = EXCLUDED.display_name
        """)
        
        players = [
            ('Vox', '18587359353'),
            ('Fuzwuz', '17604206113'),
            ('Pants', '17605830059'),
            ('Starslider', '14698345364')
        ]
        
        results = []
        for name, phone in players:
            cursor.execute("SELECT id FROM players WHERE name = %s AND league_id = 3", (name,))
            existing = cursor.fetchone()
            
            if not existing:
                cursor.execute("""
                    INSERT INTO players (name, phone_number, league_id)
                    VALUES (%s, %s, 3)
                    RETURNING id
                """, (name, phone))
                player_id = cursor.fetchone()[0]
                results.append(f"Inserted {name} with ID {player_id}")
            else:
                results.append(f"{name} already exists with ID {existing[0]}")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'results': results
        })
    except Exception as e:
        logging.error(f"Error: {e}")
        import traceback
        return {'error': str(e), 'traceback': traceback.format_exc()}, 500

@app.route('/migrate-league3', methods=['POST'])
def migrate_league3_endpoint():
    """Run League 3 migration"""
    try:
        from migrate_league3 import migrate_league3
        migrate_league3()
        return jsonify({
            'success': True,
            'message': 'League 3 migration completed'
        })
    except Exception as e:
        logging.error(f"Error in migration: {e}")
        import traceback
        traceback.print_exc()
        return {'error': str(e)}, 500

@app.route('/regenerate-all-html', methods=['POST'])
def regenerate_all_html():
    """Regenerate HTML for all leagues"""
    try:
        from update_pipeline import run_update_pipeline
        
        results = []
        for league_id in [1, 3, 4, 7]:
            logging.info(f"Regenerating HTML for League {league_id}...")
            success = run_update_pipeline(league_id)
            results.append({
                'league_id': league_id,
                'success': success
            })
        
        return jsonify({
            'success': True,
            'message': 'All league HTML regenerated',
            'results': results
        })
    except Exception as e:
        import traceback
        return {'error': str(e), 'traceback': traceback.format_exc()}, 500

@app.route('/regenerate-league3-html', methods=['POST'])
def regenerate_league3_html():
    """Regenerate HTML for League 3 to display season winners"""
    try:
        from update_pipeline import run_update_pipeline
        
        logging.info("Regenerating HTML for League 3...")
        success = run_update_pipeline(3)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'League 3 HTML regenerated successfully'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to regenerate League 3 HTML'
            }), 500
    except Exception as e:
        import traceback
        return {'error': str(e), 'traceback': traceback.format_exc()}, 500

@app.route('/fix-season-winners', methods=['POST'])
def fix_season_winners():
    """Fix duplicate season winners and add missing League 3 winners"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Delete duplicate season winners (keep only real historical seasons)
        # League 1: Seasons 1-3
        # League 3: Seasons 1-4
        # League 4: Seasons 1-3
        cursor.execute("""
            DELETE FROM season_winners 
            WHERE (league_id = 1 AND season_number > 3)
               OR (league_id = 3 AND season_number > 4)
               OR (league_id = 4 AND season_number > 3)
        """)
        
        # Get Vox's player_id from League 3
        cursor.execute("SELECT id FROM players WHERE name = 'Vox' AND league_id = 3")
        vox_id = cursor.fetchone()[0]
        
        # Insert League 3 season winners
        league3_winners = [
            (1, vox_id, 3, '2025-09-15'),
            (2, vox_id, 4, '2025-09-29'),
            (3, vox_id, 4, '2025-10-27'),
            (4, vox_id, 4, '2025-11-24')
        ]
        
        for season, player_id, wins, completed_date in league3_winners:
            cursor.execute("""
                INSERT INTO season_winners (league_id, season_number, player_id, wins, completed_date)
                VALUES (3, %s, %s, %s, %s)
                ON CONFLICT (league_id, season_number, player_id) DO NOTHING
            """, (season, player_id, wins, completed_date))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Fixed duplicate season winners and added League 3 winners'
        })
    except Exception as e:
        import traceback
        return {'error': str(e), 'traceback': traceback.format_exc()}, 500

@app.route('/create-league7', methods=['POST'])
def create_league7():
    """Create League 7 entry in leagues table"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO leagues (id, name, display_name, twilio_conversation_sid, github_path)
            VALUES (7, 'bellyup', 'Belly Up', 'CH4438ff5531514178bb13c5c0e96d5579', 'bellyup')
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                display_name = EXCLUDED.display_name,
                twilio_conversation_sid = EXCLUDED.twilio_conversation_sid,
                github_path = EXCLUDED.github_path
        """)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'League 7 created in leagues table'
        })
    except Exception as e:
        import traceback
        return {'error': str(e), 'traceback': traceback.format_exc()}, 500

@app.route('/check-league7-exists', methods=['GET'])
def check_league7_exists():
    """Check if League 7 exists in leagues table"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, name, display_name FROM leagues WHERE id = 7")
        result = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if result:
            return jsonify({
                'success': True,
                'exists': True,
                'league': {
                    'id': result[0],
                    'name': result[1],
                    'display_name': result[2]
                }
            })
        else:
            return jsonify({
                'success': True,
                'exists': False,
                'message': 'League 7 not found in leagues table'
            })
    except Exception as e:
        import traceback
        return {'error': str(e), 'traceback': traceback.format_exc()}, 500

@app.route('/recalculate-league7-winner', methods=['POST'])
def recalculate_league7_winner():
    """Manually recalculate League 7 last week winner"""
    try:
        from update_tables_cloud import run_full_update_for_league
        
        logging.info("Recalculating League 7 last week winner...")
        success = run_full_update_for_league(7)
        
        return jsonify({
            'success': success,
            'message': 'League 7 winner recalculated' if success else 'Failed to recalculate'
        })
    except Exception as e:
        import traceback
        return {'error': str(e), 'traceback': traceback.format_exc()}, 500

@app.route('/debug-league7-lastweek', methods=['GET'])
def debug_league7_lastweek():
    """Debug what scores exist for League 7 last week"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check scores for Wordles 1626-1632
        cursor.execute("""
            SELECT p.name, s.wordle_number, s.score, s.date
            FROM scores s
            JOIN players p ON s.player_id = p.id
            WHERE p.league_id = 7
            AND s.wordle_number BETWEEN 1626 AND 1632
            ORDER BY p.name, s.wordle_number
        """)
        
        scores = []
        for row in cursor.fetchall():
            scores.append({
                'player': row[0],
                'wordle': row[1],
                'score': row[2],
                'date': str(row[3])
            })
        
        # Group by player
        from collections import defaultdict
        player_scores = defaultdict(list)
        for score in scores:
            player_scores[score['player']].append(score['score'])
        
        # Calculate best 5 for each
        summary = []
        for player, scores_list in player_scores.items():
            sorted_scores = sorted(scores_list)
            best_5 = sorted_scores[:5] if len(sorted_scores) >= 5 else None
            summary.append({
                'player': player,
                'total_games': len(scores_list),
                'all_scores': sorted_scores,
                'best_5': best_5,
                'best_5_total': sum(best_5) if best_5 else None
            })
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'league': 'League 7 (Belly Up)',
            'week': '1626-1632 (Dec 1-7)',
            'total_scores': len(scores),
            'player_summary': sorted(summary, key=lambda x: x['best_5_total'] if x['best_5_total'] else 999)
        })
    except Exception as e:
        import traceback
        return {'error': str(e), 'traceback': traceback.format_exc()}, 500

@app.route('/create-seasons-table', methods=['POST'])
def create_seasons_table():
    """Create the seasons table"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS seasons (
                id SERIAL PRIMARY KEY,
                league_id INTEGER NOT NULL REFERENCES leagues(id),
                season_number INTEGER NOT NULL,
                start_week INTEGER,
                end_week INTEGER,
                UNIQUE(league_id, season_number)
            )
        """)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Seasons table created'
        })
    except Exception as e:
        import traceback
        return {'error': str(e), 'traceback': traceback.format_exc()}, 500

@app.route('/initialize-seasons-table', methods=['POST'])
def initialize_seasons_table():
    """Initialize seasons table with historical season data"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # League 1: Seasons 1-3 completed, Season 4 in progress
        seasons_data = [
            # League 1
            (1, 1, 1514, 1520),  # Season 1: Aug 11 - Aug 17 (Joanna won)
            (1, 2, 1521, 1555),  # Season 2: Aug 18 - Sep 28 (Joanna won)
            (1, 3, 1556, 1605),  # Season 3: Sep 29 - Nov 3 (Brent won with 4th win in 1605)
            (1, 4, 1612, None),  # Season 4: Nov 17 - present (in progress)
            
            # League 3: Seasons 1-4 completed, Season 5 in progress
            (3, 1, 1514, 1520),  # Season 1 (Vox won)
            (3, 2, 1521, 1548),  # Season 2 (Vox won)
            (3, 3, 1549, 1590),  # Season 3 (Vox won)
            (3, 4, 1591, 1625),  # Season 4 (Vox won)
            (3, 5, 1626, None),  # Season 5: in progress
            
            # League 4: Seasons 1-3 completed, Season 4 in progress
            (4, 1, 1514, 1520),  # Season 1 (Brent won)
            (4, 2, 1521, 1569),  # Season 2 (Brent won)
            (4, 3, 1570, 1625),  # Season 3 (Rob won)
            (4, 4, 1626, None),  # Season 4: in progress
            
            # League 7: Season 1 in progress
            (7, 1, 1619, None),  # Season 1: started Nov 24
        ]
        
        for league_id, season_num, start_week, end_week in seasons_data:
            cursor.execute("""
                INSERT INTO seasons (league_id, season_number, start_week, end_week)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (league_id, season_number) DO UPDATE
                SET start_week = EXCLUDED.start_week, end_week = EXCLUDED.end_week
            """, (league_id, season_num, start_week, end_week))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Seasons table initialized with historical data'
        })
    except Exception as e:
        import traceback
        return {'error': str(e), 'traceback': traceback.format_exc()}, 500

@app.route('/fix-league-seasons', methods=['POST'])
def fix_league_seasons():
    """Reset league seasons to correct values"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Set League 1 to Season 4
        cursor.execute("""
            UPDATE league_seasons
            SET current_season = 4
            WHERE league_id = 1
        """)
        
        # Set League 3 to Season 5
        cursor.execute("""
            UPDATE league_seasons
            SET current_season = 5
            WHERE league_id = 3
        """)
        
        # Set League 4 to Season 4
        cursor.execute("""
            UPDATE league_seasons
            SET current_season = 4
            WHERE league_id = 4
        """)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'League seasons updated: League 1=Season 4, League 3=Season 5, League 4=Season 4'
        })
    except Exception as e:
        import traceback
        return {'error': str(e), 'traceback': traceback.format_exc()}, 500

@app.route('/check-league-seasons', methods=['GET'])
def check_league_seasons():
    """Check current season and season_start_week for all leagues"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT league_id, current_season, season_start_week
            FROM league_seasons
            ORDER BY league_id
        """)
        
        seasons = []
        for row in cursor.fetchall():
            seasons.append({
                'league_id': row[0],
                'current_season': row[1],
                'season_start_week': row[2]
            })
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'seasons': seasons
        })
    except Exception as e:
        import traceback
        return {'error': str(e), 'traceback': traceback.format_exc()}, 500

@app.route('/send-message-to-league', methods=['POST'])
def send_message_to_league():
    """
    Send a message to a league's Twilio conversation
    
    POST body:
    {
        "league_id": 1,
        "message": "Your message here",
        "use_ai": true,  # Optional: use AI to enhance the message
        "context": "weekly_winner"  # Optional: context for AI (weekly_winner, season_winner, reminder, etc.)
    }
    """
    try:
        data = request.get_json()
        league_id = data.get('league_id')
        message = data.get('message')
        use_ai = data.get('use_ai', False)
        context = data.get('context', 'general')
        
        if not league_id or not message:
            return jsonify({'error': 'league_id and message are required'}), 400
        
        # Map league_id to conversation SID
        conversation_to_league = {
            'CHb7aa3110769f42a19cea7a2be9c644d2': 1,  # Warriorz
            'CHc8f0c4a776f14bcd96e7c8838a6aec13': 3,  # PAL
            'CHed74f2e9f16240e9a578f96299c395ce': 4,  # The Party
            'CH4438ff5531514178bb13c5c0e96d5579': 7,  # Belly Up
        }
        
        # Reverse lookup to get conversation SID from league_id
        conversation_sid = None
        for sid, lid in conversation_to_league.items():
            if lid == league_id:
                conversation_sid = sid
                break
        
        if not conversation_sid:
            return jsonify({'error': f'No conversation found for league {league_id}'}), 404
        
        # Optionally enhance message with AI
        final_message = message
        if use_ai:
            try:
                import openai
                openai.api_key = os.environ.get('OPENAI_API_KEY')
                
                # Create AI prompt based on context
                prompts = {
                    'weekly_winner': f"Enhance this Wordle league weekly winner announcement to be fun and celebratory (keep it under 160 chars): {message}",
                    'season_winner': f"Enhance this Wordle league season winner announcement to be epic and congratulatory (keep it under 160 chars): {message}",
                    'reminder': f"Enhance this Wordle reminder to be friendly and motivating (keep it under 160 chars): {message}",
                    'general': f"Enhance this message for a Wordle league group chat to be fun and engaging (keep it under 160 chars): {message}"
                }
                
                prompt = prompts.get(context, prompts['general'])
                
                response = openai.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are a fun, enthusiastic Wordle league announcer. Keep messages short, use emojis appropriately, and maintain a friendly competitive spirit."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=100,
                    temperature=0.8
                )
                
                final_message = response.choices[0].message.content.strip()
                logging.info(f"AI enhanced message: {final_message}")
                
            except Exception as e:
                logging.warning(f"AI enhancement failed, using original message: {e}")
                # Fall back to original message if AI fails
        
        # Send message directly to the Conversations API (will appear in group thread)
        from twilio.rest import Client
        twilio_sid = os.environ.get('TWILIO_ACCOUNT_SID')
        twilio_token = os.environ.get('TWILIO_AUTH_TOKEN')
        twilio_phone = os.environ.get('TWILIO_PHONE_NUMBER')
        client = Client(twilio_sid, twilio_token)
        
        # Send message to the conversation using the Twilio phone number as author
        # The phone number is already a participant in the conversation
        message_response = client.conversations.v1.conversations(conversation_sid).messages.create(
            body=final_message,
            author=twilio_phone  # Use the Twilio number that's already in the conversation
        )
        
        return jsonify({
            'success': True,
            'league_id': league_id,
            'conversation_sid': conversation_sid,
            'message_sid': message_response.sid,
            'original_message': message,
            'final_message': final_message,
            'ai_enhanced': use_ai
        })
        
    except Exception as e:
        import traceback
        return {'error': str(e), 'traceback': traceback.format_exc()}, 500

def get_weekly_standings_for_race(league_id, week_start_wordle):
    """Get current weekly standings for a league"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get all active players
        cursor.execute("""
            SELECT id, name FROM players 
            WHERE league_id = %s AND active = TRUE
            ORDER BY name
        """, (league_id,))
        players = cursor.fetchall()
        
        # Get today's Wordle number
        todays_wordle = get_todays_wordle_number()
        
        standings = []
        
        for player_id, player_name in players:
            # Get all scores for this week
            cursor.execute("""
                SELECT wordle_number, score 
                FROM scores 
                WHERE player_id = %s 
                AND wordle_number >= %s 
                AND wordle_number <= %s
                ORDER BY wordle_number
            """, (player_id, week_start_wordle, todays_wordle))
            
            scores = cursor.fetchall()
            score_dict = {w: s for w, s in scores}
            
            # Calculate total and check if posted today
            total = sum(s for w, s in scores)
            posted_today = todays_wordle in score_dict
            days_posted = len(scores)
            
            standings.append({
                'player_id': player_id,
                'name': player_name,
                'total': total,
                'days_posted': days_posted,
                'posted_today': posted_today,
                'scores': score_dict
            })
        
        cursor.close()
        conn.close()
        
        # Sort by total (lowest is best)
        standings.sort(key=lambda x: x['total'])
        
        return standings, todays_wordle
        
    except Exception as e:
        logging.error(f"Error getting weekly standings: {e}")
        cursor.close()
        conn.close()
        return [], None

def calculate_what_they_need(current_leader_total, player_total, player_days_posted):
    """Calculate what score a player needs to tie or win"""
    # If they haven't posted today, they need one more score
    if player_days_posted < 7:  # Assuming 7 days in a week
        # What score would tie?
        score_to_tie = current_leader_total - player_total
        score_to_win = score_to_tie - 1
        
        return {
            'to_tie': score_to_tie if score_to_tie >= 1 else None,
            'to_win': score_to_win if score_to_win >= 1 else None
        }
    return None

@app.route('/test-sunday-race-update', methods=['POST'])
def test_sunday_race_update():
    """Test the Sunday race update for a specific league"""
    try:
        import pytz
        from league_data_adapter import get_week_start_date
        
        data = request.get_json()
        league_id = data.get('league_id', 4)  # Default to League 4
        
        # Get week start
        pacific = pytz.timezone('America/Los_Angeles')
        today = datetime.now(pacific).date()
        week_start = get_week_start_date(today)
        ref_date = date(2025, 7, 31)
        ref_wordle = 1503
        days_offset = (week_start - ref_date).days
        week_start_wordle = ref_wordle + days_offset
        
        # Get standings
        standings, todays_wordle = get_weekly_standings_for_race(league_id, week_start_wordle)
        
        if not standings:
            return jsonify({'error': 'No standings data'}), 500
        
        # Find current leader(s)
        leader_total = standings[0]['total']
        leaders = [s for s in standings if s['total'] == leader_total]
        leader_names = [s['name'] for s in leaders]
        
        # Find who hasn't posted today
        not_posted = [s for s in standings if not s['posted_today']]
        
        # Build context for AI
        if len(leader_names) == 1:
            leader_text = f"{leader_names[0]} is in the lead with {leader_total} points"
        elif len(leader_names) == 2:
            leader_text = f"{leader_names[0]} and {leader_names[1]} are tied for the lead with {leader_total} points"
        else:
            leader_text = f"{', '.join(leader_names[:-1])}, and {leader_names[-1]} are all tied with {leader_total} points"
        
        # Build "what they need" context
        scenarios = []
        for player in not_posted:
            needs = calculate_what_they_need(leader_total, player['total'], player['days_posted'])
            if needs:
                if needs['to_win'] and needs['to_win'] >= 1:
                    scenarios.append(f"{player['name']} needs a {needs['to_win']} to win or a {needs['to_tie']} to tie")
                elif needs['to_tie'] and needs['to_tie'] >= 1:
                    scenarios.append(f"{player['name']} needs a {needs['to_tie']} to tie")
        
        # Build message for AI to enhance
        if scenarios:
            scenario_text = ". ".join(scenarios)
            base_message = f"Sunday Race Update! {leader_text}. {scenario_text}."
        else:
            base_message = f"Sunday Race Update! {leader_text}. Everyone has posted today! Winner announcement tomorrow!"
        
        # Use the existing send_message_to_league logic with AI enhancement
        result = send_message_to_league_internal(league_id, base_message, use_ai=True, context="sunday_race")
        
        return jsonify({
            'success': result.get('success', False),
            'league_id': league_id,
            'leader_text': leader_text,
            'scenarios': scenarios,
            'message': result.get('final_message', '')
        })
        
    except Exception as e:
        import traceback
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

def send_message_to_league_internal(league_id, message, use_ai=False, context="general"):
    """Internal function to send message (used by both endpoint and scheduled tasks)"""
    import openai
    from twilio.rest import Client
    
    # Map league_id to conversation SID
    conversation_sids = {
        1: 'CHb7aa3110769f42a19cea7a2be9c644d2',  # Warriorz
        3: 'CHc8f0c4a776f14bcd96e7c8838a6aec13',  # PAL
        4: 'CHed74f2e9f16240e9a578f96299c395ce',  # The Party
        7: 'CH4438ff5531514178bb13c5c0e96d5579',  # Belly Up
    }
    
    conversation_sid = conversation_sids.get(league_id)
    if not conversation_sid:
        return {'success': False, 'error': f'No conversation SID for league {league_id}'}
    
    final_message = message
    if use_ai:
        try:
            openai.api_key = os.environ.get('OPENAI_API_KEY')
            
            # Create AI prompt based on context
            if context == "sunday_race":
                prompt = f"Transform this into an exciting sports announcer style message: '{message}'. Make it enthusiastic and engaging! Use emojis. Keep it under 280 characters."
            else:
                prompt = f"Enhance this message to be more fun and engaging: '{message}'. Keep the same meaning but make it more exciting. Use appropriate emojis. Keep it under 160 characters."
            
            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a fun, enthusiastic Wordle league announcer. Keep messages short, use emojis appropriately, and maintain a friendly competitive spirit."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=100,
                temperature=0.8
            )
            
            final_message = response.choices[0].message.content.strip()
            logging.info(f"AI enhanced message: {final_message}")
            
        except Exception as e:
            logging.warning(f"AI enhancement failed, using original message: {e}")
    
    # Send message
    twilio_sid = os.environ.get('TWILIO_ACCOUNT_SID')
    twilio_token = os.environ.get('TWILIO_AUTH_TOKEN')
    twilio_phone = os.environ.get('TWILIO_PHONE_NUMBER')
    client = Client(twilio_sid, twilio_token)
    
    message_response = client.conversations.v1.conversations(conversation_sid).messages.create(
        body=final_message,
        author=twilio_phone
    )
    
    return {
        'success': True,
        'league_id': league_id,
        'conversation_sid': conversation_sid,
        'message_sid': message_response.sid,
        'original_message': message,
        'final_message': final_message,
        'ai_enhanced': use_ai
    }

@app.route('/fix-nanna-score', methods=['POST'])
def fix_nanna_score():
    """Fix Nanna's score to remove 'whew' from emoji pattern"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get Nanna's player_id
        cursor.execute("""
            SELECT id FROM players WHERE name = 'Nanna' AND league_id = 1
        """)
        player_result = cursor.fetchone()
        if not player_result:
            return jsonify({'error': 'Nanna not found'}), 404
        
        player_id = player_result[0]
        
        # Get Nanna's latest score from scores table
        cursor.execute("""
            SELECT id, emoji_pattern FROM scores
            WHERE player_id = %s
            ORDER BY date DESC
            LIMIT 1
        """, (player_id,))
        
        result = cursor.fetchone()
        if not result:
            return jsonify({'error': 'No score found for Nanna'}), 404
        
        score_id = result[0]
        old_pattern = result[1]
        
        # Clean the pattern - extract only emoji characters
        if old_pattern:
            lines = old_pattern.split('\n')
            cleaned_lines = []
            for line in lines:
                emoji_only = ''.join(char for char in line if char in ['🟩', '⬛', '⬜', '🟨'])
                if emoji_only:
                    cleaned_lines.append(emoji_only)
            
            new_pattern = '\n'.join(cleaned_lines)
            
            # Update the database
            cursor.execute("""
                UPDATE scores
                SET emoji_pattern = %s
                WHERE id = %s
            """, (new_pattern, score_id))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return jsonify({
                'success': True,
                'old_pattern': old_pattern,
                'new_pattern': new_pattern
            })
        else:
            return jsonify({'error': 'No emoji pattern found'}), 404
            
    except Exception as e:
        import traceback
        return {'error': str(e), 'traceback': traceback.format_exc()}, 500

@app.route('/debug-league3-data', methods=['GET'])
def debug_league3_data():
    """Debug what data is being fetched for League 3"""
    try:
        from league_data_adapter import get_complete_league_data
        
        data = get_complete_league_data(3)
        
        return jsonify({
            'success': True,
            'current_season': data.get('current_season'),
            'season_standings': data.get('season_standings'),
            'season_winners': data.get('season_winners')
        })
    except Exception as e:
        import traceback
        return {'error': str(e), 'traceback': traceback.format_exc()}, 500

@app.route('/check-league3-winners', methods=['GET'])
def check_league3_winners():
    """Check League 3 all weekly winners"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT week_wordle_number, player_name, score
            FROM weekly_winners
            WHERE league_id = 3
            ORDER BY week_wordle_number DESC
            LIMIT 10
        """)
        
        winners = []
        for row in cursor.fetchall():
            winners.append({
                'week': row[0],
                'player': row[1],
                'score': row[2]
            })
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'league': 'League 3 (PAL)',
            'winners': winners,
            'count': len(winners)
        })
    except Exception as e:
        import traceback
        return {'error': str(e), 'traceback': traceback.format_exc()}, 500

@app.route('/check-league1-season4-winners', methods=['GET'])
def check_league1_season4_winners():
    """Check League 1 weekly winners for Season 4 (week 1619+)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT week_wordle_number, player_name, score
            FROM weekly_winners
            WHERE league_id = 1 AND week_wordle_number >= 1619
            ORDER BY week_wordle_number
        """)
        
        winners = []
        for row in cursor.fetchall():
            winners.append({
                'week': row[0],
                'player': row[1],
                'score': row[2]
            })
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'league': 'League 1 Season 4',
            'start_week': 1619,
            'winners': winners,
            'count': len(winners)
        })
    except Exception as e:
        import traceback
        return {'error': str(e), 'traceback': traceback.format_exc()}, 500

@app.route('/check-all-weekly-winners', methods=['GET'])
def check_all_weekly_winners():
    """Check all weekly winners for all leagues"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT ww.league_id, l.name, ww.week_wordle_number, ww.player_name, ww.score
            FROM weekly_winners ww
            LEFT JOIN leagues l ON ww.league_id = l.id
            ORDER BY ww.league_id, ww.week_wordle_number DESC
        """)
        
        winners_by_league = {}
        for row in cursor.fetchall():
            league_id = row[0]
            league_name = row[1] or f"League {league_id}"
            
            if league_id not in winners_by_league:
                winners_by_league[league_id] = {
                    'league_name': league_name,
                    'winners': []
                }
            
            winners_by_league[league_id]['winners'].append({
                'week': row[2],
                'player': row[3],
                'score': row[4]
            })
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'leagues': winners_by_league
        })
    except Exception as e:
        import traceback
        return {'error': str(e), 'traceback': traceback.format_exc()}, 500

@app.route('/check-last-week-winners', methods=['GET'])
def check_last_week_winners():
    """Check who won last week (Wordle 1626) for each league"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT ww.league_id, l.name, ww.player_name, ww.score
            FROM weekly_winners ww
            JOIN leagues l ON ww.league_id = l.id
            WHERE ww.week_wordle_number = 1626
            ORDER BY ww.league_id, ww.score
        """)
        
        winners = []
        for row in cursor.fetchall():
            winners.append({
                'league_id': row[0],
                'league_name': row[1],
                'player': row[2],
                'score': row[3]
            })
        
        # Also check all League 7 entries
        cursor.execute("""
            SELECT week_wordle_number, player_name, score
            FROM weekly_winners
            WHERE league_id = 7
            ORDER BY week_wordle_number DESC
            LIMIT 5
        """)
        
        league7_recent = []
        for row in cursor.fetchall():
            league7_recent.append({
                'week': row[0],
                'player': row[1],
                'score': row[2]
            })
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'week': '1626 (Dec 1-7, 2025)',
            'winners': winners,
            'league7_recent_winners': league7_recent
        })
    except Exception as e:
        import traceback
        return {'error': str(e), 'traceback': traceback.format_exc()}, 500

@app.route('/check-weekly-winners-schema', methods=['GET'])
def check_weekly_winners_schema():
    """Check the schema of weekly_winners table"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'weekly_winners'
            ORDER BY ordinal_position
        """)
        
        columns = []
        for row in cursor.fetchall():
            columns.append({
                'column_name': row[0],
                'data_type': row[1]
            })
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'columns': columns
        })
    except Exception as e:
        import traceback
        return {'error': str(e), 'traceback': traceback.format_exc()}, 500

@app.route('/check-season-winners', methods=['GET'])
def check_season_winners():
    """Check all season winners in database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT sw.league_id, sw.season_number, p.name, sw.wins, sw.completed_date
            FROM season_winners sw
            JOIN players p ON sw.player_id = p.id
            ORDER BY sw.league_id, sw.season_number
        """)
        
        winners = []
        for row in cursor.fetchall():
            winners.append({
                'league_id': row[0],
                'season': row[1],
                'player': row[2],
                'wins': row[3],
                'completed_date': str(row[4]) if row[4] else None
            })
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'season_winners': winners,
            'count': len(winners)
        })
    except Exception as e:
        import traceback
        return {'error': str(e), 'traceback': traceback.format_exc()}, 500

@app.route('/delete-league6', methods=['POST'])
def delete_league6():
    """Completely remove League 6 from the database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Delete in order due to foreign key constraints
        cursor.execute("DELETE FROM latest_scores WHERE league_id = 6")
        cursor.execute("DELETE FROM weekly_winners WHERE league_id = 6")
        cursor.execute("DELETE FROM season_winners WHERE league_id = 6")
        cursor.execute("DELETE FROM scores WHERE player_id IN (SELECT id FROM players WHERE league_id = 6)")
        cursor.execute("DELETE FROM players WHERE league_id = 6")
        cursor.execute("DELETE FROM league_seasons WHERE league_id = 6")
        cursor.execute("DELETE FROM leagues WHERE id = 6")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'League 6 completely deleted from database'
        })
    except Exception as e:
        import traceback
        return {'error': str(e), 'traceback': traceback.format_exc()}, 500

@app.route('/debug-league1-lastweek', methods=['GET'])
def debug_league1_lastweek():
    """Debug what scores exist for League 1 last week"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check scores for Wordles 1626-1632
        cursor.execute("""
            SELECT p.name, s.wordle_number, s.score, s.date
            FROM scores s
            JOIN players p ON s.player_id = p.id
            WHERE p.league_id = 1
            AND s.wordle_number BETWEEN 1626 AND 1632
            ORDER BY p.name, s.wordle_number
        """)
        
        scores = []
        for row in cursor.fetchall():
            scores.append({
                'player': row[0],
                'wordle': row[1],
                'score': row[2],
                'date': str(row[3])
            })
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'scores': scores,
            'count': len(scores)
        })
    except Exception as e:
        import traceback
        return {'error': str(e), 'traceback': traceback.format_exc()}, 500

@app.route('/calculate-last-week-winners', methods=['POST'])
def calculate_last_week_winners():
    """Manually calculate and save last week's winners for all leagues"""
    try:
        from update_tables_cloud import run_full_update_for_league
        from datetime import datetime, timedelta
        
        results = []
        for league_id in [1, 3, 4, 7]:
            logging.info(f"Calculating last week's winners for league {league_id}")
            success = run_full_update_for_league(league_id)
            results.append({
                'league_id': league_id,
                'success': success
            })
        
        return jsonify({
            'success': True,
            'results': results
        })
    except Exception as e:
        logging.error(f"Error: {e}")
        import traceback
        return {'error': str(e), 'traceback': traceback.format_exc()}, 500

@app.route('/update-conversation-names', methods=['POST'])
def update_conversation_names():
    """Update Twilio conversation unique names"""
    try:
        from update_conversation_names import client, conversations
        
        results = []
        for sid, name in conversations:
            try:
                conversation = client.conversations.conversations(sid).update(
                    unique_name=name
                )
                results.append(f"✅ Updated {sid} -> {name}")
            except Exception as e:
                results.append(f"❌ Error updating {sid}: {e}")
        
        return jsonify({
            'success': True,
            'results': results
        })
    except Exception as e:
        logging.error(f"Error: {e}")
        import traceback
        return {'error': str(e), 'traceback': traceback.format_exc()}, 500

@app.route('/insert-brent-league3', methods=['POST'])
def insert_brent_league3():
    """Manually insert Brent's League 3 score"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get Vox's player ID (Brent in League 3)
        cursor.execute("SELECT id FROM players WHERE name = 'Vox' AND league_id = 3")
        player_id = cursor.fetchone()[0]
        
        from datetime import datetime, date, timedelta
        ref_date = date(2025, 7, 31)
        wordle_date = ref_date + timedelta(days=124)  # 1627 - 1503
        timestamp = datetime.strptime('2025-12-02 09:30:27', '%Y-%m-%d %H:%M:%S')
        
        # Insert into scores
        cursor.execute("""
            INSERT INTO scores (player_id, wordle_number, score, date, emoji_pattern, timestamp)
            VALUES (%s, 1627, 4, %s, %s, %s)
            ON CONFLICT DO NOTHING
        """, (player_id, wordle_date, '⬛⬛🟨🟩⬛\n⬛🟨⬛🟩⬛\n🟨⬛🟨🟩⬛\n🟩🟩🟩🟩🟩', timestamp))
        
        # Insert into latest_scores
        cursor.execute("""
            INSERT INTO latest_scores (player_id, league_id, wordle_number, score, emoji_pattern, timestamp)
            VALUES (%s, 3, 1627, 4, %s, %s)
            ON CONFLICT (player_id) DO UPDATE 
            SET wordle_number = 1627, score = 4, emoji_pattern = EXCLUDED.emoji_pattern, timestamp = EXCLUDED.timestamp
        """, (player_id, '⬛⬛🟨🟩⬛\n⬛🟨⬛🟩⬛\n🟨⬛🟨🟩⬛\n🟩🟩🟩🟩🟩', timestamp))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        # Regenerate HTML
        from update_pipeline import run_update_pipeline
        run_update_pipeline(3)
        
        return jsonify({'success': True, 'message': 'Score inserted and HTML regenerated'})
    except Exception as e:
        logging.error(f"Error: {e}")
        import traceback
        return {'error': str(e), 'traceback': traceback.format_exc()}, 500

@app.route('/restore-league4-dec2', methods=['POST'])
def restore_league4_dec2():
    """Restore League 4 scores from Dec 2 that were lost"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Delete wrong scores from League 6
        cursor.execute("""
            DELETE FROM scores 
            WHERE wordle_number = 1627 
            AND player_id IN (SELECT id FROM players WHERE league_id = 6)
        """)
        cursor.execute("""
            DELETE FROM latest_scores 
            WHERE wordle_number = 1627 
            AND league_id = 6
        """)
        
        # Get League 4 player IDs
        cursor.execute("SELECT id, phone_number FROM players WHERE league_id = 4")
        phone_to_id = {row[1]: row[0] for row in cursor.fetchall()}
        
        # Scores to insert
        scores = [
            ('17609082401', 4, '⬜⬜🟩⬜⬜\n🟨⬜🟨⬜⬜\n⬜🟩🟩⬜🟩\n🟩🟩🟩🟩🟩', '2025-12-02 06:40:45'),
            ('17609082000', 4, '⬛🟩🟨⬛🟨\n⬛⬛⬛⬛⬛\n⬛🟩🟨🟨🟨\n🟩🟩🟩🟩🟩', '2025-12-02 07:22:42'),
            ('19165416576', 7, '⬛⬛🟨⬛⬛\n⬛🟩⬛⬛⬛\n⬛🟩⬛⬛⬛\n⬛🟩⬛⬛⬛\n⬛🟩🟨🟨🟨\n🟨🟩🟩🟨⬛', '2025-12-02 07:41:09'),
            ('16503468822', 4, '⬛⬛🟨🟩⬛\n⬛🟩⬛🟩⬛\n⬛🟩🟨🟩⬛\n🟩🟩🟩🟩🟩', '2025-12-02 08:22:53'),
            ('17608156131', 5, '⬜⬜⬜🟨🟨\n⬜⬜🟨🟨⬜\n⬜🟩⬜🟨🟨\n⬜🟩🟨⬜⬜\n🟩🟩🟩🟩🟩', '2025-12-02 08:24:38'),
        ]
        
        from datetime import datetime, date, timedelta
        ref_date = date(2025, 7, 31)
        wordle_date = ref_date + timedelta(days=124)  # 1627 - 1503
        
        inserted = 0
        for phone, score, emoji, ts in scores:
            if phone in phone_to_id:
                player_id = phone_to_id[phone]
                timestamp = datetime.strptime(ts, '%Y-%m-%d %H:%M:%S')
                
                cursor.execute("""
                    INSERT INTO scores (player_id, wordle_number, score, date, emoji_pattern, timestamp)
                    VALUES (%s, 1627, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (player_id, score, wordle_date, emoji, timestamp))
                
                cursor.execute("""
                    INSERT INTO latest_scores (player_id, league_id, wordle_number, score, emoji_pattern, timestamp)
                    VALUES (%s, 4, 1627, %s, %s, %s)
                    ON CONFLICT (player_id) DO UPDATE 
                    SET wordle_number = EXCLUDED.wordle_number,
                        score = EXCLUDED.score, 
                        emoji_pattern = EXCLUDED.emoji_pattern,
                        timestamp = EXCLUDED.timestamp
                """, (player_id, score, emoji, timestamp))
                
                inserted += 1
        
        conn.commit()
        cursor.close()
        conn.close()
        
        # Regenerate HTML
        from update_pipeline import run_update_pipeline
        run_update_pipeline(4)
        
        return jsonify({
            'success': True,
            'inserted': inserted,
            'message': f'Restored {inserted} scores and regenerated HTML'
        })
    except Exception as e:
        logging.error(f"Error restoring scores: {e}")
        import traceback
        return {'error': str(e), 'traceback': traceback.format_exc()}, 500

@app.route('/regenerate-league3', methods=['POST'])
def regenerate_league3():
    """Manually regenerate League 3 HTML"""
    try:
        from update_pipeline import run_update_pipeline
        result = run_update_pipeline(3)
        return jsonify({
            'success': True,
            'result': result,
            'message': 'League 3 HTML regenerated'
        })
    except Exception as e:
        logging.error(f"Error regenerating League 3: {e}")
        import traceback
        traceback.print_exc()
        return {'error': str(e)}, 500

@app.route('/force-insert-league3', methods=['POST'])
def force_insert_league3():
    """Force insert League 3 with detailed tracking"""
    try:
        from force_insert_league3 import force_insert
        result = force_insert()
        return jsonify(result)
    except Exception as e:
        logging.error(f"Error in force insert: {e}")
        import traceback
        return {'error': str(e), 'traceback': traceback.format_exc()}, 500

@app.route('/force-insert-league1', methods=['POST'])
def force_insert_league1():
    """Force insert League 1 with detailed tracking"""
    try:
        from force_insert_league1 import force_insert
        result = force_insert()
        return jsonify(result)
    except Exception as e:
        logging.error(f"Error in force insert: {e}")
        import traceback
        return {'error': str(e), 'traceback': traceback.format_exc()}, 500

@app.route('/bulk-insert-league1-v2', methods=['POST'])
def bulk_insert_league1_v2():
    """Bulk insert League 1 historical scores from JSON - V2"""
    try:
        from bulk_insert_league1_scores_v2 import bulk_insert_scores
        success = bulk_insert_scores()
        return jsonify({
            'success': success,
            'message': 'League 1 history imported (v2)' if success else 'Import failed'
        })
    except Exception as e:
        logging.error(f"Error importing history: {e}")
        import traceback
        traceback.print_exc()
        return {'error': str(e), 'traceback': traceback.format_exc()}, 500

@app.route('/bulk-insert-league1', methods=['POST'])
def bulk_insert_league1():
    """Bulk insert League 1 historical scores from JSON"""
    try:
        import os
        script_dir = os.path.dirname(os.path.abspath(__file__))
        json_file = os.path.join(script_dir, 'league1_historical_scores.json')
        
        logging.info(f"Checking for JSON file at: {json_file}")
        logging.info(f"File exists: {os.path.exists(json_file)}")
        
        if os.path.exists(json_file):
            import json
            with open(json_file, 'r') as f:
                data = json.load(f)
            logging.info(f"JSON file has {len(data)} scores")
        
        from bulk_insert_league1_scores import bulk_insert_scores
        result = bulk_insert_scores()
        
        if isinstance(result, dict):
            return jsonify(result)
        else:
            return jsonify({
                'success': result,
                'message': 'League 1 history imported' if result else 'Import failed'
            })
    except Exception as e:
        logging.error(f"Error importing history: {e}")
        import traceback
        traceback.print_exc()
        return {'error': str(e)}, 500

@app.route('/bulk-insert-league4', methods=['POST'])
def bulk_insert_league4():
    """Bulk insert League 4 historical scores from JSON"""
    try:
        from bulk_insert_league4_scores import bulk_insert_scores
        success = bulk_insert_scores()
        return jsonify({
            'success': success,
            'message': 'League 4 history imported' if success else 'Import failed'
        })
    except Exception as e:
        logging.error(f"Error importing history: {e}")
        import traceback
        traceback.print_exc()
        return {'error': str(e)}, 500

@app.route('/regenerate-league1', methods=['POST'])
def regenerate_league1():
    """Manually regenerate League 1 HTML"""
    try:
        from update_pipeline import run_update_pipeline
        result = run_update_pipeline(1)
        return jsonify({
            'success': True,
            'result': result,
            'message': 'League 1 HTML regenerated'
        })
    except Exception as e:
        logging.error(f"Error regenerating League 1: {e}")
        import traceback
        traceback.print_exc()
        return {'error': str(e)}, 500

@app.route('/regenerate-league7', methods=['POST'])
def regenerate_league7():
    """Manually regenerate League 7 HTML"""
    try:
        from update_pipeline import run_update_pipeline
        result = run_update_pipeline(7)
        return jsonify({
            'success': True,
            'result': result,
            'message': 'League 7 HTML regenerated'
        })
    except Exception as e:
        logging.error(f"Error regenerating League 7: {e}")
        import traceback
        traceback.print_exc()
        return {'error': str(e)}, 500

@app.route('/regenerate-league4', methods=['POST'])
def regenerate_league4():
    """Manually regenerate League 4 HTML"""
    try:
        from update_pipeline import run_update_pipeline
        result = run_update_pipeline(4)
        return jsonify({
            'success': True,
            'result': result,
            'message': 'League 4 HTML regenerated'
        })
    except Exception as e:
        logging.error(f"Error regenerating League 4: {e}")
        import traceback
        traceback.print_exc()
        return {'error': str(e)}, 500

@app.route('/insert-league4-scores', methods=['POST'])
def insert_league4_scores_endpoint():
    """Insert League 4 scores manually"""
    try:
        from insert_league4_scores import insert_scores
        insert_scores()
        return jsonify({
            'success': True,
            'message': 'League 4 scores inserted and HTML regenerated'
        })
    except Exception as e:
        logging.error(f"Error inserting scores: {e}")
        import traceback
        traceback.print_exc()
        return {'error': str(e)}, 500

@app.route('/migrate-league4', methods=['POST'])
def migrate_league4_endpoint():
    """Run League 4 migration"""
    try:
        from migrate_league4 import migrate_league4
        migrate_league4()
        return jsonify({
            'success': True,
            'message': 'League 4 migration completed'
        })
    except Exception as e:
        logging.error(f"Error in migration: {e}")
        import traceback
        traceback.print_exc()
        return {'error': str(e)}, 500

@app.route('/list-all-tables', methods=['GET'])
def list_all_tables():
    """List all tables in the database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        
        tables = [r[0] for r in cursor.fetchall()]
        
        cursor.close()
        conn.close()
        
        return jsonify({'tables': tables})
    except Exception as e:
        logging.error(f"Error listing tables: {e}")
        import traceback
        traceback.print_exc()
        return {'error': str(e)}, 500

@app.route('/check-table-schema', methods=['GET'])
def check_table_schema():
    """Check latest_scores table schema"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'latest_scores'
            ORDER BY ordinal_position
        """)
        
        columns = [{'name': r[0], 'type': r[1]} for r in cursor.fetchall()]
        
        cursor.close()
        conn.close()
        
        return jsonify({'columns': columns})
    except Exception as e:
        logging.error(f"Error checking schema: {e}")
        import traceback
        traceback.print_exc()
        return {'error': str(e)}, 500

@app.route('/check-league4-season', methods=['GET'])
def check_league4_season():
    """Check League 4 season settings"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT current_season, season_start_week
            FROM league_seasons
            WHERE league_id = 4
        """)
        
        result = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if result:
            return jsonify({
                'current_season': result[0],
                'season_start_week': result[1]
            })
        else:
            return jsonify({'error': 'No season data found for League 4'})
    except Exception as e:
        logging.error(f"Error checking season: {e}")
        import traceback
        traceback.print_exc()
        return {'error': str(e)}, 500

@app.route('/check-players/<int:league_id>', methods=['GET'])
def check_players(league_id):
    """Check players for any league"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, name, phone_number
            FROM players
            WHERE league_id = %s
            ORDER BY name
        """, (league_id,))
        
        players = []
        for row in cursor.fetchall():
            players.append({
                'id': row[0],
                'name': row[1],
                'phone': row[2]
            })
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'league_id': league_id,
            'count': len(players),
            'players': players
        })
    except Exception as e:
        logging.error(f"Error checking players: {e}")
        import traceback
        traceback.print_exc()
        return {'error': str(e)}, 500

@app.route('/check-league4-players', methods=['GET'])
def check_league4_players():
    """Check if League 4 players exist in database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, name, phone_number
            FROM players
            WHERE league_id = 4
            ORDER BY name
        """)
        
        players = [{'id': r[0], 'name': r[1], 'phone': r[2]} for r in cursor.fetchall()]
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'count': len(players),
            'players': players
        })
    except Exception as e:
        logging.error(f"Error checking players: {e}")
        import traceback
        traceback.print_exc()
        return {'error': str(e)}, 500

@app.route('/check-scores/<int:league_id>', methods=['GET'])
def check_scores(league_id):
    """Check scores for any league"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check latest_scores with player names
        cursor.execute("""
            SELECT p.name, ls.wordle_number, ls.score, ls.timestamp
            FROM latest_scores ls
            JOIN players p ON ls.player_id = p.id
            WHERE p.league_id = %s
            ORDER BY ls.timestamp DESC
        """, (league_id,))
        latest = [{'player': r[0], 'wordle': r[1], 'score': r[2], 'time': str(r[3])} for r in cursor.fetchall()]
        
        # Check scores with player names
        cursor.execute("""
            SELECT COUNT(*)
            FROM scores s
            JOIN players p ON s.player_id = p.id
            WHERE p.league_id = %s
        """, (league_id,))
        total_count = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT p.name, s.wordle_number, s.score, s.timestamp
            FROM scores s
            JOIN players p ON s.player_id = p.id
            WHERE p.league_id = %s
            ORDER BY s.timestamp DESC
            LIMIT 10
        """, (league_id,))
        permanent = [{'player': r[0], 'wordle': r[1], 'score': r[2], 'time': str(r[3])} for r in cursor.fetchall()]
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'league_id': league_id,
            'latest_scores': latest,
            'permanent_scores': permanent,
            'count_latest': len(latest),
            'count_permanent': total_count,
            'sample_count': len(permanent)
        })
    except Exception as e:
        logging.error(f"Error checking scores: {e}")
        import traceback
        traceback.print_exc()
        return {'error': str(e)}, 500

@app.route('/check-league4-scores', methods=['GET'])
def check_league4_scores():
    """Check if League 4 scores are in database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check latest_scores with player names
        cursor.execute("""
            SELECT p.name, ls.wordle_number, ls.score, ls.timestamp
            FROM latest_scores ls
            JOIN players p ON ls.player_id = p.id
            WHERE p.league_id = 4
            ORDER BY ls.timestamp DESC
        """)
        latest = [{'player': r[0], 'wordle': r[1], 'score': r[2], 'time': str(r[3])} for r in cursor.fetchall()]
        
        # Check scores with player names
        cursor.execute("""
            SELECT p.name, s.wordle_number, s.score, s.timestamp
            FROM scores s
            JOIN players p ON s.player_id = p.id
            WHERE p.league_id = 4
            ORDER BY s.timestamp DESC
            LIMIT 10
        """)
        permanent = [{'player': r[0], 'wordle': r[1], 'score': r[2], 'time': str(r[3])} for r in cursor.fetchall()]
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'latest_scores': latest,
            'permanent_scores': permanent,
            'count_latest': len(latest),
            'count_permanent': len(permanent)
        })
    except Exception as e:
        logging.error(f"Error checking scores: {e}")
        import traceback
        traceback.print_exc()
        return {'error': str(e)}, 500

@app.route('/debug-season-data/<int:league_id>', methods=['GET'])
def debug_season_data(league_id):
    """Debug endpoint to see what season data is being fetched"""
    try:
        from league_data_adapter import get_season_data
        season_data = get_season_data(league_id)
        return jsonify({
            'league_id': league_id,
            'season_data': season_data
        })
    except Exception as e:
        logging.error(f"Error in debug endpoint: {e}")
        import traceback
        traceback.print_exc()
        return {'error': str(e)}, 500

@app.route('/', methods=['GET'])
def index():
    """Root endpoint"""
    return {'message': 'Wordle League Twilio Webhook', 'status': 'running'}

@app.route('/test-sunday-update/<int:league_id>', methods=['POST'])
def test_sunday_update(league_id):
    """Test endpoint to trigger Sunday race update with images for a specific league"""
    try:
        from sunday_race_update import send_sunday_race_update
        
        # Check if force_season param is set
        force_season = request.args.get('force_season', 'false').lower() == 'true'
        
        logging.info(f"Triggering test Sunday race update for league {league_id} (force_season={force_season})")
        success = send_sunday_race_update(league_id, force_season_image=force_season)
        
        if success:
            return {'status': 'success', 'message': f'Sunday race update sent to league {league_id}'}, 200
        else:
            return {'status': 'error', 'message': 'Failed to send update'}, 500
    except Exception as e:
        logging.error(f"Error in test Sunday update: {e}")
        import traceback
        traceback.print_exc()
        return {'status': 'error', 'message': str(e)}, 500

@app.route('/screenshot/weekly/<int:league_id>', methods=['GET'])
def screenshot_weekly(league_id):
    """Generate a screenshot-friendly weekly standings page"""
    try:
        from league_data_adapter import get_complete_league_data
        import pytz
        
        league_names = {1: 'Warriorz', 3: 'PAL', 4: 'The Party', 7: 'Belly Up'}
        league_name = league_names.get(league_id, f'League {league_id}')
        
        league_data = get_complete_league_data(league_id)
        weekly_stats = league_data.get('weekly_stats', {})
        
        # Sort players: eligible first (5+ scores), then by score
        sorted_players = sorted(
            weekly_stats.items(),
            key=lambda x: (
                x[1]['used_scores'] < 5,
                x[1]['best_5_total'] if x[1]['used_scores'] >= 5 else 999,
                -x[1]['used_scores']
            )
        )
        
        # Build minimal HTML table
        rows_html = ""
        for player_name, stats in sorted_players:
            bg_color = "rgba(0, 232, 218, 0.2)" if stats['used_scores'] >= 5 else "transparent"
            total = stats['best_5_total'] if stats['used_scores'] > 0 else "-"
            failed = stats['failed_attempts'] if stats['failed_attempts'] > 0 else "-"
            thrown = ', '.join(str(s) for s in stats.get('thrown_out', [])) if stats.get('thrown_out') else "-"
            
            rows_html += f'''<tr style="background-color: {bg_color};">
                <td style="font-weight: bold;">{player_name}</td>
                <td style="text-align: center; font-weight: bold;">{total}</td>
                <td style="text-align: center;">{stats['used_scores']}</td>
                <td style="text-align: center; color: {'#ff5c5c' if failed != '-' else 'inherit'};">{failed}</td>
                <td style="text-align: center;">{thrown}</td>
            </tr>'''
        
        html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{league_name} - Weekly</title>
    <style>
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #121213; 
            color: white; 
            margin: 0; 
            padding: 10px;
        }}
        h2 {{ 
            color: #00E8DA; 
            margin: 5px 0 10px 0; 
            font-size: 18px;
            text-align: center;
        }}
        table {{ 
            width: 100%; 
            border-collapse: collapse; 
            font-size: 14px;
        }}
        th {{ 
            background: #3a3a3c; 
            padding: 8px 4px; 
            text-align: center;
            font-size: 12px;
        }}
        th:first-child {{ text-align: left; }}
        td {{ 
            padding: 8px 4px; 
            border-bottom: 1px solid #3a3a3c;
        }}
        td:first-child {{ text-align: left; }}
    </style>
</head>
<body>
    <h2>{league_name} - This Week</h2>
    <table>
        <thead>
            <tr>
                <th>Player</th>
                <th>Score</th>
                <th>Used</th>
                <th>Failed</th>
                <th>Thrown</th>
            </tr>
        </thead>
        <tbody>
            {rows_html}
        </tbody>
    </table>
</body>
</html>'''
        
        return html, 200, {'Content-Type': 'text/html'}
        
    except Exception as e:
        logging.error(f"Error generating weekly screenshot: {e}")
        import traceback
        traceback.print_exc()
        return f'<html><body>Error: {str(e)}</body></html>', 500

@app.route('/screenshot/season/<int:league_id>', methods=['GET'])
def screenshot_season(league_id):
    """Generate a screenshot-friendly season standings page"""
    try:
        from league_data_adapter import get_season_data
        
        league_names = {1: 'Warriorz', 3: 'PAL', 4: 'The Party', 7: 'Belly Up'}
        league_name = league_names.get(league_id, f'League {league_id}')
        
        season_data = get_season_data(league_id)
        current_season = season_data.get('current_season', 1)
        standings = season_data.get('season_standings', {})
        
        # Sort by wins descending
        sorted_standings = sorted(standings.items(), key=lambda x: x[1]['wins'], reverse=True)
        
        # Build rows
        rows_html = ""
        for player_name, data in sorted_standings:
            wins = data['wins']
            # Highlight players with 3+ wins (close to winning)
            bg_color = "rgba(255, 215, 0, 0.2)" if wins >= 3 else "transparent"
            star = " " if wins >= 3 else ""
            
            rows_html += f'''<tr style="background-color: {bg_color};">
                <td style="font-weight: bold;">{player_name}{star}</td>
                <td style="text-align: center; font-weight: bold; font-size: 18px;">{wins}</td>
            </tr>'''
        
        html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{league_name} - Season {current_season}</title>
    <style>
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #121213; 
            color: white; 
            margin: 0; 
            padding: 10px;
        }}
        h2 {{ 
            color: #00E8DA; 
            margin: 5px 0 10px 0; 
            font-size: 18px;
            text-align: center;
        }}
        .subtitle {{
            text-align: center;
            font-size: 12px;
            color: #818384;
            margin-bottom: 10px;
        }}
        table {{ 
            width: 100%; 
            border-collapse: collapse; 
            font-size: 14px;
        }}
        th {{ 
            background: #3a3a3c; 
            padding: 8px 4px; 
            text-align: center;
            font-size: 12px;
        }}
        th:first-child {{ text-align: left; }}
        td {{ 
            padding: 10px 4px; 
            border-bottom: 1px solid #3a3a3c;
        }}
        td:first-child {{ text-align: left; }}
    </style>
</head>
<body>
    <h2>{league_name} - Season {current_season}</h2>
    <p class="subtitle">First to 4 weekly wins takes the season!</p>
    <table>
        <thead>
            <tr>
                <th>Player</th>
                <th>Weekly Wins</th>
            </tr>
        </thead>
        <tbody>
            {rows_html}
        </tbody>
    </table>
</body>
</html>'''
        
        return html, 200, {'Content-Type': 'text/html'}
        
    except Exception as e:
        logging.error(f"Error generating season screenshot: {e}")
        import traceback
        traceback.print_exc()
        return f'<html><body>Error: {str(e)}</body></html>', 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
