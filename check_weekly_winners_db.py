#!/usr/bin/env python3
"""
Check what's in the weekly_winners table
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from league_data_adapter import get_db_connection

def check_weekly_winners():
    """Check weekly_winners table"""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    print(f"\n{'='*60}")
    print(f"WEEKLY WINNERS TABLE")
    print(f"{'='*60}")
    
    cursor.execute("""
        SELECT 
            ww.league_id,
            ww.week_start_wordle,
            ww.week_end_wordle,
            p.name,
            ww.best_5_total,
            ww.week_start_date
        FROM weekly_winners ww
        JOIN players p ON ww.player_id = p.id
        ORDER BY ww.league_id, ww.week_start_wordle DESC
        LIMIT 20
    """)
    
    for row in cursor.fetchall():
        league_id = row[0]
        week_start = row[1]
        week_end = row[2]
        player_name = row[3]
        total = row[4]
        date = row[5]
        
        print(f"League {league_id}: Week {week_start}-{week_end} ({date}) - {player_name} with {total}")
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    check_weekly_winners()
