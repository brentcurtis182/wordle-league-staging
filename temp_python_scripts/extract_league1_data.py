#!/usr/bin/env python3
"""
Extract League 1 historical scores from legacy database to JSON
"""

import sqlite3
import json

# Path to legacy database
legacy_db_path = r'F:\Wordle-League\Wordle-League-Legacy-Scores\wordle_league.db'

# Connect to legacy database
conn = sqlite3.connect(legacy_db_path)
cursor = conn.cursor()

# Get all League 1 scores
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
    WHERE p.league_id = 1
    ORDER BY s.wordle_number, s.timestamp
""")

league1_scores = cursor.fetchall()
print(f"Found {len(league1_scores)} scores from League 1")

# Convert to list of dicts
all_scores = []
for score in league1_scores:
    all_scores.append({
        'player_name': score[0],
        'wordle_number': score[1],
        'score': score[2],
        'date': score[3],
        'emoji_pattern': score[4],
        'timestamp': score[5]
    })

# Save to JSON
output_file = 'league1_historical_scores.json'
with open(output_file, 'w') as f:
    json.dump(all_scores, f, indent=2)

print(f"\nSaved {len(all_scores)} scores to {output_file}")
print(f"\nTotal scores: {len(all_scores)}")

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
