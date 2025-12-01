#!/usr/bin/env python3
"""
Insert League 4 scores manually from Twilio data
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from league_data_adapter import get_db_connection
from datetime import datetime, date, timedelta
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def insert_scores():
    """Insert League 4 scores from Twilio"""
    
    # Scores from Twilio
    scores = [
        ('+19165416576', 'Dustin', 1626, 5, '⬛🟨🟨🟨⬛ ⬛🟨🟨⬛🟨 ⬛🟩🟩🟨⬛ 🟩🟩🟩⬛⬛ 🟩🟩🟩🟩🟩'),
        ('+16503468822', 'Jason', 1626, 2, '⬛🟨🟩⬛🟨 🟩🟩🟩🟩🟩'),
        ('+17609082000', 'Matt', 1626, 6, '⬜🟨⬜🟩🟨 ⬜🟨⬜⬜⬜ ⬜🟩🟩🟩🟩 ⬜🟩🟩🟩🟩 ⬜🟩🟩🟩🟩 🟩🟩🟩🟩🟩'),
        ('+17608156131', 'Rob', 1626, 6, '🟨⬜⬜⬜⬜ ⬜🟨🟩⬜🟨 🟨⬜🟩🟨⬜ 🟩🟩🟩⬜⬜ 🟩🟩🟩⬜⬜ 🟩🟩🟩🟩🟩'),
        ('+17609082401', 'Jess', 1626, 6, '⬜⬜🟨⬜⬜ 🟨⬜⬜⬜🟨 🟨🟨🟨🟨⬜ ⬜🟩🟩🟩🟩 ⬜🟩🟩🟩🟩 🟩🟩🟩🟩🟩'),
        ('+17609949392', 'Dani', 1626, 4, '⬛⬛🟨🟨⬛ ⬛🟨🟩⬛🟨 🟩🟩🟩⬛⬛ 🟩🟩🟩🟩🟩'),
    ]
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Calculate date for Wordle 1626
        ref_date = date(2025, 7, 31)
        ref_wordle = 1503
        days_offset = 1626 - ref_wordle
        wordle_date = ref_date + timedelta(days=days_offset)
        
        logging.info(f"Inserting scores for Wordle 1626 (date: {wordle_date})")
        
        for phone, player_name, wordle_num, score, emoji_pattern in scores:
            # Get player ID
            cursor.execute("""
                SELECT id FROM players 
                WHERE league_id = 4 AND name = %s
            """, (player_name,))
            
            result = cursor.fetchone()
            if not result:
                logging.error(f"Player {player_name} not found!")
                continue
            
            player_id = result[0]
            now = datetime.now()
            
            # Insert into scores table
            cursor.execute("""
                INSERT INTO scores (player_id, wordle_number, score, date, emoji_pattern, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (player_id, wordle_num, score, wordle_date, emoji_pattern, now))
            
            # Insert into latest_scores table
            cursor.execute("""
                INSERT INTO latest_scores (player_id, league_id, wordle_number, score, emoji_pattern, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (player_id, wordle_number) 
                DO UPDATE SET score = EXCLUDED.score, emoji_pattern = EXCLUDED.emoji_pattern, timestamp = EXCLUDED.timestamp
            """, (player_id, 4, wordle_num, score, emoji_pattern, now))
            
            logging.info(f"  ✅ {player_name}: {score}/6")
        
        conn.commit()
        logging.info("✅ All scores inserted successfully!")
        
        # Now regenerate HTML
        logging.info("Regenerating HTML...")
        from update_pipeline import run_update_pipeline
        success = run_update_pipeline(4)
        
        if success:
            logging.info("✅ HTML generated and published!")
        else:
            logging.error("❌ HTML generation failed")
        
    except Exception as e:
        logging.error(f"Error inserting scores: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    insert_scores()
