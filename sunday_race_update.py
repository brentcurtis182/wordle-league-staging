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
    """Send the Sunday race update message"""
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
            # Still send a message about needing more games
            prompt = "It's Sunday! No one has played 5 games yet this week to qualify for the weekly race. Keep playing to get in the running! Use emojis. Keep it under 200 characters."
        else:
            # Find current leader(s) among eligible players
            leader_total = eligible[0]['best_5_total']
            leaders = [s for s in eligible if s['best_5_total'] == leader_total]
            leader_names = [s['name'] for s in leaders]
            
            # Build context for AI
            if len(leader_names) == 1:
                leader_text = f"{leader_names[0]} is leading with a best-5 total of {leader_total}"
            elif len(leader_names) == 2:
                leader_text = f"{leader_names[0]} and {leader_names[1]} are tied for the lead with {leader_total}"
            else:
                leader_text = f"{', '.join(leader_names[:-1])}, and {leader_names[-1]} are all tied with {leader_total}"
            
            # Find who hasn't posted today among eligible players
            not_posted_eligible = [s for s in eligible if not s['posted_today'] and s['name'] not in leader_names]
            
            # Build "what they need" context for players who can still catch up
            scenarios = []
            for player in not_posted_eligible:
                needs = calculate_what_they_need(leader_total, player['best_5_total'], player['days_posted'])
                if needs and not needs.get('already_winning'):
                    points_behind = needs.get('points_behind', 0)
                    if points_behind > 0 and points_behind <= 6:  # Realistic catch-up range
                        scenarios.append(f"{player['name']} is {points_behind} points behind")
            
            # Also mention players close to qualifying
            almost_eligible = [s for s in standings if not s['eligible'] and s['days_posted'] >= 3]
            if almost_eligible:
                almost_names = [s['name'] for s in almost_eligible[:2]]  # Max 2
                if almost_names:
                    scenarios.append(f"{' and '.join(almost_names)} need{'s' if len(almost_names) == 1 else ''} more games to qualify")
            
            # Generate AI message
            if scenarios:
                scenario_text = ". ".join(scenarios)
                prompt = f"It's Sunday morning Wordle race update! {leader_text} (lower is better - best 5 scores count). {scenario_text}. Make it exciting! Use emojis. Keep it under 280 characters."
            else:
                prompt = f"It's Sunday morning Wordle race update! {leader_text} (lower is better - best 5 scores count). The race is tight! Make it exciting and build anticipation for tomorrow's winner! Use emojis. Keep it under 200 characters."
        
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an exciting sports announcer for a Wordle league. In Wordle, LOWER scores are BETTER (1/6 is perfect, 6/6 is barely made it, X/6 is failed). Build excitement for the weekly race. Use emojis and be enthusiastic!"},
                {"role": "user", "content": prompt}
            ],
            max_tokens=150,
            temperature=0.9
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
