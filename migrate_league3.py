#!/usr/bin/env python3
"""
Migrate League 3 (PAL) to cloud database
"""

import os
import sys
import json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from league_data_adapter import get_db_connection
from datetime import datetime, date, timedelta
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def migrate_league3():
    """Migrate League 3 (PAL)"""
    
    # Load weekly winners data
    with open(r'F:\Wordle-League\Wordle-League-Legacy-Scores\weekly_winners.json', 'r') as f:
        data = json.load(f)
    
    league_data = data['leagues']['3']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Step 1: Insert league
        logging.info("Inserting League 3 (PAL)...")
        cursor.execute("""
            INSERT INTO leagues (id, name, github_pages_url, twilio_conversation_sid)
            VALUES (3, 'PAL', 'https://brentcurtis182.github.io/wordle-league/pal/', 'CHc8f0c4a776f14bcd96e7c8838a6aec13')
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                github_pages_url = EXCLUDED.github_pages_url,
                twilio_conversation_sid = EXCLUDED.twilio_conversation_sid
        """)
        
        # Step 2: Insert players
        logging.info("Inserting players...")
        players = [
            ('Vox', '18587359353'),
            ('Fuzwuz', '17604206113'),
            ('Pants', '17605830059'),
            ('Starslider', '14698345364')
        ]
        
        for name, phone in players:
            cursor.execute("""
                INSERT INTO players (name, phone_number, league_id)
                VALUES (%s, %s, 3)
                ON CONFLICT DO NOTHING
            """, (name, phone))
            logging.info(f"  Added player: {name}")
        
        # Step 3: Insert current season (Season 5, started week 1619)
        logging.info("Inserting current season...")
        cursor.execute("""
            INSERT INTO league_seasons (league_id, season_number, season_start_week)
            VALUES (3, 5, 1619)
            ON CONFLICT DO NOTHING
        """)
        
        # Step 4: Insert weekly winners
        logging.info("Inserting weekly winners...")
        weekly_winners = league_data['weekly_winners']
        
        for week_str, winners in weekly_winners.items():
            week_num = int(week_str)
            for winner in winners:
                cursor.execute("""
                    INSERT INTO weekly_winners (league_id, wordle_week, player_name, score)
                    VALUES (3, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (week_num, winner['name'], winner['score']))
        
        logging.info(f"  Inserted {len(weekly_winners)} weekly winners")
        
        # Step 5: Insert season winners
        logging.info("Inserting season winners...")
        season_winners = league_data['season_winners']
        
        for sw in season_winners:
            cursor.execute("""
                INSERT INTO season_winners (league_id, season_number, player_name, weekly_wins, completed_date)
                VALUES (3, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (sw['season'], sw['name'], sw['weekly_wins'], sw['completed_date']))
            logging.info(f"  Season {sw['season']}: {sw['name']}")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logging.info("✅ League 3 migration completed successfully!")
        return True
        
    except Exception as e:
        logging.error(f"Error during migration: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        return False

if __name__ == "__main__":
    migrate_league3()
