#!/usr/bin/env python3
"""
Extract League 3 (PAL) data from legacy database
"""

import sqlite3
import json

# Path to legacy database
legacy_db_path = r'F:\Wordle-League\Wordle-League-Legacy-Scores\wordle_league.db'

# Connect to legacy database
conn = sqlite3.connect(legacy_db_path)
cursor = conn.cursor()

# Get League 3 players
cursor.execute("""
    SELECT id, name, phone_number
    FROM players
    WHERE league_id = 3
    ORDER BY name
""")

players = cursor.fetchall()
print("League 3 (PAL) Players:")
for p in players:
    print(f"  {p[1]}: {p[2]}")

# Get all League 3 scores
cursor.execute("""
    SELECT 
        p.name,
        s.wordle_number,
        s.score,
        s.date,
        s.emoji_pattern,
        s.timestamp
    FROM scores s
    JOIN players p ON s.player_id = p.id
    WHERE p.league_id = 3
    ORDER BY s.wordle_number, s.timestamp
""")

league3_scores = cursor.fetchall()
print(f"\nFound {len(league3_scores)} scores from League 3")

# Convert to list of dicts
all_scores = []
for score in league3_scores:
    all_scores.append({
        'player_name': score[0],
        'wordle_number': score[1],
        'score': score[2],
        'date': score[3],
        'emoji_pattern': score[4],
        'timestamp': score[5]
    })

# Save to JSON
output_file = 'league3_historical_scores.json'
with open(output_file, 'w') as f:
    json.dump(all_scores, f, indent=2)

print(f"\nSaved {len(all_scores)} scores to {output_file}")

# Show summary by player
player_counts = {}
for score in all_scores:
    player = score['player_name']
    player_counts[player] = player_counts.get(player, 0) + 1

print("\nScores per player:")
for player, count in sorted(player_counts.items()):
    print(f"  {player}: {count}")

cursor.close()
conn.close()
