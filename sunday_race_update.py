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

from league_data_adapter import get_db_connection, calculate_wordle_number, get_week_start_date, get_league_min_scores
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
    """Get current weekly standings for a league - uses the league's configured best-N scores."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Per-league configurable minimum scores per week (3-7, default 5)
    MIN_GAMES_FOR_RANKING = get_league_min_scores(league_id, conn=conn)
    BEST_N_SCORES = MIN_GAMES_FOR_RANKING
    
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
        import random
        miracle_phrases = [
            "needs a near-impossible 1 (hail mary!)",
            "needs a miraculous 1 (dream shot!)",
            "needs an impossible 1 (shot in the dark!)",
            "needs a legendary 1 (one-in-a-million!)",
            "needs a perfect 1 (lightning in a bottle!)",
        ]
        return random.choice(miracle_phrases)
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

def calculate_what_they_need(leader_best_5, player_best_5, player_days_posted, min_scores=5):
    """Calculate what score a player needs to tie or win

    Logic: If player has min_scores+ games, their best N is locked in.
    If player has <min_scores games, they need more games to qualify.
    If player has exactly min_scores games and hasn't posted today, a new score could replace their worst.
    """
    if player_best_5 is None:
        # Player doesn't have min_scores games yet - can't calculate
        return {'needs_more_games': True, 'games_needed': min_scores - player_days_posted}
    
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

def compute_player_scenario(player, leader_total, leader_names, min_scores=5):
    """Compute catch-up/improvement scenario for a player who hasn't posted today.

    Handles:
    - Players behind the leader (need to catch up)
    - Players TIED with the leader (can improve via throw-out to win outright)
    - Leaders who haven't posted (can extend their lead)
    - Ineligible players one game short of qualifying (could qualify with next score)

    Returns: (text, status) where status is 'can_catch_up', 'eliminated', 'can_improve', or None
    """
    name = player['name']
    is_leader = name in leader_names
    one_short = min_scores - 1

    if player['eligible']:
        diff = player['best_5_total'] - leader_total
        non_fail_scores = [s for s in player['scores'].values() if s != 7]
        sorted_scores = sorted(non_fail_scores)[:min_scores]

        if not sorted_scores:
            return None, None

        worst_best_5 = sorted_scores[-1]

        if is_leader and diff == 0:
            # Leader who hasn't posted — can improve via throw-out
            # New score replaces worst_best_5 if it's lower
            best_possible = player['best_5_total'] - worst_best_5 + 1  # if they get a 1
            improvement = worst_best_5 - 1  # max points they can improve
            if improvement > 0 and worst_best_5 > 1:
                return f"{name} (at {player['best_5_total']}) leads but hasn't posted — could improve by replacing a {worst_best_5}", 'can_improve'
            return None, None

        if diff == 0:
            # Tied with leader — can win outright by improving via throw-out
            # Need new score < worst_best_5 to improve total
            score_to_win = worst_best_5 - 1  # score that makes new total = leader_total - 1
            if score_to_win >= 1 and score_to_win <= 6:
                text = get_catch_up_text(name, score_to_win, -1, player['best_5_total'])
                # Override: tied player can only win, not "tie" (they're already tied)
                win_text = get_score_difficulty_text(score_to_win)
                text = f"{name} (at {player['best_5_total']}) is tied and {win_text} to take the lead"
                return text, 'can_catch_up'
            else:
                # Can't improve (worst score is already a 1)
                return None, None

        if diff > 0:
            # Behind the leader — standard catch-up
            score_to_tie = worst_best_5 - diff
            score_to_win = worst_best_5 - diff - 1
            text = get_catch_up_text(name, score_to_win, score_to_tie, player['best_5_total'])
            if text:
                if "eliminated" in text:
                    return text, 'eliminated'
                return text, 'can_catch_up'

        return None, None

    elif player['days_posted'] >= one_short:
        # Ineligible but close — could qualify with today's score
        non_fail_scores = [s for s in player['scores'].values() if s != 7]
        non_fail_count = len(non_fail_scores)
        if non_fail_count == one_short:
            current_total = sum(sorted(non_fail_scores)[:one_short])
            # For one-short players, the next score ADDS to their total (not replaces)
            # new_total = current_total + new_score
            # To beat leader: current_total + new_score < leader_total
            # To tie leader: current_total + new_score = leader_total
            best_possible = current_total + 1  # perfect score
            worst_possible = current_total + 6  # worst non-fail score

            if best_possible > leader_total:
                # Even a perfect 1 can't tie/beat the leader
                return f"{name} (at {current_total} with {one_short} games) is mathematically eliminated", 'eliminated'

            # They CAN catch up — figure out what they need
            # new_total = current_total + new_score
            # score_to_tie = leader_total - current_total (score that ties)
            # score_to_win = score_to_tie - 1 (score that beats)
            score_to_tie = leader_total - current_total
            score_to_win = score_to_tie - 1

            # If even worst possible score (6) beats the leader, they win no matter what
            if worst_possible < leader_total:
                return f"{name} (at {current_total} with {one_short} games) just needs to post today to qualify and WIN — any score beats the leader!", 'can_catch_up'
            elif worst_possible == leader_total:
                return f"{name} (at {current_total} with {one_short} games) just needs to post today to qualify and at minimum TIE the leader!", 'can_catch_up'

            # They need a specific score range to catch up
            text = get_catch_up_text(name, score_to_win, score_to_tie, current_total, one_short)
            if text:
                if "eliminated" in text:
                    return text, 'eliminated'
                return text, 'can_catch_up'
        elif non_fail_count < one_short:
            return f"{name} is mathematically eliminated", 'eliminated'

    return None, None

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
            'sunday_race': 'ai_sunday_race_update'
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

def _calc_season_totals(cursor, league_id, division, season_start, min_scores, this_week_scores):
    """Calculate true season totals from raw scores table (best-N per week, all weeks).
    Returns dict {player_name: season_total} for active, non-immune players.
    this_week_scores is a dict {name: best_N_total} from current week standings."""
    # Get active non-immune players in this division
    cursor.execute("""
        SELECT p.id, p.name FROM players p
        WHERE p.league_id = %s AND p.division = %s AND p.active = TRUE
            AND p.division_immunity = FALSE
    """, (league_id, division))

    players = cursor.fetchall()

    totals = {}
    for player_id, player_name in players:
        # Fetch all raw scores from season start onwards
        cursor.execute("""
            SELECT s.wordle_number, s.score
            FROM scores s
            WHERE s.player_id = %s AND s.wordle_number >= %s
            ORDER BY s.wordle_number
        """, (player_id, season_start))

        # Group scores by 7-day week blocks from season_start
        week_scores = {}
        for wn, sc in cursor.fetchall():
            ws = wn - ((wn - season_start) % 7)
            if ws not in week_scores:
                week_scores[ws] = []
            week_scores[ws].append(sc)

        # Determine current week start (the week containing today's scores)
        current_week_start = None
        if this_week_scores:
            # Current week start = highest week-start wordle that has scores in standings
            all_ws = sorted(week_scores.keys())
            if all_ws:
                current_week_start = all_ws[-1]

        # Sum best-N from each PAST week (exclude current week)
        past_total = 0
        for ws, scores in week_scores.items():
            if current_week_start and ws >= current_week_start:
                continue
            valid = sorted([s for s in scores if s < 7])
            best_n = sum(valid[:min_scores]) if valid else 0
            past_total += best_n

        # Add current week's live best-N total from standings
        current_week_score = this_week_scores.get(player_name, 0)
        totals[player_name] = past_total + current_week_score

    return totals

def check_relegation_promotion_ties(league_id, div1_season_info, div2_season_info, min_scores,
                                     div1_weekly_wins=None, div2_weekly_wins=None,
                                     div1_standings=None, div2_standings=None):
    """Check relegation (Div I) / promotion (Div II) outlook when a season could end this week.
    Uses weekly_wins (already incremented with pending win) to identify likely clinchers.
    Season totals are calculated from raw scores (best-N per week), matching the public page.
    Returns info text to append to scenario, or empty string."""
    warnings = []
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Build a lookup of current-week best-N scores from standings
        div1_this_week = {}
        if div1_standings:
            for s in div1_standings:
                if s.get('eligible') and s.get('best_5_total') is not None:
                    div1_this_week[s['name']] = s['best_5_total']
        div2_this_week = {}
        if div2_standings:
            for s in div2_standings:
                if s.get('eligible') and s.get('best_5_total') is not None:
                    div2_this_week[s['name']] = s['best_5_total']

        # --- Div I relegation check ---
        div1_season = div1_season_info.get('current_season', 1)
        div1_start = div1_season_info.get('season_start_week')
        # Only relevant if someone could clinch Div I this week
        div1_clinchers = set()
        if div1_weekly_wins:
            div1_clinchers = {name for name, wins in div1_weekly_wins.items() if wins >= DIVISION_WINS_FOR_SEASON}

        if div1_start and div1_clinchers:
            # Get existing season winners + likely clinchers = exempt from relegation
            cursor.execute("""
                SELECT p.name FROM season_winners sw
                JOIN players p ON sw.player_id = p.id
                WHERE sw.league_id = %s AND sw.division = 1 AND sw.season_number = %s
            """, (league_id, div1_season))
            existing_winners = {r[0] for r in cursor.fetchall()}
            exempt_names = existing_winners | div1_clinchers

            # Calculate true season totals from raw scores (best-N per week)
            all_totals = _calc_season_totals(cursor, league_id, 1, div1_start, min_scores, div1_this_week)

            # Build candidates list (exclude exempt players)
            candidates = [(name, total) for name, total in all_totals.items() if name not in exempt_names]
            # Sort worst (highest total) first
            candidates.sort(key=lambda x: -x[1])

            cursor.execute("SELECT COALESCE(relegated_count, 1) FROM leagues WHERE id = %s", (league_id,))
            relegated_count = cursor.fetchone()[0]

            if candidates:
                if len(candidates) > relegated_count:
                    boundary_total = candidates[relegated_count - 1][1]
                    tied_at_boundary = [c for c in candidates if c[1] == boundary_total]
                    if len(tied_at_boundary) > relegated_count:
                        names = ' and '.join(c[0] for c in tied_at_boundary)
                        warnings.append(f"Relegation drama: {names} tied at Season Total {boundary_total} for relegation — a random draw would decide who moves down! 😮")
                    else:
                        relegated = candidates[:relegated_count]
                        rel_names = ' and '.join(c[0] for c in relegated)
                        if relegated_count == 1:
                            warnings.append(f"Relegation: If the season ends, {rel_names} (Season Total {relegated[0][1]}) would be relegated to Division II.")
                        else:
                            warnings.append(f"Relegation: If the season ends, {rel_names} would be relegated to Division II.")
                elif len(candidates) == relegated_count:
                    rel_names = ' and '.join(c[0] for c in candidates)
                    warnings.append(f"Relegation: If the season ends, {rel_names} would be relegated to Division II.")

        # --- Div II promotion check ---
        cursor.execute("SELECT COALESCE(promoted_count, 1) FROM leagues WHERE id = %s", (league_id,))
        promoted_count = cursor.fetchone()[0]
        div2_season = div2_season_info.get('current_season', 1)
        div2_start = div2_season_info.get('season_start_week')
        div2_clinchers = set()
        if div2_weekly_wins:
            div2_clinchers = {name for name, wins in div2_weekly_wins.items() if wins >= DIVISION_WINS_FOR_SEASON}

        if div2_start and div2_clinchers:
            promoted_so_far = list(div2_clinchers)
            extra_spots = promoted_count - len(promoted_so_far)

            if extra_spots > 0:
                # Calculate true season totals from raw scores for Div II
                all_totals = _calc_season_totals(cursor, league_id, 2, div2_start, min_scores, div2_this_week)

                # Exclude clinchers, sort best (lowest) first
                remaining = [(name, total) for name, total in all_totals.items() if name not in div2_clinchers]
                remaining.sort(key=lambda x: x[1])

                if remaining:
                    if len(remaining) > extra_spots:
                        boundary_total = remaining[extra_spots - 1][1]
                        tied_at_boundary = [r for r in remaining if r[1] == boundary_total]
                        if len(tied_at_boundary) > extra_spots:
                            names = ' and '.join(r[0] for r in tied_at_boundary)
                            warnings.append(f"Promotion alert: {names} tied at Season Total {boundary_total} for the extra promotion spot — a random draw would decide who also moves up!")
                        else:
                            extra_promoted = remaining[:extra_spots]
                            extra_names = ' and '.join(r[0] for r in extra_promoted)
                            clincher_names = ' and '.join(promoted_so_far)
                            warnings.append(f"Promotion: {clincher_names} wins the season, and {extra_names} (Season Total {extra_promoted[0][1]}) would also earn promotion to Division I!")
                    else:
                        extra_names = ' and '.join(r[0] for r in remaining)
                        clincher_names = ' and '.join(promoted_so_far)
                        warnings.append(f"Promotion: {clincher_names} wins the season, and {extra_names} would also earn promotion to Division I!")
            elif promoted_count == 1 and len(promoted_so_far) == 1:
                pass  # Already handled by SEASON CLINCH text in build_division_scenario

    except Exception as e:
        logging.warning(f"Error checking relegation/promotion ties: {e}")
        import traceback
        logging.warning(traceback.format_exc())
    finally:
        cursor.close()
        conn.close()

    return ' '.join(warnings)


def build_division_scenario(div_standings, div_num, div_weekly_wins, div_current_season, min_scores=5):
    """Build scenario analysis text for a single division.
    Returns scenario text string for the AI prompt."""
    div_label = "Division I" if div_num == 1 else "Division II"

    eligible = [s for s in div_standings if s['eligible']]
    ineligible = [s for s in div_standings if not s['eligible']]

    if not eligible:
        return f"{div_label}: No one has played {min_scores} games yet to qualify for the weekly win."
    
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
    
    # Check who can catch up (including tied players and leaders who haven't posted)
    players_who_can_catch_up = []
    catch_up_scenarios = []
    leader_improve_scenarios = []
    eliminated = []
    
    for player in not_posted_today:
        text, status = compute_player_scenario(player, leader_total, leader_names, min_scores=min_scores)
        if text and status == 'can_catch_up':
            players_who_can_catch_up.append(player['name'])
            catch_up_scenarios.append(text)
        elif text and status == 'can_improve':
            leader_improve_scenarios.append(text)
        elif text and status == 'eliminated':
            eliminated.append(player['name'])

    # Race is decided if no one can catch the leader — leader's ability to improve is irrelevant
    race_is_decided = len(players_who_can_catch_up) == 0

    # Compute clinch candidates BEFORE incrementing pending win.
    # potential_clinchers = "1 win away entering this week" — they clinch IF they win this week.
    potential_clinchers = [name for name, wins in div_weekly_wins.items() if wins == DIVISION_WINS_FOR_SEASON - 1]

    # Build scenario
    scenarios = []
    if all_posted or race_is_decided:
        # Race is over — update win counts to include the pending win (for display only)
        for winner_name in leader_names:
            div_weekly_wins[winner_name] = div_weekly_wins.get(winner_name, 0) + 1
        
        if len(leaders) > 1:
            leader_list = " and ".join(leader_names)
            scenarios.append(f"RACE OVER! {leader_list} are tied at {leader_total} and will share the weekly win!")
        else:
            scenarios.append(f"RACE OVER! {leader_names[0]} wins the week with {leader_total}!")
    elif len(leaders) == 1:
        leader_text = f"{leader_names[0]} leads at {leader_total}"
        parts = [leader_text]
        # Only mention leader improvement if others can still catch up (race is live)
        if leader_improve_scenarios and catch_up_scenarios:
            parts.extend(leader_improve_scenarios)
        if catch_up_scenarios:
            parts.append(". ".join(catch_up_scenarios[:3]))
        elif all_eligible_posted:
            parts = [f"{leader_names[0]} is the clear winner at {leader_total}!"]
        scenarios.append(". ".join(parts))
    else:
        leader_text = f"{' and '.join(leader_names)} tied at {leader_total}"
        parts = [leader_text]
        if catch_up_scenarios:
            parts.append(". ".join(catch_up_scenarios[:3]))
        scenarios.append(". ".join(parts))
    
    # Season clinch detection for this division (potential_clinchers computed above, pre-increment)
    season_clinch_text = ""
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
                if p['name'] in contenders and (p['eligible'] or p['days_posted'] >= min_scores - 1):
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
        logging.info(f"Sunday race update disabled for league {league_id}, skipping")
        return True
    
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
        league_url = f"https://{os.environ.get('RAILWAY_PUBLIC_DOMAIN', 'app.wordplayleague.com')}/leagues/{league_slug}"

        # Per-league configurable minimum scores per week (3-7, default 5)
        min_scores = get_league_min_scores(league_id)

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
            div1_scenario = build_division_scenario(div1_standings, 1, div1_weekly_wins, div1_season_info['current_season'], min_scores=min_scores)
            div2_scenario = build_division_scenario(div2_standings, 2, div2_weekly_wins, div2_season_info['current_season'], min_scores=min_scores)
            
            scenario_text = f"{div1_scenario}\n\n{div2_scenario}"

            # Check for relegation/promotion ties (random draw warning)
            tie_warnings = check_relegation_promotion_ties(
                league_id, div1_season_info, div2_season_info, min_scores,
                div1_weekly_wins=div1_weekly_wins, div2_weekly_wins=div2_weekly_wins,
                div1_standings=div1_standings, div2_standings=div2_standings
            )
            if tie_warnings:
                scenario_text += f"\n\n{tie_warnings}"

            logging.info(f"League {league_id} division scenarios: {scenario_text}")

            # Build division standings summaries for AI context
            def build_div_standings_summary(div_standings):
                lines = []
                for s in div_standings:
                    if s['eligible']:
                        lines.append(f"  {s['name']}: best-{min_scores} total = {s['best_5_total']}, games = {s['days_posted']}, posted today = {'yes' if s['posted_today'] else 'no'}")
                    else:
                        non_fail = [v for v in s['scores'].values() if v != 7]
                        current = sum(sorted(non_fail)[:min_scores]) if non_fail else 0
                        lines.append(f"  {s['name']}: {s['days_posted']} games (needs {min_scores}), current total = {current}, posted today = {'yes' if s['posted_today'] else 'no'}")
                return "\n".join(lines) if lines else "  No players"
            
            def build_div_wins_summary(div_wins):
                lines = []
                for name, wins in sorted(div_wins.items(), key=lambda x: x[1], reverse=True):
                    lines.append(f"  {name}: {wins} win{'s' if wins != 1 else ''}")
                return "\n".join(lines) if lines else "  No wins yet"
            
            # Per-division stakes detection — omit SEASON WINS for divisions with no stakes
            # to prevent the AI from inventing win-count claims unrelated to today's race.
            div1_has_stakes = "SEASON STAKES" in div1_scenario or "SEASON CLINCH" in div1_scenario
            div2_has_stakes = "SEASON STAKES" in div2_scenario or "SEASON CLINCH" in div2_scenario

            div1_block = f"""DIVISION I STANDINGS (lower is better, best {min_scores} of 7):
{build_div_standings_summary(div1_standings)}"""
            if div1_has_stakes:
                div1_block += f"""

DIVISION I SEASON {div1_season_info['current_season']} WINS (need {DIVISION_WINS_FOR_SEASON} to win):
{build_div_wins_summary(div1_weekly_wins)}"""

            div2_block = f"""DIVISION II STANDINGS (lower is better, best {min_scores} of 7):
{build_div_standings_summary(div2_standings)}"""
            if div2_has_stakes:
                div2_block += f"""

DIVISION II SEASON {div2_season_info['current_season']} WINS (need {DIVISION_WINS_FOR_SEASON} to win):
{build_div_wins_summary(div2_weekly_wins)}"""

            div_context = f"""{div1_block}

{div2_block}

RACE ANALYSIS:
{scenario_text}"""

            has_season_stakes = div1_has_stakes or div2_has_stakes
            has_movement_stakes = "Relegation:" in scenario_text or "Promotion:" in scenario_text or "Relegation drama:" in scenario_text or "Promotion alert:" in scenario_text
            
            if has_season_stakes and has_movement_stakes:
                prompt = f"It's Sunday morning Wordle race update for a league with DIVISIONS! Give a brief update for EACH division separately. {div_context} THIS IS HUGE - MENTION THE SEASON STAKES AND THE RELEGATION/PROMOTION STAKES! Make it exciting with emojis! Keep it under 500 characters. Lower scores are better in Wordle."
            elif has_season_stakes:
                prompt = f"It's Sunday morning Wordle race update for a league with DIVISIONS! Give a brief update for EACH division separately. {div_context} THIS IS HUGE - MENTION THE SEASON STAKES! Make it exciting with emojis! Keep it under 500 characters. Lower scores are better in Wordle."
            elif has_movement_stakes:
                prompt = f"It's Sunday morning Wordle race update for a league with DIVISIONS! Give a brief update for EACH division separately. {div_context} MENTION THE RELEGATION/PROMOTION STAKES! Make it exciting with emojis! Keep it under 500 characters. Lower scores are better in Wordle."
            else:
                prompt = f"It's Sunday morning Wordle race update for a league with DIVISIONS! Give a brief update for EACH division separately. {div_context} Make it exciting with emojis! Keep it under 400 characters. Lower scores are better in Wordle."
            
            sunday_system_msg = """You are a concise sports announcer for a Wordle league with DIVISIONS. In Wordle, LOWER scores are BETTER (1/6 is perfect, 6/6 is barely made it).

STYLE RULES:
- Be CONCISE. No filler. No rhetorical questions. No "stay tuned" or "who will win?" or "the door is open".
- When the race is OVER ("RACE OVER"), just declare the winner briefly. Do NOT describe what the winner "could still do" or "potential improvements". It's done.
- Do NOT describe eliminated players' situations in detail. They lost — move on.
- Only describe catch-up scenarios for players who can ACTUALLY still win or tie.

ACCURACY RULES:
1. Convey the EXACT scenario given - don't change numbers, names, or math. Use ONLY the data provided.
2. A score of 1 is nearly impossible (use the exact dramatic phrase provided), 2 is amazing/difficult, 3 is solid, 4-6 are more achievable.
3. Don't say someone can "take the lead" unless the math supports it.
4. Only mention SEASON STAKES or SEASON CLINCH if those EXACT phrases appear in the RACE ANALYSIS. If not present for a division, do NOT mention clinching, season wins, or season implications for that division.
5. NEVER claim someone "clinched the season" unless RACE ANALYSIS explicitly says "SEASON CLINCH".
6. When mentioning season wins, use ONLY the numbers from "SEASON WINS" section. Do NOT infer or inflate.
7. If NO "SEASON WINS" section exists for a division, do NOT mention season wins at all.
8. Use emojis for excitement!
9. Division I first, then Division II. Line break between them.
10. Division seasons require 3 wins. Div II season win = PROMOTION to Div I. Extra players can also be promoted based on best Season Total. Div I season end = worst Season Total player(s) RELEGATED to Div II. Missed weeks put a player first in line for relegation.
11. If "Relegation:" or "Promotion:" text appears in RACE ANALYSIS, mention it! These are the STAKES. Convey who's in line and why.
12. FORBIDDEN PHRASES (unless explicitly in RACE ANALYSIS): "locked", "out of contention", "eliminated", "in the hunt", "hail mary" (only if score of 1 needed).
13. If two players are tied and one hasn't posted and "could improve", the race is NOT over — say they could break the tie."""
            
            response = openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": sunday_system_msg},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=400,
                temperature=0.3
            )
            
            race_message = response.choices[0].message.content.strip()
            logging.info(f"Generated division Sunday race update for league {league_id}: {race_message}")
        
        # ============================================================
        # STANDARD MODE: single league analysis (existing logic)
        # ============================================================
        else:
            # Find eligible players (min_scores+ games) and their leader
            eligible = [s for s in standings if s['eligible']]

            # Get current weekly wins for season clinching detection
            weekly_wins, current_season = get_weekly_wins_in_current_season(league_id)

            # Find players who could clinch the season with a win this week (currently at 3 wins)
            potential_season_clinchers = [name for name, wins in weekly_wins.items() if wins == WINS_FOR_SEASON_VICTORY - 1]

            # Build raw standings summary for the AI prompt
            standings_lines = []
            for s in standings:
                if s['eligible']:
                    standings_lines.append(f"  {s['name']}: best-{min_scores} total = {s['best_5_total']}, games played = {s['days_posted']}, posted today = {'yes' if s['posted_today'] else 'no'}")
                else:
                    non_fail = [v for v in s['scores'].values() if v != 7]
                    current = sum(sorted(non_fail)[:min_scores]) if non_fail else 0
                    standings_lines.append(f"  {s['name']}: {s['days_posted']} games (needs {min_scores} to qualify), current total = {current}, posted today = {'yes' if s['posted_today'] else 'no'}")
            standings_summary = "\n".join(standings_lines)
            
            # Build season wins summary
            season_wins_lines = []
            if weekly_wins:
                for name, wins in sorted(weekly_wins.items(), key=lambda x: x[1], reverse=True):
                    season_wins_lines.append(f"  {name}: {wins} win{'s' if wins != 1 else ''}")
            season_wins_summary = "\n".join(season_wins_lines) if season_wins_lines else "  No wins yet this season"
            
            prompt = None
            
            if not eligible:
                logging.info(f"No eligible players ({min_scores}+ games) in league {league_id} - sending 'no winner this week' message")
                prompt = f"It's Sunday! No one has played {min_scores} games yet this week to qualify for the weekly win. You need at least {min_scores} scores to compete! Looks like no one can claim victory this week. Use emojis. Keep it under 200 characters."
            elif len(eligible) == 1:
                # Check if any ineligible player one short of qualifying could still qualify and beat the leader
                winner = eligible[0]
                potential_qualifiers = []
                one_short = min_scores - 1
                for p in standings:
                    if not p['eligible'] and p['days_posted'] >= one_short:
                        non_fail = [s for s in p['scores'].values() if s != 7]
                        if len(non_fail) == one_short:
                            current_total = sum(sorted(non_fail)[:one_short])
                            # With a next score of 6 (worst non-fail), could they beat or tie the leader?
                            if current_total + 6 <= winner['best_5_total']:
                                potential_qualifiers.append(p)
                
                if not potential_qualifiers:
                    # Truly locked - no one can qualify and beat them
                    logging.info(f"Only one eligible player in league {league_id}: {winner['name']} has it locked")
                    prompt = f"It's Sunday morning Wordle race update! {winner['name']} has this week LOCKED at {winner['best_5_total']}! No one else has enough scores to compete. Congratulate the winner! Use emojis. Keep it under 200 characters."
                else:
                    # Someone could still qualify and beat the leader - fall through to full analysis
                    logging.info(f"Only one eligible player but {[p['name'] for p in potential_qualifiers]} could still qualify and beat them")
            
            if prompt is None and len(eligible) >= 1:
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
                
                # SCENARIO ANALYSIS using compute_player_scenario for all not-posted players
                scenarios = []
                players_who_can_catch_up = []
                catch_up_scenarios = []
                leader_improve_scenarios = []
                eliminated = []
                
                for player in not_posted_today:
                    text, status = compute_player_scenario(player, leader_total, leader_names, min_scores=min_scores)
                    if text and status == 'can_catch_up':
                        players_who_can_catch_up.append(player['name'])
                        catch_up_scenarios.append(text)
                    elif text and status == 'can_improve':
                        leader_improve_scenarios.append(text)
                    elif text and status == 'eliminated':
                        eliminated.append(player['name'])
                
                # Race is decided if no one who hasn't posted can catch up
                # Leader's ability to improve is irrelevant — if no one can catch them, they've won
                race_is_decided = len(players_who_can_catch_up) == 0
                
                if all_players_posted or race_is_decided:
                    # Race is over — the leader(s) will get this week's win
                    # Update season wins display to include the pending win so AI reports accurate counts
                    # NOTE: do NOT recompute potential_season_clinchers from this updated count —
                    # potential_season_clinchers is the pre-week snapshot ("1 away entering"), and the
                    # clinch logic below relies on that meaning.
                    for winner_name in leader_names:
                        weekly_wins[winner_name] = weekly_wins.get(winner_name, 0) + 1
                    # Rebuild season wins summary with updated counts
                    season_wins_lines = []
                    if weekly_wins:
                        for name, wins in sorted(weekly_wins.items(), key=lambda x: x[1], reverse=True):
                            season_wins_lines.append(f"  {name}: {wins} win{'s' if wins != 1 else ''}")
                    season_wins_summary = "\n".join(season_wins_lines) if season_wins_lines else "  No wins yet this season"
                    
                    if len(leaders) > 1:
                        leader_list = " and ".join(leader_names)
                        scenarios.append(f"RACE OVER! {leader_list} are tied at {leader_total} and will share the weekly win!")
                    else:
                        scenarios.append(f"RACE OVER! {leader_names[0]} wins the week with {leader_total}! Congratulations!")
                
                elif len(leaders) > 1 and all_eligible_posted and not not_posted_today:
                    leader_list = " and ".join(leader_names)
                    scenarios.append(f"{leader_list} are tied at {leader_total} and will share the win!")
                
                else:
                    if len(leaders) == 1:
                        leader_text = f"{leader_names[0]} leads at {leader_total}"
                    else:
                        leader_text = f"{' and '.join(leader_names)} tied at {leader_total}"
                    
                    scenario_parts = [leader_text]
                    # Only mention leader improvement if others can still catch up (race is live)
                    if leader_improve_scenarios and catch_up_scenarios:
                        scenario_parts.extend(leader_improve_scenarios)
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

                if all_players_posted or race_is_decided:
                    # Race is over — if a potential clincher won, they've clinched the season
                    if leaders_who_could_clinch:
                        if len(leaders_who_could_clinch) == 1:
                            season_clinch_text = f" SEASON CLINCH: {leaders_who_could_clinch[0]} clinches Season {current_season} with their {WINS_FOR_SEASON_VICTORY}th win!"
                        else:
                            clinchers_list = " and ".join(leaders_who_could_clinch)
                            season_clinch_text = f" SEASON CLINCH: {clinchers_list} clinch Season {current_season}!"
                else:
                    # Race still live — use SEASON STAKES language
                    if len(potential_season_clinchers) >= 2:
                        clinchers_in_contention = []
                        for player in standings:
                            if player['name'] in potential_season_clinchers:
                                if player['eligible'] or player['days_posted'] >= min_scores - 1:
                                    clinchers_in_contention.append(player['name'])
                        if len(clinchers_in_contention) >= 3:
                            names_list = ", ".join(clinchers_in_contention[:-1]) + f" and {clinchers_in_contention[-1]}"
                            season_clinch_text = f" EPIC SEASON STAKES: {names_list} ALL have {WINS_FOR_SEASON_VICTORY - 1} wins (one win away from the season)! A tie this week could mean SHARED Season {current_season} champions!"
                        elif len(clinchers_in_contention) == 2:
                            season_clinch_text = f" SEASON STAKES: {clinchers_in_contention[0]} and {clinchers_in_contention[1]} both have {WINS_FOR_SEASON_VICTORY - 1} wins (one win away) - winner takes Season {current_season}, or they could share it!"

                    if not season_clinch_text:
                        if leaders_who_could_clinch:
                            if len(leaders_who_could_clinch) == 1:
                                season_clinch_text = f" SEASON STAKES: {leaders_who_could_clinch[0]} has {WINS_FOR_SEASON_VICTORY - 1} wins (one win away from the season)! If they win this week, they clinch Season {current_season}!"
                            else:
                                clinchers_list = " or ".join(leaders_who_could_clinch)
                                season_clinch_text = f" SEASON STAKES: {clinchers_list} each have {WINS_FOR_SEASON_VICTORY - 1} wins (one win away)! If either wins this week, they clinch Season {current_season}!"
                        else:
                            contenders_who_could_clinch = []
                            for player in standings:
                                if player['name'] in potential_season_clinchers and player['name'] not in leader_names:
                                    if player['eligible'] or player['days_posted'] == min_scores - 1:
                                        contenders_who_could_clinch.append(player['name'])
                            if contenders_who_could_clinch:
                                if len(contenders_who_could_clinch) == 1:
                                    season_clinch_text = f" SEASON STAKES: {contenders_who_could_clinch[0]} has {WINS_FOR_SEASON_VICTORY - 1} wins (one win away from the season) and could clinch Season {current_season} with a win!"
                                else:
                                    clinchers_list = " or ".join(contenders_who_could_clinch[:2])
                                    season_clinch_text = f" SEASON STAKES: {clinchers_list} each have {WINS_FOR_SEASON_VICTORY - 1} wins (one win away) and could clinch Season {current_season} with a win!"
                
                scenario_text = " ".join(scenarios) + season_clinch_text
                logging.info(f"League {league_id} season clinch text: '{season_clinch_text}'")
                logging.info(f"League {league_id} scenario text: '{scenario_text}'")
                
                # Build the full prompt with standings and (only if relevant) season context.
                # Omit SEASON WINS entirely when there are no season stakes — prevents the AI
                # from inventing claims about win counts that aren't relevant to today's race.
                if season_clinch_text:
                    context_block = f"""CURRENT WEEKLY STANDINGS (lower is better, best {min_scores} of 7 scores):
{standings_summary}

SEASON {current_season} WINS (need {WINS_FOR_SEASON_VICTORY} to win the season):
{season_wins_summary}

WEEKLY RACE ANALYSIS: {scenario_text}"""
                else:
                    context_block = f"""CURRENT WEEKLY STANDINGS (lower is better, best {min_scores} of 7 scores):
{standings_summary}

WEEKLY RACE ANALYSIS: {scenario_text}"""
                
                if season_clinch_text:
                    prompt = f"It's Sunday morning Wordle race update! {context_block} THIS IS HUGE - MENTION THE SEASON STAKES! Make it exciting with emojis! Keep it under 280 characters. Lower scores are better in Wordle."
                else:
                    prompt = f"It's Sunday morning Wordle race update! {context_block} Make it exciting with emojis! Keep it under 280 characters. Lower scores are better in Wordle."
            
            sunday_system_msg = """You are a concise sports announcer for a Wordle league. In Wordle, LOWER scores are BETTER (1/6 is perfect, 6/6 is barely made it).

STYLE RULES:
- Be CONCISE. No filler. No rhetorical questions. No "stay tuned" or "who will win?" or "the door is open" or "can anyone catch up?".
- When the race is OVER ("RACE OVER"), just declare the winner briefly and move on. Do NOT describe what the winner "could still do" or improvements they could make. It's done.
- Do NOT describe eliminated players' situations in detail. They lost — skip them.
- Only describe catch-up scenarios for players who can ACTUALLY still win or tie.

ACCURACY RULES:
1. Convey the EXACT scenario given - don't change numbers, names, or math. Use ONLY the data provided.
2. A score of 1 is nearly impossible (use the exact dramatic phrase provided), 2 is amazing/difficult, 3 is solid, 4-6 are more achievable.
3. Don't say someone can "take the lead" unless the math supports it.
4. If the prompt contains "SEASON STAKES" or "SEASON CLINCH", mention it prominently!
5. NEVER claim someone "clinched the season" unless the prompt explicitly says "SEASON CLINCH".
6. When mentioning season wins, use ONLY numbers from "SEASON WINS" section. Do NOT infer or inflate.
7. If NO "SEASON WINS" section exists, do NOT mention season wins at all.
8. Use emojis for excitement!
9. FORBIDDEN PHRASES (unless explicitly in RACE ANALYSIS): "locked", "out of contention", "eliminated", "in the hunt", "hail mary" (only if score of 1 needed).
10. If two players are tied and one hasn't posted and "could improve", the race is NOT over — say they could break the tie."""
            
            response = openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": sunday_system_msg},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200,
                temperature=0.5
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
                    num_to_use = min(len(sorted_scores), min_scores)
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
        
        # Season image generation removed - the AI-generated text with season stakes is sufficient
        # Division mode and standard mode both only send the weekly standings image
        
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
    
    # DST-proof: Railway cron fires at both 17 and 18 UTC to cover PST/PDT.
    # Only run if it's actually 10:00 AM Pacific.
    if now.hour != 10:
        print(f"Not 10:00 AM Pacific (currently {now.strftime('%I:%M %p %Z')}), skipping")
        sys.exit(0)
    
    print("Starting Sunday race update...")
    success = run_sunday_race_updates()
    if success:
        print("Sunday race update completed successfully!")
        sys.exit(0)
    else:
        print("Sunday race update failed!")
        sys.exit(1)
