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
    """Get current weekly standings for a league"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
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
            
            # Calculate total and check if posted today
            total = sum(s for w, s in scores)
            posted_today = todays_wordle in score_dict
            days_posted = len(scores)
            
            standings.append({
                'player_id': player_id,
                'name': player_name,
                'total': total,
                'days_posted': days_posted,
                'posted_today': posted_today,
                'scores': score_dict
            })
        
        cursor.close()
        conn.close()
        
        # Sort by total (lowest is best)
        standings.sort(key=lambda x: x['total'])
        
        return standings, todays_wordle
        
    except Exception as e:
        logging.error(f"Error getting weekly standings: {e}")
        cursor.close()
        conn.close()
        return [], None

def calculate_what_they_need(current_leader_total, player_total, player_days_posted):
    """Calculate what score a player needs to tie or win"""
    # If they haven't posted today, they need one more score
    if player_days_posted < 7:  # Assuming 7 days in a week
        # What score would tie?
        score_to_tie = current_leader_total - player_total
        score_to_win = score_to_tie - 1
        
        return {
            'to_tie': score_to_tie if score_to_tie >= 1 else None,
            'to_win': score_to_win if score_to_win >= 1 else None
        }
    return None

def send_sunday_race_update(league_id):
    """Send the Sunday race update message"""
    try:
        from twilio.rest import Client
        import openai
        
        # Get environment variables
        openai.api_key = os.environ.get('OPENAI_API_KEY')
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
        
        # Find current leader(s)
        leader_total = standings[0]['total']
        leaders = [s for s in standings if s['total'] == leader_total]
        leader_names = [s['name'] for s in leaders]
        
        # Find who hasn't posted today
        not_posted = [s for s in standings if not s['posted_today']]
        
        # Build context for AI
        if len(leader_names) == 1:
            leader_text = f"{leader_names[0]} is in the lead with {leader_total} points"
        elif len(leader_names) == 2:
            leader_text = f"{leader_names[0]} and {leader_names[1]} are tied for the lead with {leader_total} points"
        else:
            leader_text = f"{', '.join(leader_names[:-1])}, and {leader_names[-1]} are all tied with {leader_total} points"
        
        # Build "what they need" context
        scenarios = []
        for player in not_posted:
            needs = calculate_what_they_need(leader_total, player['total'], player['days_posted'])
            if needs:
                if needs['to_win'] and needs['to_win'] >= 1:
                    scenarios.append(f"{player['name']} needs a {needs['to_win']} to win or a {needs['to_tie']} to tie")
                elif needs['to_tie'] and needs['to_tie'] >= 1:
                    scenarios.append(f"{player['name']} needs a {needs['to_tie']} to tie")
        
        # Generate AI message
        if scenarios:
            scenario_text = ". ".join(scenarios)
            prompt = f"It's Sunday morning! Generate an exciting weekly race update. {leader_text}. {scenario_text}. Make it exciting and engaging! Use emojis. Keep it under 280 characters."
        else:
            prompt = f"It's Sunday morning! Generate an exciting weekly race update. {leader_text}. Everyone has posted today! Make it exciting and build anticipation for tomorrow's winner announcement! Use emojis. Keep it under 200 characters."
        
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an exciting sports announcer for a Wordle league. Build excitement and anticipation for the weekly race. Use emojis and be enthusiastic!"},
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
