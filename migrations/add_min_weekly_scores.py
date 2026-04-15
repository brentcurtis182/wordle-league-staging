#!/usr/bin/env python3
"""
Migration: Add min_weekly_scores to leagues table.

Configurable per-league minimum number of scores required each week to
compete for the weekly win (and the "best N" total). Range 3-7, default 5.
"""

import os
import sys
import psycopg2
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

DATABASE_URL = os.environ.get('DATABASE_URL')

def run_migration():
    if not DATABASE_URL:
        logging.error("DATABASE_URL environment variable not set")
        sys.exit(1)

    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    try:
        logging.info("=== Add min_weekly_scores Migration ===")

        cursor.execute("""
            ALTER TABLE leagues
            ADD COLUMN IF NOT EXISTS min_weekly_scores INTEGER DEFAULT 5
        """)

        cursor.execute("""
            UPDATE leagues SET min_weekly_scores = 5 WHERE min_weekly_scores IS NULL
        """)

        cursor.execute("""
            ALTER TABLE leagues DROP CONSTRAINT IF EXISTS leagues_min_weekly_scores_range
        """)
        cursor.execute("""
            ALTER TABLE leagues
            ADD CONSTRAINT leagues_min_weekly_scores_range
            CHECK (min_weekly_scores BETWEEN 3 AND 7)
        """)

        conn.commit()

        cursor.execute("""
            SELECT id, name, min_weekly_scores FROM leagues ORDER BY id
        """)
        for row in cursor.fetchall():
            logging.info(f"  league {row[0]} '{row[1]}': min_weekly_scores = {row[2]}")

        logging.info("=== Migration Complete ===")

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
