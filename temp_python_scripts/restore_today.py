#!/usr/bin/env python3
"""Restore today's scores from Twilio logs"""
from league_data_adapter import get_db_connection
from datetime import datetime, date, timedelta

# Wordle 1621 scores from Twilio logs
scores_to_restore = [
    # League 6
    ('16503468822', 'Jason', 6, 1621, 5, '⬛🟨⬛⬛🟨\n⬛⬛⬛🟩🟩\n⬛⬛🟩🟩🟩\n⬛🟩🟩🟩🟩\n🟩🟩🟩🟩🟩'),
    ('18587359353', 'Brent', 6, 1621, 5, '⬛🟨⬛⬛🟨\n⬛⬛⬛🟩🟩\n⬛⬛🟩🟩🟩\n⬛🟩🟩🟩🟩\n🟩🟩🟩🟩🟩'),
    ('17608156131', 'Rob', 6, 1621, 4, '⬜🟨⬜🟩⬜\n⬜⬜🟨🟩⬜\n🟩⬜⬜🟩🟩\n🟩🟩🟩🟩🟩'),
    # League 7
    ('+15134781947', 'Henry', 7, 1621, 4, '⬜⬜⬜⬜🟩\n⬜⬜🟨⬜🟩\n⬜🟩⬜🟩🟩\n🟩🟩🟩🟩🟩'),
]

conn = get_db_connection()
cursor = conn.cursor()

# Calculate date for Wordle 1621
ref_date = date(2025, 7, 31)
ref_wordle = 1503
days_offset = 1621 - ref_wordle
wordle_date = ref_date + timedelta(days=days_offset)

print(f"Restoring scores for Wordle 1621 ({wordle_date})...")

for phone, name, league_id, wordle_num, score, emoji in scores_to_restore:
    # Get player ID
    cursor.execute("""
        SELECT id FROM players 
        WHERE phone_number = %s AND league_id = %s
    """, (phone, league_id))
    
    result = cursor.fetchone()
    if not result:
        print(f"  [ERROR] Player not found: {name} ({phone})")
        continue
    
    player_id = result[0]
    
    # Insert into scores table
    try:
        cursor.execute("""
            INSERT INTO scores (player_id, wordle_number, score, date, emoji_pattern, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (player_id, wordle_number) DO NOTHING
        """, (player_id, wordle_num, score, wordle_date, emoji, datetime.now()))
        
        if cursor.rowcount > 0:
            print(f"  [OK] Restored {name}: {score}/6 to scores table")
        else:
            print(f"  [SKIP] {name} already in scores table")
    except Exception as e:
        print(f"  [ERROR] Failed to restore {name} to scores: {e}")
    
    # Insert into latest_scores table (delete first if exists)
    try:
        cursor.execute("""
            DELETE FROM latest_scores WHERE player_id = %s AND wordle_number = %s
        """, (player_id, wordle_num))
        
        cursor.execute("""
            INSERT INTO latest_scores (player_id, league_id, wordle_number, score, emoji_pattern, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (player_id, league_id, wordle_num, score, emoji, datetime.now()))
        
        if cursor.rowcount > 0:
            print(f"  [OK] Restored {name}: {score}/6 to latest_scores table")
        else:
            print(f"  [SKIP] {name} already in latest_scores table")
    except Exception as e:
        print(f"  [ERROR] Failed to restore {name} to latest_scores: {e}")

conn.commit()
cursor.close()
conn.close()

print("\nDone! Triggering update...")

# Trigger update
import subprocess
subprocess.run([
    "powershell", "-Command",
    "Invoke-WebRequest -Uri 'https://wordle-league-production.up.railway.app/daily-reset' -Method POST"
])
