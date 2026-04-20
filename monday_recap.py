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
        # Check if league is in division mode
        cursor.execute("SELECT division_mode FROM leagues WHERE id = %s", (league_id,))
        div_row = cursor.fetchone()
        is_division_mode = div_row and div_row[0]
        
        # Get last week's winner(s) from weekly_winners table
        if is_division_mode:
            # Fetch winners per division
            cursor.execute("""
                SELECT player_name, score, division
                FROM weekly_winners
                WHERE league_id = %s AND week_wordle_number = %s AND division IS NOT NULL
                ORDER BY division, score ASC
            """, (league_id, last_week_start_wordle))
        else:
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
        
        # Build division winners info if applicable
        division_winners = None
        if is_division_mode:
            division_winners = {1: [], 2: []}
            for row in winners:
                div_num = row[2]
                if div_num in division_winners:
                    division_winners[div_num].append({'name': row[0], 'score': row[1]})
            # Flatten for backward compat
            winner_names = [w[0] for w in winners]
            winner_score = winners[0][1]
        else:
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
        
        # ============================================================
        # DIVISION MODE: per-division season info
        # ============================================================
        division_season_wins = None
        division_season_clinched = None
        division_current_seasons = None
        
        if is_division_mode:
            division_season_wins = {1: {}, 2: {}}
            division_season_clinched = []
            division_current_seasons = {}
            
            for div_num in (1, 2):
                # Get division season info
                cursor.execute("""
                    SELECT current_season, season_start_week
                    FROM division_seasons
                    WHERE league_id = %s AND division = %s
                """, (league_id, div_num))
                div_season_row = cursor.fetchone()
                div_current_season = div_season_row[0] if div_season_row else 1
                div_season_start = div_season_row[1] if div_season_row else last_week_start_wordle
                division_current_seasons[div_num] = div_current_season
                
                # Get per-division weekly wins in current division season
                cursor.execute("""
                    SELECT player_name, COUNT(*) as wins
                    FROM weekly_winners
                    WHERE league_id = %s AND division = %s AND week_wordle_number >= %s
                    GROUP BY player_name
                    ORDER BY wins DESC
                """, (league_id, div_num, div_season_start))
                
                for row in cursor.fetchall():
                    division_season_wins[div_num][row[0]] = row[1]
                
                # Check if a division season was just clinched
                cursor.execute("""
                    SELECT p.name, sw.wins, sw.season_number, sw.completed_date, sw.division
                    FROM season_winners sw
                    JOIN players p ON sw.player_id = p.id
                    WHERE sw.league_id = %s AND sw.division = %s
                    ORDER BY sw.completed_date DESC NULLS LAST, sw.id DESC
                    LIMIT 1
                """, (league_id, div_num))
                div_latest = cursor.fetchone()
                if div_latest:
                    completed_date = div_latest[3]
                    if completed_date and completed_date > last_monday:
                        div_label = "Division I" if div_num == 1 else "Division II"
                        clinch_info = {
                            'division': div_num,
                            'division_label': div_label,
                            'name': div_latest[0],
                            'wins': div_latest[1],
                            'season_number': div_latest[2],
                        }
                        # Div II winner gets promoted
                        if div_num == 2:
                            clinch_info['promoted'] = True
                        division_season_clinched.append(clinch_info)
        
        # Get current season info and weekly wins (standard mode / fallback)
        cursor.execute("""
            SELECT current_season, season_start_week
            FROM league_seasons
            WHERE league_id = %s
        """, (league_id,))
        season_row = cursor.fetchone()
        current_season = season_row[0] if season_row else 1
        season_start_week = season_row[1] if season_row else last_week_start_wordle
        
        # Get weekly wins in current season (standard mode)
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
        
        # Check if a season was just clinched (someone hit 4 wins) - standard mode
        cursor.execute("""
            SELECT p.name, sw.wins, sw.season_number, sw.completed_date
            FROM season_winners sw
            JOIN players p ON sw.player_id = p.id
            WHERE sw.league_id = %s AND sw.division IS NULL
            ORDER BY sw.completed_date DESC NULLS LAST, sw.id DESC
            LIMIT 1
        """, (league_id,))
        
        latest_season_winner = cursor.fetchone()
        season_just_clinched = False
        season_clincher_name = None
        season_clincher_wins = None
        clinched_season_number = None
        
        if latest_season_winner:
            completed_date = latest_season_winner[3]
            if completed_date and completed_date > last_monday:
                season_just_clinched = True
                season_clincher_name = latest_season_winner[0]
                season_clincher_wins = latest_season_winner[1]
                clinched_season_number = latest_season_winner[2]
        
        # Check for back-to-back wins (division-aware)
        two_weeks_ago_wordle = last_week_start_wordle - 7
        if is_division_mode:
            cursor.execute("""
                SELECT player_name, division FROM weekly_winners
                WHERE league_id = %s AND week_wordle_number = %s AND division IS NOT NULL
            """, (league_id, two_weeks_ago_wordle))
        else:
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
        if is_division_mode:
            # Check per-division first wins
            first_win_of_season = []
            for div_num in (1, 2):
                dw = (division_winners or {}).get(div_num, [])
                for w in dw:
                    if division_season_wins.get(div_num, {}).get(w['name'], 0) == 1:
                        first_win_of_season.append(w['name'])
        else:
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
            'division_mode': is_division_mode,
            'division_winners': division_winners,
            'division_season_wins': division_season_wins,
            'division_season_clinched': division_season_clinched,
            'division_current_seasons': division_current_seasons,
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
        logging.info(f"Monday recap disabled for league {league_id}, skipping")
        return True
    
    results = get_last_week_results(league_id)
    if not results:
        logging.info(f"No results to recap for league {league_id}")
        return True
    
    try:
        from openai import OpenAI
        openai_client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
        
        # Build the scenario text for the AI
        scenario_parts = []
        is_div = results.get('division_mode', False)
        
        # ============================================================
        # DIVISION MODE scenario building
        # ============================================================
        if is_div and results.get('division_winners'):
            div_winners = results['division_winners']
            div_season_wins = results.get('division_season_wins', {})
            div_clinched = results.get('division_season_clinched', [])
            div_seasons = results.get('division_current_seasons', {})
            
            for div_num in (1, 2):
                div_label = "Division I" if div_num == 1 else "Division II"
                dw = div_winners.get(div_num, [])
                if not dw:
                    scenario_parts.append(f"{div_label}: No winner this week (not enough eligible players).")
                    continue
                
                # Winner announcement
                if len(dw) > 1:
                    names = " and ".join([w['name'] for w in dw])
                    scenario_parts.append(f"{div_label} WINNER: {names} TIED with a best-5 total of {dw[0]['score']}!")
                else:
                    scenario_parts.append(f"{div_label} WINNER: {dw[0]['name']} won with a best-5 total of {dw[0]['score']}!")
                
                # Per-division season standings
                dsw = div_season_wins.get(div_num, {})
                if dsw:
                    standings = sorted(dsw.items(), key=lambda x: x[1], reverse=True)
                    top_entries = standings[:4]
                    standings_text = ", ".join([f"{name}: {wins} win{'s' if wins > 1 else ''}" for name, wins in top_entries])
                    div_season_num = div_seasons.get(div_num, 1)
                    scenario_parts.append(f"{div_label} Season {div_season_num} standings: {standings_text}")
            
            # Division season clinch announcements
            for clinch in div_clinched:
                if clinch.get('promoted'):
                    scenario_parts.append(f"🏆 {clinch['division_label']} SEASON CHAMPION: {clinch['name']} clinched {clinch['division_label']} Season {clinch['season_number']} with {clinch['wins']} wins and earns a PROMOTION to Division I! A new season begins!")
                else:
                    scenario_parts.append(f"🏆 {clinch['division_label']} SEASON CHAMPION: {clinch['name']} clinched {clinch['division_label']} Season {clinch['season_number']} with {clinch['wins']} wins! The worst Season Total player in Division I gets RELEGATED to Division II. A new season begins!")
        
        # ============================================================
        # STANDARD MODE scenario building
        # ============================================================
        else:
            if results['is_tie']:
                winner_list = " and ".join(results['winner_names'])
                scenario_parts.append(f"WEEKLY WINNER: {winner_list} TIED with a best-5 total of {results['winner_score']}! They share the win.")
            else:
                scenario_parts.append(f"WEEKLY WINNER: {results['winner_names'][0]} won the week with a best-5 total of {results['winner_score']}!")
            
            # Standard season clinch
            if results['season_just_clinched']:
                scenario_parts.append(f"🏆 SEASON CHAMPION: {results['season_clincher_name']} just clinched Season {results['clinched_season_number']} with {results['season_clincher_wins']} weekly wins! This is a HUGE accomplishment - a new season begins!")
            
            # Standard season standings (skip if season was just clinched — new season just started)
            if results['season_wins'] and not results['season_just_clinched']:
                standings = sorted(results['season_wins'].items(), key=lambda x: x[1], reverse=True)
                top_3 = standings[:3]
                standings_text = ", ".join([f"{name}: {wins} win{'s' if wins > 1 else ''}" for name, wins in top_3])
                scenario_parts.append(f"Season {results['current_season']} standings: {standings_text}")
        
        # ============================================================
        # Shared stats (both modes)
        # ============================================================
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
                if name not in results['back_to_back']:
                    if is_div:
                        scenario_parts.append(f"{name} got their FIRST win of the division season!")
                    else:
                        scenario_parts.append(f"{name} got their FIRST win of Season {results['current_season']}!")
        
        # Perfect scores
        if results['perfect_scores']:
            scenario_parts.append(f"Perfect score (1/6) last week by: {', '.join(results['perfect_scores'])}!")
        
        # Participation
        scenario_parts.append(f"{results['participating_players']} of {results['total_players']} players participated last week.")
        
        scenario_text = " ".join(scenario_parts)
        logging.info(f"League {league_id} Monday recap scenario: {scenario_text}")
        
        # Build the prompt and system message
        has_div_clinch = is_div and results.get('division_season_clinched')
        
        if is_div:
            if has_div_clinch:
                prompt = f"It's Monday morning! Here's last week's Wordle league recap (DIVISIONS): {scenario_text} A DIVISION SEASON WAS JUST WON - make this the BIGGEST part of the message! Celebrate the champion! Use emojis. Keep it under 500 characters. Lower scores are better in Wordle."
            else:
                prompt = f"It's Monday morning! Here's last week's Wordle league recap (DIVISIONS): {scenario_text} Announce each division's winner separately! Mention any notable stats. Use emojis. Keep it under 500 characters. Lower scores are better in Wordle."
            
            system_msg = """You are an exciting sports announcer for a Wordle league with DIVISIONS doing a Monday morning recap. In Wordle, LOWER scores are BETTER (1/6 is perfect, 6/6 is barely made it).

IMPORTANT RULES:
1. Announce each division's weekly WINNER separately - Division I first, then Division II
2. If someone clinched a DIVISION SEASON (3 weekly wins), make it a HUGE celebration!
3. Division II season winners get PROMOTED to Division I! When a Division I season ends, the worst Season Total player gets RELEGATED to Division II.
4. Mention back-to-back wins, win streaks, or first wins if provided
5. Keep the tone exciting and celebratory
6. Use emojis for excitement
7. Don't invent stats or names - only use what's provided
8. A best-5 total is the sum of their 5 best daily scores that week (lower = better)
9. Structure: Division I recap, then Division II recap, then shared stats
10. Use line breaks between divisions
11. ABSOLUTELY FORBIDDEN PHRASES unless explicitly present in the scenario text: "locked", "out of contention", "out of the race", "eliminated", "in the hunt", "miracle comeback". Do not use these as filler.
12. NEVER invent win counts, season standings, or "X wins this season" claims unless those exact numbers appear in the scenario text. If not provided, do not mention season wins at all.
13. NEVER claim someone "clinched" a season or "won the season" unless the scenario text contains "SEASON CHAMPION" or "clinched". Winning a WEEK is different from winning the SEASON."""
        
        elif results['season_just_clinched']:
            prompt = f"It's Monday morning! Here's last week's Wordle league recap: {scenario_text} THE SEASON WAS JUST WON - make this the BIGGEST part of the message! Celebrate the season champion! Use emojis. Keep it under 400 characters. Lower scores are better in Wordle."
            
            system_msg = """You are an exciting sports announcer for a Wordle league doing a Monday morning recap of last week's results. In Wordle, LOWER scores are BETTER (1/6 is perfect, 6/6 is barely made it).

IMPORTANT RULES:
1. Announce the weekly WINNER prominently - this is the main event!
2. If someone clinched the SEASON (4 weekly wins), make it a HUGE celebration - this is a major accomplishment!
3. Mention back-to-back wins, win streaks, or first wins of the season if provided
4. Keep the tone exciting and celebratory
5. Use emojis for excitement
6. Don't invent stats or names - only use what's provided
7. A best-5 total is the sum of their 5 best daily scores that week (lower = better)
8. If it's a tie, celebrate both/all winners equally
9. When a season was just clinched, do NOT mention next season standings or win counts — the new season just started with 0 wins
10. NEVER invent or guess season standings — only mention them if explicitly provided in the scenario text
11. ABSOLUTELY FORBIDDEN PHRASES unless explicitly present in the scenario text: "locked", "out of contention", "out of the race", "eliminated", "in the hunt", "miracle comeback". Do not use these as filler.
12. NEVER invent win counts or "X wins this season" claims unless those exact numbers appear in the scenario text. If not provided, do not mention season wins at all."""
        
        else:
            prompt = f"It's Monday morning! Here's last week's Wordle league recap: {scenario_text} Announce the winner enthusiastically! Mention any notable stats. Use emojis. Keep it under 350 characters. Lower scores are better in Wordle."
            
            system_msg = """You are an exciting sports announcer for a Wordle league doing a Monday morning recap of last week's results. In Wordle, LOWER scores are BETTER (1/6 is perfect, 6/6 is barely made it).

IMPORTANT RULES:
1. Announce the weekly WINNER prominently - this is the main event!
2. If someone clinched the SEASON (4 weekly wins), make it a HUGE celebration - this is a major accomplishment!
3. Mention back-to-back wins, win streaks, or first wins of the season if provided
4. Keep the tone exciting and celebratory
5. Use emojis for excitement
6. Don't invent stats or names - only use what's provided
7. A best-5 total is the sum of their 5 best daily scores that week (lower = better)
8. If it's a tie, celebrate both/all winners equally
9. NEVER invent or guess season standings — only mention them if explicitly provided in the scenario text
10. ABSOLUTELY FORBIDDEN PHRASES unless explicitly present in the scenario text: "locked", "out of contention", "out of the race", "eliminated", "in the hunt", "miracle comeback". Do not use these as filler.
11. NEVER invent win counts or "X wins this season" claims unless those exact numbers appear in the scenario text. If not provided, do not mention season wins at all.
12. NEVER claim someone "clinched the season" or "won the season" unless the scenario text contains "SEASON CHAMPION" or "clinched". Winning a WEEK is different from winning the SEASON."""
        
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt}
            ],
            max_tokens=350 if is_div else 250,
            temperature=0.4
        )
        
        recap_message = response.choices[0].message.content.strip()
        logging.info(f"Generated Monday recap for league {league_id}: {recap_message}")
        
        # Add league URL
        league_url = f"https://{os.environ.get('RAILWAY_PUBLIC_DOMAIN', 'app.wordplayleague.com')}/leagues/{results['league_slug']}"
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


def save_twilio_monthly_snapshot():
    """Save current month's per-league Twilio usage data as a snapshot.
    Uses the Conversations API to get actual inbound/outbound per league.
    Called automatically every Monday to keep snapshots fresh."""
    import requests as http_requests
    from datetime import timezone as dt_timezone

    TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID', '')
    TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN', '')
    twilio_phone = os.environ.get('TWILIO_PHONE_NUMBER', '')

    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        logging.warning("Twilio credentials not set, skipping snapshot save")
        return

    auth = (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    pacific = pytz.timezone('America/Los_Angeles')
    now = datetime.now(pacific)
    month_key = now.strftime('%Y-%m')
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_start_utc = month_start.astimezone(dt_timezone.utc)

    conn = get_db_connection()
    cursor = conn.cursor()

    # Create table if needed
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS twilio_monthly_snapshots (
            id SERIAL PRIMARY KEY,
            month_key VARCHAR(7) NOT NULL,
            league_id INTEGER NOT NULL,
            league_name VARCHAR(255) NOT NULL,
            player_count INTEGER NOT NULL DEFAULT 0,
            inbound INTEGER NOT NULL DEFAULT 0,
            outbound_billed INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(month_key, league_id)
        )
    """)
    conn.commit()

    # Get all SMS leagues with conversation SIDs
    cursor.execute("""
        SELECT l.id, l.name, l.twilio_conversation_sid,
               (SELECT COUNT(*) FROM players p WHERE p.league_id = l.id AND p.active = TRUE) as player_count
        FROM leagues l
        WHERE l.twilio_conversation_sid IS NOT NULL
    """)
    sms_leagues = cursor.fetchall()

    saved = 0
    for league_id, league_name, conv_sid, player_count in sms_leagues:
        if not conv_sid:
            continue
        num_players = max(player_count or 1, 1)
        inbound = 0
        outbound = 0
        try:
            url = f"https://conversations.twilio.com/v1/Conversations/{conv_sid}/Messages?PageSize=100&Order=desc"
            done = False
            while url and not done:
                resp = http_requests.get(url, auth=auth, timeout=5)
                if resp.status_code != 200:
                    break
                data = resp.json()
                messages = data.get('messages', [])
                if not messages:
                    break
                for msg in messages:
                    date_str = msg.get('date_created', '')
                    if date_str:
                        msg_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                        if msg_date < month_start_utc:
                            done = True
                            break
                        author = msg.get('author', '')
                        if author == twilio_phone:
                            outbound += 1
                        else:
                            inbound += 1
                meta = data.get('meta', {})
                next_url = meta.get('next_page_url')
                url = next_url if next_url and not done else None
        except Exception as e:
            logging.warning(f"Snapshot: conv fetch failed for league {league_id}: {e}")
            continue

        if inbound == 0 and outbound == 0:
            continue

        outbound_billed = outbound * num_players

        cursor.execute("""
            INSERT INTO twilio_monthly_snapshots (month_key, league_id, league_name, player_count, inbound, outbound_billed)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (month_key, league_id)
            DO UPDATE SET league_name = EXCLUDED.league_name,
                          player_count = EXCLUDED.player_count,
                          inbound = EXCLUDED.inbound,
                          outbound_billed = EXCLUDED.outbound_billed,
                          created_at = CURRENT_TIMESTAMP
        """, (month_key, league_id, league_name, num_players, inbound, outbound_billed))
        saved += 1

    conn.commit()
    cursor.close()
    conn.close()

    logging.info(f"Twilio monthly snapshot saved for {month_key}: {saved} leagues")
    print(f"Twilio snapshot: saved {saved} leagues for {month_key}")


if __name__ == "__main__":
    # This script should be run at 10:00 AM Pacific on Mondays
    pacific = pytz.timezone('America/Los_Angeles')
    now = datetime.now(pacific)
    
    # Check if it's Monday
    if now.weekday() != 0:  # 0 = Monday
        print(f"Not Monday (today is {now.strftime('%A')}), skipping Monday recap")
        sys.exit(0)
    
    # DST-proof: Railway cron fires at both 17 and 18 UTC to cover PST/PDT.
    # Only run if it's actually 10:00 AM Pacific.
    if now.hour != 10:
        print(f"Not 10:00 AM Pacific (currently {now.strftime('%I:%M %p %Z')}), skipping")
        sys.exit(0)
    
    print("Starting Monday morning recap...")
    success = run_monday_recaps()
    
    # Auto-save Twilio monthly snapshot (runs every Monday to keep data fresh)
    try:
        save_twilio_monthly_snapshot()
    except Exception as e:
        logging.error(f"Twilio snapshot auto-save failed: {e}")
    
    if success:
        print("Monday recap completed successfully!")
        sys.exit(0)
    else:
        print("Monday recap had some failures!")
        sys.exit(1)
