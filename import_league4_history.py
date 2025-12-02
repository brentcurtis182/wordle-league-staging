#!/usr/bin/env python3
"""
Import all historical scores for League 4 from legacy SQLite database
"""

import os
import sys
import sqlite3
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from league_data_adapter import get_db_connection
from datetime import datetime, date, timedelta
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def import_historical_scores():
    """Import all League 4 scores from legacy database"""
    
    # Path to legacy database
    legacy_db_path = r'F:\Wordle-League\Wordle-League-Legacy-Scores\wordle_league.db'
    
    if not os.path.exists(legacy_db_path):
        logging.error(f"Legacy database not found at {legacy_db_path}")
        return False
    
    # Connect to both databases
    legacy_conn = sqlite3.connect(legacy_db_path)
    legacy_cursor = legacy_conn.cursor()
    
    cloud_conn = get_db_connection()
    cloud_cursor = cloud_conn.cursor()
    
    try:
        # Get all League 4 scores from legacy database
        logging.info("Fetching League 4 scores from legacy database...")
        legacy_cursor.execute("""
            SELECT 
                p.name,
                s.wordle_number,
                s.score,
                s.date,
                s.emoji_pattern,
                s.timestamp
            FROM scores s
            JOIN players p ON s.player_id = p.id
            WHERE p.league_id = 4
            ORDER BY s.wordle_number, s.timestamp
        """)
        
        legacy_scores = list(legacy_cursor.fetchall())
        logging.info(f"Found {len(legacy_scores)} scores from League 4")
        
        # Also get Jason's scores from League 5
        logging.info("Fetching Jason's scores from League 5...")
        legacy_cursor.execute("""
            SELECT 
                p.name,
                s.wordle_number,
                s.score,
                s.date,
                s.emoji_pattern,
                s.timestamp
            FROM scores s
            JOIN players p ON s.player_id = p.id
            WHERE p.league_id = 5 AND p.name = 'Jason'
            ORDER BY s.wordle_number, s.timestamp
        """)
        
        jason_scores = list(legacy_cursor.fetchall())
        logging.info(f"Found {len(jason_scores)} scores from Jason in League 5")
        
        # Combine both
        legacy_scores.extend(jason_scores)
        logging.info(f"Total historical scores to import: {len(legacy_scores)}")
        
        # Map player names to cloud player IDs
        player_id_map = {}
        cloud_cursor.execute("""
            SELECT id, name FROM players WHERE league_id = 4
        """)
        for row in cloud_cursor.fetchall():
            player_id_map[row[1]] = row[0]
        
        # Import each score
        imported = 0
        skipped = 0
        
        for score_data in legacy_scores:
            player_name = score_data[0]
            wordle_num = score_data[1]
            score = score_data[2]
            score_date = score_data[3]
            emoji_pattern = score_data[4]
            timestamp = score_data[5]
            
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
            
            # Insert into cloud database (only into scores table for history)
            try:
                cloud_cursor.execute("""
                    INSERT INTO scores (player_id, wordle_number, score, date, emoji_pattern, timestamp)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (player_id, wordle_num, score, date_obj, emoji_pattern, timestamp_obj))
                
                if cloud_cursor.rowcount > 0:
                    imported += 1
                else:
                    skipped += 1
                    
            except Exception as e:
                logging.error(f"Error importing score for {player_name}, Wordle {wordle_num}: {e}")
                skipped += 1
        
        cloud_conn.commit()
        
        logging.info(f"✅ Import complete!")
        logging.info(f"  Imported: {imported}")
        logging.info(f"  Skipped: {skipped}")
        
        return True
        
    except Exception as e:
        logging.error(f"Error during import: {e}")
        import traceback
        traceback.print_exc()
        cloud_conn.rollback()
        return False
        
    finally:
        legacy_cursor.close()
        legacy_conn.close()
        cloud_cursor.close()
        cloud_conn.close()

if __name__ == "__main__":
    success = import_historical_scores()
    if success:
        logging.info("Now regenerating HTML...")
        from update_pipeline import run_update_pipeline
        run_update_pipeline(4)
        logging.info("✅ All done!")
