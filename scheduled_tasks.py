#!/usr/bin/env python3
"""
Scheduled Tasks for Wordle League Cloud
Runs daily at 12:01 AM Pacific Time to:
1. Clear latest scores for new day
2. Calculate weekly winners (on Mondays)
3. Check for season transitions
4. Update HTML and publish
"""

import os
import sys
import logging
from datetime import datetime, timedelta
import pytz

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from league_data_adapter import get_db_connection, calculate_wordle_number, get_week_start_date
from update_tables_cloud import run_full_update_for_league

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

def get_last_reset_date(league_id):
    """Get the last reset date from settings table"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        key = f'last_reset_date_league_{league_id}'
        cursor.execute("""
            SELECT value FROM settings
            WHERE key = %s
        """, (key,))
        
        result = cursor.fetchone()
        if result:
            return result[0]
        return None
    finally:
        cursor.close()
        conn.close()

def set_last_reset_date(league_id, reset_date):
    """Store the last reset date in settings table"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        key = f'last_reset_date_league_{league_id}'
        cursor.execute("""
            INSERT INTO settings (key, value)
            VALUES (%s, %s)
            ON CONFLICT (key) 
            DO UPDATE SET value = EXCLUDED.value, updated_at = CURRENT_TIMESTAMP
        """, (key, reset_date))
        
        conn.commit()
    finally:
        cursor.close()
        conn.close()

def clear_latest_scores(league_id):
    """
    Clear latest scores table for a new day
    This resets the 'Latest Scores' tab
    Only clears if we haven't already reset today
    """
    pacific = pytz.timezone('America/Los_Angeles')
    now_pacific = datetime.now(pacific)
    today = now_pacific.strftime('%Y-%m-%d')
    
    # Check if we already reset today
    last_reset = get_last_reset_date(league_id)
    
    if last_reset == today:
        logging.info(f"Already reset today ({today}) - skipping")
        return False
    
    logging.info(f"Clearing latest scores for league {league_id} (last reset: {last_reset}, today: {today})")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Clear all latest scores for this league
        cursor.execute("""
            DELETE FROM latest_scores
            WHERE league_id = %s
        """, (league_id,))
        
        conn.commit()
        logging.info(f"Cleared {cursor.rowcount} latest scores for league {league_id}")
        
        # Update last reset date
        set_last_reset_date(league_id, today)
        
        return True
        
    except Exception as e:
        conn.rollback()
        logging.error(f"Error clearing latest scores: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

def is_monday():
    """Check if today is Monday (start of new week)"""
    pacific = pytz.timezone('America/Los_Angeles')
    now = datetime.now(pacific)
    return now.weekday() == 0  # Monday = 0

def run_daily_reset(league_id):
    """
    Run daily reset tasks:
    1. Clear latest scores
    2. If Monday, calculate weekly winners and check season transitions
    3. Regenerate and publish HTML
    """
    logging.info("=" * 60)
    logging.info(f"DAILY RESET - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logging.info("=" * 60)
    
    try:
        # Step 1: Clear latest scores
        clear_latest_scores(league_id)
        
        # Step 2: If Monday, run full weekly update
        if is_monday():
            logging.info("🗓️  MONDAY - Running weekly winner calculation and season check")
            success = run_full_update_for_league(league_id)
            if success:
                logging.info("✅ Weekly update completed successfully")
            else:
                logging.error("❌ Weekly update failed")
        else:
            logging.info("Not Monday - skipping weekly winner calculation")
            
            # Still regenerate HTML to show cleared latest scores
            from update_pipeline import run_update_pipeline
            pipeline_status = run_update_pipeline(league_id)
            if pipeline_status['success']:
                logging.info("✅ HTML regenerated and published")
            else:
                logging.error("❌ HTML regeneration failed")
        
        logging.info("=" * 60)
        logging.info("DAILY RESET COMPLETE")
        logging.info("=" * 60)
        
        return True
        
    except Exception as e:
        logging.error(f"Error in daily reset: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_all_leagues_daily_reset():
    """Run daily reset for all active leagues (dynamically from database)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, display_name, channel_type FROM leagues
            WHERE (twilio_conversation_sid IS NOT NULL OR slack_channel_id IS NOT NULL OR discord_channel_id IS NOT NULL)
            ORDER BY id
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        leagues = [(r[0], r[1], r[2] or 'sms') for r in rows]
        logging.info(f"Found {len(leagues)} active leagues for daily reset: {[(l[0], l[1], l[2]) for l in leagues]}")
    except Exception as e:
        logging.error(f"Failed to fetch active leagues from database: {e}")
        return False
    
    all_success = True
    for league_id, league_name, channel_type in leagues:
        logging.info(f"\n{'='*60}")
        logging.info(f"Processing League {league_id} ({league_name}) [{channel_type}]")
        logging.info(f"{'='*60}")
        success = run_daily_reset(league_id)
        if not success:
            all_success = False
    
    return all_success

if __name__ == "__main__":
    # This script should be run daily at 12:01 AM Pacific
    # Can be run via Railway cron job or external scheduler
    print("Starting daily reset...")
    success = run_all_leagues_daily_reset()
    if success:
        print("Daily reset completed successfully!")
        sys.exit(0)
    else:
        print("Daily reset failed!")
        sys.exit(1)
