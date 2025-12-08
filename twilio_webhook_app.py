#!/usr/bin/env python3
"""
Twilio Webhook Flask App for Wordle League
Receives SMS messages from Twilio and extracts Wordle scores
"""

import os
import re
import logging
from datetime import datetime, date, timedelta
from flask import Flask, request, jsonify
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
    # League 1: Warriorz
    1: {
        "18587359353": "Brent",
        "17603341190": "Malia",
        "17608462302": "Evan",
        "13109263555": "Joanna",
        "19492304472": "Nanna",
    },
    # League 3: PAL
    3: {
        "18587359353": "Vox",
        "17604206113": "Fuzwuz",
        "17605830059": "Pants",
        "14698345364": "Starslider",
    },
    # League 4: Party
    4: {
        "18587359353": "Brent",
        "19165416576": "Dustin",
        "17609082401": "Jess",
        "17609082000": "Matt",
        "17606725317": "Meghan",
        "17608156131": "Rob",
        "16503468822": "Jason",
        "16198713458": "Patty",
        "17609949392": "Dani",
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
            
            # Trigger full update pipeline in background (async)
            try:
                import threading
                def run_pipeline_async():
                    try:
                        from update_pipeline import run_update_pipeline
                        logging.info(f"[Async] Triggering update pipeline for league {league_id}...")
                        result_data = run_update_pipeline(league_id)
                        if result_data.get('success'):
                            logging.info(f"[Async] Pipeline completed successfully for league {league_id}")
                        else:
                            logging.error(f"[Async] Pipeline failed for league {league_id}: {result_data.get('errors')}")
                    except Exception as e:
                        logging.error(f"[Async] Pipeline error for league {league_id}: {e}")
                
                thread = threading.Thread(target=run_pipeline_async, daemon=True)
                thread.start()
                logging.info(f"Pipeline triggered in background thread for league {league_id}")
            except Exception as pipeline_error:
                logging.error(f"Error starting pipeline thread: {pipeline_error}")
                # Don't fail the webhook if pipeline fails
                
        elif result == "updated":
            logging.info(f"✅ Score updated! {player_name}: Wordle #{wordle_num} - {score if score != 7 else 'X'}/6")
            
            # Also trigger full update in background
            try:
                import threading
                def run_pipeline_async():
                    try:
                        from update_pipeline import run_update_pipeline
                        logging.info(f"[Async] Triggering update pipeline for league {league_id}...")
                        result_data = run_update_pipeline(league_id)
                        if result_data.get('success'):
                            logging.info(f"[Async] Pipeline completed successfully for league {league_id}")
                        else:
                            logging.error(f"[Async] Pipeline failed for league {league_id}: {result_data.get('errors')}")
                    except Exception as e:
                        logging.error(f"[Async] Pipeline error for league {league_id}: {e}")
                
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

@app.route('/calculate-last-week-winners', methods=['POST'])
def calculate_last_week_winners_endpoint():
    """Manually calculate last week's winners"""
    try:
        from calculate_weekly_winners import calculate_last_week_winners
        logging.info("Calculating last week's winners...")
        
        leagues = [6, 7]
        results = {}
        
        for league_id in leagues:
            success = calculate_last_week_winners(league_id)
            results[f'league_{league_id}'] = 'success' if success else 'failed'
        
        return {
            'success': True,
            'message': 'Calculated last week winners',
            'results': results
        }, 200
    except Exception as e:
        logging.error(f"Error calculating last week winners: {e}")
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

@app.route('/fix-season-winners', methods=['POST'])
def fix_season_winners():
    """Fix duplicate season winners and add missing League 3 winners"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Delete duplicate season winners (keep only seasons 1-3 for each league)
        cursor.execute("""
            DELETE FROM season_winners 
            WHERE (league_id = 1 AND season_number > 3)
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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
