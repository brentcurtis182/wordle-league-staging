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
from datetime import datetime, date, timedelta
import pytz

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from league_data_adapter import get_db_connection, calculate_wordle_number, get_week_start_date

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
        # Get all active players
        cursor.execute("""
            SELECT id, name FROM players 
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
        
        for player_id, player_name in players:
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
            days_posted = len(scores)
            posted_today = todays_wordle in score_dict
            
            # Sort scores ascending and take best 5
            sorted_scores = sorted(score_values)
            best_5_scores = sorted_scores[:BEST_N_SCORES]
            best_5_total = sum(best_5_scores) if len(best_5_scores) >= MIN_GAMES_FOR_RANKING else None
            
            standings.append({
                'player_id': player_id,
                'name': player_name,
                'best_5_total': best_5_total,
                'days_posted': days_posted,
                'posted_today': posted_today,
                'scores': score_dict,
                'eligible': days_posted >= MIN_GAMES_FOR_RANKING
            })
        
        cursor.close()
        conn.close()
        
        # Separate eligible (5+ games) from ineligible
        eligible = [s for s in standings if s['eligible']]
        ineligible = [s for s in standings if not s['eligible']]
        
        # Sort eligible by best_5_total (lowest is best)
        eligible.sort(key=lambda x: x['best_5_total'])
        
        # Sort ineligible by days_posted descending (most games first)
        ineligible.sort(key=lambda x: x['days_posted'], reverse=True)
        
        # Combine: eligible first, then ineligible
        standings = eligible + ineligible
        
        return standings, todays_wordle
        
    except Exception as e:
        logging.error(f"Error getting weekly standings: {e}")
        cursor.close()
        conn.close()
        return [], None

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

def send_sunday_race_update(league_id):
    """Send the Sunday race update message with precise scenario analysis"""
    try:
        from openai import OpenAI
        from twilio.rest import Client
        
        # Get environment variables
        openai_client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
        twilio_sid = os.environ.get('TWILIO_ACCOUNT_SID')
        twilio_token = os.environ.get('TWILIO_AUTH_TOKEN')
        twilio_phone = os.environ.get('TWILIO_PHONE_NUMBER')
        
        # Map league_id to conversation SID
        conversation_sids = {
            1: 'CHb7aa3110769f42a19cea7a2be9c644d2',  # Warriorz
            3: 'CHc8f0c4a776f14bcd96e7c8838a6aec13',  # PAL
            4: 'CHed74f2e9f16240e9a578f96299c395ce',  # The Party
            7: 'CH4438ff5531514178bb13c5c0e96d5579',  # Belly Up
        }
        
        conversation_sid = conversation_sids.get(league_id)
        if not conversation_sid:
            logging.error(f"No conversation SID for league {league_id}")
            return False
        
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
        
        # Find eligible players (5+ games) and their leader
        eligible = [s for s in standings if s['eligible']]
        
        if not eligible:
            logging.warning(f"No eligible players (5+ games) in league {league_id}")
            prompt = "It's Sunday! No one has played 5 games yet this week to qualify for the weekly race. Keep playing to get in the running! Use emojis. Keep it under 200 characters."
        else:
            # Find current leader(s) among eligible players
            leader_total = eligible[0]['best_5_total']
            leaders = [s for s in eligible if s['best_5_total'] == leader_total]
            leader_names = [s['name'] for s in leaders]
            
            # Check if all eligible players have posted today
            all_eligible_posted = all(s['posted_today'] for s in eligible)
            
            # Check players who haven't posted today but could still qualify or catch up
            not_posted_today = [s for s in standings if not s['posted_today']]
            
            # SCENARIO ANALYSIS
            scenarios = []
            
            # Scenario 1: Multiple leaders = they will share the win
            if len(leaders) > 1 and all_eligible_posted:
                leader_list = " and ".join(leader_names)
                scenarios.append(f"{leader_list} are tied at {leader_total} and will share the win!")
            
            # Scenario 2: Single clear leader with everyone posted
            elif len(leaders) == 1 and all_eligible_posted:
                # Check if anyone not posted can still catch up
                can_catch_up = []
                for player in not_posted_today:
                    if player['eligible']:
                        # Already eligible, can they improve their best 5?
                        diff = player['best_5_total'] - leader_total
                        if diff > 0 and diff <= 6:
                            # They need a score that improves their best 5 by 'diff' points
                            # If their worst score in best 5 is W, they need a score of (W - diff) or better to tie
                            sorted_scores = sorted(player['scores'].values())[:5]
                            if sorted_scores:
                                worst_best_5 = sorted_scores[-1]  # Highest of their best 5
                                score_to_tie = worst_best_5 - diff
                                if score_to_tie >= 1:
                                    can_catch_up.append(f"{player['name']} needs a {score_to_tie} or better to tie")
                    elif player['days_posted'] == 4:
                        # Has 4 games, posting today would give them 5
                        # Their final best-5 total will be: current_4_total + today's_score
                        current_total = sum(sorted(player['scores'].values())[:4])
                        score_to_tie = leader_total - current_total
                        score_to_win = score_to_tie - 1
                        
                        if score_to_win >= 1 and score_to_win <= 6:
                            # Can win with a realistic score
                            can_catch_up.append(f"{player['name']} (4 games) needs a {score_to_win} to win or {score_to_tie} to tie")
                        elif score_to_tie >= 1 and score_to_tie <= 6:
                            # Can tie but not win outright
                            can_catch_up.append(f"{player['name']} (4 games) needs a {score_to_tie} to tie")
                        elif score_to_tie > 6:
                            # Mathematically eliminated - would need 7+ to tie
                            can_catch_up.append(f"{player['name']} (4 games) is out of contention")
                        elif score_to_tie <= 0:
                            # Already ahead once they post any valid score
                            can_catch_up.append(f"{player['name']} (4 games at {current_total}) takes the lead with any score!")
                
                if can_catch_up:
                    scenarios.append(f"{leader_names[0]} leads at {leader_total}. " + ". ".join(can_catch_up))
                else:
                    scenarios.append(f"{leader_names[0]} is the clear winner at {leader_total}!")
            
            # Scenario 3: Race still open - not everyone has posted
            else:
                if len(leaders) == 1:
                    leader_text = f"{leader_names[0]} leads at {leader_total}"
                else:
                    leader_text = f"{' and '.join(leader_names)} tied at {leader_total}"
                
                # Find who can still catch up or tie
                catch_up_scenarios = []
                for player in not_posted_today:
                    if player['name'] in leader_names:
                        continue  # Skip leaders
                    
                    if player['eligible']:
                        # Already has 5+ games - can they improve?
                        diff = player['best_5_total'] - leader_total
                        if diff > 0:
                            sorted_scores = sorted(player['scores'].values())[:5]
                            if sorted_scores:
                                worst_best_5 = sorted_scores[-1]
                                score_to_tie = worst_best_5 - diff
                                score_to_win = worst_best_5 - diff - 1
                                if score_to_tie >= 1 and score_to_tie <= 6:
                                    if score_to_win >= 1:
                                        catch_up_scenarios.append(f"{player['name']} (at {player['best_5_total']}) needs a {score_to_win} to win or {score_to_tie} to tie")
                                    else:
                                        catch_up_scenarios.append(f"{player['name']} (at {player['best_5_total']}) needs a {score_to_tie} to tie")
                    
                    elif player['days_posted'] == 4:
                        # Has 4 games - today would be their 5th
                        # Their final best-5 total will be: current_4_total + today's_score
                        current_4_total = sum(sorted(player['scores'].values())[:4])
                        score_to_tie = leader_total - current_4_total
                        score_to_win = score_to_tie - 1
                        
                        if score_to_win >= 1 and score_to_win <= 6:
                            # Can win with a realistic score
                            catch_up_scenarios.append(f"{player['name']} (at {current_4_total} with 4 games) needs a {score_to_win} to win or {score_to_tie} to tie")
                        elif score_to_tie >= 1 and score_to_tie <= 6:
                            # Can tie but not win outright (would need 0 or negative to win)
                            catch_up_scenarios.append(f"{player['name']} (at {current_4_total} with 4 games) needs a {score_to_tie} to tie")
                        elif score_to_tie > 6:
                            # Would need a 7+ to even tie - mathematically eliminated
                            catch_up_scenarios.append(f"{player['name']} (4 games played) is out of contention")
                        # If score_to_tie <= 0, they're already ahead once they post any score (1-6)
                        elif score_to_tie <= 0:
                            catch_up_scenarios.append(f"{player['name']} (at {current_4_total} with 4 games) takes the lead with any score today!")
                
                if catch_up_scenarios:
                    scenarios.append(f"{leader_text}. " + ". ".join(catch_up_scenarios[:3]))  # Max 3 scenarios
                else:
                    scenarios.append(f"{leader_text}. Race is heating up!")
            
            # Build final prompt
            scenario_text = " ".join(scenarios)
            prompt = f"It's Sunday morning Wordle race update! {scenario_text} Make it exciting with emojis! Keep it under 300 characters. Lower scores are better in Wordle."
        
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an exciting sports announcer for a Wordle league. In Wordle, LOWER scores are BETTER (1/6 is perfect, 6/6 is barely made it). Convey the exact scenario given - don't change the numbers or names. Build excitement! Use emojis!"},
                {"role": "user", "content": prompt}
            ],
            max_tokens=200,
            temperature=0.8
        )
        
        race_message = response.choices[0].message.content.strip()
        logging.info(f"Generated Sunday race update for league {league_id}: {race_message}")
        
        # Send to conversation
        client = Client(twilio_sid, twilio_token)
        client.conversations.v1.conversations(conversation_sid).messages.create(
            body=race_message,
            author=twilio_phone
        )
        
        logging.info(f"Sent Sunday race update to league {league_id}")
        return True
        
    except Exception as e:
        logging.error(f"Error sending Sunday race update: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return False

def run_sunday_race_updates():
    """Run Sunday race updates for all active leagues"""
    # Active leagues: 1 (Warriorz), 3 (PAL), 4 (Party), 7 (BellyUp)
    leagues = [1, 3, 4, 7]
    
    all_success = True
    for league_id in leagues:
        logging.info(f"Sending Sunday race update for League {league_id}")
        success = send_sunday_race_update(league_id)
        if not success:
            all_success = False
    
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
