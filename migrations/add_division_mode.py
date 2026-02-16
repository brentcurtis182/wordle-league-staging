#!/usr/bin/env python3
"""
Migration: Add Division Mode support
Adds columns and tables needed for Division Mode feature.

Division Mode splits a league into 2 divisions (Division I / Division II)
with independent seasons, promotion/relegation, and separate weekly winners.
"""

import os
import sys
import psycopg2
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://postgres:ueTOlkosGwQVKoNOxuMudAZrLQltHrfS@yamanote.proxy.rlwy.net:11242/railway')

def run_migration():
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    try:
        logging.info("=== Division Mode Migration ===\n")
        
        # -------------------------------------------------------
        # 1. Add division_mode columns to leagues table
        # -------------------------------------------------------
        logging.info("Step 1: Adding division columns to leagues table...")
        
        # division_mode: whether division mode is currently active
        cursor.execute("""
            ALTER TABLE leagues ADD COLUMN IF NOT EXISTS division_mode BOOLEAN DEFAULT FALSE
        """)
        
        # division_confirmed_at: when division mode was confirmed (NULL = not yet confirmed / in setup)
        cursor.execute("""
            ALTER TABLE leagues ADD COLUMN IF NOT EXISTS division_confirmed_at TIMESTAMP
        """)
        
        # division_locked: set to TRUE once a weekly winner is recorded under division mode
        # After this point, division mode cannot be reverted without a season reset
        cursor.execute("""
            ALTER TABLE leagues ADD COLUMN IF NOT EXISTS division_locked BOOLEAN DEFAULT FALSE
        """)
        
        logging.info("  Added: division_mode, division_confirmed_at, division_locked")
        
        # -------------------------------------------------------
        # 2. Add division columns to players table
        # -------------------------------------------------------
        logging.info("Step 2: Adding division columns to players table...")
        
        # division: NULL = no division mode, 1 = Division I, 2 = Division II
        cursor.execute("""
            ALTER TABLE players ADD COLUMN IF NOT EXISTS division INTEGER
        """)
        
        # division_immunity: player was recently promoted/relegated and is immune from relegation
        cursor.execute("""
            ALTER TABLE players ADD COLUMN IF NOT EXISTS division_immunity BOOLEAN DEFAULT FALSE
        """)
        
        # division_joined_week: wordle number of the week the player joined their current division
        # Used to determine if Season Total should show "Immune" or a real value
        cursor.execute("""
            ALTER TABLE players ADD COLUMN IF NOT EXISTS division_joined_week INTEGER
        """)
        
        logging.info("  Added: division, division_immunity, division_joined_week")
        
        # -------------------------------------------------------
        # 3. Add division column to weekly_winners table
        # -------------------------------------------------------
        logging.info("Step 3: Adding division column to weekly_winners table...")
        
        # division: NULL = pre-division / no division mode, 1 = Division I, 2 = Division II
        cursor.execute("""
            ALTER TABLE weekly_winners ADD COLUMN IF NOT EXISTS division INTEGER
        """)
        
        logging.info("  Added: weekly_winners.division")
        
        # -------------------------------------------------------
        # 4. Add division column to season_winners table
        # -------------------------------------------------------
        logging.info("Step 4: Adding division column to season_winners table...")
        
        # division: NULL = pre-division / no division mode, 1 = Division I, 2 = Division II
        cursor.execute("""
            ALTER TABLE season_winners ADD COLUMN IF NOT EXISTS division INTEGER
        """)
        
        logging.info("  Added: season_winners.division")
        
        # -------------------------------------------------------
        # 5. Create division_seasons table
        # -------------------------------------------------------
        logging.info("Step 5: Creating division_seasons table...")
        
        # Tracks current season and season boundaries per division per league
        # This is the division-specific equivalent of league_seasons + seasons
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS division_seasons (
                id SERIAL PRIMARY KEY,
                league_id INTEGER NOT NULL REFERENCES leagues(id),
                division INTEGER NOT NULL,
                current_season INTEGER NOT NULL DEFAULT 1,
                season_start_week INTEGER,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(league_id, division)
            )
        """)
        
        logging.info("  Created: division_seasons (league_id, division, current_season, season_start_week)")
        
        # -------------------------------------------------------
        # 6. Create division_season_boundaries table
        # -------------------------------------------------------
        logging.info("Step 6: Creating division_season_boundaries table...")
        
        # Tracks start/end week for each season in each division
        # This is the division-specific equivalent of the seasons table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS division_season_boundaries (
                id SERIAL PRIMARY KEY,
                league_id INTEGER NOT NULL REFERENCES leagues(id),
                division INTEGER NOT NULL,
                season_number INTEGER NOT NULL,
                start_week INTEGER,
                end_week INTEGER,
                UNIQUE(league_id, division, season_number)
            )
        """)
        
        logging.info("  Created: division_season_boundaries (league_id, division, season_number, start_week, end_week)")
        
        # -------------------------------------------------------
        # 7. Create division_snapshots table for undo/revert
        # -------------------------------------------------------
        logging.info("Step 7: Creating division_snapshots table...")
        
        # Stores a snapshot of the pre-division state so we can revert
        # if division mode is turned off before it's locked
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS division_snapshots (
                id SERIAL PRIMARY KEY,
                league_id INTEGER NOT NULL REFERENCES leagues(id),
                snapshot_type VARCHAR(50) NOT NULL,
                snapshot_data JSONB NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(league_id, snapshot_type)
            )
        """)
        
        logging.info("  Created: division_snapshots (league_id, snapshot_type, snapshot_data)")
        
        # -------------------------------------------------------
        # 8. Add indexes for performance
        # -------------------------------------------------------
        logging.info("Step 8: Adding indexes...")
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_players_division 
            ON players(league_id, division) WHERE division IS NOT NULL
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_weekly_winners_division 
            ON weekly_winners(league_id, division) WHERE division IS NOT NULL
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_season_winners_division 
            ON season_winners(league_id, division) WHERE division IS NOT NULL
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_division_seasons_league 
            ON division_seasons(league_id, division)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_division_boundaries_league 
            ON division_season_boundaries(league_id, division, season_number)
        """)
        
        logging.info("  Added 5 indexes")
        
        # -------------------------------------------------------
        # Commit
        # -------------------------------------------------------
        conn.commit()
        
        logging.info("\n=== Migration Complete ===")
        logging.info("New columns: leagues(division_mode, division_confirmed_at, division_locked)")
        logging.info("New columns: players(division, division_immunity, division_joined_week)")
        logging.info("New columns: weekly_winners(division), season_winners(division)")
        logging.info("New tables: division_seasons, division_season_boundaries, division_snapshots")
        
        # -------------------------------------------------------
        # Verify
        # -------------------------------------------------------
        logging.info("\n=== Verification ===")
        
        cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'leagues' AND column_name LIKE 'division%' ORDER BY column_name")
        league_cols = [r[0] for r in cursor.fetchall()]
        logging.info(f"leagues division columns: {league_cols}")
        
        cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'players' AND column_name LIKE 'division%' ORDER BY column_name")
        player_cols = [r[0] for r in cursor.fetchall()]
        logging.info(f"players division columns: {player_cols}")
        
        cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'weekly_winners' AND column_name = 'division'")
        logging.info(f"weekly_winners.division: {'exists' if cursor.fetchone() else 'MISSING'}")
        
        cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'season_winners' AND column_name = 'division'")
        logging.info(f"season_winners.division: {'exists' if cursor.fetchone() else 'MISSING'}")
        
        for table in ['division_seasons', 'division_season_boundaries', 'division_snapshots']:
            cursor.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = %s)", (table,))
            exists = cursor.fetchone()[0]
            logging.info(f"{table}: {'exists' if exists else 'MISSING'}")
        
    except Exception as e:
        conn.rollback()
        logging.error(f"Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    run_migration()
