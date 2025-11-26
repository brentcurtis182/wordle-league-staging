#!/usr/bin/env python3
"""
Season Management for Cloud Wordle League
Handles weekly winner tracking, season transitions, and season winner declarations
Ports logic from update_tables_preserve_structure.py to PostgreSQL
"""

import os
import logging
from datetime import datetime
from league_data_adapter import get_db_connection, calculate_wordle_number, get_week_start_date

# Constants
WINS_FOR_SEASON_VICTORY = 4  # Number of weekly wins needed to win a season

def create_weekly_winners_table():
    """Create weekly_winners table if it doesn't exist"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS weekly_winners (
            id SERIAL PRIMARY KEY,
            league_id INTEGER NOT NULL,
            week_wordle_number INTEGER NOT NULL,
            player_id INTEGER NOT NULL REFERENCES players(id),
            player_name VARCHAR(100) NOT NULL,
            score INTEGER NOT NULL,
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(league_id, week_wordle_number, player_id)
        )
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_weekly_winners_league_week 
        ON weekly_winners(league_id, week_wordle_number)
    """)
    
    conn.commit()
    cursor.close()
    conn.close()
    logging.info("weekly_winners table created/verified")

def create_league_seasons_table():
    """Create league_seasons table to track current season per league"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS league_seasons (
            league_id INTEGER PRIMARY KEY,
            current_season INTEGER DEFAULT 1,
            season_start_week INTEGER,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    cursor.close()
    conn.close()
    logging.info("league_seasons table created/verified")

def get_current_season(league_id):
    """Get the current season number for a league"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT current_season, season_start_week
        FROM league_seasons
        WHERE league_id = %s
    """, (league_id,))
    
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if result:
        return result[0], result[1]
    else:
        # Initialize season 1 for this league
        return initialize_league_season(league_id)

def initialize_league_season(league_id, season_number=1):
    """Initialize a league's season tracking"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get current week as season start
    current_week = calculate_wordle_number(get_week_start_date())
    
    cursor.execute("""
        INSERT INTO league_seasons (league_id, current_season, season_start_week)
        VALUES (%s, %s, %s)
        ON CONFLICT (league_id) DO UPDATE
        SET current_season = EXCLUDED.current_season,
            season_start_week = EXCLUDED.season_start_week,
            updated_at = CURRENT_TIMESTAMP
    """, (league_id, season_number, current_week))
    
    conn.commit()
    cursor.close()
    conn.close()
    
    logging.info(f"Initialized league {league_id} to season {season_number}, starting week {current_week}")
    return season_number, current_week

def save_weekly_winner(league_id, week_wordle_number, player_id, player_name, score):
    """
    Save a weekly winner to the database
    Handles ties (multiple winners in same week)
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO weekly_winners (league_id, week_wordle_number, player_id, player_name, score)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (league_id, week_wordle_number, player_id) DO UPDATE
        SET score = EXCLUDED.score,
            recorded_at = CURRENT_TIMESTAMP
    """, (league_id, week_wordle_number, player_id, player_name, score))
    
    conn.commit()
    cursor.close()
    conn.close()
    
    logging.info(f"Saved weekly winner: League {league_id}, Week {week_wordle_number}, {player_name} ({score})")

def get_weekly_wins_in_current_season(league_id):
    """
    Get weekly win counts for all players in the current season
    Returns: dict of {player_name: win_count}
    """
    current_season, season_start_week = get_current_season(league_id)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT player_name, COUNT(*) as wins
        FROM weekly_winners
        WHERE league_id = %s
          AND week_wordle_number >= %s
        GROUP BY player_name
        ORDER BY wins DESC
    """, (league_id, season_start_week))
    
    wins = {}
    for row in cursor.fetchall():
        wins[row[0]] = row[1]
    
    cursor.close()
    conn.close()
    
    return wins, current_season

def get_weekly_winner_details(league_id):
    """
    Get detailed weekly winner information for season table display
    Returns: dict of {player_name: {'wins': count, 'weeks': [week_nums]}}
    """
    current_season, season_start_week = get_current_season(league_id)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT player_name, week_wordle_number, score
        FROM weekly_winners
        WHERE league_id = %s
          AND week_wordle_number >= %s
        ORDER BY player_name, week_wordle_number
    """, (league_id, season_start_week))
    
    details = {}
    for row in cursor.fetchall():
        player_name = row[0]
        week_num = row[1]
        score = row[2]
        
        if player_name not in details:
            details[player_name] = {
                'wins': 0,
                'weeks': [],
                'scores': []
            }
        
        details[player_name]['wins'] += 1
        details[player_name]['weeks'].append(week_num)
        details[player_name]['scores'].append(score)
    
    cursor.close()
    conn.close()
    
    return details

def check_for_season_winner(league_id):
    """
    Check if any player has reached 4 weekly wins to win the season
    Returns: (winner_name, win_count) or (None, None)
    """
    wins, current_season = get_weekly_wins_in_current_season(league_id)
    
    # Find players with 4+ wins
    season_winners = [(name, count) for name, count in wins.items() if count >= WINS_FOR_SEASON_VICTORY]
    
    if not season_winners:
        return None, None
    
    # Sort by win count (highest first)
    season_winners.sort(key=lambda x: x[1], reverse=True)
    
    # Winner is the player with most wins
    winner_name = season_winners[0][0]
    win_count = season_winners[0][1]
    
    logging.info(f"Season {current_season} winner detected: {winner_name} with {win_count} wins")
    
    return winner_name, win_count

def record_season_winner(league_id, player_name, win_count):
    """Record a season winner and transition to next season"""
    current_season, _ = get_current_season(league_id)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get player_id
    cursor.execute("""
        SELECT id FROM players
        WHERE name = %s AND league_id = %s
    """, (player_name, league_id))
    
    player_result = cursor.fetchone()
    if not player_result:
        logging.error(f"Player {player_name} not found in league {league_id}")
        cursor.close()
        conn.close()
        return False
    
    player_id = player_result[0]
    
    # Check if already recorded
    cursor.execute("""
        SELECT id FROM season_winners
        WHERE league_id = %s AND season_number = %s AND player_id = %s
    """, (league_id, current_season, player_id))
    
    if cursor.fetchone():
        logging.info(f"Season winner already recorded: {player_name}, Season {current_season}")
        cursor.close()
        conn.close()
        return False
    
    # Record the season winner
    cursor.execute("""
        INSERT INTO season_winners (player_id, league_id, season_number, wins)
        VALUES (%s, %s, %s, %s)
    """, (player_id, league_id, current_season, win_count))
    
    conn.commit()
    
    logging.info(f"✅ SEASON WINNER RECORDED: {player_name} won Season {current_season} with {win_count} wins!")
    
    # Transition to next season
    next_season = current_season + 1
    current_week = calculate_wordle_number(get_week_start_date())
    next_season_start = current_week + 7  # Next Monday
    
    cursor.execute("""
        UPDATE league_seasons
        SET current_season = %s,
            season_start_week = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE league_id = %s
    """, (next_season, next_season_start, league_id))
    
    conn.commit()
    cursor.close()
    conn.close()
    
    logging.info(f"✅ SEASON TRANSITION: League {league_id} advanced to Season {next_season}, starting week {next_season_start}")
    
    return True

def get_season_winners(league_id):
    """Get all past season winners for a league"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            sw.season_number,
            p.name,
            sw.wins,
            sw.recorded_at
        FROM season_winners sw
        JOIN players p ON sw.player_id = p.id
        WHERE sw.league_id = %s
        ORDER BY sw.season_number DESC
    """, (league_id,))
    
    winners = []
    for row in cursor.fetchall():
        winners.append({
            'season': row[0],
            'name': row[1],
            'wins': row[2],
            'completed_date': row[3].strftime("%Y-%m-%d") if row[3] else None
        })
    
    cursor.close()
    conn.close()
    
    return winners

if __name__ == "__main__":
    # Test/setup
    logging.basicConfig(level=logging.INFO)
    
    print("Creating season management tables...")
    create_weekly_winners_table()
    create_league_seasons_table()
    
    print("\nInitializing League 6...")
    initialize_league_season(6, season_number=1)
    
    print("\nDone!")
