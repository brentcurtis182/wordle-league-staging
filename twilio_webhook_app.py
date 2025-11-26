#!/usr/bin/env python3
"""
Twilio Webhook Flask App for Wordle League
Receives SMS messages from Twilio and extracts Wordle scores
"""

import os
import re
import logging
from datetime import datetime, date, timedelta
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import psycopg2

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

app = Flask(__name__)

# Phone number to player/league mappings
PHONE_MAPPINGS = {
    # League 6: Beta Test
    6: {
        "18587359353": "Brent",
        "17609082000": "Matt",
        "17608156131": "Rob",
        "16503468822": "Jason",
    },
    # League 7: BellyUp
    7: {
        "18587359353": "Brent",
        "18587751124": "Jeremy",
        "15134781947": "Henry",
        "19285812935": "Mikaila",
        "12675910330": "Pete",
        "16032546373": "Meredith",
    }
}

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
    
    # Normalize phone number by removing non-digits
    digits_only = ''.join(c for c in phone_number if c.isdigit())
    
    # Try with and without leading 1 (country code)
    if league_id in PHONE_MAPPINGS:
        # Try direct match with digits
        if digits_only in PHONE_MAPPINGS[league_id]:
            return PHONE_MAPPINGS[league_id][digits_only]
        
        # Try adding leading 1 if it's missing and length is 10
        if len(digits_only) == 10:
            with_country_code = "1" + digits_only
            if with_country_code in PHONE_MAPPINGS[league_id]:
                return PHONE_MAPPINGS[league_id][with_country_code]
        
        # Try without leading 1 if it has one and length is 11
        if len(digits_only) == 11 and digits_only[0] == "1":
            without_country_code = digits_only[1:]
            if without_country_code in PHONE_MAPPINGS[league_id]:
                return PHONE_MAPPINGS[league_id][without_country_code]
    
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
                emoji_lines.append(line.strip())
    
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
            # Update if different
            if existing_score[0] != score or existing_score[1] != emoji_pattern:
                cursor.execute("""
                    UPDATE scores 
                    SET score = %s, emoji_pattern = %s, timestamp = %s 
                    WHERE player_id = %s AND wordle_number = %s
                """, (score, emoji_pattern, now, player_id, wordle_num))
                conn.commit()
                logging.info(f"Updated score for {player_name}, Wordle #{wordle_num}")
                cursor.close()
                return "updated"
            else:
                logging.info(f"Score already exists for {player_name}, Wordle #{wordle_num}")
                cursor.close()
                return "exists"
        else:
            # Insert new score
            cursor.execute("""
                INSERT INTO scores (player_id, wordle_number, score, date, emoji_pattern, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (player_id, wordle_num, score, wordle_date, emoji_pattern, now))
            conn.commit()
            logging.info(f"Inserted new score for {player_name}, Wordle #{wordle_num}")
            cursor.close()
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
            'CH1ef798b5bfba4e5297268d69c01949f5': 6,  # League 6
            'CH4438ff5531514178bb13c5c0e96d5579': 7,  # BellyUp (League 7)
        }
        
        # Default to League 6 if no conversation SID or not mapped
        league_id = conversation_to_league.get(conversation_sid, 6)
        logging.info(f"Conversation SID: {conversation_sid} -> League {league_id}")
        
        # Get player name from phone number
        player_name = get_player_from_phone(from_number, league_id)
        
        if not player_name:
            logging.warning(f"Unknown phone number: {from_number}")
            # Return empty TwiML response (no SMS sent back)
            return '<?xml version="1.0" encoding="UTF-8"?><Response></Response>', 200
        
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
            
            # Trigger full update pipeline including weekly winners
            try:
                from update_tables_cloud import run_full_update_for_league
                logging.info("Triggering full update pipeline...")
                success = run_full_update_for_league(league_id=league_id)
                if success:
                    logging.info("Pipeline completed successfully")
                else:
                    logging.error("Pipeline failed")
            except Exception as pipeline_error:
                logging.error(f"Pipeline error: {pipeline_error}")
                # Don't fail the webhook if pipeline fails
                
        elif result == "updated":
            logging.info(f"✅ Score updated! {player_name}: Wordle #{wordle_num} - {score if score != 7 else 'X'}/6")
            
            # Also trigger full update on updates
            try:
                from update_tables_cloud import run_full_update_for_league
                logging.info("Triggering full update pipeline...")
                success = run_full_update_for_league(league_id=league_id)
                if success:
                    logging.info("Pipeline completed successfully")
                else:
                    logging.error("Pipeline failed")
            except Exception as pipeline_error:
                logging.error(f"Pipeline error: {pipeline_error}")
                
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

@app.route('/', methods=['GET'])
def index():
    """Root endpoint"""
    return {'message': 'Wordle League Twilio Webhook', 'status': 'running'}

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
