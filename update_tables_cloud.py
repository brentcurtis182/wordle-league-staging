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

# Constants from original script
WINS_FOR_SEASON_VICTORY = 4  # Number of weekly wins to win a season
MIN_GAMES_REQUIRED = 5       # Require 5 games minimum for weekly winner eligibility

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

def check_for_season_winners(winners_data):
    """
    Check if any league has players with 4+ weekly wins, who qualify as season winners.
    Each league operates independently with its own season schedule.
    """
    logging.info("Checking for season winners (requires 4 weekly wins)")
    
    # Process each league independently
    for league_key in winners_data['leagues']:
        league_info = winners_data['leagues'][league_key]
        
        # Get current season from league data (don't override it)
        current_season = league_info.get('current_season', 1)
        
        logging.info(f"Checking league {league_key} ('{league_info.get('name', 'Unknown')}') - current season: {current_season}")
        
        # Get season boundaries for the current season
        seasons_data = league_info.get('seasons', {})
        season_start_week = None
        season_end_week = None
        
        if str(current_season) in seasons_data:
            season_start_week = seasons_data[str(current_season)].get('start_week')
            season_end_week = seasons_data[str(current_season)].get('end_week')
        
        # Count weekly wins per player ONLY within current season boundaries
        player_wins = {}
        
        logging.info(f"  Counting wins for season {current_season}: start_week={season_start_week}, end_week={season_end_week}")
        
        # Access weekly_winners correctly using the new structure
        if 'weekly_winners' in league_info:
            for week, winners in league_info['weekly_winners'].items():
                week_num = int(week)
                
                # Skip weeks outside current season boundaries
                if season_start_week and week_num < int(season_start_week):
                    logging.info(f"    Skipping week {week_num} (before season start {season_start_week})")
                    continue
                if season_end_week and week_num > int(season_end_week):
                    logging.info(f"    Skipping week {week_num} (after season end {season_end_week})")
                    continue
                
                logging.info(f"    Processing week {week_num} (within season boundaries)")
                for winner in winners:
                    player_name = winner.get('name', 'Unknown')
                    if player_name not in player_wins:
                        player_wins[player_name] = 0
                    player_wins[player_name] += 1
                    logging.info(f"      {player_name} now has {player_wins[player_name]} weekly wins in season {current_season}")
        
        # Check if any player has enough wins to win the season
        season_winners = []
        for player_name, win_count in player_wins.items():
            if win_count >= WINS_FOR_SEASON_VICTORY:
                season_winners.append({
                    'name': player_name,
                    'weekly_wins': win_count,
                    'season': current_season,
                    'completed_date': datetime.now().strftime("%Y-%m-%d")
                })
                logging.info(f"  {player_name} has {win_count} weekly wins (threshold: {WINS_FOR_SEASON_VICTORY})")
        
        # If we have winners, update the season_winners entry and reset league data
        if season_winners:
            # Sort by win count (descending) to find who has the most wins
            season_winners.sort(key=lambda x: x['weekly_wins'], reverse=True)
            
            # Get the highest win count
            top_win_count = season_winners[0]['weekly_wins']
            
            # CRITICAL: Only the player(s) with the MOST wins are season winners
            final_winners = [w for w in season_winners if w['weekly_wins'] == top_win_count]
            
            # Format winner names for display
            winner_names = ', '.join([w['name'] for w in final_winners])
            logging.info(f"  Season {current_season} winner(s): {winner_names} with {top_win_count} wins")
            
            # Add winners to the season_winners data
            if 'season_winners' not in league_info:
                league_info['season_winners'] = []
                
            # Add all winning players
            for winner in final_winners:
                # Check if this winner is already recorded to avoid duplicates
                winner_exists = False
                for existing_winner in league_info.get('season_winners', []):
                    if (existing_winner.get('name') == winner['name'] and 
                        (existing_winner.get('season') == winner['season'] or
                         existing_winner.get('season_number') == winner['season'])):
                        winner_exists = True
                        break
                        
                if not winner_exists:
                    league_info['season_winners'].append(winner)
                    logging.info(f"SEASON TRANSITION: League {league_key}: {winner['name']} is Season {current_season} winner with {winner['weekly_wins']} weekly wins")
            
            # Mark this season as complete
            if 'completed_seasons' not in league_info:
                league_info['completed_seasons'] = []
                
            if current_season not in league_info['completed_seasons']:
                league_info['completed_seasons'].append(current_season)
                logging.info(f"Marked season {current_season} as complete for league {league_key}")
            
            # Update season boundaries: close current season, start new season
            if str(current_season) in seasons_data:
                # Set end_week for completed season to the latest week with data
                if 'weekly_winners' in league_info:
                    weeks = sorted([int(w) for w in league_info['weekly_winners'].keys() if league_info['weekly_winners'][w]])
                    if weeks:
                        latest_week = str(weeks[-1])
                        seasons_data[str(current_season)]['end_week'] = latest_week
                        logging.info(f"Set season {current_season} end_week to {latest_week} for league {league_key}")
            
            # Increment season when player reaches 4 wins
            new_season = current_season + 1
            league_info['current_season'] = new_season
            
            # Update global current_seasons tracker
            if 'current_seasons' in winners_data:
                winners_data['current_seasons'][league_key] = new_season
            
            # Create new season entry with start week as next Monday
            if 'weekly_winners' in league_info:
                weeks = sorted([int(w) for w in league_info['weekly_winners'].keys()])
                if weeks:
                    # Next season starts 7 days after the last week
                    next_season_start = str(weeks[-1] + 7)
                    if str(new_season) not in seasons_data:
                        seasons_data[str(new_season)] = {
                            'start_week': next_season_start,
                            'end_week': None,
                            'winner': None
                        }
                        logging.info(f"Created season {new_season} entry with start_week {next_season_start} for league {league_key}")

def update_weekly_winners_from_db(league_id, week_start_wordle=None, week_end_wordle=None):
    """
    Calculate and save weekly winners for a league
    This is the cloud version of update_weekly_winners_json()
    
    If week_start_wordle and week_end_wordle are provided, only calculate that specific week.
    Otherwise, calculate all weeks (used for initial setup).
    """
    if week_start_wordle and week_end_wordle:
        logging.info(f"Updating weekly winners for league {league_id}, week {week_start_wordle}-{week_end_wordle}")
    else:
        logging.info(f"Updating weekly winners for league {league_id} (all weeks)")
    
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Per-league configurable minimum scores per week (3-7, default 5)
        cursor.execute("SELECT COALESCE(min_weekly_scores, 5) FROM leagues WHERE id = %s", (league_id,))
        _mws_row = cursor.fetchone()
        league_min_scores = int(_mws_row[0]) if _mws_row and _mws_row[0] else MIN_GAMES_REQUIRED
        if not (3 <= league_min_scores <= 7):
            league_min_scores = MIN_GAMES_REQUIRED

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
        
        # If specific week provided, only process that week
        if week_start_wordle and week_end_wordle:
            # Convert Wordle number to date
            # Reference: July 31, 2025 = Wordle 1503
            reference_date = datetime(2025, 7, 31).date()
            reference_wordle = 1503
            days_diff = week_start_wordle - reference_wordle
            monday_date = reference_date + timedelta(days=days_diff)
            
            weeks = [(monday_date, week_start_wordle)]
        else:
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

            # Clean slate for this week: drop any existing winner rows before
            # recomputing. Prevents stale rows if the winner's identity changes
            # between runs (e.g. after a settings/backfill, or a cron re-run).
            cursor.execute(
                "DELETE FROM weekly_winners WHERE league_id = %s AND week_wordle_number = %s",
                (league_id, week_wordle)
            )

            # Calculate week range (Monday to Sunday)
            sunday_date = monday_date + timedelta(days=6)
            
            # Get all scores for this week using Wordle numbers (more reliable than dates)
            week_end_wordle = week_wordle + 7
            logging.info(f"Querying scores: league_id={league_id}, wordle_number >= {week_wordle} AND < {week_end_wordle}")
            cursor.execute("""
                SELECT 
                    p.id,
                    p.name,
                    s.score,
                    s.wordle_number
                FROM scores s
                JOIN players p ON s.player_id = p.id
                WHERE p.league_id = %s
                  AND s.wordle_number >= %s
                  AND s.wordle_number < %s
                  AND s.score != 7  -- Exclude failed attempts
                ORDER BY p.name, s.score
            """, (league_id, week_wordle, week_end_wordle))
            
            rows = cursor.fetchall()
            logging.info(f"Found {len(rows)} scores for week {week_wordle}")
            
            # Group scores by player
            player_scores = {}
            for row in rows:
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
            
            # Calculate best-N totals for eligible players (league_min_scores+ games)
            eligible_players = {}
            for player_name, data in player_scores.items():
                scores = sorted(data['scores'])  # Sort ascending (best first)

                if len(scores) >= league_min_scores:
                    best_5_total = sum(scores[:league_min_scores])
                    eligible_players[player_name] = {
                        'player_id': data['player_id'],
                        'total': best_5_total,
                        'games': len(scores)
                    }
            
            if not eligible_players:
                logging.info(f"Week {week_wordle}: No eligible players (need {league_min_scores} games)")
                continue
            
            # Check if league is in division mode
            cursor.execute("SELECT division_mode FROM leagues WHERE id = %s", (league_id,))
            div_row = cursor.fetchone()
            is_division_mode = div_row and div_row[0]
            
            if is_division_mode:
                # Division mode: calculate winners per division
                # Get player division assignments
                cursor.execute("""
                    SELECT id, division FROM players
                    WHERE league_id = %s AND active = TRUE AND division IS NOT NULL
                """, (league_id,))
                player_divisions = {row[0]: row[1] for row in cursor.fetchall()}
                
                for div_num in (1, 2):
                    div_eligible = {
                        name: data for name, data in eligible_players.items()
                        if player_divisions.get(data['player_id']) == div_num
                    }
                    
                    if not div_eligible:
                        logging.info(f"Week {week_wordle} Div {div_num}: No eligible players")
                        continue
                    
                    min_total = min(p['total'] for p in div_eligible.values())
                    div_winners = [
                        {'name': name, 'score': data['total'], 'player_id': data['player_id']}
                        for name, data in div_eligible.items()
                        if data['total'] == min_total
                    ]
                    
                    for winner in div_winners:
                        cursor.execute("""
                            INSERT INTO weekly_winners (league_id, player_id, week_wordle_number, player_name, score, division)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            ON CONFLICT (league_id, week_wordle_number, player_id) DO UPDATE
                            SET player_name = EXCLUDED.player_name, score = EXCLUDED.score, division = EXCLUDED.division
                        """, (league_id, winner['player_id'], week_wordle, winner['name'], winner['score'], div_num))
                    
                    winner_names = ', '.join([w['name'] for w in div_winners])
                    logging.info(f"Week {week_wordle} Div {div_num}: Winner(s) = {winner_names} with total {min_total}")

                    for winner in div_winners:
                        try:
                            from twilio_webhook_app import forward_weekly_winner_to_staging
                            forward_weekly_winner_to_staging(league_id, winner['name'], week_wordle, winner['score'], div_num)
                        except Exception:
                            pass

                # Lock division mode after first weekly winners are recorded
                cursor.execute("""
                    UPDATE leagues SET division_locked = TRUE WHERE id = %s AND division_locked = FALSE
                """, (league_id,))
                
                conn.commit()
            else:
                # Normal mode: single winner across all players
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
                
                # Save winners to database weekly_winners table
                for winner in winners:
                    cursor.execute("""
                        INSERT INTO weekly_winners (league_id, player_id, week_wordle_number, player_name, score)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (league_id, week_wordle_number, player_id) DO UPDATE
                        SET player_name = EXCLUDED.player_name, score = EXCLUDED.score
                    """, (league_id, winner['player_id'], week_wordle, winner['name'], winner['score']))
                
                conn.commit()
                
                winner_names = ', '.join([w['name'] for w in winners])
                logging.info(f"Week {week_wordle}: Winner(s) = {winner_names} with total {min_total} - saved to database")

                for winner in winners:
                    try:
                        from twilio_webhook_app import forward_weekly_winner_to_staging
                        forward_weekly_winner_to_staging(league_id, winner['name'], week_wordle, winner['score'])
                    except Exception:
                        pass
        
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

def check_and_handle_season_transition(league_id):
    """
    Check if any player has reached 4 weekly wins and handle season transition.
    Adapted from legacy check_for_season_winners() function.
    
    This should ONLY be called by run_full_update_for_league() on Mondays.
    """
    WINS_FOR_SEASON_VICTORY = 4
    
    logging.info(f"Checking for season transition in league {league_id}")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get current season info
        cursor.execute("""
            SELECT current_season, season_start_week FROM league_seasons WHERE league_id = %s
        """, (league_id,))
        result = cursor.fetchone()
        current_season = result[0] if result else 1
        league_season_start_week = result[1] if result else None
        
        # Get current season boundaries
        cursor.execute("""
            SELECT start_week, end_week FROM seasons
            WHERE league_id = %s AND season_number = %s
        """, (league_id, current_season))
        season_bounds = cursor.fetchone()
        
        if not season_bounds or not season_bounds[0]:
            # Fallback: use league_seasons.season_start_week or earliest weekly winner
            if league_season_start_week:
                season_start = league_season_start_week
                logging.info(f"No seasons table entry for league {league_id} season {current_season}, using league_seasons.season_start_week={season_start}")
            else:
                # Derive from earliest weekly winner
                cursor.execute("SELECT MIN(week_wordle_number) FROM weekly_winners WHERE league_id = %s", (league_id,))
                min_row = cursor.fetchone()
                if min_row and min_row[0]:
                    season_start = min_row[0]
                    logging.info(f"No season_start_week for league {league_id}, derived from earliest weekly winner: {season_start}")
                else:
                    logging.warning(f"No season boundaries found for league {league_id} season {current_season}")
                    return False
            
            # Auto-create the missing seasons table entry so future checks work
            cursor.execute("""
                INSERT INTO seasons (league_id, season_number, start_week, end_week)
                VALUES (%s, %s, %s, NULL)
                ON CONFLICT (league_id, season_number) DO NOTHING
            """, (league_id, current_season, season_start))
            
            # Also fix league_seasons if it was NULL
            if not league_season_start_week:
                cursor.execute("""
                    UPDATE league_seasons SET season_start_week = %s WHERE league_id = %s
                """, (season_start, league_id))
            
            conn.commit()
            season_end = None
        else:
            season_start = season_bounds[0]
            season_end = season_bounds[1]  # Will be None if season is in progress
        
        # If season already ended, no need to check
        if season_end:
            logging.info(f"Season {current_season} already ended at week {season_end}")
            return False
        
        logging.info(f"  Counting wins for season {current_season}: start_week={season_start}, end_week={season_end}")
        
        # Count weekly wins per player ONLY within current season boundaries
        cursor.execute("""
            SELECT player_name, COUNT(*) as win_count
            FROM weekly_winners
            WHERE league_id = %s AND week_wordle_number >= %s
            GROUP BY player_name
            HAVING COUNT(*) >= %s
            ORDER BY COUNT(*) DESC
        """, (league_id, season_start, WINS_FOR_SEASON_VICTORY))
        
        potential_winners = cursor.fetchall()
        
        if not potential_winners:
            logging.info(f"No players have reached {WINS_FOR_SEASON_VICTORY} wins yet in season {current_season}")
            return False
        
        # Get the highest win count
        top_win_count = potential_winners[0][1]
        winners = [row for row in potential_winners if row[1] == top_win_count]
        
        logging.info(f"🏆 SEASON TRANSITION: League {league_id} Season {current_season} winner(s):")
        for winner_name, win_count in winners:
            logging.info(f"   {winner_name} with {win_count} weekly wins")
        
        # Find the last week with data to set as end_week
        cursor.execute("""
            SELECT MAX(week_wordle_number) FROM weekly_winners
            WHERE league_id = %s
        """, (league_id,))
        last_week = cursor.fetchone()[0]
        
        # Close current season
        cursor.execute("""
            UPDATE seasons
            SET end_week = %s
            WHERE league_id = %s AND season_number = %s
        """, (last_week, league_id, current_season))
        
        logging.info(f"Closed season {current_season} with end_week = {last_week}")
        
        # Save season winners to season_winners table
        for winner_name, win_count in winners:
            # Get player_id
            cursor.execute("""
                SELECT id FROM players WHERE name = %s AND league_id = %s
            """, (winner_name, league_id))
            player_result = cursor.fetchone()
            if player_result:
                player_id = player_result[0]
                cursor.execute("""
                    INSERT INTO season_winners (league_id, player_id, season_number, wins, completed_date)
                    VALUES (%s, %s, %s, %s, CURRENT_DATE)
                    ON CONFLICT (league_id, season_number, player_id) DO NOTHING
                """, (league_id, player_id, current_season, win_count))

                try:
                    from twilio_webhook_app import forward_season_winner_to_staging
                    forward_season_winner_to_staging(league_id, winner_name, current_season, win_count)
                except Exception:
                    pass

        # Create new season entry
        new_season = current_season + 1
        next_season_start = last_week + 7  # Next Monday
        
        cursor.execute("""
            INSERT INTO seasons (league_id, season_number, start_week, end_week)
            VALUES (%s, %s, %s, NULL)
            ON CONFLICT (league_id, season_number) DO NOTHING
        """, (league_id, new_season, next_season_start))
        
        # Update league_seasons table (both current_season AND season_start_week)
        cursor.execute("""
            UPDATE league_seasons
            SET current_season = %s,
                season_start_week = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE league_id = %s
        """, (new_season, next_season_start, league_id))
        
        conn.commit()
        
        logging.info(f"Created season {new_season} starting at week {next_season_start}")
        logging.info(f"Updated league {league_id} to season {new_season}")
        
        return True
        
    except Exception as e:
        conn.rollback()
        logging.error(f"Error checking season transition: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        cursor.close()
        conn.close()

def run_full_update_for_league(league_id):
    """
    Run the complete update process for a league:
    1. Update weekly winners for LAST week (the week that just ended)
    2. Check for season transitions
    3. Generate HTML
    4. Publish to GitHub
    """
    logging.info(f"=== Starting full update for league {league_id} ===")
    
    try:
        # Calculate LAST week's Wordle range (the week that just ended)
        # IMPORTANT: Use Pacific timezone, not UTC
        import pytz
        pacific = pytz.timezone('America/Los_Angeles')
        now_pacific = datetime.now(pacific)
        today = now_pacific.date()
        
        # Find last Monday (start of last week)
        days_since_monday = today.weekday()  # 0=Monday, 6=Sunday
        if days_since_monday == 0:
            # Today is Monday, so last week started 7 days ago
            last_monday = today - timedelta(days=7)
        else:
            # Go back to last Monday, then back 7 more days
            last_monday = today - timedelta(days=days_since_monday + 7)
        
        last_sunday = last_monday + timedelta(days=6)
        
        # Calculate Wordle numbers for last week
        last_week_start_wordle = calculate_wordle_number(last_monday)
        last_week_end_wordle = calculate_wordle_number(last_sunday)
        
        logging.info(f"Calculating winners for LAST week: {last_monday} to {last_sunday} (Wordles {last_week_start_wordle}-{last_week_end_wordle})")
        
        # Step 1: Update weekly winners for last week only
        if not update_weekly_winners_from_db(league_id, last_week_start_wordle, last_week_end_wordle):
            logging.error("Failed to update weekly winners")
            return False
        
        # Step 2: Check for season transitions (ONLY runs in scheduled task, not manual)
        # Check if league is in division mode
        div_conn = get_db_connection()
        div_cursor = div_conn.cursor()
        div_cursor.execute("SELECT division_mode FROM leagues WHERE id = %s", (league_id,))
        div_result = div_cursor.fetchone()
        is_division_mode = div_result and div_result[0]
        div_cursor.close()
        div_conn.close()
        
        if is_division_mode:
            from division_manager import check_division_season_transition, check_division1_relegation, clear_immunity
            # Check each division separately
            transitioned_divisions = []
            for div_num in (1, 2):
                transitioned = check_division_season_transition(league_id, div_num)
                if transitioned:
                    transitioned_divisions.append(div_num)
                    # Clear immunity for players in this division (their first full season just ended)
                    clear_immunity(league_id, div_num)
                    if div_num == 1:
                        # Division I season ended - relegate worst Season Total player
                        check_division1_relegation(league_id)
            
            # If both divisions finished simultaneously, the promoted player
            # doesn't need immunity — everyone starts the new season together
            if 1 in transitioned_divisions and 2 in transitioned_divisions:
                clear_immunity(league_id, 1)
                logging.info(f"Both divisions transitioned simultaneously for league {league_id} — cleared immunity on promoted player")

        else:
            check_and_handle_season_transition(league_id)
        
        # Step 3: Generate HTML (using existing pipeline)
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
