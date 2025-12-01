#!/usr/bin/env python3
"""
Create missing database tables for multi-league support
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from league_data_adapter import get_db_connection
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def create_tables():
    """Create leagues and league_seasons tables if they don't exist"""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Create leagues table
        logging.info("Creating leagues table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS leagues (
                id INTEGER PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                display_name VARCHAR(100) NOT NULL,
                twilio_conversation_sid VARCHAR(100),
                github_path VARCHAR(100)
            )
        """)
        
        # Create league_seasons table
        logging.info("Creating league_seasons table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS league_seasons (
                league_id INTEGER PRIMARY KEY REFERENCES leagues(id),
                current_season INTEGER NOT NULL,
                season_start_week INTEGER,
                season_end_week INTEGER
            )
        """)
        
        # Create season_winners table
        logging.info("Creating season_winners table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS season_winners (
                id SERIAL PRIMARY KEY,
                league_id INTEGER NOT NULL,
                season_number INTEGER NOT NULL,
                player_id INTEGER NOT NULL REFERENCES players(id),
                wins INTEGER NOT NULL,
                completed_date DATE,
                UNIQUE(league_id, season_number, player_id)
            )
        """)
        
        conn.commit()
        logging.info("✅ All tables created successfully!")
        
    except Exception as e:
        logging.error(f"Error creating tables: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    create_tables()
