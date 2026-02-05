#!/usr/bin/env python3
"""
Restore League 4 scores from Dec 2, 2025 that were lost due to incorrect conversation SID
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from league_data_adapter import get_db_connection
from datetime import datetime, date, timedelta
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def restore_scores():
    """Restore the 5 lost scores - move from League 6 to League 4 with correct player IDs"""
    
    # Phone to player mapping for League 4
    phone_to_player = {
        '19165416576': 'Dustin',
        '16503468822': 'Jason',
        '17608156131': 'Rob',
        '17609082401': 'Jess',
        '17609082000': 'Matt'
    }
    
    # Map League 6 player names to League 4 phones (since they saved with wrong names)
    # Brent in League 6 = multiple people in League 4
    # We'll use timestamps to match
    
    # Scores from Twilio conversation
    scores = [
        {
            'phone': '17609082401',
            'wordle': 1627,
            'score': 4,
            'emoji': '⬜⬜🟩⬜⬜\n🟨⬜🟨⬜⬜\n⬜🟩🟩⬜🟩\n🟩🟩🟩🟩🟩',
            'timestamp': '2025-12-02 06:40:45'
        },
        {
            'phone': '17609082000',
            'wordle': 1627,
            'score': 4,
            'emoji': '⬛🟩🟨⬛🟨\n⬛⬛⬛⬛⬛\n⬛🟩🟨🟨🟨\n🟩🟩🟩🟩🟩',
            'timestamp': '2025-12-02 07:22:42'
        },
        {
            'phone': '19165416576',
            'wordle': 1627,
            'score': 7,  # X = 7
            'emoji': '⬛⬛🟨⬛⬛\n⬛🟩⬛⬛⬛\n⬛🟩⬛⬛⬛\n⬛🟩⬛⬛⬛\n⬛🟩🟨🟨🟨\n🟨🟩🟩🟨⬛',
            'timestamp': '2025-12-02 07:41:09'
        },
        {
            'phone': '16503468822',
            'wordle': 1627,
            'score': 4,
            'emoji': '⬛⬛🟨🟩⬛\n⬛🟩⬛🟩⬛\n⬛🟩🟨🟩⬛\n🟩🟩🟩🟩🟩',
            'timestamp': '2025-12-02 08:22:53'
        },
        {
            'phone': '17608156131',
            'wordle': 1627,
            'score': 5,
            'emoji': '⬜⬜⬜🟨🟨\n⬜⬜🟨🟨⬜\n⬜🟩⬜🟨🟨\n⬜🟩🟨⬜⬜\n🟩🟩🟩🟩🟩',
            'timestamp': '2025-12-02 08:24:38'
        }
    ]
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # First, delete any Wordle 1627 scores from League 6 (they're wrong)
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
        logging.info("Deleted incorrect scores from League 6")
        
        # Get player IDs for League 4
        cursor.execute("SELECT id, name, phone_number FROM players WHERE league_id = 4")
        players = {row[2]: {'id': row[0], 'name': row[1]} for row in cursor.fetchall()}
        
        logging.info(f"Found {len(players)} League 4 players")
        logging.info(f"Player phones: {list(players.keys())}")
        
        # Calculate date for Wordle 1627
        ref_date = date(2025, 7, 31)
        ref_wordle = 1503
        days_offset = 1627 - ref_wordle
        wordle_date = ref_date + timedelta(days=days_offset)
        
        inserted = 0
        skipped = 0
        
        for score_data in scores:
            phone = score_data['phone']
            
            logging.info(f"Processing score for phone {phone}")
            
            if phone not in players:
                logging.warning(f"Phone {phone} not found in League 4 players")
                logging.warning(f"Available phones: {list(players.keys())}")
                skipped += 1
                continue
            
            player_id = players[phone]['id']
            player_name = players[phone]['name']
            
            # Check if already exists
            cursor.execute("""
                SELECT id FROM scores 
                WHERE player_id = %s AND wordle_number = %s
            """, (player_id, score_data['wordle']))
            
            if cursor.fetchone():
                logging.info(f"Score already exists for {player_name}, Wordle {score_data['wordle']}")
                skipped += 1
                continue
            
            # Parse timestamp
            timestamp = datetime.strptime(score_data['timestamp'], '%Y-%m-%d %H:%M:%S')
            
            # Insert into scores table
            cursor.execute("""
                INSERT INTO scores (player_id, wordle_number, score, date, emoji_pattern, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (player_id, score_data['wordle'], score_data['score'], wordle_date, 
                  score_data['emoji'], timestamp))
            
            # Insert into latest_scores table
            cursor.execute("""
                INSERT INTO latest_scores (player_id, league_id, wordle_number, score, emoji_pattern, timestamp)
                VALUES (%s, 4, %s, %s, %s, %s)
                ON CONFLICT (player_id, wordle_number) DO UPDATE 
                SET score = EXCLUDED.score, emoji_pattern = EXCLUDED.emoji_pattern, timestamp = EXCLUDED.timestamp
            """, (player_id, score_data['wordle'], score_data['score'], 
                  score_data['emoji'], timestamp))
            
            logging.info(f"✅ Inserted score for {player_name}: Wordle {score_data['wordle']} - {score_data['score']}/6")
            inserted += 1
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logging.info(f"\n{'='*60}")
        logging.info(f"Restore complete: {inserted} inserted, {skipped} skipped")
        logging.info(f"{'='*60}")
        
        return inserted > 0
        
    except Exception as e:
        logging.error(f"Error restoring scores: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        return False

if __name__ == "__main__":
    success = restore_scores()
    if success:
        logging.info("Now regenerating HTML...")
        from update_pipeline import run_update_pipeline
        run_update_pipeline(4)
        logging.info("Done!")
