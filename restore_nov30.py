#!/usr/bin/env python3
"""
Restore Nov 30 scores for League 6 that were submitted before the reset
"""

import os
import sys
import logging
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from league_data_adapter import get_db_connection

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

def restore_scores():
    """Restore the two missing scores from Nov 30"""
    
    scores_to_restore = [
        {
            'phone': '17609082000',  # Matt
            'wordle': 1625,
            'score': 4,
            'emoji': '⬜⬜⬜⬜⬜\n⬜⬜🟩🟨⬜\n⬜🟩🟩🟩🟩\n🟩🟩🟩🟩🟩',
            'timestamp': '2025-11-30 07:25:58'
        },
        {
            'phone': '17608156131',  # Rob
            'wordle': 1625,
            'score': 4,
            'emoji': '⬜⬜⬜⬜🟨\n⬜⬜🟨⬜⬜\n⬜🟩🟩🟩🟩\n🟩🟩🟩🟩🟩',
            'timestamp': '2025-11-30 07:52:29'
        }
    ]
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    restored_count = 0
    
    try:
        for score_data in scores_to_restore:
            # Find player by phone number
            cursor.execute("""
                SELECT id, name FROM players 
                WHERE league_id = 6 AND phone_number LIKE %s
            """, (f'%{score_data["phone"]}%',))
            
            player = cursor.fetchone()
            if not player:
                logging.error(f"Player not found for phone: {score_data['phone']}")
                continue
            
            player_id = player[0]
            player_name = player[1]
            
            logging.info(f"Restoring score for {player_name}...")
            
            # Check if score already exists
            cursor.execute("""
                SELECT score FROM scores
                WHERE player_id = %s AND wordle_number = %s
            """, (player_id, score_data['wordle']))
            
            existing = cursor.fetchone()
            
            if existing:
                logging.info(f"  Score already exists for {player_name} - skipping")
                continue
            
            # Insert into scores table
            cursor.execute("""
                INSERT INTO scores (player_id, wordle_number, score, date, emoji_pattern, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (player_id, wordle_number) DO NOTHING
            """, (
                player_id,
                score_data['wordle'],
                score_data['score'],
                '2025-11-30',
                score_data['emoji'],
                score_data['timestamp']
            ))
            
            # Insert into latest_scores table
            cursor.execute("""
                INSERT INTO latest_scores (player_id, league_id, wordle_number, score, emoji_pattern, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (player_id, wordle_number) 
                DO UPDATE SET score = EXCLUDED.score, emoji_pattern = EXCLUDED.emoji_pattern
            """, (
                player_id,
                6,  # League 6
                score_data['wordle'],
                score_data['score'],
                score_data['emoji'],
                score_data['timestamp']
            ))
            
            conn.commit()
            logging.info(f"  ✅ Restored {player_name}: Wordle {score_data['wordle']} - {score_data['score']}/6")
            restored_count += 1
        
        logging.info(f"\n{'='*60}")
        logging.info(f"Restored {restored_count} scores")
        logging.info(f"{'='*60}")
        
        return restored_count > 0
        
    except Exception as e:
        conn.rollback()
        logging.error(f"Error restoring scores: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    print("Restoring Nov 30 scores...")
    success = restore_scores()
    if success:
        print("\n✅ Scores restored! Now regenerating HTML...")
        sys.exit(0)
    else:
        print("\n❌ Failed to restore scores")
        sys.exit(1)
