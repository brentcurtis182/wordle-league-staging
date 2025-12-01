#!/usr/bin/env python3
"""
Check last week's scores to see who should have won
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from league_data_adapter import get_db_connection

def check_last_week(league_id):
    """Check last week's scores (Wordles 1619-1625, Nov 24-30)"""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    print(f"\n{'='*60}")
    print(f"League {league_id} - Last Week (Wordles 1619-1625)")
    print(f"{'='*60}")
    
    # Get all scores for last week
    cursor.execute("""
        SELECT 
            p.name,
            s.wordle_number,
            s.score,
            s.date
        FROM scores s
        JOIN players p ON s.player_id = p.id
        WHERE p.league_id = %s
          AND s.wordle_number >= 1619
          AND s.wordle_number <= 1625
        ORDER BY p.name, s.wordle_number
    """, (league_id,))
    
    scores_by_player = {}
    for row in cursor.fetchall():
        player_name = row[0]
        wordle_num = row[1]
        score = row[2]
        date = row[3]
        
        if player_name not in scores_by_player:
            scores_by_player[player_name] = []
        
        scores_by_player[player_name].append({
            'wordle': wordle_num,
            'score': score,
            'date': date
        })
    
    # Calculate best 5 for each player
    print("\nPlayer Scores:")
    print("-" * 60)
    
    eligible_players = {}
    
    for player_name, scores in sorted(scores_by_player.items()):
        valid_scores = [s['score'] for s in scores if s['score'] != 7]  # Exclude X/6
        valid_scores.sort()
        
        games_played = len(valid_scores)
        best_5 = valid_scores[:5] if games_played >= 5 else valid_scores
        best_5_total = sum(best_5)
        
        print(f"\n{player_name}:")
        print(f"  Games: {games_played}")
        print(f"  All scores: {valid_scores}")
        print(f"  Best 5: {best_5}")
        print(f"  Best 5 Total: {best_5_total}")
        
        if games_played >= 5:
            eligible_players[player_name] = best_5_total
    
    # Find winner
    if eligible_players:
        winner = min(eligible_players, key=eligible_players.get)
        winner_total = eligible_players[winner]
        
        print(f"\n{'='*60}")
        print(f"WINNER: {winner} with best 5 total of {winner_total}")
        print(f"{'='*60}")
    else:
        print(f"\n{'='*60}")
        print(f"NO ELIGIBLE PLAYERS (need 5 games)")
        print(f"{'='*60}")
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    print("Checking last week's scores from database...")
    
    check_last_week(6)  # League 6
    check_last_week(7)  # League 7
