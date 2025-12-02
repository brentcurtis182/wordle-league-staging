#!/usr/bin/env python3
"""
Bulk insert League 1 historical scores from JSON file
"""

import os
import sys
import json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from league_data_adapter import get_db_connection
from datetime import datetime, date, timedelta
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def bulk_insert_scores():
    """Insert all scores from JSON file"""
    
    json_file = 'league1_historical_scores.json'
    
    if not os.path.exists(json_file):
        logging.error(f"JSON file not found: {json_file}")
        return False
    
    # Load scores from JSON
    with open(json_file, 'r') as f:
        all_scores = json.load(f)
    
    logging.info(f"Loaded {len(all_scores)} scores from {json_file}")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Map player names to cloud player IDs
        player_id_map = {}
        cursor.execute("""
            SELECT id, name FROM players WHERE league_id = 1
        """)
        for row in cursor.fetchall():
            player_id_map[row[1]] = row[0]
        
        logging.info(f"Player mapping: {player_id_map}")
        
        # Import each score
        imported = 0
        skipped = 0
        
        for score_data in all_scores:
            player_name = score_data['player_name']
            wordle_num = score_data['wordle_number']
            score = score_data['score']
            score_date = score_data['date']
            emoji_pattern = score_data['emoji_pattern']
            timestamp = score_data['timestamp']
            
            # Get cloud player ID
            if player_name not in player_id_map:
                logging.warning(f"Player {player_name} not found in cloud database, skipping")
                skipped += 1
                continue
            
            player_id = player_id_map[player_name]
            
            # Parse date
            if isinstance(score_date, str):
                try:
                    date_obj = datetime.strptime(score_date, '%Y-%m-%d').date()
                except:
                    # Calculate from Wordle number
                    ref_date = date(2025, 7, 31)
                    ref_wordle = 1503
                    days_offset = wordle_num - ref_wordle
                    date_obj = ref_date + timedelta(days=days_offset)
            else:
                date_obj = score_date
            
            # Parse timestamp
            if isinstance(timestamp, str):
                try:
                    timestamp_obj = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
                except:
                    timestamp_obj = datetime.now()
            else:
                timestamp_obj = timestamp if timestamp else datetime.now()
            
            # Insert into cloud database
            try:
                cursor.execute("""
                    INSERT INTO scores (player_id, wordle_number, score, date, emoji_pattern, timestamp)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (player_id, wordle_num, score, date_obj, emoji_pattern, timestamp_obj))
                
                if cursor.rowcount > 0:
                    imported += 1
                    if imported % 100 == 0:
                        logging.info(f"  Imported {imported} scores so far...")
                        conn.commit()  # Commit every 100
                else:
                    skipped += 1
                    
            except Exception as e:
                logging.error(f"Error importing score for {player_name}, Wordle {wordle_num}: {e}")
                skipped += 1
        
        conn.commit()
        
        logging.info(f"Import complete!")
        logging.info(f"  Imported: {imported}")
        logging.info(f"  Skipped: {skipped}")
        
        return True
        
    except Exception as e:
        logging.error(f"Error during import: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        return False
        
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    success = bulk_insert_scores()
    if success:
        logging.info("Now regenerating HTML...")
        from update_pipeline import run_update_pipeline
        run_update_pipeline(1)
        logging.info("All done!")
