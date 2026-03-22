#!/usr/bin/env python3
"""
PostgreSQL Adapter for Existing Wordle League Logic
Ports the proven logic from export_leaderboard.py to work with PostgreSQL
"""

import os
import logging
import psycopg2
from datetime import datetime, date, timedelta
from collections import defaultdict

def get_db_connection():
    """Get PostgreSQL database connection"""
    database_url = os.environ.get('DATABASE_URL')
    if database_url:
        conn = psycopg2.connect(database_url, connect_timeout=10)
    else:
        conn = psycopg2.connect(
            host=os.environ.get('PGHOST'),
            database=os.environ.get('PGDATABASE'),
            user=os.environ.get('PGUSER'),
            password=os.environ.get('PGPASSWORD'),
            port=os.environ.get('PGPORT', 5432),
            connect_timeout=10
        )
    
    # Set statement timeout to 20 seconds to prevent hanging queries
    cursor = conn.cursor()
    cursor.execute("SET statement_timeout = '20s'")
    cursor.close()
    return conn

def calculate_wordle_number(target_date=None):
    """Calculate the Wordle number based on the date (from export_leaderboard.py)"""
    # First Wordle (Wordle 0) was on June 19, 2021
    first_wordle_date = datetime(2021, 6, 19).date()
    
    if target_date is None:
        # Use Pacific Time for "today"
        from datetime import timezone
        pacific_tz = timezone(timedelta(hours=-8))
        now_pacific = datetime.now(pacific_tz)
        target_date = now_pacific.date()
    
    # Calculate days since first Wordle
    days_since_first = (target_date - first_wordle_date).days
    
    return days_since_first

def get_week_start_date(target_date=None):
    """Get the Monday of the current week (from export_leaderboard.py logic)"""
    if target_date is None:
        from datetime import timezone
        pacific_tz = timezone(timedelta(hours=-8))
        now_pacific = datetime.now(pacific_tz)
        target_date = now_pacific.date()
    
    # Find Monday of this week
    days_since_monday = target_date.weekday()  # Monday=0, Sunday=6
    monday = target_date - timedelta(days=days_since_monday)
    
    return monday

def get_current_week_wordles():
    """Get the Wordle numbers for the current week (Monday-Sunday)"""
    monday = get_week_start_date()
    
    week_wordles = []
    for i in range(7):  # Monday through Sunday
        day = monday + timedelta(days=i)
        wordle_num = calculate_wordle_number(day)
        week_wordles.append(wordle_num)
    
    return week_wordles

def get_all_league_players(league_id, conn=None):
    """Get all active players in a league"""
    own_conn = conn is None
    if own_conn:
        conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, name, phone_number
        FROM players
        WHERE league_id = %s AND active = TRUE
        ORDER BY name
    """, (league_id,))
    
    players = []
    for row in cursor.fetchall():
        players.append({
            'id': row[0],
            'name': row[1],
            'phone': row[2]
        })
    
    cursor.close()
    if own_conn:
        conn.close()
    
    return players

def get_latest_scores_for_display(league_id, conn=None):
    """
    Get the most recent score for each player for the Latest Scores tab
    Returns: dict with player_name -> {score, emoji_pattern, wordle_num, date}
    """
    own_conn = conn is None
    if own_conn:
        conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get today's Wordle number
    today_wordle = calculate_wordle_number()
    
    # Get all players
    players = get_all_league_players(league_id, conn=conn)
    
    latest_scores = {}
    
    for player in players:
        # Get ONLY today's score (not most recent)
        cursor.execute("""
            SELECT wordle_number, score, emoji_pattern, date, timestamp
            FROM scores
            WHERE player_id = %s AND wordle_number = %s
        """, (player['id'], today_wordle))
        
        result = cursor.fetchone()
        
        if result:
            latest_scores[player['name']] = {
                'wordle_num': result[0],
                'score': result[1],
                'emoji_pattern': result[2],
                'date': result[3],
                'timestamp': result[4]
            }
        else:
            # No score for today - show as not submitted
            latest_scores[player['name']] = {
                'wordle_num': today_wordle,
                'score': None,
                'emoji_pattern': None,
                'date': None,
                'timestamp': None
            }
    
    cursor.close()
    if own_conn:
        conn.close()
    
    return latest_scores, today_wordle

def get_weekly_stats(league_id, conn=None):
    """
    Get weekly statistics using the Monday-Sunday week and best 5 scores rule
    This matches the logic from export_leaderboard.py
    """
    own_conn = conn is None
    if own_conn:
        conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get current week's Wordle numbers (Monday-Sunday)
    week_wordles = get_current_week_wordles()
    week_start = week_wordles[0]
    week_end = week_wordles[6]
    
    logging.info(f"Calculating weekly stats for league {league_id}, week {week_start}-{week_end} (Mon-Sun)")
    
    # Get all players
    players = get_all_league_players(league_id, conn=conn)
    
    weekly_stats = {}
    
    for player in players:
        # Get all scores for this week
        cursor.execute("""
            SELECT wordle_number, score, emoji_pattern
            FROM scores
            WHERE player_id = %s
              AND wordle_number >= %s
              AND wordle_number <= %s
            ORDER BY wordle_number
        """, (player['id'], week_start, week_end))
        
        scores_data = cursor.fetchall()
        
        # Build daily scores map
        daily_scores = {}
        all_scores = []
        failed_attempts = 0
        
        for wordle_num, score, emoji in scores_data:
            daily_scores[wordle_num] = {
                'score': score,
                'emoji': emoji
            }
            
            if score == 7:  # Failed attempt (X/6)
                failed_attempts += 1
            else:
                all_scores.append(score)
        
        # Calculate best 5 scores (excluding failed attempts)
        all_scores.sort()  # Sort ascending
        best_5_scores = all_scores[:5] if len(all_scores) >= 5 else all_scores
        best_5_total = sum(best_5_scores)
        used_scores = len(best_5_scores)
        
        # Get the actual thrown out scores (not just the count)
        thrown_out_scores = all_scores[5:] if len(all_scores) > 5 else []
        thrown_out = thrown_out_scores  # List of actual scores thrown out
        
        avg_score = best_5_total / used_scores if used_scores > 0 else 0
        
        weekly_stats[player['name']] = {
            'player_id': player['id'],
            'name': player['name'],
            'daily_scores': daily_scores,  # Map of wordle_num -> {score, emoji}
            'all_scores': all_scores,
            'best_5_total': best_5_total,
            'used_scores': used_scores,
            'thrown_out': thrown_out,
            'avg_score': avg_score,
            'failed_attempts': failed_attempts,
            'games_played': len(scores_data)
        }
    
    cursor.close()
    if own_conn:
        conn.close()
    
    return weekly_stats, week_wordles

def get_all_time_stats(league_id, conn=None):
    """Get all-time statistics for all players (including those with no scores)"""
    own_conn = conn is None
    if own_conn:
        conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get ALL players first
    players = get_all_league_players(league_id, conn=conn)
    
    # Get stats for players with scores
    cursor.execute("""
        SELECT 
            p.name,
            COUNT(*) as games_played,
            AVG(s.score) as avg_score
        FROM scores s
        JOIN players p ON s.player_id = p.id
        WHERE p.league_id = %s
        GROUP BY p.name
    """, (league_id,))
    
    # Build dict of stats
    stats_dict = {}
    for row in cursor.fetchall():
        stats_dict[row[0]] = {
            'name': row[0],
            'games_played': row[1],
            'avg_score': float(row[2])
        }
    
    # Add all players (with or without scores)
    stats = []
    for player in players:
        if player['name'] in stats_dict:
            stats.append(stats_dict[player['name']])
        else:
            # Player has no scores yet
            stats.append({
                'name': player['name'],
                'games_played': 0,
                'avg_score': None
            })
    
    # Sort: players with scores first (by avg), then players without scores
    stats.sort(key=lambda x: (x['avg_score'] is None, x['avg_score'] if x['avg_score'] else 999, -x['games_played']))
    
    cursor.close()
    if own_conn:
        conn.close()
    
    return stats

def get_complete_league_data(league_id):
    """
    Get all data needed for HTML generation
    This is the main function that combines everything.
    Uses a single shared DB connection for all sub-queries.
    """
    logging.info(f"Fetching complete data for league {league_id}")
    
    # Single shared connection for all queries
    conn = get_db_connection()
    
    try:
        # Get latest scores for display
        latest_scores, today_wordle = get_latest_scores_for_display(league_id, conn=conn)
        
        # Get weekly stats
        weekly_stats, week_wordles = get_weekly_stats(league_id, conn=conn)
        
        # Get all-time stats
        all_time_stats = get_all_time_stats(league_id, conn=conn)
        
        # Determine weekly winner (must have at least 5 scores)
        eligible_players = {
            name: stats 
            for name, stats in weekly_stats.items() 
            if stats['used_scores'] >= 5
        }
        
        weekly_winner = None
        if eligible_players:
            winner_name = min(eligible_players.keys(), key=lambda n: eligible_players[n]['best_5_total'])
            weekly_winner = {
                'name': winner_name,
                'stats': eligible_players[winner_name]
            }
            logging.info(f"Weekly winner: {winner_name} with best 5 total of {eligible_players[winner_name]['best_5_total']}")
        else:
            logging.warning(f"No players met minimum 5 games requirement for week {week_wordles[0]}")
        
        # Get season data
        season_data = get_season_data(league_id, conn=conn)
        
        # Division-related queries
        div_cursor = conn.cursor()
        
        # Check if league is in division mode
        div_cursor.execute("SELECT division_mode, division_confirmed_at, COALESCE(promoted_count, 1), COALESCE(relegated_count, 1) FROM leagues WHERE id = %s", (league_id,))
        div_result = div_cursor.fetchone()
        is_division_mode = div_result and div_result[0]
        division_confirmed_at = div_result[1] if div_result else None
        promoted_count = div_result[2] if div_result else 1
        relegated_count = div_result[3] if div_result else 1
        
        # Check if there are any division season winners in the database (even if division mode is OFF)
        # This ensures division season history is retained when toggling division mode off
        div_cursor.execute("""
            SELECT COUNT(*) FROM season_winners
            WHERE league_id = %s AND division IS NOT NULL
        """, (league_id,))
        has_division_history = div_cursor.fetchone()[0] > 0
        
        # Get player division assignments for weekly stats filtering
        player_divisions = {}
        if is_division_mode:
            div_cursor.execute("""
                SELECT name, division FROM players
                WHERE league_id = %s AND active = TRUE AND division IS NOT NULL
            """, (league_id,))
            player_divisions = {row[0]: row[1] for row in div_cursor.fetchall()}
        
        # Count regular (pre-division) seasons for unified season numbering
        regular_season_count = 0
        if is_division_mode or has_division_history:
            div_cursor.execute("""
                SELECT COALESCE(MAX(season_number), 0) FROM season_winners
                WHERE league_id = %s AND division IS NULL
            """, (league_id,))
            regular_season_count = div_cursor.fetchone()[0]
        
        div_cursor.close()
        
        division_data = None
        if is_division_mode or has_division_history:
            division_data = get_division_season_data(league_id, weekly_stats=weekly_stats, conn=conn)
        
        # Calculate missed weeks for all players (standard league display)
        # A missed week = past completed week in current season with < 5 valid scores
        missed_weeks = {}
        season_start_for_missed = season_data.get('season_start_week') if season_data else None
        if not season_start_for_missed:
            # Fallback: try to get from seasons table via season_data
            sd_cursor = conn.cursor()
            sd_cursor.execute("""
                SELECT start_week FROM seasons
                WHERE league_id = %s AND season_number = %s
            """, (league_id, season_data.get('current_season', 1)))
            sr = sd_cursor.fetchone()
            if sr:
                season_start_for_missed = sr[0]
            sd_cursor.close()
        
        current_week_start = week_wordles[0] if week_wordles else None
        
        if season_start_for_missed and current_week_start:
            mw_cursor = conn.cursor()
            for player_name, pstats in weekly_stats.items():
                player_id = pstats.get('player_id')
                if not player_id:
                    missed_weeks[player_name] = 0
                    continue
                
                mw_cursor.execute("""
                    SELECT s.wordle_number, s.score
                    FROM scores s
                    WHERE s.player_id = %s
                      AND s.wordle_number >= %s
                      AND s.wordle_number < %s
                    ORDER BY s.wordle_number
                """, (player_id, season_start_for_missed, current_week_start))
                
                # Group by week
                week_scores = {}
                for wn, sc in mw_cursor.fetchall():
                    ws = wn - ((wn - season_start_for_missed) % 7)
                    if ws not in week_scores:
                        week_scores[ws] = []
                    week_scores[ws].append(sc)
                
                player_missed = 0
                w = season_start_for_missed
                while w < current_week_start:
                    scores_in_week = week_scores.get(w, [])
                    valid_count = len([s for s in scores_in_week if s < 7])
                    if valid_count < 5:
                        player_missed += 1
                    w += 7
                
                missed_weeks[player_name] = player_missed
            mw_cursor.close()
    finally:
        conn.close()
    
    return {
        'league_id': league_id,
        'today_wordle': today_wordle,
        'week_wordles': week_wordles,
        'latest_scores': latest_scores,
        'weekly_stats': weekly_stats,
        'weekly_winner': weekly_winner,
        'all_time_stats': all_time_stats,
        'season_data': season_data,
        'division_mode': is_division_mode,
        'division_confirmed_at': division_confirmed_at,
        'division_data': division_data,
        'player_divisions': player_divisions,
        'regular_season_count': regular_season_count,
        'missed_weeks': missed_weeks,
        'promoted_count': promoted_count,
        'relegated_count': relegated_count,
        'timestamp': datetime.now()
    }

def get_season_data(league_id, conn=None):
    """Get season information from PostgreSQL"""
    own_conn = conn is None
    if own_conn:
        conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get current season
    cursor.execute("""
        SELECT current_season, season_start_week
        FROM league_seasons
        WHERE league_id = %s
    """, (league_id,))
    
    season_result = cursor.fetchone()
    current_season = season_result[0] if season_result else 1
    season_start_week = season_result[1] if season_result else None
    
    # Get current season boundaries from seasons table
    cursor.execute("""
        SELECT start_week, end_week
        FROM seasons
        WHERE league_id = %s AND season_number = %s
    """, (league_id, current_season))
    
    season_bounds = cursor.fetchone()
    season_start = season_bounds[0] if season_bounds else None
    season_end = season_bounds[1] if season_bounds else None
    
    # Get current season standings (weekly wins)
    # Only show weekly winners from current season (between start_week and end_week)
    season_standings = {}
    
    if season_start and season_end:
        # Season has both start and end (completed season)
        cursor.execute("""
            SELECT 
                ww.player_name,
                ww.week_wordle_number,
                ww.score
            FROM weekly_winners ww
            WHERE ww.league_id = %s 
              AND ww.week_wordle_number >= %s 
              AND ww.week_wordle_number <= %s
            ORDER BY ww.player_name, ww.week_wordle_number
        """, (league_id, season_start, season_end))
    elif season_start:
        # Season has start but no end (current season in progress)
        cursor.execute("""
            SELECT 
                ww.player_name,
                ww.week_wordle_number,
                ww.score
            FROM weekly_winners ww
            WHERE ww.league_id = %s AND ww.week_wordle_number >= %s
            ORDER BY ww.player_name, ww.week_wordle_number
        """, (league_id, season_start))
    else:
        # No season boundaries set, show all (fallback)
        cursor.execute("""
            SELECT 
                ww.player_name,
                ww.week_wordle_number,
                ww.score
            FROM weekly_winners ww
            WHERE ww.league_id = %s
            ORDER BY ww.player_name, ww.week_wordle_number
        """, (league_id,))
    
    for row in cursor.fetchall():
        player_name = row[0]
        week_num = row[1]
        score = row[2]
        
        if player_name not in season_standings:
            season_standings[player_name] = {
                'wins': 0,
                'weeks': [],
                'scores': []
            }
        
        season_standings[player_name]['wins'] += 1
        season_standings[player_name]['weeks'].append(week_num)
        season_standings[player_name]['scores'].append(score)
    
    # Get past season winners (regular/non-division only)
    cursor.execute("""
        SELECT sw.season_number, p.name, sw.wins
        FROM season_winners sw
        JOIN players p ON sw.player_id = p.id
        WHERE sw.league_id = %s AND sw.division IS NULL
        ORDER BY sw.season_number DESC
    """, (league_id,))
    
    season_winners = []
    for row in cursor.fetchall():
        season_winners.append({
            'season': row[0],
            'name': row[1],
            'wins': row[2]
        })
    
    # Get past season breakdowns (weekly winners per past season)
    past_season_breakdowns = {}
    if season_winners:
        # Get all past season boundaries
        past_season_nums = list(set(w['season'] for w in season_winners))
        for sn in past_season_nums:
            cursor.execute("""
                SELECT start_week, end_week
                FROM seasons
                WHERE league_id = %s AND season_number = %s
            """, (league_id, sn))
            bounds = cursor.fetchone()
            if bounds and bounds[0] and bounds[1]:
                # Order by week so we can replay chronologically and stop at 4 wins
                cursor.execute("""
                    SELECT ww.player_name, ww.week_wordle_number, ww.score
                    FROM weekly_winners ww
                    WHERE ww.league_id = %s
                      AND ww.week_wordle_number >= %s
                      AND ww.week_wordle_number <= %s
                    ORDER BY ww.week_wordle_number, ww.player_name
                """, (league_id, bounds[0], bounds[1]))
                
                # Replay week by week, stop after the week where someone hits 4 wins
                all_rows = cursor.fetchall()
                breakdown = {}
                winning_week = None
                for pname, wnum, wscore in all_rows:
                    # Stop if we've passed the winning week
                    if winning_week is not None and wnum > winning_week:
                        break
                    if pname not in breakdown:
                        breakdown[pname] = {'wins': 0, 'weeks': [], 'scores': []}
                    breakdown[pname]['wins'] += 1
                    breakdown[pname]['weeks'].append(wnum)
                    breakdown[pname]['scores'].append(wscore)
                    if breakdown[pname]['wins'] >= 4 and winning_week is None:
                        winning_week = wnum
                
                if breakdown:
                    # Validate: the top player in breakdown should match the recorded season winner
                    # If not, the weekly_winners data for this season is incomplete/misaligned — skip it
                    recorded_winners_for_sn = [w['name'] for w in season_winners if w['season'] == sn]
                    top_player = max(breakdown.items(), key=lambda x: x[1]['wins'])[0]
                    if top_player in recorded_winners_for_sn and max(d['wins'] for d in breakdown.values()) >= 4:
                        past_season_breakdowns[sn] = breakdown
    
    cursor.close()
    if own_conn:
        conn.close()
    
    return {
        'current_season': current_season,
        'season_start_week': season_start,
        'season_standings': season_standings,
        'season_winners': season_winners,
        'past_season_breakdowns': past_season_breakdowns
    }

def get_division_season_data(league_id, weekly_stats=None, conn=None):
    """Get division-specific season data for a league in division mode.
    Returns data for both divisions including standings, winners, and breakdowns.
    weekly_stats: if provided, current week's best_5_total is added to season totals."""
    own_conn = conn is None
    if own_conn:
        conn = get_db_connection()
    cursor = conn.cursor()
    
    DIVISION_WINS = 3  # Wins needed for division season
    
    division_data = {}
    
    for div_num in (1, 2):
        # Get current division season
        cursor.execute("""
            SELECT current_season, season_start_week
            FROM division_seasons
            WHERE league_id = %s AND division = %s
        """, (league_id, div_num))
        
        ds_result = cursor.fetchone()
        current_season = ds_result[0] if ds_result else 1
        season_start_week = ds_result[1] if ds_result else None
        
        # Get season boundaries
        cursor.execute("""
            SELECT start_week, end_week
            FROM division_season_boundaries
            WHERE league_id = %s AND division = %s AND season_number = %s
        """, (league_id, div_num, current_season))
        
        bounds = cursor.fetchone()
        season_start = bounds[0] if bounds else season_start_week
        season_end = bounds[1] if bounds else None
        
        # Get current season standings
        season_standings = {}
        if season_start and season_end:
            cursor.execute("""
                SELECT ww.player_name, ww.week_wordle_number, ww.score
                FROM weekly_winners ww
                WHERE ww.league_id = %s AND ww.division = %s
                  AND ww.week_wordle_number >= %s AND ww.week_wordle_number <= %s
                ORDER BY ww.player_name, ww.week_wordle_number
            """, (league_id, div_num, season_start, season_end))
        elif season_start:
            cursor.execute("""
                SELECT ww.player_name, ww.week_wordle_number, ww.score
                FROM weekly_winners ww
                WHERE ww.league_id = %s AND ww.division = %s
                  AND ww.week_wordle_number >= %s
                ORDER BY ww.player_name, ww.week_wordle_number
            """, (league_id, div_num, season_start))
        else:
            cursor.execute("""
                SELECT ww.player_name, ww.week_wordle_number, ww.score
                FROM weekly_winners ww
                WHERE ww.league_id = %s AND ww.division = %s
                ORDER BY ww.player_name, ww.week_wordle_number
            """, (league_id, div_num))
        
        for row in cursor.fetchall():
            player_name, week_num, score = row[0], row[1], row[2]
            if player_name not in season_standings:
                season_standings[player_name] = {'wins': 0, 'weeks': [], 'scores': []}
            season_standings[player_name]['wins'] += 1
            season_standings[player_name]['weeks'].append(week_num)
            season_standings[player_name]['scores'].append(score)
        
        # Get division season winners (past seasons)
        cursor.execute("""
            SELECT sw.season_number, p.name, sw.wins, sw.player_id
            FROM season_winners sw
            LEFT JOIN players p ON sw.player_id = p.id
            WHERE sw.league_id = %s AND sw.division = %s
            ORDER BY sw.season_number DESC
        """, (league_id, div_num))
        
        season_winners = []
        for row in cursor.fetchall():
            # If player_id is NULL, this is a "Closed" season
            season_winners.append({
                'season': row[0],
                'name': row[1] if row[3] is not None else 'Closed',
                'wins': row[2]
            })
        
        # Get past season breakdowns
        past_season_breakdowns = {}
        if season_winners:
            past_season_nums = list(set(w['season'] for w in season_winners))
            for sn in past_season_nums:
                cursor.execute("""
                    SELECT start_week, end_week
                    FROM division_season_boundaries
                    WHERE league_id = %s AND division = %s AND season_number = %s
                """, (league_id, div_num, sn))
                sb = cursor.fetchone()
                if sb and sb[0] and sb[1]:
                    cursor.execute("""
                        SELECT ww.player_name, ww.week_wordle_number, ww.score
                        FROM weekly_winners ww
                        WHERE ww.league_id = %s AND ww.division = %s
                          AND ww.week_wordle_number >= %s AND ww.week_wordle_number <= %s
                        ORDER BY ww.week_wordle_number, ww.player_name
                    """, (league_id, div_num, sb[0], sb[1]))
                    
                    breakdown = {}
                    winning_week = None
                    for pname, wnum, wscore in cursor.fetchall():
                        if winning_week is not None and wnum > winning_week:
                            break
                        if pname not in breakdown:
                            breakdown[pname] = {'wins': 0, 'weeks': [], 'scores': []}
                        breakdown[pname]['wins'] += 1
                        breakdown[pname]['weeks'].append(wnum)
                        breakdown[pname]['scores'].append(wscore)
                        if breakdown[pname]['wins'] >= DIVISION_WINS and winning_week is None:
                            winning_week = wnum
                    
                    if breakdown:
                        recorded = [w['name'] for w in season_winners if w['season'] == sn]
                        top = max(breakdown.items(), key=lambda x: x[1]['wins'])[0]
                        if top in recorded and max(d['wins'] for d in breakdown.values()) >= DIVISION_WINS:
                            past_season_breakdowns[sn] = breakdown
        
        # Get players in this division with immunity info
        cursor.execute("""
            SELECT id, name, division_immunity, division_joined_week
            FROM players
            WHERE league_id = %s AND division = %s AND active = TRUE
            ORDER BY name
        """, (league_id, div_num))
        
        div_players = []
        for row in cursor.fetchall():
            div_players.append({
                'id': row[0],
                'name': row[1],
                'immunity': row[2] or False,
                'joined_week': row[3]
            })
        
        # Calculate season totals for each player
        # Season total = sum of best-5 weekly scores from ALL weeks in the season
        # Calculated from the scores table, not just weekly_winners
        # This is used for relegation (worst/highest total in Div I gets relegated)
        season_totals = {}
        missed_weeks = {}
        
        # Determine current week start wordle from weekly_stats
        current_week_start = None
        if weekly_stats:
            for pname, pstats in weekly_stats.items():
                if pstats.get('daily_scores'):
                    current_week_start = min(pstats['daily_scores'].keys())
                    break
        
        for p in div_players:
            if p['immunity']:
                season_totals[p['name']] = None  # Will display as "Immune"
                missed_weeks[p['name']] = 0
            elif season_start:
                # Get all scores for this player from the season start onwards
                cursor.execute("""
                    SELECT s.wordle_number, s.score
                    FROM scores s
                    WHERE s.player_id = %s
                      AND s.wordle_number >= %s
                    ORDER BY s.wordle_number
                """, (p['id'], season_start))
                
                # Group scores by week (7-day blocks from season_start)
                week_scores = {}
                for wn, sc in cursor.fetchall():
                    week_start = wn - ((wn - season_start) % 7)
                    if week_start not in week_scores:
                        week_scores[week_start] = []
                    week_scores[week_start].append(sc)
                
                # Sum best-5 from each past week (exclude current week)
                # Also count missed weeks (past weeks with fewer than 5 valid scores)
                past_total = 0
                player_missed = 0
                for ws_start, scores in week_scores.items():
                    if current_week_start and ws_start >= current_week_start:
                        continue  # Skip current week, handled via weekly_stats
                    valid = sorted([s for s in scores if s < 7])
                    best5 = sum(valid[:5]) if len(valid) >= 5 else sum(valid)
                    past_total += best5
                    if len(valid) < 5:
                        player_missed += 1
                
                # Also check past weeks where the player had zero scores
                # (they won't appear in week_scores at all)
                if current_week_start and season_start < current_week_start:
                    w = season_start
                    while w < current_week_start:
                        if w not in week_scores:
                            player_missed += 1
                        w += 7
                
                # Add current week's live best-5 total from weekly_stats
                current_week_score = 0
                if weekly_stats and p['name'] in weekly_stats:
                    ws = weekly_stats[p['name']]
                    if ws.get('used_scores', 0) > 0:
                        current_week_score = ws.get('best_5_total', 0)
                
                season_totals[p['name']] = past_total + current_week_score
                missed_weeks[p['name']] = player_missed
            else:
                season_totals[p['name']] = 0
                missed_weeks[p['name']] = 0
        
        division_data[div_num] = {
            'current_season': current_season,
            'season_start_week': season_start_week,
            'season_standings': season_standings,
            'season_winners': season_winners,
            'past_season_breakdowns': past_season_breakdowns,
            'players': div_players,
            'season_totals': season_totals,
            'missed_weeks': missed_weeks,
            'wins_needed': DIVISION_WINS
        }
    
    cursor.close()
    if own_conn:
        conn.close()
    
    return division_data


if __name__ == "__main__":
    # Test the adapter
    logging.basicConfig(level=logging.INFO)
    data = get_complete_league_data(6)
    print(f"\nToday: Wordle #{data['today_wordle']}")
    print(f"Week: {data['week_wordles'][0]}-{data['week_wordles'][6]} (Mon-Sun)")
    print(f"Players with scores: {len([p for p in data['latest_scores'].values() if p['score']])}")
    print(f"Weekly winner: {data['weekly_winner']['name'] if data['weekly_winner'] else 'TBD'}")
