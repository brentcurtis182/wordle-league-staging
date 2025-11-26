#!/usr/bin/env python3
"""
Cloud version of update_tables_preserve_structure.py
Uses PostgreSQL instead of SQLite and weekly_winners table instead of JSON
Maintains all the proven business logic from the original script
"""

import os
import sys
import logging
from datetime import datetime, timedelta

# Add parent directory to path to import original functions
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the weekly winners adapter
from weekly_winners_adapter import load_weekly_winners, save_weekly_winners
from league_data_adapter import get_db_connection, calculate_wordle_number, get_week_start_date

# Import core functions from original script
from update_tables_preserve_structure import (
    check_for_season_winners,
    WINS_FOR_SEASON_VICTORY,
    MIN_GAMES_REQUIRED
)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

def update_weekly_winners_from_db(league_id):
    """
    Calculate and save weekly winners for a league
    This is the cloud version of update_weekly_winners_json()
    """
    logging.info(f"Updating weekly winners for league {league_id}")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Load current winners data
        winners_data = load_weekly_winners()
        
        league_key = str(league_id)
        if league_key not in winners_data['leagues']:
            winners_data['leagues'][league_key] = {
                'name': f'League {league_id}',
                'current_season': 1,
                'weekly_winners': {},
                'season_winners': [],
                'seasons': {}
            }
        
        league_info = winners_data['leagues'][league_key]
        
        # Get current season info
        cursor.execute("""
            SELECT current_season, season_start_week
            FROM league_seasons
            WHERE league_id = %s
        """, (league_id,))
        
        season_result = cursor.fetchone()
        current_season = season_result[0] if season_result else 1
        season_start_week = season_result[1] if season_result else None
        
        # Get all weeks since season start (or all time if no season start)
        if season_start_week:
            min_wordle = season_start_week
        else:
            min_wordle = 1507  # OFFICIAL_SEASON_START
        
        # Get all Monday dates (week starts) that have scores
        cursor.execute("""
            SELECT DISTINCT 
                DATE_TRUNC('week', date + INTERVAL '1 day')::date - INTERVAL '1 day' as monday_date,
                MIN(wordle_number) as week_wordle
            FROM scores s
            JOIN players p ON s.player_id = p.id
            WHERE p.league_id = %s
              AND s.wordle_number >= %s
            GROUP BY monday_date
            ORDER BY monday_date
        """, (league_id, min_wordle))
        
        weeks = cursor.fetchall()
        
        for week_row in weeks:
            monday_date = week_row[0]
            week_wordle = week_row[1]
            
            # Calculate week range (Monday to Sunday)
            sunday_date = monday_date + timedelta(days=6)
            
            # Get all scores for this week
            cursor.execute("""
                SELECT 
                    p.id,
                    p.name,
                    s.score,
                    s.wordle_number
                FROM scores s
                JOIN players p ON s.player_id = p.id
                WHERE p.league_id = %s
                  AND s.date >= %s
                  AND s.date <= %s
                  AND s.score != 7  -- Exclude failed attempts
                ORDER BY p.name, s.score
            """, (league_id, monday_date, sunday_date))
            
            # Group scores by player
            player_scores = {}
            for row in cursor.fetchall():
                player_id = row[0]
                player_name = row[1]
                score = row[2]
                wordle_num = row[3]
                
                if player_name not in player_scores:
                    player_scores[player_name] = {
                        'player_id': player_id,
                        'scores': []
                    }
                
                player_scores[player_name]['scores'].append(score)
            
            # Calculate best 5 totals for eligible players (5+ games)
            eligible_players = {}
            for player_name, data in player_scores.items():
                scores = sorted(data['scores'])  # Sort ascending (best first)
                
                if len(scores) >= MIN_GAMES_REQUIRED:
                    best_5_total = sum(scores[:5])
                    eligible_players[player_name] = {
                        'player_id': data['player_id'],
                        'total': best_5_total,
                        'games': len(scores)
                    }
            
            if not eligible_players:
                logging.info(f"Week {week_wordle}: No eligible players (need {MIN_GAMES_REQUIRED} games)")
                continue
            
            # Find winner(s) - lowest best 5 total
            min_total = min(p['total'] for p in eligible_players.values())
            winners = [
                {'name': name, 'score': data['total'], 'player_id': data['player_id']}
                for name, data in eligible_players.items()
                if data['total'] == min_total
            ]
            
            # Save winners to data structure
            week_key = str(week_wordle)
            league_info['weekly_winners'][week_key] = [
                {'name': w['name'], 'score': w['score']}
                for w in winners
            ]
            
            winner_names = ', '.join([w['name'] for w in winners])
            logging.info(f"Week {week_wordle}: Winner(s) = {winner_names} with total {min_total}")
        
        # Check for season winners
        check_for_season_winners(winners_data)
        
        # Save back to database
        save_weekly_winners(winners_data)
        
        logging.info(f"Successfully updated weekly winners for league {league_id}")
        return True
        
    except Exception as e:
        logging.error(f"Error updating weekly winners: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        cursor.close()
        conn.close()

def run_full_update_for_league(league_id):
    """
    Run the complete update process for a league:
    1. Update weekly winners
    2. Check for season transitions
    3. Generate HTML
    4. Publish to GitHub
    """
    logging.info(f"=== Starting full update for league {league_id} ===")
    
    try:
        # Step 1: Update weekly winners
        if not update_weekly_winners_from_db(league_id):
            logging.error("Failed to update weekly winners")
            return False
        
        # Step 2: Generate HTML (using existing pipeline)
        from update_pipeline import run_update_pipeline
        if not run_update_pipeline(league_id):
            logging.error("Failed to generate and publish HTML")
            return False
        
        logging.info(f"=== Successfully completed full update for league {league_id} ===")
        return True
        
    except Exception as e:
        logging.error(f"Error in full update: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import sys
    
    # Get league ID from command line or default to 6
    league_id = 6
    if len(sys.argv) > 1:
        league_id = int(sys.argv[1])
    
    print(f"Running full update for league {league_id}...")
    success = run_full_update_for_league(league_id)
    
    if success:
        print("✅ Update completed successfully!")
        sys.exit(0)
    else:
        print("❌ Update failed!")
        sys.exit(1)
