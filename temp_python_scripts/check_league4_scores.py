#!/usr/bin/env python3
"""
Check if League 4 scores are being saved
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from league_data_adapter import get_db_connection

def check_scores():
    """Check League 4 scores"""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    print(f"\n{'='*60}")
    print(f"LEAGUE 4 SCORES IN DATABASE")
    print(f"{'='*60}")
    
    # Check latest_scores
    cursor.execute("""
        SELECT player_name, wordle_number, score, timestamp
        FROM latest_scores
        WHERE league_id = 4
        ORDER BY timestamp DESC
    """)
    
    rows = cursor.fetchall()
    if rows:
        print(f"\nLatest Scores ({len(rows)} found):")
        for row in rows:
            print(f"  {row[0]}: Wordle {row[1]} - {row[2]} (at {row[3]})")
    else:
        print("\n❌ No scores found in latest_scores for League 4")
    
    # Check scores table
    cursor.execute("""
        SELECT player_name, wordle_number, score, timestamp
        FROM scores
        WHERE league_id = 4
        ORDER BY timestamp DESC
        LIMIT 10
    """)
    
    rows = cursor.fetchall()
    if rows:
        print(f"\nPermanent Scores ({len(rows)} found):")
        for row in rows:
            print(f"  {row[0]}: Wordle {row[1]} - {row[2]} (at {row[3]})")
    else:
        print("\n❌ No scores found in scores table for League 4")
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    check_scores()
