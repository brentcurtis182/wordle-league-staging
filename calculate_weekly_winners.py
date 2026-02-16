#!/usr/bin/env python3
"""
Manually calculate and save weekly winners for last week
Use this to fix missing weekly winner calculations
"""

import os
import sys
import logging
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from league_data_adapter import get_db_connection, get_current_week_wordles, calculate_wordle_number
from update_tables_cloud import update_weekly_winners_from_db, run_full_update_for_league

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

def calculate_last_week_winners(league_id):
    """Calculate winners for LAST week (the week that just ended)"""
    
    # Get LAST week's Wordle range (7 days ago)
    # Current week starts Monday, so last week is 7-13 days ago
    today = datetime.now().date()
    
    # Find last Monday (start of last week)
    days_since_monday = today.weekday()  # 0=Monday, 6=Sunday
    if days_since_monday == 0:
        # Today is Monday, so last week started 7 days ago
        last_monday = today - timedelta(days=7)
    else:
        # Go back to last Monday, then back 7 more days
        last_monday = today - timedelta(days=days_since_monday + 7)
    
    last_sunday = last_monday + timedelta(days=6)
    
    # Calculate Wordle numbers for last week
    last_week_start_wordle = calculate_wordle_number(last_monday)
    last_week_end_wordle = calculate_wordle_number(last_sunday)
    
    logging.info(f"Calculating winners for LAST week:")
    logging.info(f"  Date range: {last_monday} to {last_sunday}")
    logging.info(f"  Wordle range: {last_week_start_wordle} to {last_week_end_wordle}")
    
    # Use the existing function to calculate and save winners
    success = update_weekly_winners_from_db(
        league_id=league_id,
        week_start_wordle=last_week_start_wordle,
        week_end_wordle=last_week_end_wordle
    )
    
    if success:
        logging.info(f"✅ Weekly winners calculated and saved for league {league_id}")
        
        # Now regenerate HTML to show the updated season table
        logging.info("Regenerating HTML...")
        run_full_update_for_league(league_id)
        logging.info("✅ HTML regenerated")
        
        return True
    else:
        logging.error(f"❌ Failed to calculate weekly winners for league {league_id}")
        return False

if __name__ == "__main__":
    print("Calculating last week's winners...")
    
    # Get all active leagues from DB
    from db_connection import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM leagues WHERE (twilio_conversation_sid IS NOT NULL OR slack_channel_id IS NOT NULL OR discord_channel_id IS NOT NULL) ORDER BY id")
    leagues = [r[0] for r in cursor.fetchall()]
    cursor.close()
    conn.close()
    
    for league_id in leagues:
        print(f"\n{'='*60}")
        print(f"League {league_id}")
        print(f"{'='*60}")
        calculate_last_week_winners(league_id)
    
    print("\n✅ Done! Check the Season tables on the websites.")
