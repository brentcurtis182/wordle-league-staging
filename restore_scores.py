#!/usr/bin/env python3
"""Restore deleted Wordle 1620 scores"""
from league_data_adapter import get_db_connection
from datetime import datetime, date, timedelta

# Wordle 1620 scores from Twilio
scores_to_restore = [
    # League 6 (no + prefix)
    ('17608156131', 'Rob', 6, 1620, 3, '🟨🟨⬜🟨⬜\n🟨🟨🟨🟩⬜\n🟩🟩🟩🟩🟩'),
    ('16503468822', 'Jason', 6, 1620, 3, '🟨🟨⬛🟨⬛\n⬛⬛🟨🟨🟨\n🟩🟩🟩🟩🟩'),
    ('17609082000', 'Matt', 6, 1620, 3, '⬜🟨⬜⬜⬜\n⬜⬜⬜⬜🟨\n🟩🟩🟩🟩🟩'),
    ('18587359353', 'Brent', 6, 1620, 2, '🟨⬛🟨⬛⬛\n🟩🟩🟩🟩🟩'),
    # League 7 (BellyUp)
    ('+18587359353', 'Brent', 7, 1620, 2, '🟨⬛🟨⬛⬛\n🟩🟩🟩🟩🟩'),
    ('+12675910330', 'Pete', 7, 1620, 3, '🟨🟩⬛🟨⬛\n⬛🟩🟩🟩⬛\n🟩🟩🟩🟩🟩'),
    ('+15134781947', 'Henry', 7, 1620, 3, '⬜⬜🟨⬜🟨\n⬜🟩⬜🟩⬜\n🟩🟩🟩🟩🟩'),
    ('+18587751124', 'Jeremy', 7, 1620, 3, '🟩🟨🟨⬛⬛\n🟩🟨⬛🟨⬛\n🟩🟩🟩🟩🟩'),
]

conn = get_db_connection()
cursor = conn.cursor()

# Calculate date for Wordle 1620
ref_date = date(2025, 7, 31)
ref_wordle = 1503
days_offset = 1620 - ref_wordle
wordle_date = ref_date + timedelta(days=days_offset)

print(f"Restoring scores for Wordle 1620 ({wordle_date})...")

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
    
    # Insert score (skip if already exists)
    try:
        cursor.execute("""
            INSERT INTO scores (player_id, wordle_number, score, date, emoji_pattern, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (player_id, wordle_number) DO NOTHING
        """, (player_id, wordle_num, score, wordle_date, emoji, datetime.now()))
        
        if cursor.rowcount > 0:
            print(f"  [OK] Restored {name}: {score}/6")
        else:
            print(f"  [SKIP] {name} already exists")
    except Exception as e:
        print(f"  [ERROR] Failed to restore {name}: {e}")

conn.commit()
cursor.close()
conn.close()

print("\nDone! Run trigger_update.ps1 to publish.")
