#!/usr/bin/env python3
"""Add twilio_numbers table and per-league number assignment.

Creates:
    twilio_numbers table     -- pool of Twilio phone numbers with status
    leagues.twilio_number_id -- FK to twilio_numbers, nullable

Seeds 4 numbers (1 legacy + 3 new) and backfills legacy leagues.

Idempotent -- safe to re-run.

Usage:
    DATABASE_URL="<public_url>" python migrations/add_twilio_numbers.py
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

    # 1. Create twilio_numbers table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS twilio_numbers (
            id SERIAL PRIMARY KEY,
            phone_number VARCHAR(20) NOT NULL UNIQUE,
            phone_display VARCHAR(20) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'active',
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    print("Created table twilio_numbers (if not exists)")

    # 2. Seed with all 4 numbers
    cur.execute("""
        INSERT INTO twilio_numbers (phone_number, phone_display, status) VALUES
            ('+18586666827', '(858) 666-6827', 'legacy'),
            ('+17606425815', '(760) 642-5815', 'active'),
            ('+17604215357', '(760) 421-5357', 'active'),
            ('+17604529850', '(760) 452-9850', 'active')
        ON CONFLICT (phone_number) DO NOTHING
    """)
    print("Seeded 4 phone numbers (legacy + 3 active)")

    # 3. Add twilio_number_id column to leagues
    cur.execute("""
        ALTER TABLE leagues
        ADD COLUMN IF NOT EXISTS twilio_number_id INTEGER REFERENCES twilio_numbers(id)
    """)
    print("Added column leagues.twilio_number_id (FK to twilio_numbers)")

    # 4. Backfill legacy leagues (IDs 1, 3, 4, 7, 8, 19)
    cur.execute("""
        UPDATE leagues
        SET twilio_number_id = (
            SELECT id FROM twilio_numbers WHERE phone_number = '+18586666827'
        )
        WHERE id IN (1, 3, 4, 7, 8, 19)
          AND twilio_number_id IS NULL
    """)
    print("Backfilled legacy leagues (1, 3, 4, 7, 8, 19) with legacy number")

    cur.close()
    conn.close()
    print("Migration complete.")


if __name__ == '__main__':
    main()
