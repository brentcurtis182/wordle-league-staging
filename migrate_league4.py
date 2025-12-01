#!/usr/bin/env python3
"""
Migrate League 4 "Party" to cloud deployment
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from league_data_adapter import get_db_connection
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def migrate_league4():
    """Migrate League 4 with all historical data"""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Step 1: Create League 4
        logging.info("Creating League 4...")
        cursor.execute("""
            INSERT INTO leagues (id, name, display_name, twilio_conversation_sid, github_path)
            VALUES (4, 'party', 'Party', 'CHed74f2e9f16240e9a578f96299c395ce', 'party')
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                display_name = EXCLUDED.display_name,
                twilio_conversation_sid = EXCLUDED.twilio_conversation_sid,
                github_path = EXCLUDED.github_path
        """)
        
        # Step 2: Add all 9 players
        logging.info("Adding players...")
        players = [
            (4, 'Brent', '18587359353'),
            (4, 'Dustin', '19165416576'),
            (4, 'Jess', '17609082401'),
            (4, 'Matt', '17609082000'),
            (4, 'Meghan', '17606725317'),
            (4, 'Rob', '17608156131'),
            (4, 'Jason', '16503468822'),
            (4, 'Patty', '16198713458'),
            (4, 'Dani', '17609949392'),
        ]
        
        for league_id, name, phone in players:
            cursor.execute("""
                INSERT INTO players (league_id, name, phone_number)
                VALUES (%s, %s, %s)
                ON CONFLICT (league_id, name) DO UPDATE SET
                    phone_number = EXCLUDED.phone_number
            """, (league_id, name, phone))
            logging.info(f"  Added {name}")
        
        # Step 3: Set current season to 4
        logging.info("Setting current season to 4...")
        cursor.execute("""
            INSERT INTO league_seasons (league_id, current_season, season_start_week)
            VALUES (4, 4, 1626)
            ON CONFLICT (league_id) DO UPDATE SET
                current_season = EXCLUDED.current_season,
                season_start_week = EXCLUDED.season_start_week
        """)
        
        # Step 4: Import weekly winners (15 weeks)
        logging.info("Importing weekly winners...")
        weekly_winners = [
            (1514, 'Matt', 19),
            (1521, 'Brent', 18),
            (1528, 'Brent', 20),
            (1528, 'Jess', 20),
            (1535, 'Matt', 14),
            (1542, 'Brent', 17),
            (1542, 'Jess', 17),
            (1542, 'Matt', 17),
            (1549, 'Matt', 16),
            (1556, 'Brent', 16),
            (1563, 'Brent', 17),
            (1570, 'Brent', 16),
            (1577, 'Brent', 19),
            (1577, 'Matt', 19),
            (1584, 'Brent', 16),
            (1584, 'Matt', 16),
            (1591, 'Rob', 16),
            (1598, 'Rob', 14),
            (1605, 'Rob', 17),
            (1612, 'Matt', 18),
            (1612, 'Meghan', 18),
            (1619, 'Rob', 17),
        ]
        
        for week, player_name, score in weekly_winners:
            # Get player_id
            cursor.execute("SELECT id FROM players WHERE league_id = 4 AND name = %s", (player_name,))
            result = cursor.fetchone()
            if result:
                player_id = result[0]
                cursor.execute("""
                    INSERT INTO weekly_winners (league_id, week_wordle_number, player_id, player_name, score)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (league_id, week_wordle_number, player_id) DO UPDATE SET
                        score = EXCLUDED.score
                """, (4, week, player_id, player_name, score))
                logging.info(f"  Week {week}: {player_name} ({score})")
        
        # Step 5: Import season winners
        logging.info("Importing season winners...")
        season_winners = [
            (1, 'Brent', 4, '2025-09-15'),
            (2, 'Brent', 4, '2025-10-20'),
            (3, 'Rob', 4, '2025-12-01'),
        ]
        
        for season, player_name, wins, completed_date in season_winners:
            # Get player_id
            cursor.execute("SELECT id FROM players WHERE league_id = 4 AND name = %s", (player_name,))
            result = cursor.fetchone()
            if result:
                player_id = result[0]
                cursor.execute("""
                    INSERT INTO season_winners (league_id, season_number, player_id, wins, completed_date)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (league_id, season_number, player_id) DO UPDATE SET
                        wins = EXCLUDED.wins,
                        completed_date = EXCLUDED.completed_date
                """, (4, season, player_id, wins, completed_date))
                logging.info(f"  Season {season}: {player_name} ({wins} wins)")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logging.info("✅ League 4 migration completed successfully!")
        
        # Step 6: Generate HTML (separate from DB transaction)
        logging.info("Generating HTML...")
        try:
            from update_pipeline import run_update_pipeline
            success = run_update_pipeline(4)
            
            if success:
                logging.info("✅ HTML generated and published!")
            else:
                logging.error("❌ HTML generation failed")
        except Exception as html_error:
            logging.error(f"HTML generation error (non-fatal): {html_error}")
        
    except Exception as e:
        logging.error(f"Error during migration: {e}")
        import traceback
        traceback.print_exc()
        try:
            conn.rollback()
            cursor.close()
            conn.close()
        except:
            pass
        raise

if __name__ == "__main__":
    migrate_league4()
