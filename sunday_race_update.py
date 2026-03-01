#!/usr/bin/env python3
"""
Sunday Race Update - Runs at 10:00 AM Pacific on Sundays
Sends an exciting weekly race update to all leagues showing:
- Current leader(s)
- Who hasn't posted yet
- What scores they need to tie/win
"""

import os
import sys
import logging
import requests
import base64
from datetime import datetime, date, timedelta
import pytz

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from league_data_adapter import get_db_connection, calculate_wordle_number, get_week_start_date
from season_management import get_weekly_wins_in_current_season
from image_generator import generate_weekly_image, generate_season_image, generate_division_weekly_image, image_to_bytes

WINS_FOR_SEASON_VICTORY = 4

# Twilio MCS (Media Content Service) for uploading images
TWILIO_MCS_URL = "https://mcs.us1.twilio.com/v1/Services/{service_sid}/Media"

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

def get_weekly_standings(league_id, week_start_wordle):
    """Get current weekly standings for a league - uses BEST 5 scores like weekly winner calc"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    MIN_GAMES_FOR_RANKING = 5  # Must have at least 5 games to be in the running
    BEST_N_SCORES = 5  # Use best (lowest) 5 scores for ranking
    
    try:
        # Get all active players (include division assignment)
        cursor.execute("""
            SELECT id, name, division FROM players 
            WHERE league_id = %s AND active = TRUE
            ORDER BY name
        """, (league_id,))
        players = cursor.fetchall()
        
        # Get today's Wordle number
        pacific = pytz.timezone('America/Los_Angeles')
        today = datetime.now(pacific).date()
        ref_date = date(2025, 7, 31)
        ref_wordle = 1503
        days_offset = (today - ref_date).days
        todays_wordle = ref_wordle + days_offset
        
        standings = []
        
        for player_id, player_name, player_division in players:
            # Get all scores for this week
            cursor.execute("""
                SELECT wordle_number, score 
                FROM scores 
                WHERE player_id = %s 
                AND wordle_number >= %s 
                AND wordle_number <= %s
                ORDER BY wordle_number
            """, (player_id, week_start_wordle, todays_wordle))
            
            scores = cursor.fetchall()
            score_dict = {w: s for w, s in scores}
            score_values = [s for w, s in scores]
            
            # Calculate best 5 total (lowest scores are best)
            # IMPORTANT: Exclude failed attempts (score 7) from best 5 calculation
            days_posted = len(scores)
            posted_today = todays_wordle in score_dict
            failed_attempts = sum(1 for s in score_values if s == 7)
            non_fail_scores = [s for s in score_values if s != 7]
            
            # Sort non-fail scores ascending and take best 5
            sorted_scores = sorted(non_fail_scores)
            best_5_scores = sorted_scores[:BEST_N_SCORES]
            
            # Calculate thrown out scores (scores beyond best 5)
            thrown_out = sorted_scores[BEST_N_SCORES:] if len(sorted_scores) > BEST_N_SCORES else []
            
            # Only eligible if they have 5+ non-fail scores
            eligible = len(non_fail_scores) >= MIN_GAMES_FOR_RANKING
            best_5_total = sum(best_5_scores) if eligible else None
            
            standings.append({
                'player_id': player_id,
                'name': player_name,
                'division': player_division,
                'best_5_total': best_5_total,
                'days_posted': days_posted,
                'posted_today': posted_today,
                'scores': score_dict,
                'eligible': eligible,
                'failed_attempts': failed_attempts,
                'thrown_out': thrown_out
            })
        
        cursor.close()
        conn.close()
        
        # Separate eligible (5+ games) from ineligible
        eligible = [s for s in standings if s['eligible']]
        ineligible = [s for s in standings if not s['eligible']]
        
        # Sort eligible by best_5_total (lowest is best)
        eligible.sort(key=lambda x: x['best_5_total'])
        
        # Sort ineligible by days_posted descending (most games first), then by score
        # Calculate non-fail score for sorting
        for p in ineligible:
            non_fail_scores = [s for s in p['scores'].values() if s != 7]
            p['current_total'] = sum(sorted(non_fail_scores)[:5]) if non_fail_scores else 999
        
        ineligible.sort(key=lambda x: (-x['days_posted'], x['current_total']))
        
        # Combine: eligible first, then ineligible
        standings = eligible + ineligible
        
        logging.info(f"Sorted standings: {[(s['name'], s['days_posted'], s.get('current_total', s.get('best_5_total'))) for s in standings]}")
        
        return standings, todays_wordle
        
    except Exception as e:
        logging.error(f"Error getting weekly standings: {e}")
        cursor.close()
        conn.close()
        return [], None

def get_score_difficulty_text(score_needed):
    """Return realistic language based on how difficult the score needed is"""
    if score_needed == 1:
        return "needs a near-impossible 1 (hail mary!)"
    elif score_needed == 2:
        return "needs an amazing 2"
    elif score_needed == 3:
        return "needs a solid 3"
    elif score_needed == 4:
        return "needs a 4"
    elif score_needed == 5:
        return "needs a 5"
    elif score_needed == 6:
        return "needs a 6 (just barely!)"
    else:
        return f"needs a {score_needed}"

def get_catch_up_text(player_name, score_to_win, score_to_tie, current_total=None, games_count=None):
    """Generate catch-up scenario text with realistic language"""
    context = ""
    if current_total is not None and games_count is not None:
        context = f" (at {current_total} with {games_count} games)"
    elif current_total is not None:
        context = f" (at {current_total})"
    
    if score_to_win >= 1 and score_to_win <= 6:
        win_text = get_score_difficulty_text(score_to_win)
        if score_to_tie >= 1 and score_to_tie <= 6 and score_to_tie != score_to_win:
            tie_text = get_score_difficulty_text(score_to_tie).replace("needs ", "")
            return f"{player_name}{context} {win_text} to win or {tie_text} to tie"
        return f"{player_name}{context} {win_text} to win"
    elif score_to_tie >= 1 and score_to_tie <= 6:
        tie_text = get_score_difficulty_text(score_to_tie)
        return f"{player_name}{context} {tie_text} to tie"
    elif score_to_tie > 6 or score_to_tie <= 0:
        return f"{player_name}{context} is mathematically eliminated"
    return None

def calculate_what_they_need(leader_best_5, player_best_5, player_days_posted):
    """Calculate what score a player needs to tie or win
    
    Logic: If player has 5+ games, their best 5 is locked in.
    If player has <5 games, they need more games to qualify.
    If player has exactly 5 games and hasn't posted today, a new score could replace their worst.
    """
    if player_best_5 is None:
        # Player doesn't have 5 games yet - can't calculate
        return {'needs_more_games': True, 'games_needed': 5 - player_days_posted}
    
    # Player has 5+ games - calculate what they need
    diff = player_best_5 - leader_best_5
    
    if diff <= 0:
        # Already tied or winning
        return {'already_winning': True}
    
    # They need to improve by 'diff' points
    # A score of X would replace their worst score in best 5
    return {
        'points_behind': diff,
        'to_tie': diff,  # Need to make up this many points
        'to_win': diff + 1  # Need to beat by 1
    }

def upload_image_to_twilio(image_bytes, twilio_sid, twilio_token, chat_service_sid):
    """Upload an image to Twilio MCS and return the Media SID"""
    try:
        url = TWILIO_MCS_URL.format(service_sid=chat_service_sid)
        
        response = requests.post(
            url,
            auth=(twilio_sid, twilio_token),
            data=image_bytes,
            headers={'Content-Type': 'image/png'}
        )
        
        if response.status_code == 201:
            media_data = response.json()
            media_sid = media_data.get('sid')
            logging.info(f"Uploaded image to Twilio MCS: {media_sid}")
            return media_sid
        else:
            logging.error(f"Failed to upload image to Twilio MCS: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logging.error(f"Error uploading image to Twilio: {e}")
        return None

def is_ai_message_enabled(league_id, message_type):
    """Check if a specific AI message type is enabled for a league"""
    import psycopg2
    try:
        database_url = os.environ.get('DATABASE_URL')
        if database_url:
            conn = psycopg2.connect(database_url)
        else:
            conn = psycopg2.connect(
                host=os.environ.get('PGHOST'),
                database=os.environ.get('PGDATABASE'),
                user=os.environ.get('PGUSER'),
                password=os.environ.get('PGPASSWORD'),
                port=os.environ.get('PGPORT', 5432)
            )
        
        cursor = conn.cursor()
        column_map = {
            'perfect_score': 'ai_perfect_score_congrats',
            'failure_roast': 'ai_failure_roast',
            'sunday_race': 'ai_sunday_race_update',
            'daily_loser': 'ai_daily_loser_roast'
        }
        column = column_map.get(message_type)
        if not column:
            cursor.close()
            conn.close()
            return False
        
        cursor.execute(f"SELECT {column} FROM leagues WHERE id = %s", (league_id,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if result and result[0] is not None:
            return result[0]
        
        # Default values
        defaults = {'sunday_race': True}
        return defaults.get(message_type, False)
    except Exception as e:
        logging.error(f"Error checking AI message setting: {e}")
        return True  # Default to enabled for sunday_race

DIVISION_WINS_FOR_SEASON = 3  # Division seasons require 3 wins (not 4)

def build_division_scenario(div_standings, div_num, div_weekly_wins, div_current_season):
    """Build scenario analysis text for a single division.
    Returns scenario text string for the AI prompt."""
    div_label = "Division I" if div_num == 1 else "Division II"
    
    eligible = [s for s in div_standings if s['eligible']]
    ineligible = [s for s in div_standings if not s['eligible']]
    
    if not eligible:
        return f"{div_label}: No one has played 5 games yet to qualify for the weekly win."
    
    if len(eligible) == 1:
        winner = eligible[0]
        return f"{div_label}: {winner['name']} has this week LOCKED at {winner['best_5_total']}! No one else has enough scores to compete."
    
    # Find leader(s)
    leader_total = eligible[0]['best_5_total']
    leaders = [s for s in eligible if s['best_5_total'] == leader_total]
    leader_names = [s['name'] for s in leaders]
    
    all_eligible_posted = all(s['posted_today'] for s in eligible)
    all_posted = all(s['posted_today'] for s in div_standings)
    not_posted_today = [s for s in div_standings if not s['posted_today']]
    
    # Check who can catch up
    players_who_can_catch_up = []
    catch_up_scenarios = []
    eliminated = []
    
    for player in not_posted_today:
        if player['name'] in leader_names:
            continue
        if player['eligible']:
            diff = player['best_5_total'] - leader_total
            if diff > 0:
                non_fail_scores = [s for s in player['scores'].values() if s != 7]
                sorted_scores = sorted(non_fail_scores)[:5]
                if sorted_scores:
                    worst_best_5 = sorted_scores[-1]
                    score_to_tie = worst_best_5 - diff
                    score_to_win = worst_best_5 - diff - 1
                    text = get_catch_up_text(player['name'], score_to_win, score_to_tie, player['best_5_total'])
                    if text:
                        if "eliminated" in text:
                            eliminated.append(player['name'])
                        else:
                            players_who_can_catch_up.append(player['name'])
                            catch_up_scenarios.append(text)
        elif player['days_posted'] >= 4:
            non_fail_scores = [s for s in player['scores'].values() if s != 7]
            if len(non_fail_scores) == 4:
                current_total = sum(sorted(non_fail_scores)[:4])
                score_to_tie = leader_total - current_total
                score_to_win = score_to_tie - 1
                if score_to_tie <= 0:
                    eliminated.append(player['name'])
                else:
                    text = get_catch_up_text(player['name'], score_to_win, score_to_tie, current_total, 4)
                    if text:
                        if "eliminated" in text:
                            eliminated.append(player['name'])
                        else:
                            players_who_can_catch_up.append(player['name'])
                            catch_up_scenarios.append(text)
    
    race_is_decided = all_eligible_posted and len(players_who_can_catch_up) == 0
    
    # Build scenario
    scenarios = []
    if all_posted or race_is_decided:
        if len(leaders) > 1:
            leader_list = " and ".join(leader_names)
            scenarios.append(f"RACE OVER! {leader_list} are tied at {leader_total} and will share the weekly win!")
        else:
            scenarios.append(f"RACE OVER! {leader_names[0]} wins the week with {leader_total}!")
    elif len(leaders) == 1:
        leader_text = f"{leader_names[0]} leads at {leader_total}"
        if catch_up_scenarios:
            scenarios.append(f"{leader_text}. " + ". ".join(catch_up_scenarios[:3]))
        elif all_eligible_posted:
            scenarios.append(f"{leader_names[0]} is the clear winner at {leader_total}!")
        else:
            scenarios.append(leader_text)
    else:
        leader_text = f"{' and '.join(leader_names)} tied at {leader_total}"
        if catch_up_scenarios:
            scenarios.append(f"{leader_text}. " + ". ".join(catch_up_scenarios[:3]))
        else:
            scenarios.append(leader_text)
    
    # Season clinch detection for this division
    season_clinch_text = ""
    potential_clinchers = [name for name, wins in div_weekly_wins.items() if wins == DIVISION_WINS_FOR_SEASON - 1]
    leaders_who_could_clinch = [name for name in leader_names if name in potential_clinchers]
    
    if race_is_decided or all_posted:
        # Race is over — only mention clinch if the potential clincher actually WON (or tied for the win)
        actual_clinchers = [name for name in leaders_who_could_clinch]
        if actual_clinchers:
            if len(actual_clinchers) == 1:
                clincher = actual_clinchers[0]
                if div_num == 2:
                    season_clinch_text = f" SEASON CLINCH: {clincher} clinches {div_label} Season {div_current_season} and earns a PROMOTION to Division I!"
                else:
                    season_clinch_text = f" SEASON CLINCH: {clincher} clinches {div_label} Season {div_current_season}!"
            else:
                clinchers_list = " and ".join(actual_clinchers)
                if div_num == 2:
                    season_clinch_text = f" SEASON CLINCH: {clinchers_list} clinch {div_label} Season {div_current_season} and earn a PROMOTION to Division I!"
                else:
                    season_clinch_text = f" SEASON CLINCH: {clinchers_list} clinch {div_label} Season {div_current_season}!"
        # If potential clinchers exist but didn't win, no clinch text — they didn't clinch
    else:
        # Race is still live — only mention clinch for players who haven't posted today
        not_posted_names = {p['name'] for p in div_standings if not p['posted_today']}
        
        if leaders_who_could_clinch:
            # Leaders who haven't posted yet could still clinch
            leaders_still_live = [name for name in leaders_who_could_clinch if name in not_posted_names]
            # Leaders who already posted and are leading — they're on track
            leaders_already_posted = [name for name in leaders_who_could_clinch if name not in not_posted_names]
            
            clinch_names = leaders_already_posted + leaders_still_live  # posted leaders are ahead, still valid
            if clinch_names:
                if len(clinch_names) == 1:
                    clincher = clinch_names[0]
                    if div_num == 2:
                        season_clinch_text = f" SEASON STAKES: If {clincher} wins this week, they clinch {div_label} Season {div_current_season} and earn a PROMOTION to Division I!"
                    else:
                        season_clinch_text = f" SEASON STAKES: If {clincher} wins this week, they clinch {div_label} Season {div_current_season}!"
                else:
                    clinchers_list = " or ".join(clinch_names)
                    if div_num == 2:
                        season_clinch_text = f" SEASON STAKES: If {clinchers_list} wins this week, they clinch {div_label} Season {div_current_season} and earn a PROMOTION to Division I!"
                    else:
                        season_clinch_text = f" SEASON STAKES: If {clinchers_list} wins this week, they clinch {div_label} Season {div_current_season}!"
        else:
            # Check contenders not currently leading who haven't posted yet
            contenders = [name for name in potential_clinchers if name not in leader_names and name in not_posted_names]
            contenders_in_hunt = []
            for p in div_standings:
                if p['name'] in contenders and (p['eligible'] or p['days_posted'] >= 4):
                    contenders_in_hunt.append(p['name'])
            if contenders_in_hunt:
                clinchers_list = " or ".join(contenders_in_hunt[:2])
                if div_num == 2:
                    season_clinch_text = f" SEASON STAKES: {clinchers_list} could clinch {div_label} Season {div_current_season} with a win — earning a PROMOTION to Division I!"
                else:
                    season_clinch_text = f" SEASON STAKES: {clinchers_list} could clinch {div_label} Season {div_current_season} with a win!"
    
    scenario_text = f"{div_label}: " + " ".join(scenarios) + season_clinch_text
    return scenario_text


def send_sunday_race_update(league_id, force_season_image=False):
    """Send the Sunday race update message with precise scenario analysis
    
    Args:
        league_id: The league to send the update to
        force_season_image: If True, always send season image (for testing)
    """
    # Check if Sunday race update is enabled for this league
    if not is_ai_message_enabled(league_id, 'sunday_race'):
        logging.info(f"Sunday race update disabled for league {league_id}")
        return False
    
    try:
        from openai import OpenAI
        from message_router import send_league_message
        
        # Get environment variables
        openai_client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
        
        # Get league info from database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT channel_type, twilio_conversation_sid, display_name, slug, division_mode FROM leagues WHERE id = %s", (league_id,))
        league_row = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not league_row:
            logging.error(f"League {league_id} not found")
            return False
        
        channel_type = league_row[0] or 'sms'
        conversation_sid = league_row[1]
        league_display_name = league_row[2] or f"League {league_id}"
        is_division_mode = league_row[4] or False
        league_slug = league_row[3] or f"league{league_id}"
        league_url = f"https://app.wordplayleague.com/leagues/{league_slug}"
        
        # Get week start
        pacific = pytz.timezone('America/Los_Angeles')
        today = datetime.now(pacific).date()
        week_start = get_week_start_date(today)
        ref_date = date(2025, 7, 31)
        ref_wordle = 1503
        days_offset = (week_start - ref_date).days
        week_start_wordle = ref_wordle + days_offset
        
        # Get standings
        standings, todays_wordle = get_weekly_standings(league_id, week_start_wordle)
        
        if not standings:
            logging.warning(f"No standings data for league {league_id}")
            return False
        
        # ============================================================
        # DIVISION MODE: separate analysis per division
        # ============================================================
        if is_division_mode:
            from division_manager import get_division_weekly_wins, get_division_season_info
            
            # Split standings by division
            div1_standings = sorted(
                [s for s in standings if s.get('division') == 1],
                key=lambda x: (not x['eligible'], x['best_5_total'] if x['best_5_total'] is not None else 999)
            )
            div2_standings = sorted(
                [s for s in standings if s.get('division') == 2],
                key=lambda x: (not x['eligible'], x['best_5_total'] if x['best_5_total'] is not None else 999)
            )
            
            logging.info(f"Division mode: Div I has {len(div1_standings)} players, Div II has {len(div2_standings)} players")
            
            # Get per-division weekly wins and season info
            div1_weekly_wins = get_division_weekly_wins(league_id, 1)
            div2_weekly_wins = get_division_weekly_wins(league_id, 2)
            div1_season_info = get_division_season_info(league_id, 1)
            div2_season_info = get_division_season_info(league_id, 2)
            
            # Build per-division scenario text
            div1_scenario = build_division_scenario(div1_standings, 1, div1_weekly_wins, div1_season_info['current_season'])
            div2_scenario = build_division_scenario(div2_standings, 2, div2_weekly_wins, div2_season_info['current_season'])
            
            scenario_text = f"{div1_scenario}\n\n{div2_scenario}"
            logging.info(f"League {league_id} division scenarios: {scenario_text}")
            
            has_season_stakes = "SEASON STAKES" in scenario_text
            
            if has_season_stakes:
                prompt = f"It's Sunday morning Wordle race update for a league with DIVISIONS! Give a brief update for EACH division separately. {scenario_text} THIS IS HUGE - MENTION THE SEASON STAKES! Make it exciting with emojis! Keep it under 500 characters. Lower scores are better in Wordle."
            else:
                prompt = f"It's Sunday morning Wordle race update for a league with DIVISIONS! Give a brief update for EACH division separately. {scenario_text} Make it exciting with emojis! Keep it under 500 characters. Lower scores are better in Wordle."
            
            sunday_system_msg = """You are an exciting sports announcer for a Wordle league with DIVISIONS. In Wordle, LOWER scores are BETTER (1/6 is perfect, 6/6 is barely made it).

IMPORTANT RULES:
1. Convey the EXACT scenario given - don't change numbers, names, or math
2. A score of 1 is nearly impossible (hail mary), 2 is amazing/difficult, 3 is solid, 4-6 are more achievable
3. If someone is "eliminated" or "out of contention", they cannot win even with a perfect score
4. Don't say someone can "take the lead" or "catapult into first" unless the math actually supports it
5. Focus on players who realistically CAN still win or tie
6. Include SEASON STAKES info if provided - this is CRITICAL context about clinching the season! Always mention it prominently!
7. Use emojis for excitement!
8. NEVER say "can anyone catch up?" or "stay tuned" or "will anyone challenge" when the scenario says "RACE OVER" - the race is DECIDED, declare the winner definitively!
9. When someone clinches the SEASON (not just the week), make it a BIG DEAL - this is a major accomplishment!
10. This league has DIVISIONS (Division I and Division II) competing separately. Each division has its own weekly winner and its own season.
11. Division seasons require 3 wins (not 4). Winning a Division II season earns a PROMOTION to Division I! When a Division I season ends, the worst player gets RELEGATED to Division II.
12. Structure your message with Division I first, then Division II. Use line breaks between divisions."""
            
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": sunday_system_msg},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=350,
                temperature=0.7
            )
            
            race_message = response.choices[0].message.content.strip()
            logging.info(f"Generated division Sunday race update for league {league_id}: {race_message}")
        
        # ============================================================
        # STANDARD MODE: single league analysis (existing logic)
        # ============================================================
        else:
            # Find eligible players (5+ games) and their leader
            eligible = [s for s in standings if s['eligible']]
            
            # Get current weekly wins for season clinching detection
            weekly_wins, current_season = get_weekly_wins_in_current_season(league_id)
            
            # Find players who could clinch the season with a win this week (currently at 3 wins)
            potential_season_clinchers = [name for name, wins in weekly_wins.items() if wins == WINS_FOR_SEASON_VICTORY - 1]
            
            if not eligible:
                logging.info(f"No eligible players (5+ games) in league {league_id} - sending 'no winner this week' message")
                prompt = "It's Sunday! No one has played 5 games yet this week to qualify for the weekly win. You need at least 5 scores to compete! Looks like no one can claim victory this week. Use emojis. Keep it under 200 characters."
            elif len(eligible) == 1:
                # Only one eligible player - they have it locked!
                winner = eligible[0]
                logging.info(f"Only one eligible player in league {league_id}: {winner['name']} has it locked")
                prompt = f"It's Sunday morning Wordle race update! {winner['name']} has this week LOCKED at {winner['best_5_total']}! No one else has enough scores to compete. Congratulate the winner! Use emojis. Keep it under 200 characters."
            else:
                # Find current leader(s) among eligible players
                leader_total = eligible[0]['best_5_total']
                leaders = [s for s in eligible if s['best_5_total'] == leader_total]
                leader_names = [s['name'] for s in leaders]
                
                # Check if all eligible players have posted today
                all_eligible_posted = all(s['posted_today'] for s in eligible)
                
                # Check if ALL players in the league have posted today (race is completely over)
                all_players_posted = all(s['posted_today'] for s in standings)
                
                # Check players who haven't posted today but could still qualify or catch up
                not_posted_today = [s for s in standings if not s['posted_today']]
                
                logging.info(f"League {league_id} scenario analysis: eligible={len(eligible)}, leaders={leader_names}, all_eligible_posted={all_eligible_posted}, all_players_posted={all_players_posted}, not_posted_today={[p['name'] for p in not_posted_today]}")
                
                # SCENARIO ANALYSIS
                scenarios = []
                
                # Check if any non-posted players can realistically catch up
                players_who_can_catch_up = []
                for player in not_posted_today:
                    if player['name'] in leader_names:
                        continue
                    if player['eligible']:
                        diff = player['best_5_total'] - leader_total
                        if diff > 0:
                            non_fail_scores = [s for s in player['scores'].values() if s != 7]
                            sorted_scores = sorted(non_fail_scores)[:5]
                            if sorted_scores:
                                worst_best_5 = sorted_scores[-1]
                                score_to_tie = worst_best_5 - diff
                                if score_to_tie >= 1 and score_to_tie <= 6:
                                    players_who_can_catch_up.append(player['name'])
                    elif player['days_posted'] >= 4:
                        non_fail_scores = [s for s in player['scores'].values() if s != 7]
                        if len(non_fail_scores) == 4:
                            current_total = sum(sorted(non_fail_scores)[:4])
                            score_to_tie = leader_total - current_total
                            if score_to_tie >= 1 and score_to_tie <= 6:
                                players_who_can_catch_up.append(player['name'])
                
                race_is_decided = all_eligible_posted and len(players_who_can_catch_up) == 0
                
                if all_players_posted or race_is_decided:
                    if len(leaders) > 1:
                        leader_list = " and ".join(leader_names)
                        scenarios.append(f"RACE OVER! {leader_list} are tied at {leader_total} and will share the weekly win!")
                    else:
                        scenarios.append(f"RACE OVER! {leader_names[0]} wins the week with {leader_total}! Congratulations!")
                
                elif len(leaders) > 1 and all_eligible_posted and not not_posted_today:
                    leader_list = " and ".join(leader_names)
                    scenarios.append(f"{leader_list} are tied at {leader_total} and will share the win!")
                
                elif len(leaders) == 1 and all_eligible_posted:
                    can_catch_up = []
                    eliminated = []
                    for player in not_posted_today:
                        if player['eligible']:
                            diff = player['best_5_total'] - leader_total
                            if diff > 0:
                                non_fail_scores = [s for s in player['scores'].values() if s != 7]
                                sorted_scores = sorted(non_fail_scores)[:5]
                                if sorted_scores:
                                    worst_best_5 = sorted_scores[-1]
                                    score_to_tie = worst_best_5 - diff
                                    score_to_win = worst_best_5 - diff - 1
                                    text = get_catch_up_text(player['name'], score_to_win, score_to_tie, player['best_5_total'])
                                    if text:
                                        if "eliminated" in text:
                                            eliminated.append(player['name'])
                                        else:
                                            can_catch_up.append(text)
                        elif player['days_posted'] >= 4:
                            non_fail_scores = [s for s in player['scores'].values() if s != 7]
                            non_fail_count = len(non_fail_scores)
                            if non_fail_count == 4:
                                current_total = sum(sorted(non_fail_scores)[:4])
                                score_to_tie = leader_total - current_total
                                score_to_win = score_to_tie - 1
                                if score_to_tie <= 0:
                                    eliminated.append(player['name'])
                                else:
                                    text = get_catch_up_text(player['name'], score_to_win, score_to_tie, current_total, 4)
                                    if text:
                                        if "eliminated" in text:
                                            eliminated.append(player['name'])
                                        else:
                                            can_catch_up.append(text)
                            elif non_fail_count < 4:
                                eliminated.append(player['name'])
                    
                    if can_catch_up:
                        scenarios.append(f"{leader_names[0]} leads at {leader_total}. " + ". ".join(can_catch_up))
                    elif eliminated:
                        scenarios.append(f"{leader_names[0]} is the clear winner at {leader_total}! {', '.join(eliminated)} eliminated.")
                    else:
                        scenarios.append(f"{leader_names[0]} is the clear winner at {leader_total}!")
                
                else:
                    if len(leaders) == 1:
                        leader_text = f"{leader_names[0]} leads at {leader_total}"
                    else:
                        leader_text = f"{' and '.join(leader_names)} tied at {leader_total}"
                    
                    catch_up_scenarios = []
                    eliminated = []
                    for player in not_posted_today:
                        if player['name'] in leader_names:
                            continue
                        if player['eligible']:
                            diff = player['best_5_total'] - leader_total
                            if diff > 0:
                                non_fail_scores = [s for s in player['scores'].values() if s != 7]
                                sorted_scores = sorted(non_fail_scores)[:5]
                                if sorted_scores:
                                    worst_best_5 = sorted_scores[-1]
                                    score_to_tie = worst_best_5 - diff
                                    score_to_win = worst_best_5 - diff - 1
                                    text = get_catch_up_text(player['name'], score_to_win, score_to_tie, player['best_5_total'])
                                    if text:
                                        if "eliminated" in text:
                                            eliminated.append(player['name'])
                                        else:
                                            catch_up_scenarios.append(text)
                        elif player['days_posted'] >= 4:
                            non_fail_scores = [s for s in player['scores'].values() if s != 7]
                            non_fail_count = len(non_fail_scores)
                            if non_fail_count == 4:
                                current_total = sum(sorted(non_fail_scores)[:4])
                                score_to_tie = leader_total - current_total
                                score_to_win = score_to_tie - 1
                                if score_to_tie <= 0:
                                    eliminated.append(player['name'])
                                else:
                                    text = get_catch_up_text(player['name'], score_to_win, score_to_tie, current_total, 4)
                                    if text:
                                        if "eliminated" in text:
                                            eliminated.append(player['name'])
                                        else:
                                            catch_up_scenarios.append(text)
                            elif non_fail_count < 4:
                                eliminated.append(player['name'])
                    
                    scenario_parts = [leader_text]
                    if catch_up_scenarios:
                        scenario_parts.append(". ".join(catch_up_scenarios[:3]))
                    elif not catch_up_scenarios and len(eligible) > 1:
                        other_eligible = [p for p in eligible if p['name'] not in leader_names]
                        if other_eligible and all(p['posted_today'] for p in other_eligible):
                            scenario_parts.append(f"No one else can catch up - {leader_names[0]} has this locked!")
                    
                    scenarios.append(". ".join(scenario_parts))
                
                # Season clinch detection
                season_clinch_text = ""
                leaders_who_could_clinch = [name for name in leader_names if name in potential_season_clinchers]
                
                if len(potential_season_clinchers) >= 2:
                    clinchers_in_contention = []
                    for player in standings:
                        if player['name'] in potential_season_clinchers:
                            if player['eligible'] or player['days_posted'] >= 4:
                                clinchers_in_contention.append(player['name'])
                    if len(clinchers_in_contention) >= 3:
                        names_list = ", ".join(clinchers_in_contention[:-1]) + f" and {clinchers_in_contention[-1]}"
                        season_clinch_text = f" EPIC SEASON STAKES: {names_list} ALL have 3 wins! A tie this week could mean SHARED Season {current_season} champions!"
                    elif len(clinchers_in_contention) == 2:
                        season_clinch_text = f" SEASON STAKES: {clinchers_in_contention[0]} and {clinchers_in_contention[1]} both have 3 wins - winner takes Season {current_season}, or they could share it!"
                
                if not season_clinch_text:
                    if leaders_who_could_clinch:
                        if len(leaders_who_could_clinch) == 1:
                            season_clinch_text = f" SEASON STAKES: If {leaders_who_could_clinch[0]} wins this week, they clinch Season {current_season}!"
                        else:
                            clinchers_list = " or ".join(leaders_who_could_clinch)
                            season_clinch_text = f" SEASON STAKES: If {clinchers_list} wins this week, they clinch Season {current_season}!"
                    else:
                        contenders_who_could_clinch = []
                        for player in standings:
                            if player['name'] in potential_season_clinchers and player['name'] not in leader_names:
                                if player['eligible'] or player['days_posted'] == 4:
                                    contenders_who_could_clinch.append(player['name'])
                        if contenders_who_could_clinch:
                            if len(contenders_who_could_clinch) == 1:
                                season_clinch_text = f" SEASON STAKES: {contenders_who_could_clinch[0]} could clinch Season {current_season} with a win!"
                            else:
                                clinchers_list = " or ".join(contenders_who_could_clinch[:2])
                                season_clinch_text = f" SEASON STAKES: {clinchers_list} could clinch Season {current_season} with a win!"
                
                scenario_text = " ".join(scenarios) + season_clinch_text
                logging.info(f"League {league_id} season clinch text: '{season_clinch_text}'")
                
                if season_clinch_text:
                    prompt = f"It's Sunday morning Wordle race update! {scenario_text} THIS IS HUGE - MENTION THE SEASON STAKES! Make it exciting with emojis! Keep it under 320 characters. Lower scores are better in Wordle."
                else:
                    prompt = f"It's Sunday morning Wordle race update! {scenario_text} Make it exciting with emojis! Keep it under 320 characters. Lower scores are better in Wordle."
            
            sunday_system_msg = """You are an exciting sports announcer for a Wordle league. In Wordle, LOWER scores are BETTER (1/6 is perfect, 6/6 is barely made it).

IMPORTANT RULES:
1. Convey the EXACT scenario given - don't change numbers, names, or math
2. A score of 1 is nearly impossible (hail mary), 2 is amazing/difficult, 3 is solid, 4-6 are more achievable
3. If someone is "eliminated" or "out of contention", they cannot win even with a perfect score
4. Don't say someone can "take the lead" or "catapult into first" unless the math actually supports it
5. Focus on players who realistically CAN still win or tie
6. Include SEASON STAKES info if provided - this is CRITICAL context about clinching the season! Always mention it prominently!
7. Use emojis for excitement!
8. NEVER say "can anyone catch up?" or "stay tuned" or "will anyone challenge" when the scenario says "RACE OVER" - the race is DECIDED, declare the winner definitively!
9. When someone clinches the SEASON (not just the week), make it a BIG DEAL - this is a major accomplishment!"""
            
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": sunday_system_msg},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200,
                temperature=0.7
            )
            
            race_message = response.choices[0].message.content.strip()
            logging.info(f"Generated Sunday race update for league {league_id}: {race_message}")
        
        # Get Chat Service SID for MCS uploads (only needed for SMS)
        chat_service_sid = None
        if channel_type == 'sms' and conversation_sid:
            from twilio.rest import Client as TwilioClient
            twilio_sid_tmp = os.environ.get('TWILIO_ACCOUNT_SID')
            twilio_token_tmp = os.environ.get('TWILIO_AUTH_TOKEN')
            tmp_client = TwilioClient(twilio_sid_tmp, twilio_token_tmp)
            conversation = tmp_client.conversations.v1.conversations(conversation_sid).fetch()
            chat_service_sid = conversation.chat_service_sid
        
        # Generate weekly standings image - use dynamic name from database
        league_name = league_display_name
        
        # Format week date string (e.g., "Jan 05")
        week_date_str = week_start.strftime("%b %d")
        
        # Helper to build image data for a list of player standings
        def build_image_data(player_list):
            image_data = []
            for player in player_list:
                if player['days_posted'] > 0:
                    score_values = [s for s in player['scores'].values() if s != 7]
                    sorted_scores = sorted(score_values)
                    num_to_use = min(len(sorted_scores), 5)
                    current_score = sum(sorted_scores[:num_to_use]) if sorted_scores else 0
                else:
                    current_score = None
                image_data.append({
                    'name': player['name'],
                    'score': current_score,
                    'used': player['days_posted'],
                    'failed': player.get('failed_attempts', 0),
                    'thrown': player.get('thrown_out', []),
                    'eligible': player['eligible']
                })
            return image_data
        
        # Generate images
        media_sids = []
        image_bytes_list = []
        
        # For SMS, we need Twilio credentials for media upload
        twilio_sid = os.environ.get('TWILIO_ACCOUNT_SID')
        twilio_token = os.environ.get('TWILIO_AUTH_TOKEN')
        twilio_phone = os.environ.get('TWILIO_PHONE_NUMBER')
        
        try:
            if is_division_mode:
                # Division mode: generate image with two separate division tables
                div1_image_data = build_image_data(div1_standings)
                div2_image_data = build_image_data(div2_standings)
                weekly_img = generate_division_weekly_image(league_name, div1_image_data, div2_image_data, week_date_str)
            else:
                # Standard mode: single table
                weekly_image_data = build_image_data(standings)
                weekly_img = generate_weekly_image(league_name, weekly_image_data, week_date_str)
            
            weekly_bytes = image_to_bytes(weekly_img)
            image_bytes_list.append(weekly_bytes)
            if channel_type == 'sms':
                weekly_media_sid = upload_image_to_twilio(weekly_bytes, twilio_sid, twilio_token, chat_service_sid)
                if weekly_media_sid:
                    media_sids.append(weekly_media_sid)
                    logging.info(f"Weekly image uploaded: {weekly_media_sid}")
        except Exception as img_error:
            logging.error(f"Failed to generate/upload weekly image: {img_error}")
            import traceback
            logging.error(traceback.format_exc())
        
        # Generate season image ONLY if there are potential season clinchers (or force_season_image for testing)
        # Division mode: no separate season images — the summary text mentions season stakes when relevant
        if is_division_mode:
            pass  # Division mode only sends the weekly table image
        else:
            # Standard mode season image
            logging.info(f"Season image check: potential_clinchers={potential_season_clinchers}, force={force_season_image}, weekly_wins={weekly_wins}")
            if potential_season_clinchers or force_season_image:
                try:
                    season_image_data = [
                        {'name': name, 'wins': wins}
                        for name, wins in sorted(weekly_wins.items(), key=lambda x: x[1], reverse=True)
                    ]
                    
                    logging.info(f"Generating season image with data: {season_image_data}")
                    season_img = generate_season_image(league_name, current_season, season_image_data)
                    logging.info(f"Season image result: {season_img is not None}")
                    if season_img:
                        season_bytes = image_to_bytes(season_img)
                        image_bytes_list.append(season_bytes)
                        if channel_type == 'sms':
                            season_media_sid = upload_image_to_twilio(season_bytes, twilio_sid, twilio_token, chat_service_sid)
                            if season_media_sid:
                                media_sids.append(season_media_sid)
                                logging.info(f"Season image uploaded (stakes are high!): {season_media_sid}")
                except Exception as img_error:
                    logging.error(f"Failed to generate/upload season image: {img_error}")
        
        # Append league URL to the race message
        race_message_with_url = f"{race_message}\n\n📊 {league_url}"
        
        # Send message via appropriate channel
        if channel_type == 'sms':
            from twilio.rest import Client
            client = Client(twilio_sid, twilio_token)
            
            if media_sids:
                for media_sid in media_sids:
                    client.conversations.v1.conversations(conversation_sid).messages.create(
                        media_sid=media_sid,
                        author=twilio_phone
                    )
            client.conversations.v1.conversations(conversation_sid).messages.create(
                body=race_message_with_url,
                author=twilio_phone
            )
        elif image_bytes_list:
            # Slack/Discord - send images as bytes via message router
            send_league_message(league_id, race_message_with_url, media_bytes=image_bytes_list[0])
            for extra_bytes in image_bytes_list[1:]:
                send_league_message(league_id, "", media_bytes=extra_bytes)
        else:
            # Text only - use message router for all channel types
            send_league_message(league_id, race_message_with_url)
        
        logging.info(f"Sent Sunday race update to league {league_id} via {channel_type}")
        return True
        
    except Exception as e:
        logging.error(f"Error sending Sunday race update: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return False

def run_sunday_race_updates():
    """Run Sunday race updates for all active leagues (dynamically from database)"""
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
        logging.info(f"Found {len(leagues)} active leagues for Sunday race update: {[(l[0], l[1], l[2]) for l in leagues]}")
    except Exception as e:
        logging.error(f"Failed to fetch active leagues from database: {e}")
        return False
    
    all_success = True
    for league_id, league_name, channel_type in leagues:
        logging.info(f"Sending Sunday race update for League {league_id} ({league_name}) [{channel_type}]")
        success = send_sunday_race_update(league_id)
        if not success:
            all_success = False
        
        # Add delay between leagues to avoid carrier SMS throttling
        import time
        time.sleep(2)
    
    return all_success

if __name__ == "__main__":
    # This script should be run at 10:00 AM Pacific on Sundays
    pacific = pytz.timezone('America/Los_Angeles')
    now = datetime.now(pacific)
    
    # Check if it's Sunday
    if now.weekday() != 6:  # 6 = Sunday
        print(f"Not Sunday (today is {now.strftime('%A')}), skipping race update")
        sys.exit(0)
    
    print("Starting Sunday race update...")
    success = run_sunday_race_updates()
    if success:
        print("Sunday race update completed successfully!")
        sys.exit(0)
    else:
        print("Sunday race update failed!")
        sys.exit(1)
