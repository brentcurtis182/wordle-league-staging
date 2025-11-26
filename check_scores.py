#!/usr/bin/env python3
"""Check what scores are in the database"""
from league_data_adapter import get_db_connection

conn = get_db_connection()
cursor = conn.cursor()

print("\n=== League 6 Recent Scores ===")
cursor.execute("""
    SELECT p.name, s.wordle_number, s.score 
    FROM scores s 
    JOIN players p ON s.player_id = p.id 
    WHERE p.league_id = 6 
    ORDER BY s.wordle_number DESC 
    LIMIT 10
""")
for row in cursor.fetchall():
    print(f"  {row[0]}: Wordle {row[1]} - {row[2]}/6")

print("\n=== League 7 Recent Scores ===")
cursor.execute("""
    SELECT p.name, s.wordle_number, s.score 
    FROM scores s 
    JOIN players p ON s.player_id = p.id 
    WHERE p.league_id = 7 
    ORDER BY s.wordle_number DESC 
    LIMIT 10
""")
for row in cursor.fetchall():
    print(f"  {row[0]}: Wordle {row[1]} - {row[2]}/6")

cursor.close()
conn.close()
