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
        return psycopg2.connect(database_url)
    else:
        return psycopg2.connect(
            host=os.environ.get('PGHOST'),
            database=os.environ.get('PGDATABASE'),
            user=os.environ.get('PGUSER'),
            password=os.environ.get('PGPASSWORD'),
            port=os.environ.get('PGPORT', 5432)
        )

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

def get_all_league_players(league_id):
    """Get all active players in a league"""
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
    conn.close()
    
    return players

def get_latest_scores_for_display(league_id):
    """
    Get the most recent score for each player for the Latest Scores tab
    Returns: dict with player_name -> {score, emoji_pattern, wordle_num, date}
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get today's Wordle number
    today_wordle = calculate_wordle_number()
    
    # Get all players
    players = get_all_league_players(league_id)
    
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
    conn.close()
    
    return latest_scores, today_wordle

def get_weekly_stats(league_id):
    """
    Get weekly statistics using the Monday-Sunday week and best 5 scores rule
    This matches the logic from export_leaderboard.py
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get current week's Wordle numbers (Monday-Sunday)
    week_wordles = get_current_week_wordles()
    week_start = week_wordles[0]
    week_end = week_wordles[6]
    
    logging.info(f"Calculating weekly stats for league {league_id}, week {week_start}-{week_end} (Mon-Sun)")
    
    # Get all players
    players = get_all_league_players(league_id)
    
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
    conn.close()
    
    return weekly_stats, week_wordles

def get_all_time_stats(league_id):
    """Get all-time statistics for all players (including those with no scores)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get ALL players first
    players = get_all_league_players(league_id)
    
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
    conn.close()
    
    return stats

def get_complete_league_data(league_id):
    """
    Get all data needed for HTML generation
    This is the main function that combines everything
    """
    logging.info(f"Fetching complete data for league {league_id}")
    
    # Get latest scores for display
    latest_scores, today_wordle = get_latest_scores_for_display(league_id)
    
    # Get weekly stats
    weekly_stats, week_wordles = get_weekly_stats(league_id)
    
    # Get all-time stats
    all_time_stats = get_all_time_stats(league_id)
    
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
    
    # Get season data (will be populated by season_management module)
    season_data = get_season_data(league_id)
    
    return {
        'league_id': league_id,
        'today_wordle': today_wordle,
        'week_wordles': week_wordles,
        'latest_scores': latest_scores,
        'weekly_stats': weekly_stats,
        'weekly_winner': weekly_winner,
        'all_time_stats': all_time_stats,
        'season_data': season_data,
        'timestamp': datetime.now()
    }

def get_season_data(league_id):
    """Get season information from PostgreSQL"""
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
    
    # Get current season standings (weekly wins)
    # Only show weekly winners from current season (>= season_start_week)
    season_standings = {}
    if season_start_week:
        cursor.execute("""
            SELECT 
                ww.player_name,
                ww.week_wordle_number,
                ww.score
            FROM weekly_winners ww
            WHERE ww.league_id = %s AND ww.week_wordle_number >= %s
            ORDER BY ww.player_name, ww.week_wordle_number
        """, (league_id, season_start_week))
    else:
        # No season start week set, show all
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
    
    # Get past season winners
    cursor.execute("""
        SELECT sw.season_number, p.name, sw.wins
        FROM season_winners sw
        JOIN players p ON sw.player_id = p.id
        WHERE sw.league_id = %s
        ORDER BY sw.season_number DESC
    """, (league_id,))
    
    season_winners = []
    for row in cursor.fetchall():
        season_winners.append({
            'season': row[0],
            'name': row[1],
            'wins': row[2]
        })
    
    cursor.close()
    conn.close()
    
    return {
        'current_season': current_season,
        'season_standings': season_standings,
        'season_winners': season_winners
    }

if __name__ == "__main__":
    # Test the adapter
    logging.basicConfig(level=logging.INFO)
    data = get_complete_league_data(6)
    print(f"\nToday: Wordle #{data['today_wordle']}")
    print(f"Week: {data['week_wordles'][0]}-{data['week_wordles'][6]} (Mon-Sun)")
    print(f"Players with scores: {len([p for p in data['latest_scores'].values() if p['score']])}")
    print(f"Weekly winner: {data['weekly_winner']['name'] if data['weekly_winner'] else 'TBD'}")
