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
    
    # Embedded league data (from weekly_winners.json)
    league_data = {
        "name": "PAL",
        "current_season": 5,
        "season_winners": [
            {"season": 1, "name": "Vox", "weekly_wins": 3, "completed_date": "2025-09-15"},
            {"season": 2, "name": "Vox", "weekly_wins": 4, "completed_date": "2025-09-29"},
            {"season": 3, "name": "Vox", "weekly_wins": 4, "completed_date": "2025-10-27"},
            {"season": 4, "name": "Vox", "weekly_wins": 4, "completed_date": "2025-11-24"}
        ],
        "weekly_winners": {
            "1514": [{"name": "Vox", "score": 21}],
            "1521": [{"name": "Vox", "score": 18}],
            "1528": [{"name": "Vox", "score": 20}],
            "1535": [{"name": "Vox", "score": 17}],
            "1542": [{"name": "Vox", "score": 17}],
            "1549": [{"name": "Vox", "score": 22}],
            "1556": [{"name": "Vox", "score": 16}],
            "1563": [{"name": "Vox", "score": 17}],
            "1570": [{"name": "Vox", "score": 16}],
            "1577": [{"name": "Vox", "score": 19}],
            "1584": [{"name": "Vox", "score": 16}],
            "1591": [{"name": "Vox", "score": 19}],
            "1598": [{"name": "Vox", "score": 15}],
            "1605": [{"name": "Vox", "score": 18}],
            "1612": [{"name": "Vox", "score": 21}],
            "1619": [{"name": "Vox", "score": 19}]
        }
    }
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Step 1: Insert league
        logging.info("Inserting League 3 (PAL)...")
        cursor.execute("""
            INSERT INTO leagues (id, name)
            VALUES (3, 'PAL')
            ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name
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
            # Check if player already exists
            cursor.execute("""
                SELECT id FROM players WHERE name = %s AND league_id = 3
            """, (name,))
            existing = cursor.fetchone()
            
            if not existing:
                try:
                    cursor.execute("""
                        INSERT INTO players (name, phone_number, league_id)
                        VALUES (%s, %s, 3)
                    """, (name, phone))
                    logging.info(f"  Added player: {name}")
                except Exception as player_error:
                    logging.error(f"  Error adding player {name}: {player_error}")
                    raise
            else:
                logging.info(f"  Player already exists: {name}")
        
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
