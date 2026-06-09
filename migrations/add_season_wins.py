#!/usr/bin/env python3
"""Add per-league custom Season Wins (season-length) setting.

Adds:
    leagues.season_wins  -- nullable INTEGER, 2-6 when set.
                            NULL = use the mode default (4 regular / 3 division).

NULL is intentional: leaving it unset preserves the existing hardcoded
defaults, so no behavior changes for any existing league until a manager
explicitly picks a value.

Idempotent -- safe to re-run.

Usage:
    DATABASE_URL="<public_url>" python migrations/add_season_wins.py
"""
import os
import psycopg2


def main():
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise SystemExit("DATABASE_URL not set")

    conn = psycopg2.connect(database_url)
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute("""
        ALTER TABLE leagues
        ADD COLUMN IF NOT EXISTS season_wins INTEGER
    """)
    print("Added column leagues.season_wins (nullable; NULL = mode default)")

    cur.close()
    conn.close()
    print("Migration complete.")


if __name__ == '__main__':
    main()
