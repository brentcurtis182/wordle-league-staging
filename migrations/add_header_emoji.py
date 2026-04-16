#!/usr/bin/env python3
"""Add header_emoji column to leagues table for mascot feature.

NULL = no mascot, rendered as no header emoji.
Non-NULL = a single emoji string, rendered floating above the league title.

Idempotent — safe to re-run.

Usage:
    DATABASE_URL="<public_url>" python migrations/add_header_emoji.py
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
        ADD COLUMN IF NOT EXISTS header_emoji VARCHAR(16)
    """)
    print("Added column leagues.header_emoji (VARCHAR(16), nullable)")

    cur.execute("SELECT id, display_name, header_emoji FROM leagues ORDER BY id")
    rows = cur.fetchall()
    print(f"\nCurrent state ({len(rows)} leagues):")
    for league_id, name, emoji in rows:
        print(f"  {league_id:3d} {name!r:<30} header_emoji={emoji!r}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
