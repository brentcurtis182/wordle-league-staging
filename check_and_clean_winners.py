#!/usr/bin/env python3
"""
Check what's in weekly_winners table and clean up if needed
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from league_data_adapter import get_db_connection

def check_winners():
    """Check all weekly winners in database"""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    print(f"\n{'='*60}")
    print(f"ALL WEEKLY WINNERS IN DATABASE")
    print(f"{'='*60}")
    
    cursor.execute("""
        SELECT 
            ww.league_id,
            ww.week_wordle_number,
            ww.player_name,
            ww.score
        FROM weekly_winners ww
        ORDER BY ww.league_id, ww.week_wordle_number
    """)
    
    for row in cursor.fetchall():
        league_id = row[0]
        week = row[1]
        player = row[2]
        score = row[3]
        print(f"League {league_id}: Week {week} - {player} ({score})")
    
    print(f"\n{'='*60}")
    print("Do you want to delete ALL and start fresh? (y/n)")
    response = input().strip().lower()
    
    if response == 'y':
        cursor.execute("DELETE FROM weekly_winners")
        deleted = cursor.rowcount
        conn.commit()
        print(f"✅ Deleted {deleted} rows")
    else:
        print("No changes made")
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    check_winners()
