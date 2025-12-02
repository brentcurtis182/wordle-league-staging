#!/usr/bin/env python3
"""
Force insert League 3 scores with detailed logging
"""

import os
import sys
import json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from league_data_adapter import get_db_connection
from datetime import datetime, date, timedelta
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def force_insert():
    """Force insert with detailed tracking"""
    
    json_file = 'league3_historical_scores.json'
    
    if not os.path.exists(json_file):
        return {'error': 'JSON file not found'}
    
    with open(json_file, 'r') as f:
        all_scores = json.load(f)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get player mapping
    cursor.execute("SELECT id, name FROM players WHERE league_id = 3")
    player_map = {row[1]: row[0] for row in cursor.fetchall()}
    
    results = {
        'total': len(all_scores),
        'imported': 0,
        'skipped': 0,
        'errors': [],
        'player_map': player_map
    }
    
    ref_date = date(2025, 7, 31)
    ref_wordle = 1503
    
    for i, score_data in enumerate(all_scores):
        try:
            player_name = score_data['player_name']
            wordle_num = score_data['wordle_number']
            score = score_data['score']
            
            # Convert 'X' to 7 for failed attempts
            if score == 'X' or score == 'x':
                score = 7
            
            if player_name not in player_map:
                results['errors'].append(f"Player {player_name} not found")
                results['skipped'] += 1
                continue
            
            player_id = player_map[player_name]
            
            # Parse date
            try:
                date_obj = datetime.strptime(score_data['date'], '%Y-%m-%d').date()
            except:
                days_offset = wordle_num - ref_wordle
                date_obj = ref_date + timedelta(days=days_offset)
            
            # Parse timestamp
            try:
                timestamp_obj = datetime.strptime(score_data['timestamp'], '%Y-%m-%d %H:%M:%S')
            except:
                timestamp_obj = datetime.now()
            
            # Insert with individual error handling
            try:
                cursor.execute("""
                    INSERT INTO scores (player_id, wordle_number, score, date, emoji_pattern, timestamp)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (player_id, wordle_number) DO NOTHING
                """, (player_id, wordle_num, score, date_obj, score_data.get('emoji_pattern'), timestamp_obj))
                
                if cursor.rowcount > 0:
                    results['imported'] += 1
                    # Commit every 50
                    if results['imported'] % 50 == 0:
                        conn.commit()
                        logging.info(f"Committed {results['imported']} scores")
                else:
                    results['skipped'] += 1
            except Exception as insert_error:
                # Rollback this one insert and continue
                conn.rollback()
                results['errors'].append(f"Insert error on score {i} ({player_name}, W{wordle_num}): {str(insert_error)}")
                results['skipped'] += 1
                
        except Exception as e:
            results['errors'].append(f"Parse error on score {i}: {str(e)}")
            results['skipped'] += 1
    
    # Final commit
    conn.commit()
    cursor.close()
    conn.close()
    
    return results

if __name__ == "__main__":
    result = force_insert()
    print(json.dumps(result, indent=2))
