#!/usr/bin/env python3
"""Add SMS opt-in columns to players and leagues tables.

players.sms_opt_in_status  VARCHAR(10) DEFAULT 'IN'  -- 'IN', 'OUT', 'WAITING'
players.opt_in_nudge_sent  BOOLEAN     DEFAULT FALSE -- one-time nudge guard
leagues.opt_in_welcome_sent BOOLEAN    DEFAULT FALSE -- one-time welcome guard

DEFAULT 'IN' grandfathers all existing players so nothing changes for them.

Idempotent -- safe to re-run.

Usage:
    DATABASE_URL="<public_url>" python migrations/add_sms_opt_in.py
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
        ALTER TABLE players
        ADD COLUMN IF NOT EXISTS sms_opt_in_status VARCHAR(10) DEFAULT 'IN'
    """)
    print("Added column players.sms_opt_in_status (VARCHAR(10), default 'IN')")

    cur.execute("""
        ALTER TABLE players
        ADD COLUMN IF NOT EXISTS opt_in_nudge_sent BOOLEAN DEFAULT FALSE
    """)
    print("Added column players.opt_in_nudge_sent (BOOLEAN, default FALSE)")

    cur.execute("""
        ALTER TABLE leagues
        ADD COLUMN IF NOT EXISTS opt_in_welcome_sent BOOLEAN DEFAULT FALSE
    """)
    print("Added column leagues.opt_in_welcome_sent (BOOLEAN, default FALSE)")

    cur.execute("""
        SELECT p.id, p.name, l.display_name, p.sms_opt_in_status, p.opt_in_nudge_sent
        FROM players p
        JOIN leagues l ON p.league_id = l.id
        WHERE p.active = TRUE
        ORDER BY l.id, p.name
    """)
    rows = cur.fetchall()
    print(f"\nCurrent state ({len(rows)} active players):")
    for pid, pname, lname, status, nudge in rows:
        print(f"  {pid:4d} {lname:<25} {pname:<20} opt_in={status!r}  nudge_sent={nudge}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
