#!/usr/bin/env python3
"""
Migrate League 1 "Warriorz" to cloud deployment
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from league_data_adapter import get_db_connection
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def migrate_league1():
    """Migrate League 1 with all historical data"""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Step 1: Create League 1
        logging.info("Creating League 1...")
        cursor.execute("""
            INSERT INTO leagues (id, name, display_name, twilio_conversation_sid, github_path)
            VALUES (1, 'warriorz', 'Warriorz', 'CHb7aa3110769f42a19cea7a2be9c644d2', '')
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                display_name = EXCLUDED.display_name,
                twilio_conversation_sid = EXCLUDED.twilio_conversation_sid,
                github_path = EXCLUDED.github_path
        """)
        
        # Step 2: Add all 5 players
        logging.info("Adding players...")
        players = [
            (1, 'Brent', '18587359353'),
            (1, 'Malia', '17603341190'),
            (1, 'Evan', '17608462302'),
            (1, 'Joanna', '13109263555'),
            (1, 'Nanna', '19492304472'),
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
            VALUES (1, 4, 1612)
            ON CONFLICT (league_id) DO UPDATE SET
                current_season = EXCLUDED.current_season,
                season_start_week = EXCLUDED.season_start_week
        """)
        
        # Step 4: Import weekly winners (15 weeks)
        logging.info("Importing weekly winners...")
        weekly_winners = [
            (1514, 'Joanna', 17),
            (1521, 'Joanna', 17),
            (1528, 'Joanna', 15),
            (1535, 'Joanna', 14),
            (1542, 'Malia', 16),
            (1549, 'Joanna', 14),
            (1556, 'Joanna', 15),
            (1563, 'Joanna', 16),
            (1570, 'Brent', 16),
            (1577, 'Joanna', 16),
            (1584, 'Brent', 16),
            (1584, 'Joanna', 16),
            (1591, 'Joanna', 17),
            (1598, 'Brent', 15),
            (1605, 'Brent', 18),
            (1612, 'Joanna', 17),
            (1612, 'Nanna', 17),
            (1619, 'Nanna', 18),
        ]
        
        for week, player_name, score in weekly_winners:
            # Get player_id
            cursor.execute("SELECT id FROM players WHERE league_id = 1 AND name = %s", (player_name,))
            result = cursor.fetchone()
            if result:
                player_id = result[0]
                cursor.execute("""
                    INSERT INTO weekly_winners (league_id, week_wordle_number, player_id, player_name, score)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (league_id, week_wordle_number, player_id) DO UPDATE SET
                        score = EXCLUDED.score
                """, (1, week, player_id, player_name, score))
                logging.info(f"  Week {week}: {player_name} ({score})")
        
        # Step 5: Import season winners
        logging.info("Importing season winners...")
        season_winners = [
            (1, 'Joanna', 3, '2025-09-15'),
            (2, 'Joanna', 4, '2025-09-29'),
            (3, 'Brent', 4, '2025-11-17'),
        ]
        
        for season, player_name, wins, completed_date in season_winners:
            # Get player_id
            cursor.execute("SELECT id FROM players WHERE league_id = 1 AND name = %s", (player_name,))
            result = cursor.fetchone()
            if result:
                player_id = result[0]
                cursor.execute("""
                    INSERT INTO season_winners (league_id, season_number, player_id, wins, completed_date)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (league_id, season_number, player_id) DO UPDATE SET
                        wins = EXCLUDED.wins,
                        completed_date = EXCLUDED.completed_date
                """, (1, season, player_id, wins, completed_date))
                logging.info(f"  Season {season}: {player_name} ({wins} wins)")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logging.info("✅ League 1 migration completed successfully!")
        
        # Step 6: Generate HTML
        logging.info("Generating HTML...")
        try:
            from update_pipeline import run_update_pipeline
            result = run_update_pipeline(1)
            
            if result.get('success'):
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
    migrate_league1()
