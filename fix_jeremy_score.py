#!/usr/bin/env python3
"""
Fix Jeremy's score - restore his correct 4/6 for Wordle 1623
His score was overwritten by a reaction message
"""

import os
import sys
import logging
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from league_data_adapter import get_db_connection

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

def fix_jeremy_score():
    """Fix Jeremy's score for Wordle 1623 in League 7"""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Find Jeremy in League 7
        cursor.execute("""
            SELECT id, name FROM players 
            WHERE league_id = 7 AND (name LIKE '%Jeremy%' OR phone_number LIKE '%8587751124%')
        """)
        
        player = cursor.fetchone()
        if not player:
            logging.error("Could not find Jeremy in League 7")
            return False
        
        player_id = player[0]
        player_name = player[1]
        logging.info(f"Found player: {player_name} (ID: {player_id})")
        
        # Check current score
        cursor.execute("""
            SELECT score, emoji_pattern FROM scores
            WHERE player_id = %s AND wordle_number = 1623
        """, (player_id,))
        
        current = cursor.fetchone()
        if current:
            logging.info(f"Current score: {current[0]}, emoji: {current[1][:50] if current[1] else 'None'}...")
        
        # Jeremy's correct score from Twilio:
        # Wordle 1,623 4/6 🟩🟩⬛⬛⬛ 🟩🟩⬛⬛⬛ 🟩🟩🟩🟩⬛ 🟩🟩🟩🟩🟩
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
        
        logging.info(f"✅ Fixed Jeremy's score to 4/6 for Wordle 1623")
        logging.info(f"   Updated {cursor.rowcount} row(s)")
        
        return True
        
    except Exception as e:
        conn.rollback()
        logging.error(f"Error fixing Jeremy's score: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    print("Fixing Jeremy's score...")
    success = fix_jeremy_score()
    if success:
        print("✅ Score fixed! Run trigger_update.ps1 to regenerate HTML")
        sys.exit(0)
    else:
        print("❌ Failed to fix score")
        sys.exit(1)
