#!/usr/bin/env python3
"""
Restore today's scores from Twilio logs
Fetches messages from today and re-processes them
"""

import os
import sys
import logging
from datetime import datetime, date, timedelta
import pytz

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from twilio.rest import Client
from league_data_adapter import get_db_connection
from twilio_webhook_app import extract_wordle_score, get_player_from_phone, save_score_to_db

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# Conversation SID to League mapping
CONVERSATION_TO_LEAGUE = {
    'CH1ef798b5bfba4e5297268d69c01949f5': 6,  # League 6
    'CH4438ff5531514178bb13c5c0e96d5579': 7,  # BellyUp (League 7)
}

def restore_todays_scores():
    """Fetch today's messages from Twilio and restore scores"""
    
    # Get Twilio credentials from environment
    account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
    auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
    
    if not account_sid or not auth_token:
        logging.error("Twilio credentials not found in environment variables")
        return False
    
    # Initialize Twilio client
    client = Client(account_sid, auth_token)
    
    # Get today's date in Pacific timezone
    pacific = pytz.timezone('America/Los_Angeles')
    today = datetime.now(pacific).date()
    today_start = datetime.combine(today, datetime.min.time()).replace(tzinfo=pacific)
    
    logging.info(f"Fetching messages from {today_start} onwards...")
    
    restored_count = 0
    
    # Process each league's conversation
    for conversation_sid, league_id in CONVERSATION_TO_LEAGUE.items():
        logging.info(f"\n{'='*60}")
        logging.info(f"Processing League {league_id} (Conversation: {conversation_sid})")
        logging.info(f"{'='*60}")
        
        try:
            # Fetch messages from this conversation
            messages = client.conversations.v1.conversations(conversation_sid).messages.list(
                date_created_after=today_start
            )
            
            logging.info(f"Found {len(messages)} messages in League {league_id} today")
            
            # Get database connection
            conn = get_db_connection()
            
            # Process each message
            for msg in messages:
                author = msg.author
                body = msg.body
                timestamp = msg.date_created
                
                logging.info(f"\n--- Message from {author} at {timestamp} ---")
                logging.info(f"Body: {body[:100]}...")
                
                # Skip if no body
                if not body:
                    logging.info("Skipping: No message body")
                    continue
                
                # Extract Wordle score
                wordle_num, score, emoji_pattern = extract_wordle_score(body)
                
                if not wordle_num or not score:
                    logging.info("Skipping: No valid Wordle score found")
                    continue
                
                logging.info(f"Extracted: Wordle #{wordle_num}, Score: {score}/6")
                
                # Get player name from phone number
                player_name = get_player_from_phone(author, league_id)
                
                if not player_name:
                    logging.warning(f"Unknown phone number: {author}")
                    continue
                
                logging.info(f"Player: {player_name}")
                
                # Save to database
                result = save_score_to_db(player_name, wordle_num, score, emoji_pattern, league_id, conn)
                
                if result == "new":
                    logging.info(f"✅ Restored score for {player_name}")
                    restored_count += 1
                elif result == "exists":
                    logging.info(f"⏭️  Score already exists for {player_name}")
                else:
                    logging.warning(f"⚠️  Failed to restore score for {player_name}: {result}")
            
            conn.close()
            
        except Exception as e:
            logging.error(f"Error processing League {league_id}: {e}")
            import traceback
            traceback.print_exc()
    
    logging.info(f"\n{'='*60}")
    logging.info(f"RESTORATION COMPLETE")
    logging.info(f"{'='*60}")
    logging.info(f"Total scores restored: {restored_count}")
    
    return restored_count > 0

if __name__ == "__main__":
    print("Restoring today's scores from Twilio...")
    success = restore_todays_scores()
    
    if success:
        print("\n✅ Scores restored! Now run:")
        print("   Invoke-WebRequest -Uri 'https://wordle-league-production.up.railway.app/daily-reset' -Method POST")
        print("\nThis will regenerate the HTML with the restored scores.")
        sys.exit(0)
    else:
        print("\n⚠️  No scores were restored")
        sys.exit(1)
