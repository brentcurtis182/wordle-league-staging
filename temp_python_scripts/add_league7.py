#!/usr/bin/env python3
"""
Add League 7 (BellyUp) to the database
"""

import os
from league_data_adapter import get_db_connection

def add_league_7():
    """Add BellyUp league and players"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    league_id = 7
    league_name = "BellyUp"
    
    players = [
        ("Brent", "+18587359353"),
        ("Jeremy", "+18587751124"),
        ("Henry", "+15134781947"),
        ("Mikaila", "+19285812935"),
        ("Pete", "+12675910330"),
        ("Meredith", "+16032546373")
    ]
    
    try:
        print(f"Adding League {league_id}: {league_name}")
        
        for name, phone in players:
            # Check if player already exists
            cursor.execute("""
                SELECT id FROM players 
                WHERE name = %s AND league_id = %s
            """, (name, league_id))
            
            if cursor.fetchone():
                print(f"  [SKIP] {name} already exists")
                continue
            
            # Insert player
            cursor.execute("""
                INSERT INTO players (name, phone_number, league_id)
                VALUES (%s, %s, %s)
            """, (name, phone, league_id))
            
            print(f"  [OK] Added {name} ({phone})")
        
        # Initialize league season
        cursor.execute("""
            INSERT INTO league_seasons (league_id, current_season, season_start_week)
            VALUES (%s, 1, 1619)
            ON CONFLICT (league_id) DO NOTHING
        """, (league_id,))
        
        conn.commit()
        print(f"\n[SUCCESS] League {league_id} ({league_name}) added!")
        print(f"   Players: {len(players)}")
        
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] {e}")
        raise
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    add_league_7()
