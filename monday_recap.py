#!/usr/bin/env python3
"""
Monday Morning Recap - Runs at 10:00 AM Pacific on Mondays
Sends a recap of the previous week's results to all leagues:
- Weekly winner announcement
- Season clinch detection (4th win)
- Fun stats: first win of season, back-to-back wins, streaks, etc.
"""

import os
import sys
import logging
from datetime import datetime, date, timedelta
import pytz

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from league_data_adapter import get_db_connection, calculate_wordle_number, get_week_start_date
from season_management import get_weekly_wins_in_current_season
from message_router import send_league_message

WINS_FOR_SEASON_VICTORY = 4

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


def is_monday_recap_enabled(league_id):
    """Check if Monday recap is enabled for a league"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT ai_monday_recap FROM leagues WHERE id = %s", (league_id,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if result and result[0] is not None:
            return result[0]
        return True  # Default to enabled
    except Exception as e:
        logging.error(f"Error checking Monday recap setting: {e}")
        return True  # Default to enabled


def get_last_week_results(league_id):
    """Get the results from last week (the week that just ended Sunday)"""
    pacific = pytz.timezone('America/Los_Angeles')
    today = datetime.now(pacific).date()
    
    # Today is Monday, so last week was Monday-7 to Sunday-1
    last_monday = today - timedelta(days=7)
    last_sunday = today - timedelta(days=1)
    
    # Calculate Wordle numbers
    ref_date = date(2025, 7, 31)
    ref_wordle = 1503
    last_week_start_wordle = ref_wordle + (last_monday - ref_date).days
    last_week_end_wordle = ref_wordle + (last_sunday - ref_date).days
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get last week's winner(s) from weekly_winners table
        cursor.execute("""
            SELECT player_name, score
            FROM weekly_winners
            WHERE league_id = %s AND week_wordle_number = %s
            ORDER BY score ASC
        """, (league_id, last_week_start_wordle))
        
        winners = cursor.fetchall()
        
        if not winners:
            logging.info(f"No winners found for league {league_id} week {last_week_start_wordle}")
            return None
        
        winner_names = [w[0] for w in winners]
        winner_score = winners[0][1]
        
        # Get all player scores for last week for fun stats
        cursor.execute("""
            SELECT p.name, s.score, s.wordle_number
            FROM scores s
            JOIN players p ON s.player_id = p.id
            WHERE p.league_id = %s
              AND s.wordle_number >= %s
              AND s.wordle_number <= %s
              AND p.active = TRUE
            ORDER BY p.name, s.wordle_number
        """, (league_id, last_week_start_wordle, last_week_end_wordle))
        
        all_scores = cursor.fetchall()
        
        # Build per-player stats
        player_stats = {}
        for name, score, wordle_num in all_scores:
            if name not in player_stats:
                player_stats[name] = {'scores': [], 'games': 0, 'fails': 0}
            player_stats[name]['scores'].append(score)
            player_stats[name]['games'] += 1
            if score == 7:
                player_stats[name]['fails'] += 1
        
        # Get current season info and weekly wins
        cursor.execute("""
            SELECT current_season, season_start_week
            FROM league_seasons
            WHERE league_id = %s
        """, (league_id,))
        season_row = cursor.fetchone()
        current_season = season_row[0] if season_row else 1
        season_start_week = season_row[1] if season_row else last_week_start_wordle
        
        # Get weekly wins in current season (AFTER this week's winner was recorded)
        cursor.execute("""
            SELECT player_name, COUNT(*) as wins
            FROM weekly_winners
            WHERE league_id = %s AND week_wordle_number >= %s
            GROUP BY player_name
            ORDER BY wins DESC
        """, (league_id, season_start_week))
        
        season_wins = {}
        for row in cursor.fetchall():
            season_wins[row[0]] = row[1]
        
        # Check if a season was just clinched (someone hit 4 wins)
        # Look at season_winners table for the most recent entry
        cursor.execute("""
            SELECT p.name, sw.wins, sw.season_number, sw.completed_date
            FROM season_winners sw
            JOIN players p ON sw.player_id = p.id
            WHERE sw.league_id = %s
            ORDER BY sw.completed_date DESC NULLS LAST, sw.id DESC
            LIMIT 1
        """, (league_id,))
        
        latest_season_winner = cursor.fetchone()
        season_just_clinched = False
        season_clincher_name = None
        season_clincher_wins = None
        clinched_season_number = None
        
        if latest_season_winner:
            # Check if this was completed in the last week
            completed_date = latest_season_winner[3]
            if completed_date and completed_date >= last_monday:
                season_just_clinched = True
                season_clincher_name = latest_season_winner[0]
                season_clincher_wins = latest_season_winner[1]
                clinched_season_number = latest_season_winner[2]
        
        # Check for back-to-back wins
        # Get the winner of the week BEFORE last week
        two_weeks_ago_wordle = last_week_start_wordle - 7
        cursor.execute("""
            SELECT player_name FROM weekly_winners
            WHERE league_id = %s AND week_wordle_number = %s
        """, (league_id, two_weeks_ago_wordle))
        
        prev_week_winners = [r[0] for r in cursor.fetchall()]
        back_to_back = [name for name in winner_names if name in prev_week_winners]
        
        # Check for win streaks (3+ consecutive weeks)
        streak_info = {}
        for winner_name in winner_names:
            streak = 1
            check_week = last_week_start_wordle - 7
            while True:
                cursor.execute("""
                    SELECT 1 FROM weekly_winners
                    WHERE league_id = %s AND week_wordle_number = %s AND player_name = %s
                """, (league_id, check_week, winner_name))
                if cursor.fetchone():
                    streak += 1
                    check_week -= 7
                else:
                    break
            if streak >= 2:
                streak_info[winner_name] = streak
        
        # Check if this is someone's first win of the season
        first_win_of_season = [name for name in winner_names if season_wins.get(name, 0) == 1]
        
        # Find any perfect scores (1/6) from last week
        perfect_scores = []
        for name, stats in player_stats.items():
            if 1 in stats['scores']:
                perfect_scores.append(name)
        
        # Count total active players
        cursor.execute("""
            SELECT COUNT(*) FROM players WHERE league_id = %s AND active = TRUE
        """, (league_id,))
        total_players = cursor.fetchone()[0]
        
        # How many players participated last week
        participating_players = len(player_stats)
        
        # Get league display name
        cursor.execute("SELECT display_name, slug FROM leagues WHERE id = %s", (league_id,))
        league_info = cursor.fetchone()
        league_display_name = league_info[0] if league_info else f"League {league_id}"
        league_slug = league_info[1] if league_info else f"league{league_id}"
        
        return {
            'winner_names': winner_names,
            'winner_score': winner_score,
            'is_tie': len(winners) > 1,
            'player_stats': player_stats,
            'season_wins': season_wins,
            'current_season': current_season,
            'season_just_clinched': season_just_clinched,
            'season_clincher_name': season_clincher_name,
            'season_clincher_wins': season_clincher_wins,
            'clinched_season_number': clinched_season_number,
            'back_to_back': back_to_back,
            'streak_info': streak_info,
            'first_win_of_season': first_win_of_season,
            'perfect_scores': perfect_scores,
            'total_players': total_players,
            'participating_players': participating_players,
            'league_display_name': league_display_name,
            'league_slug': league_slug,
            'week_start': last_monday,
            'week_end': last_sunday,
        }
        
    except Exception as e:
        logging.error(f"Error getting last week results for league {league_id}: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return None
    finally:
        cursor.close()
        conn.close()


def send_monday_recap(league_id):
    """Send the Monday morning recap for a league"""
    
    if not is_monday_recap_enabled(league_id):
        logging.info(f"Monday recap disabled for league {league_id}")
        return False
    
    results = get_last_week_results(league_id)
    if not results:
        logging.info(f"No results to recap for league {league_id}")
        return False
    
    try:
        from openai import OpenAI
        openai_client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
        
        # Build the scenario text for the AI
        scenario_parts = []
        
        # Winner announcement
        if results['is_tie']:
            winner_list = " and ".join(results['winner_names'])
            scenario_parts.append(f"WEEKLY WINNER: {winner_list} TIED with a best-5 total of {results['winner_score']}! They share the win.")
        else:
            scenario_parts.append(f"WEEKLY WINNER: {results['winner_names'][0]} won the week with a best-5 total of {results['winner_score']}!")
        
        # Season clinch - THIS IS THE BIG ONE
        if results['season_just_clinched']:
            scenario_parts.append(f"🏆 SEASON CHAMPION: {results['season_clincher_name']} just clinched Season {results['clinched_season_number']} with {results['season_clincher_wins']} weekly wins! This is a HUGE accomplishment - a new season begins!")
        
        # Season standings context
        if results['season_wins']:
            standings = sorted(results['season_wins'].items(), key=lambda x: x[1], reverse=True)
            top_3 = standings[:3]
            standings_text = ", ".join([f"{name}: {wins} win{'s' if wins > 1 else ''}" for name, wins in top_3])
            scenario_parts.append(f"Season {results['current_season']} standings: {standings_text}")
        
        # Back-to-back wins
        if results['back_to_back']:
            for name in results['back_to_back']:
                streak = results['streak_info'].get(name, 2)
                if streak >= 3:
                    scenario_parts.append(f"🔥 {name} is on a {streak}-week WIN STREAK!")
                else:
                    scenario_parts.append(f"{name} won BACK-TO-BACK weeks!")
        
        # First win of the season
        if results['first_win_of_season']:
            for name in results['first_win_of_season']:
                if name not in results['back_to_back']:  # Don't double-mention
                    scenario_parts.append(f"{name} got their FIRST win of Season {results['current_season']}!")
        
        # Perfect scores
        if results['perfect_scores']:
            scenario_parts.append(f"Perfect score (1/6) last week by: {', '.join(results['perfect_scores'])}!")
        
        # Participation
        scenario_parts.append(f"{results['participating_players']} of {results['total_players']} players participated last week.")
        
        scenario_text = " ".join(scenario_parts)
        logging.info(f"League {league_id} Monday recap scenario: {scenario_text}")
        
        # Build the prompt
        if results['season_just_clinched']:
            prompt = f"It's Monday morning! Here's last week's Wordle league recap: {scenario_text} THE SEASON WAS JUST WON - make this the BIGGEST part of the message! Celebrate the season champion! Use emojis. Keep it under 400 characters. Lower scores are better in Wordle."
        else:
            prompt = f"It's Monday morning! Here's last week's Wordle league recap: {scenario_text} Announce the winner enthusiastically! Mention any notable stats. Use emojis. Keep it under 350 characters. Lower scores are better in Wordle."
        
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": """You are an exciting sports announcer for a Wordle league doing a Monday morning recap of last week's results. In Wordle, LOWER scores are BETTER (1/6 is perfect, 6/6 is barely made it).

IMPORTANT RULES:
1. Announce the weekly WINNER prominently - this is the main event!
2. If someone clinched the SEASON (4 weekly wins), make it a HUGE celebration - this is a major accomplishment!
3. Mention back-to-back wins, win streaks, or first wins of the season if provided
4. Keep the tone exciting and celebratory
5. Use emojis for excitement
6. Don't invent stats or names - only use what's provided
7. A best-5 total is the sum of their 5 best daily scores that week (lower = better)
8. If it's a tie, celebrate both/all winners equally"""},
                {"role": "user", "content": prompt}
            ],
            max_tokens=250,
            temperature=0.7
        )
        
        recap_message = response.choices[0].message.content.strip()
        logging.info(f"Generated Monday recap for league {league_id}: {recap_message}")
        
        # Add league URL
        league_url = f"https://app.wordplayleague.com/leagues/{results['league_slug']}"
        recap_with_url = f"{recap_message}\n\n📊 {league_url}"
        
        # Send via message router
        send_league_message(league_id, recap_with_url)
        
        logging.info(f"Sent Monday recap to league {league_id}")
        return True
        
    except Exception as e:
        logging.error(f"Error sending Monday recap for league {league_id}: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return False


def run_monday_recaps():
    """Run Monday recaps for all active leagues (dynamically from database)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, display_name, channel_type FROM leagues
            WHERE (twilio_conversation_sid IS NOT NULL OR slack_channel_id IS NOT NULL OR discord_channel_id IS NOT NULL)
            ORDER BY id
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        leagues = [(r[0], r[1], r[2] or 'sms') for r in rows]
        logging.info(f"Found {len(leagues)} active leagues for Monday recap: {[(l[0], l[1], l[2]) for l in leagues]}")
    except Exception as e:
        logging.error(f"Failed to fetch active leagues: {e}")
        return False
    
    all_success = True
    for league_id, league_name, channel_type in leagues:
        logging.info(f"Sending Monday recap for League {league_id} ({league_name}) [{channel_type}]")
        success = send_monday_recap(league_id)
        if not success:
            all_success = False
        
        # Add delay between leagues to avoid Twilio delivery queue issues
        import time
        time.sleep(2)
    
    return all_success


if __name__ == "__main__":
    # This script should be run at 10:00 AM Pacific on Mondays
    pacific = pytz.timezone('America/Los_Angeles')
    now = datetime.now(pacific)
    
    # Check if it's Monday
    if now.weekday() != 0:  # 0 = Monday
        print(f"Not Monday (today is {now.strftime('%A')}), skipping Monday recap")
        sys.exit(0)
    
    print("Starting Monday morning recap...")
    success = run_monday_recaps()
    if success:
        print("Monday recap completed successfully!")
        sys.exit(0)
    else:
        print("Monday recap had some failures!")
        sys.exit(1)
