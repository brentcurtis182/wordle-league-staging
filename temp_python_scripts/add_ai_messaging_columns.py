#!/usr/bin/env python3
"""
Migration script to add AI messaging toggle columns to leagues table
"""

import os
import psycopg2

def run_migration():
    """Add AI messaging toggle columns to leagues table"""
    
    database_url = os.environ.get('DATABASE_URL')
    if database_url:
        conn = psycopg2.connect(database_url)
    else:
        conn = psycopg2.connect(
            host=os.environ.get('PGHOST'),
            database=os.environ.get('PGDATABASE'),
            user=os.environ.get('PGUSER'),
            password=os.environ.get('PGPASSWORD'),
            port=os.environ.get('PGPORT', 5432)
        )
    
    cursor = conn.cursor()
    
    # Add 4 columns for AI messaging toggles
    # Default values match current behavior:
    # - perfect_score_congrats: FALSE (currently disabled)
    # - failure_roast: TRUE (currently active)
    # - sunday_race_update: TRUE (currently active)
    # - daily_loser_roast: FALSE (currently disabled)
    
    columns = [
        ("ai_perfect_score_congrats", "FALSE"),
        ("ai_failure_roast", "TRUE"),
        ("ai_sunday_race_update", "TRUE"),
        ("ai_daily_loser_roast", "FALSE")
    ]
    
    for col_name, default_val in columns:
        try:
            cursor.execute(f"""
                ALTER TABLE leagues 
                ADD COLUMN IF NOT EXISTS {col_name} BOOLEAN DEFAULT {default_val}
            """)
            print(f"Added column {col_name} with default {default_val}")
        except Exception as e:
            print(f"Column {col_name} may already exist: {e}")
            conn.rollback()
    
    conn.commit()
    
    # Verify columns exist
    cursor.execute("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'leagues' AND column_name LIKE 'ai_%'
    """)
    ai_columns = cursor.fetchall()
    print(f"\nAI messaging columns in leagues table: {[c[0] for c in ai_columns]}")
    
    # Show current values for all leagues
    cursor.execute("""
        SELECT id, display_name, ai_perfect_score_congrats, ai_failure_roast, 
               ai_sunday_race_update, ai_daily_loser_roast
        FROM leagues
        ORDER BY id
    """)
    print("\nCurrent AI messaging settings per league:")
    for row in cursor.fetchall():
        print(f"  League {row[0]} ({row[1]}): perfect={row[2]}, failure={row[3]}, sunday={row[4]}, daily_loser={row[5]}")
    
    cursor.close()
    conn.close()
    print("\nMigration complete!")

if __name__ == "__main__":
    run_migration()
