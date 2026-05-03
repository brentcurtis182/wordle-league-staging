"""
Fix: New players added to division-mode leagues mid-season need immunity.

Previously, the add-player code set division but not division_immunity or
division_joined_week. This left new players eligible for relegation despite
having no history in the division.

This script finds affected players and grants them immunity with today's
wordle number as their joined_week. Safe to re-run (only touches players
with NULL division_joined_week).
"""

import os
import psycopg2
from datetime import date

def get_db_connection():
    database_url = os.environ.get('DATABASE_URL')
    if database_url:
        return psycopg2.connect(database_url, connect_timeout=10)
    else:
        return psycopg2.connect(
            host=os.environ.get('PGHOST'),
            database=os.environ.get('PGDATABASE'),
            user=os.environ.get('PGUSER'),
            password=os.environ.get('PGPASSWORD'),
            port=os.environ.get('PGPORT', 5432),
            connect_timeout=10
        )

def get_todays_wordle_number():
    ref_date = date(2025, 7, 31)
    ref_wordle = 1503
    days_since_ref = (date.today() - ref_date).days
    return ref_wordle + days_since_ref

def main():
    conn = get_db_connection()
    cursor = conn.cursor()

    current_week = get_todays_wordle_number()
    print(f"Today's wordle number: {current_week}")

    # Find players in division-mode leagues who have a division assigned
    # but no division_joined_week (meaning they were added without immunity)
    cursor.execute("""
        SELECT p.id, p.name, p.league_id, p.division, l.name as league_name
        FROM players p
        JOIN leagues l ON l.id = p.league_id
        WHERE p.division IS NOT NULL
          AND p.active = TRUE
          AND p.division_joined_week IS NULL
          AND l.division_mode = TRUE
    """)

    affected = cursor.fetchall()

    if not affected:
        print("No affected players found. All division players already have joined_week set.")
        cursor.close()
        conn.close()
        return

    print(f"\nFound {len(affected)} player(s) missing immunity/joined_week:")
    for player_id, name, league_id, division, league_name in affected:
        print(f"  - {name} (id={player_id}) in {league_name} (league {league_id}), Division {'I' if division == 1 else 'II'}")

    # Set immunity and joined_week for all affected players
    cursor.execute("""
        UPDATE players
        SET division_immunity = TRUE, division_joined_week = %s
        WHERE division IS NOT NULL
          AND active = TRUE
          AND division_joined_week IS NULL
          AND league_id IN (SELECT id FROM leagues WHERE division_mode = TRUE)
    """, (current_week,))

    updated = cursor.rowcount
    conn.commit()

    print(f"\nFixed {updated} player(s) - set division_immunity=TRUE, division_joined_week={current_week}")
    print("These players will be exempt from relegation until their first full season completes.")

    cursor.close()
    conn.close()

if __name__ == '__main__':
    main()
